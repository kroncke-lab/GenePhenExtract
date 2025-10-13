"""Data models used throughout GenePhenExtract."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class PhenotypeObservation:
    """Structured representation of a phenotype mention for a variant carrier."""

    phenotype: str
    ontology_id: Optional[str] = None
    onset_age: Optional[str] = None
    notes: Optional[str] = None

    def __post_init__(self) -> None:
        normalized = (self.phenotype or "").strip()
        if not normalized:
            msg = "phenotype cannot be blank"
            raise ValueError(msg)
        self.phenotype = normalized

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ExtractionResult:
    """Container for the structured data returned by the extraction pipeline."""

    pmid: str
    variant: str
    carrier_status: Optional[str] = None
    phenotypes: List[PhenotypeObservation] = field(default_factory=list)
    age: Optional[float] = None
    sex: Optional[str] = None
    treatment: Optional[str] = None
    outcome: Optional[str] = None
    title: Optional[str] = None
    journal: Optional[str] = None
    publication_date: Optional[str] = None
    abstract: Optional[str] = None
    extracted_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self) -> None:
        self.pmid = str(self.pmid)
        self.variant = self.variant.strip()

    def to_dict(self) -> dict:
        data = asdict(self)
        data["extracted_at"] = self.extracted_at.isoformat()
        data["phenotypes"] = [phenotype.to_dict() for phenotype in self.phenotypes]
        return data


@dataclass
class PipelineInput:
    """Input payload that drives the extraction pipeline."""

    query: Optional[str] = None
    pmids: List[str] = field(default_factory=list)
    max_results: int = 10
    schema_path: Optional[str] = None

    def __post_init__(self) -> None:
        self.pmids = [str(value) for value in self.pmids]
        if self.query is not None:
            self.query = self.query.strip() or None
