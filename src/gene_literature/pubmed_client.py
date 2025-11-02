"""Client utilities for interacting with the PubMed E-utilities API."""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, asdict
from typing import List, Optional, Sequence

logger = logging.getLogger(__name__)

EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
USER_AGENT = "GeneLiteratureCollector/0.1 (+https://github.com/openai)"


class PubMedError(RuntimeError):
    """Raised when communication with the PubMed API fails."""


@dataclass
class ArticleMetadata:
    """Structured metadata about a single PubMed article."""

    pmid: str
    title: Optional[str]
    abstract: Optional[str]
    first_author: Optional[str]
    publication_year: Optional[int]
    journal: Optional[str]
    xml_available: bool
    patient_level_evidence: bool
    pmcid: Optional[str] = None
    doi: Optional[str] = None
    pubmed_url: Optional[str] = None
    pmc_url: Optional[str] = None
    doi_url: Optional[str] = None
    pmc_pdf_url: Optional[str] = None
    relevance_score: Optional[float] = None
    relevance_reasoning: Optional[str] = None

    def to_dict(self) -> dict:
        """Return the metadata as a plain dictionary."""

        return asdict(self)


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

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def search(self, query: str, *, retmax: int = 100) -> List[str]:
        """Return a list of PubMed IDs (PMIDs) that match the provided query."""

        logger.info("Searching PubMed with query: %s", query)
        raw = self._request(
            "esearch.fcgi",
            {"db": "pubmed", "term": query, "retmax": str(retmax), "retmode": "json"},
        )
        data = json.loads(raw)
        pmids = data.get("esearchresult", {}).get("idlist", [])
        logger.debug("PubMed returned %d PMIDs", len(pmids))
        return pmids

    def fetch_metadata(self, pmids: Sequence[str], batch_size: int = 200) -> List[ArticleMetadata]:
        """Fetch detailed article metadata for the provided PMIDs.

        Args:
            pmids: Sequence of PubMed IDs to fetch metadata for
            batch_size: Number of PMIDs to fetch per request (default 200)
                       to avoid URI length limits
        """

        if not pmids:
            return []

        logger.info("Fetching metadata for %d PMIDs", len(pmids))

        # Process PMIDs in batches to avoid URI length limits
        all_records: List[ArticleMetadata] = []
        pmid_list = list(pmids)
        total_batches = (len(pmid_list) + batch_size - 1) // batch_size

        for batch_num in range(total_batches):
            start_idx = batch_num * batch_size
            end_idx = min(start_idx + batch_size, len(pmid_list))
            batch_pmids = pmid_list[start_idx:end_idx]

            logger.info(
                "Fetching batch %d/%d (%d PMIDs)",
                batch_num + 1,
                total_batches,
                len(batch_pmids)
            )

            xml_payload = self._request(
                "efetch.fcgi",
                {
                    "db": "pubmed",
                    "id": ",".join(batch_pmids),
                    "retmode": "xml",
                },
            )
            try:
                xml_root = ET.fromstring(xml_payload)
            except ET.ParseError as exc:  # pragma: no cover - defensive
                raise PubMedError("Unable to parse PubMed XML response") from exc

            for article in xml_root.findall(".//PubmedArticle"):
                pmid = _find_text(article, ".//PMID")
                if not pmid:
                    logger.debug("Skipping article without PMID")
                    continue

                title = _find_text(article, ".//ArticleTitle")
                abstract_parts = [
                    (element.text or "").strip()
                    for element in article.findall(".//Abstract/AbstractText")
                    if (element.text or "").strip()
                ]
                abstract = "\n".join(abstract_parts) if abstract_parts else None
                first_author = _extract_first_author(article)
                publication_year = _extract_publication_year(article)
                journal = _find_text(article, ".//Journal/Title")
                pmcid = _extract_pmcid(article)
                doi = _extract_doi(article)
                xml_available = pmcid is not None
                patient_level_evidence = _contains_patient_level_terms(title, abstract)

                # Build download URLs
                urls = _build_urls(pmid, pmcid, doi)

                all_records.append(
                    ArticleMetadata(
                        pmid=pmid,
                        title=title,
                        abstract=abstract,
                        first_author=first_author,
                        publication_year=publication_year,
                        journal=journal,
                        xml_available=xml_available,
                        patient_level_evidence=patient_level_evidence,
                        pmcid=pmcid,
                        doi=doi,
                        pubmed_url=urls["pubmed_url"],
                        pmc_url=urls["pmc_url"],
                        doi_url=urls["doi_url"],
                        pmc_pdf_url=urls["pmc_pdf_url"],
                    )
                )

            # Be respectful of PubMed rate limits between batches
            if batch_num < total_batches - 1:
                time.sleep(0.34)  # ~3 requests per second (NCBI guideline)

        logger.info("Successfully fetched metadata for %d articles", len(all_records))
        return all_records

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _request(self, endpoint: str, params: dict) -> str:
        payload = {**params}
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
                    return response.read().decode("utf-8")
            except urllib.error.URLError as exc:
                last_error = exc
                logger.warning(
                    "PubMed request failed (attempt %d/%d): %s",
                    attempt,
                    self.max_retries,
                    exc,
                )
                if attempt == self.max_retries:
                    break
                sleep_for = min(5, 2 ** (attempt - 1))
                logger.debug("Sleeping %.1f seconds before retry", sleep_for)
                time.sleep(sleep_for)

        raise PubMedError("Failed to communicate with PubMed") from last_error


# ----------------------------------------------------------------------
# XML parsing helpers
# ----------------------------------------------------------------------

def _find_text(root: ET.Element, selector: str) -> Optional[str]:
    element = root.find(selector)
    if element is None:
        return None
    text = element.text or ""
    text = text.strip()
    return text or None


def _extract_first_author(article: ET.Element) -> Optional[str]:
    author = article.find(".//AuthorList/Author")
    if author is None:
        return None
    last_name = _find_text(author, "LastName")
    fore_name = _find_text(author, "ForeName")
    collective_name = _find_text(author, "CollectiveName")
    if collective_name:
        return collective_name
    if last_name and fore_name:
        return f"{fore_name} {last_name}"
    return last_name or fore_name


def _extract_publication_year(article: ET.Element) -> Optional[int]:
    pubdate = article.find(".//Article/Journal/JournalIssue/PubDate")
    if pubdate is None:
        return None
    year_text = _find_text(pubdate, "Year")
    if not year_text:
        year_text = _find_text(pubdate, "MedlineDate")
    if not year_text:
        return None
    for token in year_text.split():
        if token.isdigit() and len(token) == 4:
            try:
                return int(token)
            except ValueError:  # pragma: no cover - defensive
                return None
    return None


PATIENT_KEYWORDS = {
    "patient",
    "patients",
    "case",
    "case report",
    "cases",
    "cohort",
    "subjects",
    "clinical",
}


def _contains_patient_level_terms(title: Optional[str], abstract: Optional[str]) -> bool:
    """Simple heuristic to infer the presence of patient-level evidence."""

    combined = " ".join(part for part in [title or "", abstract or ""] if part)
    combined = combined.lower()
    return any(keyword in combined for keyword in PATIENT_KEYWORDS)


def _has_pmcid(article: ET.Element) -> bool:
    """Return True if the article includes a PubMed Central identifier.

    Checks for multiple possible IdType values and attribute names:
    - IdType="pmc" (current PubMed standard)
    - IdType="pmcid" (older format)
    - idtype (lowercase attribute, for compatibility)
    """

    for article_id in article.findall(".//ArticleIdList/ArticleId"):
        # Check both capitalized and lowercase attribute names
        id_type = article_id.get("IdType") or article_id.get("idtype") or ""
        id_type_lower = id_type.lower()

        # Accept both "pmc" and "pmcid" as valid PMC identifiers
        if id_type_lower in ("pmc", "pmcid") and (article_id.text or "").strip():
            return True
    return False


def _extract_pmcid(article: ET.Element) -> Optional[str]:
    """Extract the PubMed Central ID if available.

    Checks for multiple possible IdType values and attribute names:
    - IdType="pmc" (current PubMed standard)
    - IdType="pmcid" (older format)
    - idtype (lowercase attribute, for compatibility)
    """

    for article_id in article.findall(".//ArticleIdList/ArticleId"):
        # Check both capitalized and lowercase attribute names
        id_type = article_id.get("IdType") or article_id.get("idtype") or ""
        id_type_lower = id_type.lower()

        # Accept both "pmc" and "pmcid" as valid PMC identifiers
        if id_type_lower in ("pmc", "pmcid"):
            pmcid = (article_id.text or "").strip()
            if pmcid:
                return pmcid
    return None


def _extract_doi(article: ET.Element) -> Optional[str]:
    """Extract the DOI if available.

    Checks both capitalized and lowercase IdType attribute names.
    """

    for article_id in article.findall(".//ArticleIdList/ArticleId"):
        # Check both capitalized and lowercase attribute names
        id_type = article_id.get("IdType") or article_id.get("idtype") or ""

        if id_type.lower() == "doi":
            doi = (article_id.text or "").strip()
            if doi:
                return doi
    return None


def _build_urls(pmid: str, pmcid: Optional[str], doi: Optional[str]) -> dict:
    """Build various download URLs for the article."""

    urls = {
        "pubmed_url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        "pmc_url": None,
        "doi_url": None,
        "pmc_pdf_url": None,
    }

    if pmcid:
        urls["pmc_url"] = f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/"
        urls["pmc_pdf_url"] = f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/pdf/"

    if doi:
        urls["doi_url"] = f"https://doi.org/{doi}"

    return urls
