"""
Cohort-level data models for extracting aggregate counts from papers.

Use this approach when papers report aggregate statistics:
"50 patients with heterozygous KCNH2 variants, 35 had long QT syndrome"

For papers that detail individual patients, use penetrance_models.py instead.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict
import json


@dataclass
class PhenotypeCount:
    """Count of patients with a specific phenotype in a cohort.

    Attributes:
        phenotype: Name of the phenotype (e.g., "long QT syndrome")
        affected_count: Number of carriers who have this phenotype
        notes: Optional additional information about this phenotype observation
    """
    phenotype: str
    affected_count: int
    notes: Optional[str] = None

    def get_unaffected_count(self, total_carriers: int) -> int:
        """Calculate unaffected count from total carriers.

        Args:
            total_carriers: Total number of carriers in the cohort

        Returns:
            Number of carriers without this phenotype
        """
        return total_carriers - self.affected_count


@dataclass
class CohortData:
    """Aggregate data from a cohort study.

    Represents data from papers that report counts/statistics rather than
    individual patient details. Example:

    "We studied 50 patients with heterozygous KCNH2 p.Tyr54Asn variants.
     35 had long QT syndrome, 12 had syncope, 15 were asymptomatic."

    Attributes:
        pmid: PubMed ID of the source paper
        gene: Gene name (e.g., "KCNH2")
        variant: Specific variant (e.g., "p.Tyr54Asn"), None if multiple variants
        genotype: Genotype category (heterozygous, homozygous, compound_heterozygous)
        total_carriers: Total number of carriers with this genotype
        phenotype_counts: List of phenotype counts for this cohort
        population: Optional description of the population (e.g., "probands", "family members")
        notes: Optional additional information
    """
    pmid: str
    gene: str
    genotype: str  # heterozygous, homozygous, compound_heterozygous
    total_carriers: int
    phenotype_counts: List[PhenotypeCount] = field(default_factory=list)
    variant: Optional[str] = None  # None if cohort includes multiple variants
    population: Optional[str] = None
    notes: Optional[str] = None

    def get_affected_count(self, phenotype: Optional[str] = None) -> int:
        """Get count of affected carriers.

        Args:
            phenotype: Specific phenotype to count, or None for any phenotype

        Returns:
            Number of carriers with the specified phenotype (or any phenotype if None)
        """
        if phenotype:
            for pc in self.phenotype_counts:
                if pc.phenotype == phenotype:
                    return pc.affected_count
            return 0
        else:
            # Return count with ANY phenotype (may include duplicates if one person has multiple)
            return sum(pc.affected_count for pc in self.phenotype_counts)

    def get_unaffected_count(self, phenotype: Optional[str] = None) -> int:
        """Get count of unaffected carriers.

        Args:
            phenotype: Specific phenotype, or None for carriers without ANY phenotype

        Returns:
            Number of carriers without the phenotype
        """
        if phenotype:
            affected = self.get_affected_count(phenotype)
            return self.total_carriers - affected
        else:
            # This is approximate - some carriers may have multiple phenotypes
            return self.total_carriers - self.get_affected_count()

    def calculate_frequency(self, phenotype: str) -> float:
        """Calculate frequency of a phenotype in this cohort.

        Args:
            phenotype: The phenotype to calculate frequency for

        Returns:
            Frequency as a decimal (e.g., 0.7 for 70%)
        """
        if self.total_carriers == 0:
            return 0.0
        affected = self.get_affected_count(phenotype)
        return affected / self.total_carriers

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "pmid": self.pmid,
            "gene": self.gene,
            "variant": self.variant,
            "genotype": self.genotype,
            "total_carriers": self.total_carriers,
            "phenotype_counts": [
                {
                    "phenotype": pc.phenotype,
                    "affected_count": pc.affected_count,
                    "unaffected_count": pc.get_unaffected_count(self.total_carriers),
                    "notes": pc.notes
                }
                for pc in self.phenotype_counts
            ],
            "population": self.population,
            "notes": self.notes
        }


@dataclass
class GeneticCohortDatabase:
    """Database aggregating cohort data across multiple studies.

    Useful for analyzing data across multiple papers reporting aggregate counts.
    """
    gene: str
    cohorts: List[CohortData] = field(default_factory=list)

    def add_cohort(self, cohort: CohortData):
        """Add a cohort study to the database."""
        if cohort.gene != self.gene:
            raise ValueError(f"Cohort gene {cohort.gene} doesn't match database gene {self.gene}")
        self.cohorts.append(cohort)

    def filter_by_genotype(self, genotype: str) -> List[CohortData]:
        """Filter cohorts by genotype.

        Args:
            genotype: "heterozygous", "homozygous", or "compound_heterozygous"

        Returns:
            List of cohorts with the specified genotype
        """
        return [c for c in self.cohorts if c.genotype == genotype]

    def filter_by_variant(self, variant: str) -> List[CohortData]:
        """Filter cohorts by specific variant.

        Args:
            variant: Variant identifier (e.g., "p.Tyr54Asn")

        Returns:
            List of cohorts studying this variant
        """
        return [c for c in self.cohorts if c.variant and variant.lower() in c.variant.lower()]

    def get_total_carriers(self, genotype: Optional[str] = None, variant: Optional[str] = None) -> int:
        """Get total number of carriers across all cohorts.

        Args:
            genotype: Optional filter by genotype
            variant: Optional filter by variant

        Returns:
            Total number of carriers
        """
        cohorts = self.cohorts
        if genotype:
            cohorts = [c for c in cohorts if c.genotype == genotype]
        if variant:
            cohorts = [c for c in cohorts if c.variant and variant.lower() in c.variant.lower()]
        return sum(c.total_carriers for c in cohorts)

    def get_aggregate_phenotype_counts(
        self,
        phenotype: str,
        genotype: Optional[str] = None,
        variant: Optional[str] = None
    ) -> tuple[int, int]:
        """Get aggregate counts for a phenotype across cohorts.

        Args:
            phenotype: Phenotype to count
            genotype: Optional filter by genotype
            variant: Optional filter by variant

        Returns:
            Tuple of (affected_count, total_carriers)
        """
        cohorts = self.cohorts
        if genotype:
            cohorts = [c for c in cohorts if c.genotype == genotype]
        if variant:
            cohorts = [c for c in cohorts if c.variant and variant.lower() in c.variant.lower()]

        affected = sum(c.get_affected_count(phenotype) for c in cohorts)
        total = sum(c.total_carriers for c in cohorts)
        return affected, total

    def calculate_aggregate_frequency(
        self,
        phenotype: str,
        genotype: Optional[str] = None,
        variant: Optional[str] = None
    ) -> Optional[float]:
        """Calculate phenotype frequency across all cohorts.

        Args:
            phenotype: Phenotype to calculate frequency for
            genotype: Optional filter by genotype
            variant: Optional filter by variant

        Returns:
            Frequency as decimal, or None if no data
        """
        affected, total = self.get_aggregate_phenotype_counts(phenotype, genotype, variant)
        if total == 0:
            return None
        return affected / total

    def get_summary(self, genotype: Optional[str] = None) -> Dict[str, any]:
        """Get summary statistics for the database.

        Args:
            genotype: Optional filter by genotype

        Returns:
            Dictionary with summary statistics
        """
        cohorts = self.cohorts if not genotype else self.filter_by_genotype(genotype)

        # Collect all unique phenotypes
        all_phenotypes = set()
        for cohort in cohorts:
            for pc in cohort.phenotype_counts:
                all_phenotypes.add(pc.phenotype)

        # Calculate frequencies for each phenotype
        phenotype_stats = {}
        for phenotype in all_phenotypes:
            affected, total = self.get_aggregate_phenotype_counts(phenotype, genotype)
            phenotype_stats[phenotype] = {
                "affected_count": affected,
                "total_carriers": total,
                "frequency": affected / total if total > 0 else 0.0
            }

        return {
            "gene": self.gene,
            "genotype_filter": genotype,
            "total_cohorts": len(cohorts),
            "total_carriers": sum(c.total_carriers for c in cohorts),
            "phenotype_statistics": phenotype_stats
        }

    def export_to_dict(self) -> dict:
        """Export entire database to dictionary."""
        return {
            "gene": self.gene,
            "total_cohorts": len(self.cohorts),
            "cohorts": [c.to_dict() for c in self.cohorts]
        }

    def export_to_json(self, filepath: str):
        """Export database to JSON file."""
        with open(filepath, 'w') as f:
            json.dump(self.export_to_dict(), f, indent=2)
