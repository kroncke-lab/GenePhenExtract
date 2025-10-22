"""
Individual-level data models for penetrance studies.

THE CORE USE CASE:
Papers report families with multiple members. Some carriers are affected, some are not.
We need to extract EACH INDIVIDUAL to calculate true penetrance.

Example:
Paper: "Family with 5 members. Proband (het, affected), Mother (het, affected),
        Father (wt, unaffected), Sister (het, UNaffected), Brother (het, affected)"

Extract:
- 3 heterozygous carriers: 2 affected, 1 UNaffected
- Penetrance = 2/3 = 67%

This is what the project is ACTUALLY for!
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional

from .models import PhenotypeObservation


@dataclass
class Individual:
    """A single individual (family member or case) with genotype and phenotype data.

    This is the CORE data model for penetrance studies.
    """

    # Identity
    individual_id: str  # Unique ID (e.g., "proband", "mother", "patient_1")
    pmid: str

    # Genotype
    variant: Optional[str] = None  # e.g., "KCNH2 p.Ser906Leu"
    gene: Optional[str] = None
    genotype: Optional[str] = None  # "heterozygous", "homozygous", "compound_heterozygous", "wild-type"

    # Phenotype
    affected: Optional[bool] = None  # True = has phenotype, False = carrier but unaffected
    phenotypes: List[PhenotypeObservation] = field(default_factory=list)

    # Demographics
    age: Optional[float] = None  # Current age
    sex: Optional[str] = None  # "male", "female"

    # Clinical details
    age_at_onset: Optional[float] = None  # Age when first symptoms appeared
    age_at_diagnosis: Optional[float] = None

    # Family context
    relation: Optional[str] = None  # "proband", "mother", "father", "sibling", "offspring"
    family_id: Optional[str] = None  # Link individuals in same family

    # Paper metadata
    title: Optional[str] = None
    journal: Optional[str] = None
    publication_date: Optional[str] = None

    # Quality
    confidence: Optional[float] = None

    def is_carrier(self) -> bool:
        """Check if individual carries the variant."""
        return self.genotype in ["heterozygous", "homozygous", "compound_heterozygous"]

    def is_heterozygous(self) -> bool:
        """Check if individual is heterozygous carrier."""
        return self.genotype == "heterozygous"

    def is_affected_carrier(self) -> bool:
        """Check if individual is a carrier AND affected."""
        return self.is_carrier() and self.affected is True

    def is_unaffected_carrier(self) -> bool:
        """Check if individual is a carrier but UNaffected (key for penetrance!)."""
        return self.is_carrier() and self.affected is False

    def to_dict(self) -> dict:
        data = asdict(self)
        data["phenotypes"] = [p.to_dict() for p in self.phenotypes]
        return data


@dataclass
class FamilyStudy:
    """A family or cohort study with multiple individuals.

    This represents one paper that reports multiple family members or patients.
    """

    pmid: str
    variant: str  # The variant being studied
    gene: str

    individuals: List[Individual] = field(default_factory=list)

    # Study metadata
    title: Optional[str] = None
    journal: Optional[str] = None
    publication_date: Optional[str] = None
    study_type: Optional[str] = None  # "family", "case_series", "cohort"

    # Family context
    family_id: Optional[str] = None
    n_families: int = 1

    def add_individual(self, individual: Individual) -> None:
        """Add an individual to this study."""
        # Ensure individual has correct pmid and variant
        individual.pmid = self.pmid
        if not individual.variant:
            individual.variant = self.variant
        if not individual.gene:
            individual.gene = self.gene
        if not individual.family_id:
            individual.family_id = self.family_id or f"{self.pmid}_family1"

        self.individuals.append(individual)

    def get_carriers(self, genotype: Optional[str] = None) -> List[Individual]:
        """Get all carriers, optionally filtered by genotype."""
        carriers = [ind for ind in self.individuals if ind.is_carrier()]

        if genotype:
            carriers = [c for c in carriers if c.genotype == genotype]

        return carriers

    def get_heterozygous_carriers(self) -> List[Individual]:
        """Get all heterozygous carriers."""
        return self.get_carriers(genotype="heterozygous")

    def get_affected_carriers(self, genotype: Optional[str] = None) -> List[Individual]:
        """Get carriers who are affected."""
        carriers = self.get_carriers(genotype)
        return [c for c in carriers if c.affected is True]

    def get_unaffected_carriers(self, genotype: Optional[str] = None) -> List[Individual]:
        """Get carriers who are UNaffected (critical for penetrance!)."""
        carriers = self.get_carriers(genotype)
        return [c for c in carriers if c.affected is False]

    def calculate_penetrance(
        self,
        phenotype: Optional[str] = None,
        genotype: Optional[str] = None,
    ) -> Optional[float]:
        """Calculate penetrance for this family.

        Args:
            phenotype: Specific phenotype to calculate penetrance for (None = any phenotype)
            genotype: Filter to specific genotype (None = all carriers)

        Returns:
            Penetrance (0.0-1.0) or None if no data
        """
        carriers = self.get_carriers(genotype)

        if not carriers:
            return None

        if phenotype:
            # Penetrance for specific phenotype
            affected = [
                c for c in carriers
                if c.affected and any(p.phenotype == phenotype for p in c.phenotypes)
            ]
        else:
            # Overall penetrance (any phenotype)
            affected = [c for c in carriers if c.affected is True]

        return len(affected) / len(carriers) if carriers else None

    def get_phenotype_counts(self, genotype: Optional[str] = None) -> Dict[str, int]:
        """Count how many carriers have each phenotype."""
        carriers = self.get_carriers(genotype)
        counts: Dict[str, int] = {}

        for carrier in carriers:
            for pheno in carrier.phenotypes:
                counts[pheno.phenotype] = counts.get(pheno.phenotype, 0) + 1

        return counts

    def to_dict(self) -> dict:
        return {
            "pmid": self.pmid,
            "variant": self.variant,
            "gene": self.gene,
            "title": self.title,
            "journal": self.journal,
            "publication_date": self.publication_date,
            "study_type": self.study_type,
            "n_individuals": len(self.individuals),
            "n_carriers": len(self.get_carriers()),
            "n_heterozygous": len(self.get_heterozygous_carriers()),
            "n_affected": len(self.get_affected_carriers()),
            "n_unaffected": len(self.get_unaffected_carriers()),
            "penetrance": self.calculate_penetrance(),
            "individuals": [ind.to_dict() for ind in self.individuals],
        }


@dataclass
class VariantPenetranceDatabase:
    """Database aggregating penetrance data across multiple studies.

    This calculates TRUE penetrance by counting affected vs unaffected carriers
    across all papers.
    """

    variant: str
    gene: str
    genotype_filter: Optional[str] = None  # e.g., "heterozygous"

    studies: List[FamilyStudy] = field(default_factory=list)

    def add_study(self, study: FamilyStudy) -> None:
        """Add a family study to the database."""
        self.studies.append(study)

    def get_all_carriers(self) -> List[Individual]:
        """Get all carriers across all studies."""
        carriers = []
        for study in self.studies:
            if self.genotype_filter:
                carriers.extend(study.get_carriers(self.genotype_filter))
            else:
                carriers.extend(study.get_carriers())
        return carriers

    def get_affected_carriers(self, phenotype: Optional[str] = None) -> List[Individual]:
        """Get all affected carriers."""
        carriers = self.get_all_carriers()

        if phenotype:
            return [
                c for c in carriers
                if c.affected and any(p.phenotype == phenotype for p in c.phenotypes)
            ]
        else:
            return [c for c in carriers if c.affected is True]

    def get_unaffected_carriers(self) -> List[Individual]:
        """Get all UNaffected carriers (carriers without phenotype)."""
        carriers = self.get_all_carriers()
        return [c for c in carriers if c.affected is False]

    def calculate_overall_penetrance(self, phenotype: Optional[str] = None) -> Optional[float]:
        """Calculate penetrance across ALL studies.

        This is the TRUE penetrance:
        affected carriers / total carriers (including unaffected)

        Args:
            phenotype: Specific phenotype (None = any phenotype)

        Returns:
            Penetrance (0.0-1.0) or None if no data
        """
        all_carriers = self.get_all_carriers()

        if not all_carriers:
            return None

        affected = self.get_affected_carriers(phenotype)

        return len(affected) / len(all_carriers)

    def get_penetrance_by_phenotype(self) -> Dict[str, float]:
        """Get penetrance for each phenotype.

        Returns:
            Dict mapping phenotype -> penetrance
        """
        all_carriers = self.get_all_carriers()

        if not all_carriers:
            return {}

        # Get all unique phenotypes
        phenotypes = set()
        for carrier in all_carriers:
            for pheno in carrier.phenotypes:
                phenotypes.add(pheno.phenotype)

        # Calculate penetrance for each
        penetrance_map = {}
        for phenotype in phenotypes:
            affected = self.get_affected_carriers(phenotype)
            penetrance_map[phenotype] = len(affected) / len(all_carriers)

        return penetrance_map

    def get_summary(self) -> dict:
        """Get summary statistics."""
        all_carriers = self.get_all_carriers()
        affected = self.get_affected_carriers()
        unaffected = self.get_unaffected_carriers()

        return {
            "variant": self.variant,
            "gene": self.gene,
            "genotype": self.genotype_filter or "all",
            "n_studies": len(self.studies),
            "n_total_carriers": len(all_carriers),
            "n_affected_carriers": len(affected),
            "n_unaffected_carriers": len(unaffected),
            "overall_penetrance": self.calculate_overall_penetrance(),
            "penetrance_by_phenotype": self.get_penetrance_by_phenotype(),
            "studies": [study.to_dict() for study in self.studies],
        }

    def to_dataframe(self):
        """Export individual-level data to DataFrame.

        Returns one row per individual.
        """
        try:
            import pandas as pd
        except ImportError:
            raise ImportError("pandas required. Install with: pip install pandas")

        rows = []
        for study in self.studies:
            for individual in study.individuals:
                base_row = {
                    "pmid": individual.pmid,
                    "variant": individual.variant,
                    "gene": individual.gene,
                    "genotype": individual.genotype,
                    "affected": individual.affected,
                    "age": individual.age,
                    "sex": individual.sex,
                    "age_at_onset": individual.age_at_onset,
                    "relation": individual.relation,
                    "family_id": individual.family_id,
                    "is_carrier": individual.is_carrier(),
                    "is_heterozygous": individual.is_heterozygous(),
                    "is_affected_carrier": individual.is_affected_carrier(),
                    "is_unaffected_carrier": individual.is_unaffected_carrier(),
                }

                if individual.phenotypes:
                    for pheno in individual.phenotypes:
                        row = base_row.copy()
                        row["phenotype"] = pheno.phenotype
                        row["phenotype_ontology_id"] = pheno.ontology_id
                        rows.append(row)
                else:
                    # Include unaffected individuals with no phenotypes
                    row = base_row.copy()
                    row["phenotype"] = None
                    row["phenotype_ontology_id"] = None
                    rows.append(row)

        return pd.DataFrame(rows)

    def export_to_csv(self, path: str) -> None:
        """Export to CSV file."""
        df = self.to_dataframe()
        df.to_csv(path, index=False)
        print(f"Exported {len(df)} individuals to {path}")
