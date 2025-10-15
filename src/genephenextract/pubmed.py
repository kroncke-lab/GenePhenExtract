"""Utilities for interacting with the PubMed E-utilities API."""

from __future__ import annotations

import calendar
import io
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
PMC_ARTICLE_BASE = "https://pmc.ncbi.nlm.nih.gov/articles"
USER_AGENT = "GenePhenExtract/0.1 (+https://github.com/brettkroncke/GenePhenExtract)"
XLINK_HREF = "{http://www.w3.org/1999/xlink}href"


class PubMedError(RuntimeError):
    """Raised when communication with the PubMed API fails."""


class FullTextNotAvailableError(PubMedError):
    """Raised when full-text content is not available for a given article."""


class PubMedClient:
    """Thin wrapper around the PubMed E-utilities endpoints used by the project."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        email: Optional[str] = None,
        *,
        timeout: float = 15.0,
        max_retries: int = 3,
    ) -> None:
        self.api_key = api_key
        self.email = email
        self.timeout = timeout
        self.max_retries = max_retries

    def close(self) -> None:  # pragma: no cover - compatibility no-op
        """Provided for API symmetry with httpx-based implementations."""

    def _request(self, endpoint: str, params: Dict[str, str]) -> str:
        payload = {**params}
        payload.setdefault("retmode", "json")
        if self.api_key:
            payload["api_key"] = self.api_key
        if self.email:
            payload["email"] = self.email
        query = urllib.parse.urlencode(payload)
        url = f"{EUTILS_BASE}/{endpoint}?{query}"
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

        last_error: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    body = response.read().decode("utf-8")
                return body
            except urllib.error.URLError as exc:
                last_error = exc
                logger.warning("PubMed request failed (attempt %d/%d)", attempt, self.max_retries)
                if attempt == self.max_retries:
                    break
                sleep_for = min(5, 2 ** (attempt - 1))
                time.sleep(sleep_for)
        raise PubMedError("Failed to communicate with PubMed") from last_error

    def search(self, query: str, *, retmax: int = 20) -> List[str]:
        """Return a list of PMIDs that match the provided PubMed query."""

        raw = self._request("esearch.fcgi", {"db": "pubmed", "term": query, "retmax": str(retmax)})
        data = json.loads(raw)
        return data.get("esearchresult", {}).get("idlist", [])

    def fetch_details(self, pmids: Iterable[str]) -> Dict[str, Dict[str, Optional[str]]]:
        """Fetch article metadata for the given PMIDs using `efetch`."""

        id_param = ",".join(pmids)
        if not id_param:
            return {}
        raw = self._request(
            "efetch.fcgi",
            {
                "db": "pubmed",
                "id": id_param,
                "retmode": "xml",
            },
        )
        try:
            xml_root = ET.fromstring(raw)
        except ET.ParseError as exc:  # pragma: no cover - defensive
            raise PubMedError("Unable to parse PubMed XML") from exc

        articles: Dict[str, Dict[str, Optional[str]]] = {}
        for article in xml_root.findall(".//PubmedArticle"):
            pmid = _find_text(article, ".//PMID")
            if not pmid:
                continue
            title = _find_text(article, ".//ArticleTitle")
            abstract_parts = [
                (element.text or "").strip()
                for element in article.findall(".//Abstract/AbstractText")
                if (element.text or "").strip()
            ]
            abstract = "\n".join(abstract_parts) if abstract_parts else None
            journal = _find_text(article, ".//Journal/Title")
            publication_date = _parse_publication_date(article)
            articles[pmid] = {
                "title": title,
                "abstract": abstract,
                "journal": journal,
                "publication_date": publication_date,
            }
        return articles

    def fetch_abstract(self, pmid: str) -> Optional[str]:
        """Retrieve a single abstract text via `efetch`."""

        raw = self._request(
            "efetch.fcgi",
            {
                "db": "pubmed",
                "id": pmid,
                "retmode": "xml",
            },
        )
        try:
            xml_root = ET.fromstring(raw)
        except ET.ParseError as exc:  # pragma: no cover - defensive
            raise PubMedError("Unable to parse PubMed XML") from exc
        abstract_texts = [
            element.text or ""
            for element in xml_root.findall(".//Abstract/AbstractText")
        ]
        if not abstract_texts:
            logger.info("No abstract found for PMID %s", pmid)
            return None
        return "\n".join(text.strip() for text in abstract_texts if text)

    def pmid_to_pmcid(self, pmid: str) -> Optional[str]:
        """Convert a PMID to a PMCID using the ID converter API."""
        raw = self._request(
            "elink.fcgi",
            {
                "dbfrom": "pubmed",
                "db": "pmc",
                "id": pmid,
                "retmode": "json",
            },
        )
        try:
            data = json.loads(raw)
            linksets = data.get("linksets", [])
            if not linksets:
                logger.info("No PMC article found for PMID %s", pmid)
                return None
            
            links = linksets[0].get("linksetdbs", [])
            for linkdb in links:
                if linkdb.get("dbto") == "pmc":
                    pmc_ids = linkdb.get("links", [])
                    if pmc_ids:
                        return f"PMC{pmc_ids[0]}"
            logger.info("No PMC article found for PMID %s", pmid)
            return None
        except (json.JSONDecodeError, KeyError, IndexError) as exc:
            logger.warning("Failed to parse PMCID response for PMID %s: %s", pmid, exc)
            return None

    def fetch_full_text(self, pmid: str) -> Optional[str]:
        """
        Attempt to retrieve full-text content for a given PMID.
        
        First tries to convert PMID to PMCID and fetch from PMC.
        Returns None if full-text is not available.
        """
        pmcid = self.pmid_to_pmcid(pmid)
        if not pmcid:
            logger.info("Full-text not available for PMID %s (no PMCID)", pmid)
            return None
        
        return self.fetch_pmc_full_text(pmcid)

    def fetch_pmc_full_text(self, pmcid: str) -> Optional[str]:
        """
        Fetch full-text content from PMC using a PMCID.
        
        Args:
            pmcid: PubMed Central ID (e.g., 'PMC1234567' or just '1234567')
        
        Returns:
            Full-text content as a string, or None if not available.
        """
        # Normalize PMCID format
        if not pmcid.startswith("PMC"):
            pmcid = f"PMC{pmcid}"
        
        # Remove 'PMC' prefix for the API call
        pmc_number = pmcid.replace("PMC", "")
        
        try:
            raw = self._request(
                "efetch.fcgi",
                {
                    "db": "pmc",
                    "id": pmc_number,
                    "retmode": "xml",
                },
            )
        except PubMedError as exc:
            logger.warning("Failed to fetch full-text for %s: %s", pmcid, exc)
            return None
        
        try:
            xml_root = ET.fromstring(raw)
        except ET.ParseError as exc:
            logger.warning("Unable to parse PMC XML for %s: %s", pmcid, exc)
            return None

        # Extract text from various sections
        text_parts: List[str] = []
        
        # Title
        title = xml_root.find(".//article-title")
        if title is not None and title.text:
            text_parts.append(f"# {title.text.strip()}\n")
        
        # Abstract
        abstract = xml_root.find(".//abstract")
        if abstract is not None:
            abstract_text = _extract_text_from_element(abstract)
            if abstract_text:
                text_parts.append(f"## Abstract\n{abstract_text}\n")
        
        # Body sections
        body = xml_root.find(".//body")
        if body is not None:
            for sec in body.findall(".//sec"):
                section_text = _extract_section_text(sec)
                if section_text:
                    text_parts.append(section_text)
        
        supplementary_sections = _extract_supplementary_sections(xml_root, pmcid)
        text_parts.extend(supplementary_sections)

        if not text_parts:
            logger.warning("No text content found in PMC XML for %s", pmcid)
            return None

        full_text = "\n\n".join(text_parts)
        logger.info("Successfully retrieved full-text for %s (%d characters)", pmcid, len(full_text))
        return full_text

    def fetch_text(self, pmid: str, prefer_full_text: bool = False) -> Tuple[str, str]:
        """
        Fetch text content for a PMID, with option to prefer full-text.
        
        Args:
            pmid: PubMed ID
            prefer_full_text: If True, attempts to fetch full-text first, falls back to abstract
        
        Returns:
            Tuple of (text_content, source_type) where source_type is 'full_text' or 'abstract'
        """
        if prefer_full_text:
            full_text = self.fetch_full_text(pmid)
            if full_text:
                return full_text, "full_text"
            logger.info("Falling back to abstract for PMID %s", pmid)
        
        abstract = self.fetch_abstract(pmid)
        if abstract:
            return abstract, "abstract"
        
        raise PubMedError(f"No text content available for PMID {pmid}")

    def __enter__(self) -> "PubMedClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


def _find_text(node: ET.Element, path: str) -> Optional[str]:
    element = node.find(path)
    if element is None or element.text is None:
        return None
    return element.text.strip() or None


def _extract_supplementary_sections(xml_root: ET.Element, pmcid: str) -> List[str]:
    sections: List[str] = []
    for index, material in enumerate(xml_root.findall(".//supplementary-material")):
        section_text = _supplementary_material_to_text(material, pmcid, index)
        if section_text:
            sections.append(section_text)
    return sections


def _supplementary_material_to_text(
    material: ET.Element, pmcid: str, index: int
) -> Optional[str]:
    label_candidates: Sequence[Optional[str]] = (
        _find_text(material, "label"),
        material.get("id"),
        material.get("title"),
        material.get("{http://www.w3.org/1999/xlink}title"),
    )
    label = next((value for value in label_candidates if value), None)
    if not label:
        label = f"Supplementary material {index + 1}"

    body_parts: List[str] = []

    caption = material.find("caption")
    if caption is not None:
        caption_text = _extract_text_from_element(caption).strip()
        if caption_text:
            body_parts.append(caption_text)

    href = material.get(XLINK_HREF)
    if href:
        text = _fetch_supplementary_text(href, pmcid)
        if text:
            body_parts.append(text.strip())
        else:
            logger.debug(
                "Unable to extract supplementary material %s for %s", href, pmcid
            )
    else:
        inline_text = _extract_text_from_element(material).strip()
        if inline_text:
            body_parts.append(inline_text)

    if not body_parts:
        return None

    heading = f"## Supplementary: {label.strip()}"
    return "\n\n".join([heading, "\n\n".join(body_parts).strip()])


def _fetch_supplementary_text(href: str, pmcid: str) -> Optional[str]:
    urls = _supplementary_urls(href, pmcid)
    last_error: Optional[Exception] = None
    for url in urls:
        try:
            content = _download_binary(url)
        except PubMedError as exc:
            last_error = exc
            logger.debug("Failed to download supplementary file %s: %s", url, exc)
            continue
        text = _decode_supplementary_bytes(href, content)
        if text:
            return text
    if last_error:
        logger.info(
            "Supplementary material %s for %s could not be retrieved", href, pmcid
        )
    return None


def _supplementary_urls(href: str, pmcid: str) -> Sequence[str]:
    clean_pmcid = pmcid if pmcid.startswith("PMC") else f"PMC{pmcid}"
    base_article_url = f"{PMC_ARTICLE_BASE}/{clean_pmcid}/"
    candidates = [
        urllib.parse.urljoin(base_article_url, href),
        urllib.parse.urljoin("https://pmc.ncbi.nlm.nih.gov/", href),
    ]
    # Preserve order while removing duplicates
    seen = set()
    unique: List[str] = []
    for url in candidates:
        if url not in seen:
            seen.add(url)
            unique.append(url)
    return unique


def _download_binary(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read()
    except urllib.error.URLError as exc:  # pragma: no cover - network dependent
        raise PubMedError(f"Failed to download supplementary file from {url}") from exc


def _decode_supplementary_bytes(href: str, content: bytes) -> Optional[str]:
    suffix = href.split("?")[0].lower()
    if suffix.endswith(".docx"):
        try:
            return _extract_docx_text(content)
        except (zipfile.BadZipFile, KeyError, ET.ParseError) as exc:
            logger.debug("Unable to parse DOCX supplementary file %s: %s", href, exc)
            return None
    if suffix.endswith((".txt", ".csv", ".tsv")):
        return content.decode("utf-8", errors="replace")
    if suffix.endswith(".xml"):
        return _extract_xml_text(content)
    return None


def _extract_xml_text(content: bytes) -> Optional[str]:
    try:
        xml_root = ET.fromstring(content)
    except ET.ParseError:
        text = content.decode("utf-8", errors="replace").strip()
        return text or None
    text = _extract_text_from_element(xml_root).strip()
    return text or None


def _extract_docx_text(content: bytes) -> Optional[str]:
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        try:
            with archive.open("word/document.xml") as document:
                document_xml = document.read()
        except KeyError as exc:
            raise KeyError("DOCX file missing document.xml") from exc

    root = ET.fromstring(document_xml)
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs: List[str] = []
    for para in root.findall(".//w:p", namespace):
        runs = [text.text or "" for text in para.findall(".//w:t", namespace) if text.text]
        paragraph = "".join(runs).strip()
        if paragraph:
            paragraphs.append(paragraph)
    return "\n".join(paragraphs) if paragraphs else None


def _extract_text_from_element(element: ET.Element) -> str:
    """Recursively extract text from an XML element and its children."""
    texts = []
    if element.text:
        texts.append(element.text.strip())
    
    for child in element:
        child_text = _extract_text_from_element(child)
        if child_text:
            texts.append(child_text)
        if child.tail:
            texts.append(child.tail.strip())
    
    return " ".join(t for t in texts if t)


def _extract_section_text(section: ET.Element) -> str:
    """Extract text from a PMC article section with proper formatting."""
    parts = []
    
    # Section title
    title = section.find("title")
    if title is not None and title.text:
        parts.append(f"## {title.text.strip()}")
    
    # Section paragraphs
    for para in section.findall(".//p"):
        para_text = _extract_text_from_element(para)
        if para_text:
            parts.append(para_text)
    
    return "\n\n".join(parts) if parts else ""


def _gather_supplementary_texts(
    xml_root: ET.Element, pmcid: str, *, timeout: float
) -> List[str]:
    """Collect text from supplementary materials referenced in the PMC XML."""

    supplementary_sections: List[str] = []
    supplementary_elements = xml_root.findall(".//supplementary-material")
    if not supplementary_elements:
        return supplementary_sections

    logger.info("Found %d supplementary materials for %s", len(supplementary_elements), pmcid)

    for index, element in enumerate(supplementary_elements, start=1):
        label = _supplementary_label(element, index)
        hrefs = _supplementary_hrefs(element)
        if not hrefs:
            inline_text = _extract_text_from_element(element).strip()
            if inline_text:
                supplementary_sections.append(f"### {label}\n{inline_text}")
            else:
                logger.debug(
                    "Supplementary material %s for %s has no associated media", label, pmcid
                )
            continue

        for href in hrefs:
            text = _download_supplementary_text(pmcid, href, label, timeout)
            if text:
                supplementary_sections.append(f"### {label}\n{text.strip()}")
                break
        else:
            logger.warning("Failed to process supplementary material %s for %s", label, pmcid)

    return supplementary_sections


def _supplementary_label(element: ET.Element, index: int) -> str:
    for tag in ("label", "title"):
        tag_element = element.find(tag)
        if tag_element is not None and tag_element.text:
            label = tag_element.text.strip()
            if label:
                return label
    for attr in ("id", "label"):
        value = element.get(attr)
        if value:
            return value
    return f"Supplementary Material {index}"


def _supplementary_hrefs(element: ET.Element) -> List[str]:
    hrefs: List[str] = []
    xlink_href = "{http://www.w3.org/1999/xlink}href"

    direct_href = element.get(xlink_href) or element.get("href")
    if direct_href:
        hrefs.append(direct_href.strip())

    for media in element.findall(".//{*}media"):
        href = media.get(xlink_href) or media.get("href")
        if href:
            hrefs.append(href.strip())

    for ext_link in element.findall(".//{*}ext-link"):
        href = ext_link.get(xlink_href) or ext_link.get("href")
        if href:
            hrefs.append(href.strip())

    # Preserve order but remove duplicates
    seen = set()
    unique_hrefs = []
    for href in hrefs:
        if href and href not in seen:
            unique_hrefs.append(href)
            seen.add(href)
    return unique_hrefs


def _download_supplementary_text(
    pmcid: str, href: str, label: str, timeout: float
) -> Optional[str]:
    """Download and extract text from a supplementary file."""

    url_candidates = _candidate_supplementary_urls(pmcid, href)
    for url in url_candidates:
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=timeout) as response:
                data = response.read()
                content_type = response.headers.get("Content-Type", "")
        except Exception as exc:  # pragma: no cover - network failures
            logger.debug(
                "Unable to download supplementary material %s from %s: %s", label, url, exc
            )
            continue

        text = _extract_supplementary_text(href, data, content_type)
        if text:
            logger.info("Processed supplementary file %s for %s", url, pmcid)
            return text

    return None


def _candidate_supplementary_urls(pmcid: str, href: str) -> List[str]:
    parsed = urllib.parse.urlparse(href)
    if parsed.scheme in {"http", "https"}:
        return [href]

    clean_path = href.lstrip("/")
    base_article = f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/"
    base_pdf = urllib.parse.urljoin(base_article, "pdf/")
    base_ftp = f"https://ftp.ncbi.nlm.nih.gov/pub/pmc/articles/{pmcid}/"

    candidates = [
        urllib.parse.urljoin(base_article, clean_path),
        urllib.parse.urljoin(base_pdf, clean_path),
        urllib.parse.urljoin(base_ftp, clean_path),
    ]

    seen = set()
    ordered_candidates = []
    for candidate in candidates:
        if candidate not in seen:
            ordered_candidates.append(candidate)
            seen.add(candidate)
    return ordered_candidates


def _extract_supplementary_text(href: str, data: bytes, content_type: str) -> Optional[str]:
    """Extract textual content from a supplementary file payload."""

    path = urllib.parse.urlparse(href).path
    _, ext = os.path.splitext(path.lower())

    if ext == ".docx" or "application/vnd.openxmlformats-officedocument" in content_type:
        try:
            from docx import Document  # type: ignore
        except ImportError:  # pragma: no cover - optional dependency
            logger.warning("python-docx is required to read DOCX supplementary files")
            return None

        document = Document(io.BytesIO(data))
        paragraphs = [para.text.strip() for para in document.paragraphs if para.text and para.text.strip()]
        return "\n".join(paragraphs)

    if ext == ".pdf" or content_type.startswith("application/pdf"):
        try:
            from pypdf import PdfReader  # type: ignore
        except ImportError:  # pragma: no cover - optional dependency
            logger.warning("pypdf is required to read PDF supplementary files")
            return None

        reader = PdfReader(io.BytesIO(data))
        pages = []
        for page in reader.pages:
            try:
                page_text = page.extract_text() or ""
            except Exception:  # pragma: no cover - defensive for malformed PDFs
                page_text = ""
            if page_text.strip():
                pages.append(page_text.strip())
        return "\n\n".join(pages) if pages else None

    if ext in {".txt", ".csv"} or content_type.startswith("text/"):
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError:
            return data.decode("latin-1", errors="ignore")

    return None


def _parse_publication_date(article: ET.Element) -> Optional[str]:
    pub_date = article.find(".//Journal/JournalIssue/PubDate")
    if pub_date is None:
        return None
    year = _find_text(pub_date, "Year")
    if not year:
        return _find_text(pub_date, "MedlineDate")
    month_text = _find_text(pub_date, "Month")
    day_text = _find_text(pub_date, "Day")
    month = _month_number(month_text) if month_text else 1
    day = int(day_text) if day_text and day_text.isdigit() else 1
    try:
        return f"{int(year):04d}-{month:02d}-{day:02d}"
    except ValueError:
        logger.debug("Unable to parse publication date for article: %s", ET.tostring(article, encoding="unicode"))
        return year


def _month_number(month: Optional[str]) -> int:
    if not month:
        return 1
    month_clean = month.strip().lower()
    if month_clean.isdigit():
        value = int(month_clean)
        if 1 <= value <= 12:
            return value
    try:
        return list(calendar.month_abbr).index(month_clean.title())
    except ValueError:
        pass
    try:
        return list(calendar.month_name).index(month_clean.title())
    except ValueError:
        pass
    month_lookup = {
        "jan": 1,
        "feb": 2,
        "mar": 3,
        "apr": 4,
        "may": 5,
        "jun": 6,
        "jul": 7,
        "aug": 8,
        "sep": 9,
        "sept": 9,
        "oct": 10,
        "nov": 11,
        "dec": 12,
    }
    return month_lookup.get(month_clean[:3], 1)
