"""Top-level package for GenePhenExtract."""

from .extraction import (
    BaseExtractor,
    ClaudeExtractor,
    GeminiExtractor,
    MockExtractor,
    MultiStageExtractor,
    OpenAIExtractor,
    RelevanceFilter,
)
from .gene_pipeline import GeneCentricPipeline, GeneVariantDatabase
from .hpo import PhenotypeOntologyMapper
from .models import ExtractionResult, PhenotypeObservation, PipelineInput
from .pdf_utility import PDFParserError, download_pdf, extract_text_from_pdf
from .pipeline import ExtractionPipeline
from .pubmed import PubMedClient
from .variant_models import (
    ParsedVariant,
    VariantPhenotypeAssociation,
    VariantSummary,
    extract_gene_from_variant,
    normalize_variant,
    parse_variant,
)

__all__ = [
    # Extractors
    "BaseExtractor",
    "ClaudeExtractor",
    "GeminiExtractor",
    "MockExtractor",
    "MultiStageExtractor",
    "OpenAIExtractor",
    "RelevanceFilter",
    # Pipelines
    "ExtractionPipeline",
    "GeneCentricPipeline",
    # Data models
    "ExtractionResult",
    "PhenotypeObservation",
    "PipelineInput",
    # Variant models
    "ParsedVariant",
    "VariantPhenotypeAssociation",
    "VariantSummary",
    "GeneVariantDatabase",
    # Utilities
    "PhenotypeOntologyMapper",
    "PubMedClient",
    "PDFParserError",
    # Functions
    "download_pdf",
    "extract_text_from_pdf",
    "extract_gene_from_variant",
    "normalize_variant",
    "parse_variant",
]

__version__ = "0.1.0"
