"""Gene-focused literature collection utilities."""

from .collector import LiteratureCollector, build_gene_query
from .pubmed_client import ArticleMetadata, PubMedClient

__all__ = [
    "ArticleMetadata",
    "LiteratureCollector",
    "PubMedClient",
    "build_gene_query",
]
