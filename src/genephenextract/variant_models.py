"""Enhanced data models for variant-phenotype associations."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional, Tuple

from .models import PhenotypeObservation


@dataclass
class ParsedVariant:
    """Structured representation of a genetic variant."""

    raw_string: str
    gene: Optional[str] = None
    cdna_change: Optional[str] = None  # e.g., c.2717C>T
    protein_change: Optional[str] = None  # e.g., p.Ser906Leu
    transcript: Optional[str] = None
    is_valid_hgvs: bool = False
    normalized: Optional[str] = None  # Canonical representation

    def __str__(self) -> str:
        if self.normalized:
            return self.normalized
        return self.raw_string

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class VariantPhenotypeAssociation:
    """Link between a specific variant, genotype, and phenotype with evidence."""

    variant: str  # Variant string (ideally normalized)
    gene: str
    genotype: str  # heterozygous, homozygous, compound_heterozygous
    phenotype: PhenotypeObservation
    pmid: str

    # Optional quantitative data
    n_carriers: Optional[int] = None  # Number of carriers in study
    n_affected: Optional[int] = None  # Number showing this phenotype
    age_at_onset: Optional[float] = None
    severity: Optional[str] = None  # mild, moderate, severe

    # Quality metrics
    confidence: Optional[float] = None  # 0.0-1.0
    evidence_text: Optional[str] = None  # Supporting quote from paper

    # Metadata
    title: Optional[str] = None
    journal: Optional[str] = None
    publication_date: Optional[str] = None

    @property
    def penetrance(self) -> Optional[float]:
        """Calculate penetrance if we have carrier data."""
        if self.n_carriers and self.n_affected:
            return self.n_affected / self.n_carriers
        return None

    def to_dict(self) -> dict:
        data = asdict(self)
        data["penetrance"] = self.penetrance
        data["phenotype"] = self.phenotype.to_dict()
        return data


@dataclass
class VariantSummary:
    """Aggregated summary of a variant across multiple papers."""

    variant: str
    gene: str
    genotype: str  # Filter for specific genotype

    # Papers and evidence
    pmids: List[str] = field(default_factory=list)
    n_papers: int = 0

    # Carrier statistics
    total_carriers: int = 0
    total_affected: int = 0

    # Phenotype associations
    phenotypes: Dict[str, PhenotypeSummary] = field(default_factory=dict)

    # Database cross-references
    clinvar_classification: Optional[str] = None
    gnomad_frequency: Optional[float] = None

    @property
    def overall_penetrance(self) -> Optional[float]:
        """Overall penetrance across all phenotypes."""
        if self.total_carriers > 0:
            return self.total_affected / self.total_carriers
        return None

    def add_association(self, assoc: VariantPhenotypeAssociation) -> None:
        """Add a variant-phenotype association to this summary."""
        if assoc.pmid not in self.pmids:
            self.pmids.append(assoc.pmid)
            self.n_papers += 1

        if assoc.n_carriers:
            self.total_carriers += assoc.n_carriers
        if assoc.n_affected:
            self.total_affected += assoc.n_affected

        # Add phenotype
        pheno_name = assoc.phenotype.phenotype
        if pheno_name not in self.phenotypes:
            self.phenotypes[pheno_name] = PhenotypeSummary(name=pheno_name)

        self.phenotypes[pheno_name].add_observation(assoc)

    def top_phenotypes(self, n: int = 10) -> List[PhenotypeSummary]:
        """Get top N phenotypes by frequency."""
        return sorted(
            self.phenotypes.values(), key=lambda p: p.count, reverse=True
        )[:n]

    def to_dict(self) -> dict:
        data = asdict(self)
        data["overall_penetrance"] = self.overall_penetrance
        data["phenotypes"] = {
            name: pheno.to_dict() for name, pheno in self.phenotypes.items()
        }
        return data


@dataclass
class PhenotypeSummary:
    """Summary of a phenotype across multiple observations."""

    name: str
    count: int = 0  # Number of papers reporting this phenotype
    total_carriers: int = 0
    total_affected: int = 0
    pmids: List[str] = field(default_factory=list)

    # Severity distribution
    severity_counts: Dict[str, int] = field(default_factory=dict)

    # Age at onset
    onset_ages: List[float] = field(default_factory=list)

    @property
    def penetrance(self) -> Optional[float]:
        """Penetrance for this specific phenotype."""
        if self.total_carriers > 0:
            return self.total_affected / self.total_carriers
        return None

    @property
    def mean_onset_age(self) -> Optional[float]:
        """Mean age at onset."""
        if self.onset_ages:
            return sum(self.onset_ages) / len(self.onset_ages)
        return None

    def add_observation(self, assoc: VariantPhenotypeAssociation) -> None:
        """Add an observation of this phenotype."""
        self.count += 1

        if assoc.pmid not in self.pmids:
            self.pmids.append(assoc.pmid)

        if assoc.n_carriers:
            self.total_carriers += assoc.n_carriers
        if assoc.n_affected:
            self.total_affected += assoc.n_affected

        if assoc.severity:
            self.severity_counts[assoc.severity] = (
                self.severity_counts.get(assoc.severity, 0) + 1
            )

        if assoc.age_at_onset:
            self.onset_ages.append(assoc.age_at_onset)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["penetrance"] = self.penetrance
        data["mean_onset_age"] = self.mean_onset_age
        return data


def parse_variant(variant_string: str) -> ParsedVariant:
    """Parse a variant string into structured components.

    Handles formats like:
    - "KCNH2 p.Tyr54Asn"
    - "KCNH2 c.2717C>T p.(Ser906Leu)"
    - "SCN5A p.R1193Q"
    - "KCNQ1 c.1032G>A"

    Args:
        variant_string: Raw variant string from extraction

    Returns:
        ParsedVariant with extracted components
    """
    variant_string = variant_string.strip()

    # Try to extract gene name (capital letters at start)
    gene_match = re.match(r'^([A-Z][A-Z0-9]+)\s+', variant_string)
    gene = gene_match.group(1) if gene_match else None

    # Extract cDNA change (c.###X>Y)
    cdna_match = re.search(r'c\.(\d+[A-Z]>[A-Z])', variant_string, re.IGNORECASE)
    cdna_change = f"c.{cdna_match.group(1)}" if cdna_match else None

    # Extract protein change (p.XxxNNNYyy or p.(XxxNNNYyy))
    protein_patterns = [
        r'p\.\(([A-Z][a-z]{2}\d+[A-Z][a-z]{2})\)',  # p.(Ser906Leu)
        r'p\.([A-Z][a-z]{2}\d+[A-Z][a-z]{2})',  # p.Ser906Leu
        r'p\.\(([A-Z]\d+[A-Z])\)',  # p.(R534C)
        r'p\.([A-Z]\d+[A-Z])',  # p.R534C
    ]

    protein_change = None
    for pattern in protein_patterns:
        match = re.search(pattern, variant_string)
        if match:
            protein_change = f"p.{match.group(1)}"
            break

    # Determine if this looks like valid HGVS
    is_valid = bool(gene and (cdna_change or protein_change))

    # Create normalized representation
    normalized = None
    if gene:
        parts = [gene]
        if cdna_change:
            parts.append(cdna_change)
        if protein_change:
            parts.append(protein_change)
        normalized = " ".join(parts)

    return ParsedVariant(
        raw_string=variant_string,
        gene=gene,
        cdna_change=cdna_change,
        protein_change=protein_change,
        is_valid_hgvs=is_valid,
        normalized=normalized or variant_string,
    )


def normalize_variant(variant_string: str) -> str:
    """Normalize a variant string to canonical format.

    Args:
        variant_string: Raw variant string

    Returns:
        Normalized variant string (e.g., "KCNH2 c.2717C>T p.Ser906Leu")
    """
    parsed = parse_variant(variant_string)
    return parsed.normalized or variant_string


def extract_gene_from_variant(variant_string: str) -> Optional[str]:
    """Extract gene name from variant string.

    Args:
        variant_string: Variant string

    Returns:
        Gene name or None
    """
    parsed = parse_variant(variant_string)
    return parsed.gene
