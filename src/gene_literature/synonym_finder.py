"""
Automatic synonym discovery for genes using NCBI Gene database.

This module provides functionality to:
1. Query NCBI Gene database for official gene synonyms and aliases
2. Use LLM to assess relevance of synonyms
3. Present synonyms to users for interactive selection
4. Return selected synonyms for use in PubMed searches
"""

import logging
import time
from dataclasses import dataclass
from typing import List, Optional, Set
from urllib.parse import urlencode

import requests
from requests.adapters import HTTPAdapter, Retry

logger = logging.getLogger(__name__)

try:
    from gene_literature.synonym_relevance_checker import (
        SynonymRelevanceChecker,
        SynonymRelevance,
    )
    RELEVANCE_CHECKER_AVAILABLE = True
except ImportError:
    RELEVANCE_CHECKER_AVAILABLE = False


class SynonymFinderError(RuntimeError):
    """Raised when synonym lookup fails."""


@dataclass
class GeneSynonym:
    """Represents a gene synonym with metadata."""

    term: str
    source: str  # e.g., "official_symbol", "alias", "other_designations"
    gene_id: Optional[int] = None
    is_relevant: Optional[bool] = None  # LLM-assessed relevance
    relevance_confidence: Optional[float] = None  # 0.0 to 1.0
    relevance_reasoning: Optional[str] = None


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
        anthropic_api_key: Optional[str] = None,
    ):
        """
        Initialize the SynonymFinder.

        Args:
            email: Email address for NCBI API (recommended)
            api_key: NCBI API key for higher rate limits (optional)
            retry_attempts: Number of retry attempts for failed requests
            anthropic_api_key: Anthropic API key for LLM-based relevance checking (optional)
        """
        self.email = email
        self.api_key = api_key
        self.retry_attempts = retry_attempts
        self.anthropic_api_key = anthropic_api_key

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

        # Step 3: Check relevance with LLM if API key provided
        if self.anthropic_api_key and RELEVANCE_CHECKER_AVAILABLE:
            logger.info("Checking synonym relevance with LLM...")
            synonyms = self._check_synonyms_relevance(gene, synonyms)
        elif self.anthropic_api_key and not RELEVANCE_CHECKER_AVAILABLE:
            logger.warning(
                "Anthropic API key provided but anthropic package not installed. "
                "Install with: pip install anthropic"
            )

        return synonyms

    def _check_synonyms_relevance(
        self,
        gene: str,
        synonyms: List[GeneSynonym],
    ) -> List[GeneSynonym]:
        """
        Check relevance of synonyms using LLM.

        Args:
            gene: Primary gene name
            synonyms: List of synonym candidates

        Returns:
            List of GeneSynonym objects with relevance information added
        """
        checker = SynonymRelevanceChecker(api_key=self.anthropic_api_key)

        # Check each synonym
        for synonym in synonyms:
            relevance = checker.check_synonym_relevance(
                gene_name=gene,
                synonym=synonym.term,
                source=synonym.source,
            )

            # Update synonym with relevance info
            synonym.is_relevant = relevance.is_relevant
            synonym.relevance_confidence = relevance.confidence
            synonym.relevance_reasoning = relevance.reasoning

            logger.debug(
                "Synonym '%s': %s (confidence: %.2f) - %s",
                synonym.term,
                "RELEVANT" if relevance.is_relevant else "NOT RELEVANT",
                relevance.confidence,
                relevance.reasoning,
            )

        # Sort synonyms: relevant first, then by confidence
        synonyms_sorted = sorted(
            synonyms,
            key=lambda s: (
                not s.is_relevant if s.is_relevant is not None else False,
                -(s.relevance_confidence or 0.0),
            ),
        )

        relevant_count = sum(1 for s in synonyms if s.is_relevant)
        logger.info(
            "LLM assessed %d/%d synonyms as relevant",
            relevant_count,
            len(synonyms),
        )

        return synonyms_sorted

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

    # Check if any synonyms have relevance information
    has_relevance_info = any(s.is_relevant is not None for s in synonyms)

    print(f"\n{'='*60}")
    print(f"Found {len(synonyms)} potential synonyms for '{gene}':")
    print(f"{'='*60}\n")

    # Group synonyms by source
    official = [s for s in synonyms if s.source == "official_symbol"]
    aliases = [s for s in synonyms if s.source == "alias"]
    other = [s for s in synonyms if s.source == "other_designation"]

    selected: Set[str] = set()

    def format_synonym(syn: GeneSynonym) -> str:
        """Format a synonym with optional relevance info."""
        if has_relevance_info and syn.is_relevant is not None:
            relevance_marker = "✓" if syn.is_relevant else "✗"
            confidence_str = f"{syn.relevance_confidence:.0%}" if syn.relevance_confidence else "??"
            return f"{syn.term} [{relevance_marker} {confidence_str}]"
        return syn.term

    # Display official symbols
    if official:
        print("Official Gene Symbol:")
        for i, syn in enumerate(official, 1):
            print(f"  [{i}] {format_synonym(syn)}")
            if auto_include_official:
                selected.add(syn.term)

        if auto_include_official:
            print("  → Automatically included in search")
        print()

    # Display aliases
    if aliases:
        print(f"Gene Aliases ({len(aliases)} found):")
        for i, syn in enumerate(aliases, 1):
            print(f"  [{i}] {format_synonym(syn)}")
            if has_relevance_info and syn.relevance_reasoning:
                # Show reasoning for first few items
                if i <= 3:
                    print(f"      {syn.relevance_reasoning}")
        print()

    # Display other designations (if any)
    if other:
        print(f"Other Designations ({len(other)} found - may be verbose):")
        # Show only first 5 to avoid overwhelming user
        for i, syn in enumerate(other[:5], 1):
            print(f"  [{i}] {format_synonym(syn)}")
        if len(other) > 5:
            print(f"  ... and {len(other) - 5} more")
        print()

    if has_relevance_info:
        print("Legend: ✓ = LLM assessed as relevant, ✗ = not relevant")
        print()

    # Interactive selection
    print("Select synonyms to include in PubMed search:")
    print("  - Enter numbers separated by commas (e.g., '1,2,3')")
    print("  - Enter 'all' to include all")
    print("  - Enter 'aliases' to include all aliases only")
    if has_relevance_info:
        print("  - Enter 'relevant' to include only LLM-assessed relevant synonyms")
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

        if user_input == "relevant" and has_relevance_info:
            selected = {syn.term for syn in synonyms if syn.is_relevant}
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
            valid_options = "'all', 'aliases'"
            if has_relevance_info:
                valid_options += ", 'relevant'"
            valid_options += ", 'none', or press Enter"
            print(f"Invalid input. Please enter numbers separated by commas, {valid_options}")

    result = sorted(selected)

    print(f"\n{'='*60}")
    print(f"Selected {len(result)} terms for PubMed search:")
    for term in result:
        print(f"  ✓ {term}")
    print(f"{'='*60}\n")

    return result
