"""Gene-centric extraction pipeline for variant-phenotype associations."""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

from .extraction import BaseExtractor
from .models import ExtractionResult, PipelineInput
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

logger = logging.getLogger(__name__)


class GeneCentricPipeline:
    """Extract variant-phenotype associations for specific genes.

    This pipeline is optimized for the core use case:
    Extract phenotypes for individuals heterozygous for variants in specific genes.
    """

    def __init__(
        self,
        extractor: BaseExtractor,
        pubmed_client: Optional[PubMedClient] = None,
        filter_genotypes: Optional[List[str]] = None,
    ) -> None:
        """Initialize gene-centric pipeline.

        Args:
            extractor: LLM extractor to use
            pubmed_client: PubMed client (creates default if None)
            filter_genotypes: Only extract these genotypes (e.g., ["heterozygous"])
        """
        self.extractor = extractor
        self.pubmed_client = pubmed_client or PubMedClient()
        self.filter_genotypes = filter_genotypes or []
        self.pipeline = ExtractionPipeline(
            pubmed_client=self.pubmed_client, extractor=extractor
        )
        logger.info(
            "Initialized GeneCentricPipeline with genotype filter: %s",
            filter_genotypes,
        )

    def extract_for_genes(
        self,
        genes: List[str],
        max_papers_per_gene: int = 100,
        date_range: Optional[Tuple[int, int]] = None,
        prefer_full_text: bool = True,
    ) -> GeneVariantDatabase:
        """Extract all variants and phenotypes for specified genes.

        Args:
            genes: List of gene symbols (e.g., ["KCNH2", "SCN5A"])
            max_papers_per_gene: Maximum papers to process per gene
            date_range: Optional (start_year, end_year) to filter publications
            prefer_full_text: Use PMC full-text when available

        Returns:
            GeneVariantDatabase with all extracted associations
        """
        database = GeneVariantDatabase()

        for gene in genes:
            logger.info("Processing gene: %s", gene)

            # Build PubMed query for this gene
            query = self._build_gene_query(gene, date_range)

            # Run extraction
            payload = PipelineInput(query=query, max_results=max_papers_per_gene)

            results = self.pipeline.run(payload)

            logger.info(f"Retrieved {len(results)} results for {gene}")

            # Convert to associations
            associations = self._results_to_associations(results, target_gene=gene)

            # Filter by genotype if specified
            if self.filter_genotypes:
                associations = [
                    a for a in associations if a.genotype in self.filter_genotypes
                ]
                logger.info(
                    f"Filtered to {len(associations)} associations matching genotypes: {self.filter_genotypes}"
                )

            # Add to database
            for assoc in associations:
                database.add_association(assoc)

            logger.info(
                f"Added {len(associations)} associations for {gene} to database"
            )

        logger.info(
            f"Gene-centric extraction complete: {len(database.variants)} unique variants"
        )
        return database

    def extract_for_variant(
        self,
        variant: str,
        genotype: Optional[str] = None,
        max_papers: int = 50,
    ) -> List[VariantPhenotypeAssociation]:
        """Extract phenotypes for a specific variant.

        Args:
            variant: Variant string (e.g., "KCNH2 p.Ser906Leu")
            genotype: Optional genotype filter (e.g., "heterozygous")
            max_papers: Maximum papers to process

        Returns:
            List of variant-phenotype associations
        """
        # Parse variant to get gene and specific mutation
        parsed = parse_variant(variant)

        if not parsed.gene:
            raise ValueError(f"Could not extract gene from variant: {variant}")

        # Build query for this specific variant
        query = self._build_variant_query(parsed)

        # Run extraction
        payload = PipelineInput(query=query, max_results=max_papers)
        results = self.pipeline.run(payload)

        # Convert to associations
        associations = self._results_to_associations(results, target_gene=parsed.gene)

        # Filter by variant (normalized comparison)
        target_normalized = normalize_variant(variant)
        associations = [
            a
            for a in associations
            if normalize_variant(a.variant) == target_normalized
        ]

        # Filter by genotype if specified
        if genotype:
            associations = [a for a in associations if a.genotype == genotype]

        return associations

    def _build_gene_query(
        self, gene: str, date_range: Optional[Tuple[int, int]] = None
    ) -> str:
        """Build PubMed query for a gene.

        Args:
            gene: Gene symbol
            date_range: Optional (start_year, end_year)

        Returns:
            PubMed query string
        """
        # Core query: gene + variant/mutation terms
        query_parts = [
            f'("{gene}"[Gene] OR "{gene}"[Title/Abstract])',
            'AND (',
            '"variant"[Title/Abstract] OR "mutation"[Title/Abstract]',
            'OR "polymorphism"[Title/Abstract]',
            ')',
            'AND (',
            '"phenotype"[Title/Abstract] OR "clinical"[Title/Abstract]',
            'OR "patient"[Title/Abstract] OR "case"[Title/Abstract]',
            ')',
        ]

        # Add date range if specified
        if date_range:
            start_year, end_year = date_range
            query_parts.append(f'AND "{start_year}"[PDAT]:"{end_year}"[PDAT]')

        # Exclude common irrelevant article types
        query_parts.extend(
            [
                'NOT "review"[Publication Type]',
                'NOT ("in vitro"[Title/Abstract] AND NOT "patient"[Title/Abstract])',
            ]
        )

        return " ".join(query_parts)

    def _build_variant_query(self, parsed: ParsedVariant) -> str:
        """Build PubMed query for a specific variant.

        Args:
            parsed: Parsed variant

        Returns:
            PubMed query string
        """
        terms = [f'"{parsed.gene}"[Title/Abstract]']

        # Add protein change if available
        if parsed.protein_change:
            # Try different notations
            protein_clean = parsed.protein_change.replace("p.", "").replace("(", "").replace(")", "")
            terms.append(f'("{parsed.protein_change}"[Title/Abstract] OR "{protein_clean}"[Title/Abstract])')

        # Add cDNA change if available
        if parsed.cdna_change:
            terms.append(f'OR "{parsed.cdna_change}"[Title/Abstract]')

        query = " ".join(terms)
        query += ' AND ("phenotype"[Title/Abstract] OR "clinical"[Title/Abstract] OR "patient"[Title/Abstract])'

        return query

    def _results_to_associations(
        self, results: List[ExtractionResult], target_gene: Optional[str] = None
    ) -> List[VariantPhenotypeAssociation]:
        """Convert extraction results to variant-phenotype associations.

        Args:
            results: List of extraction results
            target_gene: Optional gene to filter by

        Returns:
            List of variant-phenotype associations
        """
        associations = []

        for result in results:
            if not result.variant:
                continue

            # Parse variant to get gene
            gene = extract_gene_from_variant(result.variant)

            # Filter by target gene if specified
            if target_gene and gene and gene != target_gene:
                continue

            if not gene:
                gene = target_gene or "UNKNOWN"

            # Get genotype (default to unknown if not specified)
            genotype = result.carrier_status or "unknown"

            # Create one association per phenotype
            for phenotype in result.phenotypes:
                assoc = VariantPhenotypeAssociation(
                    variant=result.variant,
                    gene=gene,
                    genotype=genotype,
                    phenotype=phenotype,
                    pmid=result.pmid,
                    age_at_onset=result.age,
                    title=result.title,
                    journal=result.journal,
                    publication_date=result.publication_date,
                )
                associations.append(assoc)

        return associations

    def close(self) -> None:
        """Clean up resources."""
        self.pipeline.close()

    def __enter__(self) -> "GeneCentricPipeline":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


class GeneVariantDatabase:
    """Database of variant-phenotype associations organized by variant."""

    def __init__(self) -> None:
        self.associations: List[VariantPhenotypeAssociation] = []
        self.variants: Dict[str, VariantSummary] = {}

    def add_association(self, assoc: VariantPhenotypeAssociation) -> None:
        """Add a variant-phenotype association.

        Args:
            assoc: Association to add
        """
        self.associations.append(assoc)

        # Create key: variant + genotype
        # This allows separate summaries for het vs hom
        key = f"{normalize_variant(assoc.variant)}|{assoc.genotype}"

        if key not in self.variants:
            self.variants[key] = VariantSummary(
                variant=normalize_variant(assoc.variant),
                gene=assoc.gene,
                genotype=assoc.genotype,
            )

        self.variants[key].add_association(assoc)

    def get_variant_summary(
        self, variant: str, genotype: Optional[str] = None
    ) -> Optional[VariantSummary]:
        """Get summary for a specific variant.

        Args:
            variant: Variant string
            genotype: Optional genotype filter

        Returns:
            VariantSummary or None if not found
        """
        normalized = normalize_variant(variant)

        if genotype:
            key = f"{normalized}|{genotype}"
            return self.variants.get(key)

        # If no genotype specified, return first match
        for key, summary in self.variants.items():
            if summary.variant == normalized:
                return summary

        return None

    def filter_by_gene(self, gene: str) -> List[VariantSummary]:
        """Get all variants for a specific gene.

        Args:
            gene: Gene symbol

        Returns:
            List of variant summaries
        """
        return [v for v in self.variants.values() if v.gene == gene]

    def filter_by_genotype(self, genotype: str) -> List[VariantSummary]:
        """Get all variants with specific genotype.

        Args:
            genotype: Genotype (e.g., "heterozygous")

        Returns:
            List of variant summaries
        """
        return [v for v in self.variants.values() if v.genotype == genotype]

    def to_dict(self) -> dict:
        """Export database to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "n_associations": len(self.associations),
            "n_unique_variants": len(self.variants),
            "variants": [v.to_dict() for v in self.variants.values()],
        }

    def to_dataframe(self):
        """Export to pandas DataFrame.

        Returns:
            DataFrame with one row per variant-genotype combination
        """
        try:
            import pandas as pd
        except ImportError:
            raise ImportError("pandas required for to_dataframe(). Install with: pip install pandas")

        rows = []
        for summary in self.variants.values():
            for pheno_name, pheno_summary in summary.phenotypes.items():
                rows.append({
                    "variant": summary.variant,
                    "gene": summary.gene,
                    "genotype": summary.genotype,
                    "phenotype": pheno_name,
                    "n_papers": pheno_summary.count,
                    "total_carriers": pheno_summary.total_carriers,
                    "total_affected": pheno_summary.total_affected,
                    "penetrance": pheno_summary.penetrance,
                    "mean_onset_age": pheno_summary.mean_onset_age,
                })

        return pd.DataFrame(rows)

    def export_to_csv(self, path: str) -> None:
        """Export database to CSV file.

        Args:
            path: Output file path
        """
        df = self.to_dataframe()
        df.to_csv(path, index=False)
        logger.info(f"Exported {len(df)} variant-phenotype associations to {path}")
