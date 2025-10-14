"""Utilities for interacting with the PubMed E-utilities API."""

from __future__ import annotations

import json
import logging
import calendar
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Dict, Iterable, List, Optional, Tuple

logger = logging.getLogger(__name__)

EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
USER_AGENT = "GenePhenExtract/0.1 (+https://github.com/brettkroncke/GenePhenExtract)"


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
        text_parts = []
        
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
