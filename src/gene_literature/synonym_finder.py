"""
Automatic synonym discovery for genes using NCBI Gene database.

This module provides functionality to:
1. Query NCBI Gene database for official gene synonyms and aliases
2. Present synonyms to users for interactive selection
3. Return selected synonyms for use in PubMed searches
"""

import logging
import time
from dataclasses import dataclass
from typing import List, Optional, Set
from urllib.parse import urlencode

import requests
from requests.adapters import HTTPAdapter, Retry

logger = logging.getLogger(__name__)


class SynonymFinderError(RuntimeError):
    """Raised when synonym lookup fails."""


@dataclass
class GeneSynonym:
    """Represents a gene synonym with metadata."""

    term: str
    source: str  # e.g., "official_symbol", "alias", "other_designations"
    gene_id: Optional[int] = None


class SynonymFinder:
    """
    Finds gene synonyms using NCBI Gene database.

    Uses the NCBI E-utilities API to search for genes and retrieve their
    official symbols, aliases, and other designations.
    """

    BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    def __init__(
        self,
        email: Optional[str] = None,
        api_key: Optional[str] = None,
        retry_attempts: int = 3,
    ):
        """
        Initialize the SynonymFinder.

        Args:
            email: Email address for NCBI API (recommended)
            api_key: NCBI API key for higher rate limits (optional)
            retry_attempts: Number of retry attempts for failed requests
        """
        self.email = email
        self.api_key = api_key
        self.retry_attempts = retry_attempts

        # Configure session with retry logic
        self.session = requests.Session()
        retry_strategy = Retry(
            total=retry_attempts,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def find_gene_synonyms(
        self,
        gene: str,
        include_other_designations: bool = True,
    ) -> List[GeneSynonym]:
        """
        Find synonyms for a given gene.

        Args:
            gene: Gene name or symbol to search for
            include_other_designations: Include other gene designations

        Returns:
            List of GeneSynonym objects

        Raises:
            SynonymFinderError: If the API request fails
        """
        logger.info("Searching for synonyms of '%s'", gene)

        # Step 1: Search for the gene to get Gene ID
        gene_id = self._search_gene(gene)
        if gene_id is None:
            logger.warning("No gene found for '%s'", gene)
            return []

        logger.info("Found Gene ID: %s", gene_id)

        # Step 2: Fetch gene summary to get synonyms
        synonyms = self._fetch_gene_summary(gene_id, include_other_designations)

        logger.info("Found %d synonyms for '%s'", len(synonyms), gene)
        return synonyms

    def _search_gene(self, gene: str) -> Optional[int]:
        """
        Search for a gene in NCBI Gene database.

        Args:
            gene: Gene name or symbol

        Returns:
            Gene ID if found, None otherwise
        """
        params = {
            "db": "gene",
            "term": f"{gene}[Gene Name] AND human[Organism]",
            "retmode": "json",
            "retmax": 1,  # Only need the top result
        }

        if self.email:
            params["email"] = self.email
        if self.api_key:
            params["api_key"] = self.api_key

        url = f"{self.BASE_URL}/esearch.fcgi"

        try:
            response = self._request(url, params)
            data = response.json()

            id_list = data.get("esearchresult", {}).get("idlist", [])
            if id_list:
                return int(id_list[0])
            return None

        except Exception as e:
            logger.error("Failed to search for gene '%s': %s", gene, e)
            raise SynonymFinderError(f"Gene search failed: {e}") from e

    def _fetch_gene_summary(
        self,
        gene_id: int,
        include_other_designations: bool,
    ) -> List[GeneSynonym]:
        """
        Fetch gene summary including synonyms.

        Args:
            gene_id: NCBI Gene ID
            include_other_designations: Include other gene designations

        Returns:
            List of GeneSynonym objects
        """
        params = {
            "db": "gene",
            "id": str(gene_id),
            "retmode": "json",
        }

        if self.email:
            params["email"] = self.email
        if self.api_key:
            params["api_key"] = self.api_key

        url = f"{self.BASE_URL}/esummary.fcgi"

        try:
            response = self._request(url, params)
            data = response.json()

            result = data.get("result", {}).get(str(gene_id), {})
            synonyms = []

            # Official symbol
            official_symbol = result.get("name")
            if official_symbol:
                synonyms.append(GeneSynonym(
                    term=official_symbol,
                    source="official_symbol",
                    gene_id=gene_id,
                ))

            # Aliases (common synonyms)
            aliases = result.get("otheraliases", "").split(", ")
            for alias in aliases:
                alias = alias.strip()
                if alias:
                    synonyms.append(GeneSynonym(
                        term=alias,
                        source="alias",
                        gene_id=gene_id,
                    ))

            # Other designations (if requested)
            if include_other_designations:
                other_designations = result.get("otherdesignations", "").split("|")
                for designation in other_designations:
                    designation = designation.strip()
                    if designation:
                        synonyms.append(GeneSynonym(
                            term=designation,
                            source="other_designation",
                            gene_id=gene_id,
                        ))

            return synonyms

        except Exception as e:
            logger.error("Failed to fetch gene summary for ID %s: %s", gene_id, e)
            raise SynonymFinderError(f"Gene summary fetch failed: {e}") from e

    def _request(self, url: str, params: dict) -> requests.Response:
        """
        Make an HTTP request with retry logic.

        Args:
            url: URL to request
            params: Query parameters

        Returns:
            Response object

        Raises:
            SynonymFinderError: If request fails after retries
        """
        for attempt in range(self.retry_attempts):
            try:
                # Add delay to respect NCBI rate limits (3 requests/sec without API key)
                if attempt > 0:
                    delay = 2 ** attempt  # Exponential backoff
                    logger.debug("Retrying request after %ds delay...", delay)
                    time.sleep(delay)
                else:
                    # Small delay between requests
                    time.sleep(0.34)

                response = self.session.get(url, params=params, timeout=30)
                response.raise_for_status()
                return response

            except requests.RequestException as e:
                logger.warning("Request attempt %d failed: %s", attempt + 1, e)
                if attempt == self.retry_attempts - 1:
                    raise SynonymFinderError(f"Request failed after {self.retry_attempts} attempts") from e

        # Should not reach here, but just in case
        raise SynonymFinderError("Request failed")


def interactive_synonym_selection(
    gene: str,
    synonyms: List[GeneSynonym],
    auto_include_official: bool = True,
) -> List[str]:
    """
    Interactively prompt user to select synonyms to include in search.

    Args:
        gene: Original gene name
        synonyms: List of found synonyms
        auto_include_official: Automatically include official symbols

    Returns:
        List of selected synonym terms
    """
    if not synonyms:
        print(f"\nNo synonyms found for '{gene}'")
        return []

    print(f"\n{'='*60}")
    print(f"Found {len(synonyms)} potential synonyms for '{gene}':")
    print(f"{'='*60}\n")

    # Group synonyms by source
    official = [s for s in synonyms if s.source == "official_symbol"]
    aliases = [s for s in synonyms if s.source == "alias"]
    other = [s for s in synonyms if s.source == "other_designation"]

    selected: Set[str] = set()

    # Display official symbols
    if official:
        print("Official Gene Symbol:")
        for i, syn in enumerate(official, 1):
            print(f"  [{i}] {syn.term}")
            if auto_include_official:
                selected.add(syn.term)

        if auto_include_official:
            print("  → Automatically included in search")
        print()

    # Display aliases
    if aliases:
        print(f"Gene Aliases ({len(aliases)} found):")
        for i, syn in enumerate(aliases, 1):
            print(f"  [{i}] {syn.term}")
        print()

    # Display other designations (if any)
    if other:
        print(f"Other Designations ({len(other)} found - may be verbose):")
        # Show only first 5 to avoid overwhelming user
        for i, syn in enumerate(other[:5], 1):
            print(f"  [{i}] {syn.term}")
        if len(other) > 5:
            print(f"  ... and {len(other) - 5} more")
        print()

    # Interactive selection
    print("Select synonyms to include in PubMed search:")
    print("  - Enter numbers separated by commas (e.g., '1,2,3')")
    print("  - Enter 'all' to include all")
    print("  - Enter 'aliases' to include all aliases only")
    print("  - Enter 'none' to skip synonym expansion")
    print("  - Press Enter to accept automatically selected terms")

    while True:
        user_input = input("\nYour selection: ").strip().lower()

        if not user_input:
            # User pressed Enter - use auto-selected
            break

        if user_input == "none":
            selected.clear()
            break

        if user_input == "all":
            selected = {syn.term for syn in synonyms}
            break

        if user_input == "aliases":
            selected.update(syn.term for syn in official + aliases)
            break

        # Parse comma-separated indices
        try:
            indices = [int(x.strip()) for x in user_input.split(",")]

            # Map indices to synonyms
            all_syns = official + aliases + other
            selected.clear()

            for idx in indices:
                if 1 <= idx <= len(all_syns):
                    selected.add(all_syns[idx - 1].term)
                else:
                    print(f"Warning: Index {idx} out of range, skipping")

            break

        except ValueError:
            print("Invalid input. Please enter numbers separated by commas, 'all', 'aliases', 'none', or press Enter")

    result = sorted(selected)

    print(f"\n{'='*60}")
    print(f"Selected {len(result)} terms for PubMed search:")
    for term in result:
        print(f"  ✓ {term}")
    print(f"{'='*60}\n")

    return result
