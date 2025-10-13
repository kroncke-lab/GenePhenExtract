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
from typing import Dict, Iterable, List, Optional

logger = logging.getLogger(__name__)

EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
USER_AGENT = "GenePhenExtract/0.1 (+https://github.com/brettkroncke/GenePhenExtract)"


class PubMedError(RuntimeError):
    """Raised when communication with the PubMed API fails."""


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

    def __enter__(self) -> "PubMedClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


def _find_text(node: ET.Element, path: str) -> Optional[str]:
    element = node.find(path)
    if element is None or element.text is None:
        return None
    return element.text.strip() or None


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
