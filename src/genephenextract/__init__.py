"""Top-level package for GenePhenExtract."""

from .cohort_models import (
    CohortData,
    GeneticCohortDatabase,
    PhenotypeCount,
)
from .extraction import (
    BaseExtractor,
    ClaudeExtractor,
    GeminiExtractor,
    GroqExtractor,
    MockExtractor,
    MultiStageExtractor,
    OpenAIExtractor,
    RelevanceFilter,
)
from .gene_pipeline import GeneCentricPipeline, GeneVariantDatabase
from .hpo import PhenotypeOntologyMapper
from .models import ExtractionResult, PhenotypeObservation, PipelineInput
from .pdf_utility import PDFParserError, download_pdf, extract_text_from_pdf
from .penetrance_extractor import PenetranceExtractor, extract_penetrance_for_gene
from .penetrance_models import (
    FamilyStudy,
    Individual,
    VariantPenetranceDatabase,
)
from .pipeline import ExtractionPipeline
from .pubmed import PubMedClient
from .unified_extractor import UnifiedExtractor, extract_gene_data
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
    "GroqExtractor",
    "MockExtractor",
    "MultiStageExtractor",
    "OpenAIExtractor",
    "RelevanceFilter",
    "PenetranceExtractor",
    "UnifiedExtractor",
    # Pipelines
    "ExtractionPipeline",
    "GeneCentricPipeline",
    # Data models
    "ExtractionResult",
    "PhenotypeObservation",
    "PipelineInput",
    # Cohort models (for aggregate counts)
    "CohortData",
    "PhenotypeCount",
    "GeneticCohortDatabase",
    # Individual models (for detailed pedigrees)
    "Individual",
    "FamilyStudy",
    "VariantPenetranceDatabase",
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
    "extract_penetrance_for_gene",
    "extract_gene_data",
    "normalize_variant",
    "parse_variant",
]

__version__ = "0.1.0"
