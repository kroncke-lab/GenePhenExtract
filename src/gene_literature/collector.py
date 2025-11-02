"""High-level orchestration for gene-focused literature collection."""

from __future__ import annotations

import logging
from typing import List, Optional, Sequence

from .pubmed_client import ArticleMetadata, PubMedClient

logger = logging.getLogger(__name__)

try:
    from .relevance_checker import RelevanceChecker
    RELEVANCE_CHECKER_AVAILABLE = True
except ImportError:
    RELEVANCE_CHECKER_AVAILABLE = False
    logger.debug("RelevanceChecker not available (anthropic package not installed)")


def build_gene_query(gene: str, synonyms: Optional[Sequence[str]] = None) -> str:
    """Build a simple PubMed query using the provided gene and synonyms."""

    terms = [gene, *(synonyms or [])]
    sanitized = [term.strip() for term in terms if term and term.strip()]
    quoted = [f'"{term}"[Title/Abstract]' for term in sanitized]
    if not quoted:
        raise ValueError("At least one search term must be provided")
    query = " OR ".join(quoted)
    logger.debug("Constructed PubMed query: %s", query)
    return query


class LiteratureCollector:
    """Coordinate the process of searching PubMed and gathering article metadata."""

    def __init__(
        self,
        client: PubMedClient,
        relevance_checker: Optional["RelevanceChecker"] = None,
    ) -> None:
        self.client = client
        self.relevance_checker = relevance_checker

    def collect(
        self,
        gene: str,
        *,
        synonyms: Optional[Sequence[str]] = None,
        retmax: int = 100,
        filter_irrelevant: bool = False,
        min_relevance_score: float = 0.7,
    ) -> List[ArticleMetadata]:
        """Collect article metadata for the provided gene and optional synonyms.

        Args:
            gene: Primary gene symbol
            synonyms: Optional list of gene synonyms
            retmax: Maximum number of results from PubMed
            filter_irrelevant: If True, filter out papers below min_relevance_score
            min_relevance_score: Minimum relevance score (0.0-1.0) to keep papers

        Returns:
            List of article metadata, optionally filtered by relevance
        """

        query = build_gene_query(gene, synonyms)
        pmids = self.client.search(query, retmax=retmax)
        if not pmids:
            logger.info("No PubMed records found for query: %s", query)
            return []

        records = self.client.fetch_metadata(pmids)

        # Apply relevance checking if requested
        if filter_irrelevant and self.relevance_checker:
            logger.info("Checking relevance for %d papers", len(records))
            records = self._filter_by_relevance(
                gene, records, min_relevance_score
            )
            logger.info("After filtering: %d papers remain", len(records))
        elif filter_irrelevant and not self.relevance_checker:
            logger.warning(
                "Relevance filtering requested but no RelevanceChecker provided. "
                "Install anthropic package and provide API key."
            )

        return records

    def _filter_by_relevance(
        self,
        gene: str,
        records: List[ArticleMetadata],
        min_score: float,
    ) -> List[ArticleMetadata]:
        """Filter papers by relevance score."""

        filtered_records = []
        for record in records:
            if not record.title:
                # Can't assess relevance without title
                logger.debug(f"Skipping PMID {record.pmid} - no title")
                continue

            score = self.relevance_checker.check_relevance(
                gene, record.title, record.abstract, record.pmid
            )

            # Update record with relevance info
            record.relevance_score = score.confidence
            record.relevance_reasoning = score.reasoning

            if score.is_relevant and score.confidence >= min_score:
                filtered_records.append(record)
                logger.debug(
                    f"PMID {record.pmid}: RELEVANT (score={score.confidence:.2f})"
                )
            else:
                logger.info(
                    f"PMID {record.pmid}: FILTERED OUT "
                    f"(score={score.confidence:.2f}, reason: {score.reasoning})"
                )

        return filtered_records
