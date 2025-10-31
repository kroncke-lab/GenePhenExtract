"""
Unified extractor that handles both cohort-level and individual-level data.

Automatically determines the appropriate extraction method based on how
the paper reports data:
- Cohort-level: "50 patients with heterozygous variants, 35 had long QT"
- Individual-level: "Proband: male, age 23, het, long QT; Mother: female, age 45, het, asymptomatic"
"""

import json
import os
from typing import Union, List, Optional
from pathlib import Path

from .extraction import BaseExtractor
from .cohort_models import CohortData, PhenotypeCount, GeneticCohortDatabase
from .penetrance_models import (
    Individual, FamilyStudy, PhenotypeObservation, VariantPenetranceDatabase
)
from .pubmed import PubMedClient


class UnifiedExtractor:
    """Extractor that automatically handles both cohort and individual data.

    This extractor uses a unified schema and returns the appropriate data model
    based on how the paper reports genotype-phenotype information.

    Example:
        >>> extractor = UnifiedExtractor(llm_extractor=ClaudeExtractor())
        >>> result = extractor.extract(text, pmid="12345678")
        >>> if isinstance(result, CohortData):
        ...     print(f"Cohort: {result.total_carriers} carriers")
        >>> elif isinstance(result, FamilyStudy):
        ...     print(f"Family: {len(result.individuals)} individuals")
    """

    def __init__(self, llm_extractor: BaseExtractor):
        """Initialize the unified extractor.

        Args:
            llm_extractor: Any LLM extractor (ClaudeExtractor, OpenAIExtractor, etc.)
        """
        self.llm_extractor = llm_extractor

        # Load the unified schema
        schema_path = Path(__file__).parent / "schema" / "unified_extraction_schema.json"
        with open(schema_path) as f:
            self.schema = json.load(f)

    def _create_extraction_prompt(self, text: str, gene: Optional[str] = None) -> str:
        """Create prompt for unified extraction.

        Args:
            text: The text to extract from
            gene: Optional gene to focus on

        Returns:
            Formatted prompt
        """
        gene_context = f"Focus on variants in the {gene} gene." if gene else ""

        return f"""Extract genotype-phenotype information from this text.

{gene_context}

IMPORTANT: Choose the appropriate extraction type based on how the paper reports data:

1. Use COHORT extraction if the paper reports AGGREGATE COUNTS:
   Example: "We studied 50 patients with heterozygous KCNH2 variants. 35 had long QT syndrome, 12 had syncope."

2. Use INDIVIDUAL extraction if the paper describes SPECIFIC PATIENTS:
   Example: "The proband (male, age 23) carried a heterozygous KCNH2 p.Tyr54Asn variant and presented with long QT. His mother (age 45) was an asymptomatic carrier."

For COHORT extraction:
- Report total_carriers (total with this genotype)
- For each phenotype, report affected_count (how many had it)
- Unaffected count is calculated as: total_carriers - affected_count

For INDIVIDUAL extraction:
- Extract EACH person mentioned (affected AND unaffected carriers)
- Record individual characteristics: age, sex, age_at_onset, age_at_diagnosis
- affected: true if has phenotypes, false if asymptomatic carrier
- Include wild-type family members if mentioned

Text to analyze:
{text}
"""

    def extract(
        self,
        text: str,
        pmid: str,
        gene: Optional[str] = None
    ) -> Union[CohortData, FamilyStudy, List[Union[CohortData, FamilyStudy]]]:
        """Extract genotype-phenotype data from text.

        Args:
            text: The text to extract from (abstract or full-text)
            pmid: PubMed ID of the source paper
            gene: Optional gene to focus extraction on

        Returns:
            CohortData, FamilyStudy, or list of both (if paper has multiple datasets)
        """
        prompt = self._create_extraction_prompt(text, gene)

        # Use the LLM extractor with our schema
        result = self.llm_extractor.extract(
            text=text,
            schema=self.schema,
            prompt=prompt
        )

        if not result or not isinstance(result, dict):
            return None

        extraction_type = result.get("extraction_type")
        gene_extracted = result.get("gene", gene)

        # Parse based on extraction type
        if extraction_type == "cohort":
            return self._parse_cohort_data(result, pmid, gene_extracted)
        elif extraction_type == "individual":
            return self._parse_individual_data(result, pmid, gene_extracted)
        else:
            return None

    def _parse_cohort_data(
        self,
        result: dict,
        pmid: str,
        gene: str
    ) -> Union[CohortData, List[CohortData]]:
        """Parse cohort-level extraction results.

        Args:
            result: Extraction result dictionary
            pmid: PubMed ID
            gene: Gene name

        Returns:
            CohortData or list of CohortData if multiple cohorts
        """
        cohort_data_list = result.get("cohort_data", [])

        if not cohort_data_list:
            return None

        cohorts = []
        for cohort_dict in cohort_data_list:
            phenotype_counts = [
                PhenotypeCount(
                    phenotype=pc["phenotype"],
                    affected_count=pc["affected_count"],
                    notes=pc.get("notes")
                )
                for pc in cohort_dict.get("phenotype_counts", [])
            ]

            cohort = CohortData(
                pmid=pmid,
                gene=gene,
                variant=cohort_dict.get("variant"),
                genotype=cohort_dict["genotype"],
                total_carriers=cohort_dict["total_carriers"],
                phenotype_counts=phenotype_counts,
                population=cohort_dict.get("population"),
                notes=cohort_dict.get("notes")
            )
            cohorts.append(cohort)

        return cohorts[0] if len(cohorts) == 1 else cohorts

    def _parse_individual_data(
        self,
        result: dict,
        pmid: str,
        gene: str
    ) -> FamilyStudy:
        """Parse individual-level extraction results.

        Args:
            result: Extraction result dictionary
            pmid: PubMed ID
            gene: Gene name

        Returns:
            FamilyStudy containing all individuals
        """
        individual_data_list = result.get("individual_data", [])

        if not individual_data_list:
            return None

        individuals = []
        for ind_dict in individual_data_list:
            phenotypes = [
                PhenotypeObservation(
                    phenotype=p["phenotype"],
                    severity=p.get("severity"),
                    notes=p.get("notes")
                )
                for p in ind_dict.get("phenotypes", [])
            ]

            individual = Individual(
                individual_id=ind_dict["id"],
                pmid=pmid,
                gene=gene,
                variant=ind_dict.get("variant"),
                genotype=ind_dict["genotype"],
                affected=ind_dict.get("affected"),
                phenotypes=phenotypes,
                age=ind_dict.get("age"),
                sex=ind_dict.get("sex"),
                age_at_onset=ind_dict.get("age_at_onset"),
                age_at_diagnosis=ind_dict.get("age_at_diagnosis"),
                relation=ind_dict.get("relation"),
                notes=ind_dict.get("notes")
            )
            individuals.append(individual)

        # Try to determine the primary variant from individuals
        variants = [ind.variant for ind in individuals if ind.variant]
        primary_variant = variants[0] if variants else "unknown"

        return FamilyStudy(
            pmid=pmid,
            gene=gene,
            variant=primary_variant,
            individuals=individuals
        )


def extract_gene_data(
    gene: str,
    extractor: UnifiedExtractor,
    max_papers: int = 50,
    date_range: Optional[tuple[int, int]] = None
) -> tuple[GeneticCohortDatabase, VariantPenetranceDatabase]:
    """Extract both cohort and individual data for a gene.

    Args:
        gene: Gene name (e.g., "KCNH2")
        extractor: UnifiedExtractor instance
        max_papers: Maximum number of papers to process
        date_range: Optional (start_year, end_year) tuple

    Returns:
        Tuple of (cohort_database, individual_database)
    """
    # Initialize databases
    cohort_db = GeneticCohortDatabase(gene=gene)
    individual_db = VariantPenetranceDatabase()

    # Search PubMed
    pubmed = PubMedClient()
    query = f"{gene}[Gene] AND (variant OR mutation OR genotype)"

    if date_range:
        start, end = date_range
        query += f" AND {start}:{end}[PDAT]"

    pmids = pubmed.search(query, max_results=max_papers)

    print(f"Found {len(pmids)} papers for {gene}")

    # Process each paper
    for i, pmid in enumerate(pmids, 1):
        print(f"Processing {i}/{len(pmids)}: PMID {pmid}")

        # Get full text or abstract
        try:
            details = pubmed.fetch_details([pmid])
            if not details:
                continue

            article_details = details.get(pmid)
            if not article_details:
                continue

            text = article_details.get("abstract", "")
            if not text:
                continue

            # Extract data
            result = extractor.extract(text, pmid, gene)

            if not result:
                continue

            # Add to appropriate database
            if isinstance(result, CohortData):
                cohort_db.add_cohort(result)
            elif isinstance(result, list):
                for item in result:
                    if isinstance(item, CohortData):
                        cohort_db.add_cohort(item)
                    elif isinstance(item, FamilyStudy):
                        individual_db.add_study(item)
            elif isinstance(result, FamilyStudy):
                individual_db.add_study(result)

        except Exception as e:
            print(f"  Error processing PMID {pmid}: {e}")
            continue

    print(f"\nExtraction complete:")
    print(f"  Cohort studies: {len(cohort_db.cohorts)}")
    print(f"  Family studies: {len(individual_db.studies)}")

    return cohort_db, individual_db
