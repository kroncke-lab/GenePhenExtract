"""Top-level package for GenePhenExtract."""

from .models import ExtractionResult, PhenotypeObservation, PipelineInput
from .pipeline import ExtractionPipeline
from .pubmed import PubMedClient

__all__ = [
    "ExtractionPipeline",
    "ExtractionResult",
    "PhenotypeObservation",
    "PipelineInput",
    "PubMedClient",
]

__version__ = "0.1.0"
