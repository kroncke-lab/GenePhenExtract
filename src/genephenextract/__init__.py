"""Top-level package for GenePhenExtract."""

from .extraction import BaseExtractor, GeminiExtractor, MockExtractor
from .hpo import PhenotypeOntologyMapper
from .models import ExtractionResult, PhenotypeObservation, PipelineInput
from .pipeline import ExtractionPipeline
from .pubmed import PubMedClient

__all__ = [
    "BaseExtractor",
    "ExtractionPipeline",
    "ExtractionResult",
    "GeminiExtractor",
    "MockExtractor",
    "PhenotypeObservation",
    "PhenotypeOntologyMapper",
    "PipelineInput",
    "PubMedClient",
]

__version__ = "0.1.0"
