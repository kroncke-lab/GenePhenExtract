"""Gene-focused literature collection utilities."""

from .collector import LiteratureCollector, build_gene_query
from .pubmed_client import ArticleMetadata, PubMedClient
from .synonym_finder import GeneSynonym, SynonymFinder, interactive_synonym_selection

__all__ = [
    "ArticleMetadata",
    "GeneSynonym",
    "LiteratureCollector",
    "PubMedClient",
    "SynonymFinder",
    "build_gene_query",
    "interactive_synonym_selection",
]
