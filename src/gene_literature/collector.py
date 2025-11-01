"""High-level orchestration for gene-focused literature collection."""

from __future__ import annotations

import logging
from typing import List, Optional, Sequence

from .pubmed_client import ArticleMetadata, PubMedClient

logger = logging.getLogger(__name__)


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

    def __init__(self, client: PubMedClient) -> None:
        self.client = client

    def collect(
        self,
        gene: str,
        *,
        synonyms: Optional[Sequence[str]] = None,
        retmax: int = 100,
    ) -> List[ArticleMetadata]:
        """Collect article metadata for the provided gene and optional synonyms."""

        query = build_gene_query(gene, synonyms)
        pmids = self.client.search(query, retmax=retmax)
        if not pmids:
            logger.info("No PubMed records found for query: %s", query)
            return []
        return self.client.fetch_metadata(pmids)
