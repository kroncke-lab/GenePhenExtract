#!/usr/bin/env python3
"""
🔥 PENETRANCE WORKFLOW - THE MAIN USE CASE 🔥

Extract INDIVIDUAL family members to calculate TRUE penetrance.

Mission: Find heterozygous carriers (both affected AND unaffected) to calculate:
- How many het carriers total?
- How many are affected?
- How many are UNaffected (asymptomatic)?
- Penetrance = affected / total

This is what the project is ACTUALLY for!
"""

import json
import os
from pathlib import Path

from genephenextract import ClaudeExtractor, OpenAIExtractor
from genephenextract.penetrance_extractor import (
    PenetranceExtractor,
    extract_penetrance_for_gene,
)
from genephenextract.penetrance_models import VariantPenetranceDatabase


def example_1_basic_penetrance():
    """Example 1: Extract individuals and calculate penetrance."""
    print("=" * 70)
    print("Example 1: Individual-Level Extraction for Penetrance")
    print("=" * 70)

    # Set up LLM extractor
    if os.getenv("ANTHROPIC_API_KEY"):
        llm = ClaudeExtractor(model="claude-3-5-sonnet-20241022")
        print("Using Claude 3.5 Sonnet")
    elif os.getenv("OPENAI_API_KEY"):
        llm = OpenAIExtractor(model="gpt-4o")
        print("Using GPT-4o")
    else:
        print("ERROR: Set ANTHROPIC_API_KEY or OPENAI_API_KEY")
        return

    # Create penetrance extractor
    extractor = PenetranceExtractor(llm_extractor=llm)

    # Extract penetrance data for a gene
    gene = "KCNH2"
    print(f"\nExtracting penetrance data for {gene}...")
    print("This will extract INDIVIDUAL family members from each paper")
    print("Including both affected and UNaffected carriers!\n")

    studies = extract_penetrance_for_gene(
        gene=gene,
        extractor=extractor,
        max_papers=10,  # Start with 10 papers
    )

    print(f"\n{'=' * 70}")
    print("RESULTS")
    print(f"{'=' * 70}")
    print(f"Extracted {len(studies)} family/cohort studies\n")

    # Show results per study
    for i, study in enumerate(studies[:5], 1):  # Show first 5
        print(f"\n{i}. PMID {study.pmid}: {study.title}")
        print(f"   Variant: {study.variant}")
        print(f"   Individuals: {len(study.individuals)}")
        print(f"   Carriers: {len(study.get_carriers())}")
        print(f"     - Heterozygous: {len(study.get_heterozygous_carriers())}")
        print(f"     - Affected: {len(study.get_affected_carriers())}")
        print(f"     - UNaffected: {len(study.get_unaffected_carriers())}")

        penetrance = study.calculate_penetrance()
        if penetrance is not None:
            print(f"   Penetrance: {penetrance:.1%}")

        # Show some individuals
        print(f"   Sample individuals:")
        for ind in study.individuals[:3]:
            status = "AFFECTED" if ind.affected else "unaffected"
            phenos = [p.phenotype for p in ind.phenotypes]
            print(
                f"     - {ind.individual_id} ({ind.genotype}): {status} - {phenos}"
            )


def example_2_aggregate_penetrance():
    """Example 2: Aggregate penetrance across multiple papers."""
    print("\n" + "=" * 70)
    print("Example 2: Aggregate Penetrance Across Papers")
    print("=" * 70)

    if not os.getenv("ANTHROPIC_API_KEY"):
        print("Skipping: requires ANTHROPIC_API_KEY")
        return

    llm = ClaudeExtractor()
    extractor = PenetranceExtractor(llm_extractor=llm)

    # Extract data
    gene = "KCNH2"
    print(f"\nExtracting penetrance data for {gene}...")

    studies = extract_penetrance_for_gene(
        gene=gene, extractor=extractor, max_papers=20
    )

    # Filter to a specific variant (optional)
    # For demonstration, take the most common variant
    variant_counts = {}
    for study in studies:
        variant_counts[study.variant] = variant_counts.get(study.variant, 0) + 1

    if not variant_counts:
        print("No variants extracted")
        return

    target_variant = max(variant_counts, key=variant_counts.get)

    print(f"\nFocusing on: {target_variant}")
    print(f"Found in {variant_counts[target_variant]} studies")

    # Create penetrance database for this variant
    db = VariantPenetranceDatabase(
        variant=target_variant,
        gene=gene,
        genotype_filter="heterozygous",  # Focus on het carriers
    )

    # Add studies
    for study in studies:
        if study.variant == target_variant:
            db.add_study(study)

    # Get summary
    summary = db.get_summary()

    print(f"\n{'=' * 70}")
    print(f"PENETRANCE SUMMARY: {target_variant} (heterozygous carriers)")
    print(f"{'=' * 70}")
    print(f"Studies: {summary['n_studies']}")
    print(f"Total heterozygous carriers: {summary['n_total_carriers']}")
    print(f"  - Affected: {summary['n_affected_carriers']}")
    print(f"  - UNaffected: {summary['n_unaffected_carriers']}")
    print(f"\nOverall Penetrance: {summary['overall_penetrance']:.1%}")

    print(f"\nPenetrance by phenotype:")
    for pheno, penet in sorted(
        summary["penetrance_by_phenotype"].items(),
        key=lambda x: x[1],
        reverse=True,
    ):
        print(f"  {pheno}: {penet:.1%}")

    # Export individual-level data
    output_file = "penetrance_individuals.csv"
    db.export_to_csv(output_file)
    print(f"\n✅ Exported individual-level data to {output_file}")


def example_3_analyze_individuals():
    """Example 3: Detailed individual-level analysis."""
    print("\n" + "=" * 70)
    print("Example 3: Individual-Level Analysis")
    print("=" * 70)

    csv_file = "penetrance_individuals.csv"

    if not Path(csv_file).exists():
        print(f"{csv_file} not found. Run example 2 first.")
        return

    try:
        import pandas as pd
    except ImportError:
        print("pandas required. Install with: pip install pandas")
        return

    # Load data
    df = pd.read_csv(csv_file)

    print(f"\nLoaded {len(df)} individual records")

    # Filter to carriers only
    carriers = df[df["is_carrier"] == True].copy()

    print(f"Carriers: {len(carriers)}")
    print(f"  - Heterozygous: {len(carriers[carriers['is_heterozygous']])}")
    print(f"  - Affected: {len(carriers[carriers['affected']])}")
    print(f"  - UNaffected: {len(carriers[~carriers['affected']])}")

    # Penetrance calculation
    het_carriers = carriers[carriers["is_heterozygous"]]
    affected_het = het_carriers[het_carriers["affected"]]

    overall_penetrance = len(affected_het) / len(het_carriers)
    print(f"\nOverall penetrance (het): {overall_penetrance:.1%}")

    # Penetrance by phenotype
    print("\nPenetrance by phenotype:")
    phenotype_penetrance = {}

    for phenotype in het_carriers["phenotype"].dropna().unique():
        affected_with_pheno = het_carriers[
            (het_carriers["affected"]) & (het_carriers["phenotype"] == phenotype)
        ]
        penetrance = len(affected_with_pheno) / len(het_carriers)
        phenotype_penetrance[phenotype] = penetrance

    for pheno, penet in sorted(
        phenotype_penetrance.items(), key=lambda x: x[1], reverse=True
    ):
        print(f"  {pheno}: {penet:.1%}")

    # Age analysis
    print("\nAge distribution:")
    print(f"  Mean age: {carriers['age'].mean():.1f} years")
    print(f"  Mean age at onset: {carriers['age_at_onset'].mean():.1f} years")

    # Sex distribution
    print("\nSex distribution:")
    print(carriers["sex"].value_counts())

    # Family structure
    print("\nRelationships:")
    print(carriers["relation"].value_counts().head(10))


def example_4_compare_variants():
    """Example 4: Compare penetrance between variants."""
    print("\n" + "=" * 70)
    print("Example 4: Compare Penetrance Between Variants")
    print("=" * 70)

    if not os.getenv("ANTHROPIC_API_KEY"):
        print("Skipping: requires ANTHROPIC_API_KEY")
        return

    llm = ClaudeExtractor()
    extractor = PenetranceExtractor(llm_extractor=llm)

    gene = "KCNH2"
    studies = extract_penetrance_for_gene(
        gene=gene, extractor=extractor, max_papers=30
    )

    # Group by variant
    variants = {}
    for study in studies:
        if study.variant not in variants:
            variants[study.variant] = []
        variants[study.variant].append(study)

    print(f"\nFound {len(variants)} unique variants in {gene}\n")

    # Calculate penetrance for each variant
    variant_penetrance = []

    for variant, variant_studies in variants.items():
        db = VariantPenetranceDatabase(
            variant=variant, gene=gene, genotype_filter="heterozygous"
        )

        for study in variant_studies:
            db.add_study(study)

        summary = db.get_summary()

        if summary["n_total_carriers"] >= 3:  # At least 3 carriers
            variant_penetrance.append(
                {
                    "variant": variant,
                    "n_studies": summary["n_studies"],
                    "n_carriers": summary["n_total_carriers"],
                    "n_affected": summary["n_affected_carriers"],
                    "penetrance": summary["overall_penetrance"],
                }
            )

    # Sort by penetrance
    variant_penetrance.sort(key=lambda x: x["penetrance"], reverse=True)

    print("Variant Penetrance Comparison (heterozygous):")
    print("-" * 70)
    for vp in variant_penetrance[:10]:  # Top 10
        print(f"{vp['variant']}")
        print(
            f"  Studies: {vp['n_studies']}, Carriers: {vp['n_carriers']}, "
            f"Affected: {vp['n_affected']}, Penetrance: {vp['penetrance']:.1%}"
        )


def example_5_export_summary_table():
    """Example 5: Create publication-ready summary table."""
    print("\n" + "=" * 70)
    print("Example 5: Create Summary Table for Publication")
    print("=" * 70)

    csv_file = "penetrance_individuals.csv"

    if not Path(csv_file).exists():
        print(f"{csv_file} not found. Run example 2 first.")
        return

    try:
        import pandas as pd
    except ImportError:
        print("pandas required")
        return

    df = pd.read_csv(csv_file)

    # Create summary table grouped by variant
    summary_rows = []

    for variant in df["variant"].unique():
        variant_df = df[df["variant"] == variant]

        # Get heterozygous carriers
        het = variant_df[variant_df["is_heterozygous"]]

        if len(het) == 0:
            continue

        n_total = len(het)
        n_affected = len(het[het["affected"]])
        n_unaffected = len(het[~het["affected"]])
        penetrance = n_affected / n_total if n_total > 0 else 0

        # Get top phenotypes
        phenotypes = (
            het[het["affected"]]["phenotype"]
            .value_counts()
            .head(3)
            .index.tolist()
        )

        summary_rows.append(
            {
                "Variant": variant,
                "Gene": het["gene"].iloc[0],
                "Total Het Carriers": n_total,
                "Affected": n_affected,
                "Unaffected": n_unaffected,
                "Penetrance": f"{penetrance:.1%}",
                "Top Phenotypes": ", ".join(phenotypes),
                "N Studies": het["pmid"].nunique(),
            }
        )

    summary_df = pd.DataFrame(summary_rows)
    summary_df = summary_df.sort_values("Total Het Carriers", ascending=False)

    print("\nSummary Table:")
    print(summary_df.to_string(index=False))

    # Save
    summary_df.to_csv("penetrance_summary_table.csv", index=False)
    print("\n✅ Saved to penetrance_summary_table.csv")


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("🔥 PENETRANCE WORKFLOW - INDIVIDUAL-LEVEL EXTRACTION 🔥")
    print("=" * 70)
    print("\nTHIS IS THE CORE USE CASE:")
    print("Extract individual family members (affected AND unaffected)")
    print("to calculate TRUE penetrance")
    print("=" * 70)

    print("\nSet API key first:")
    print("  export ANTHROPIC_API_KEY='...'  # Recommended")
    print("  export OPENAI_API_KEY='...'")

    # Run examples
    example_1_basic_penetrance()  # THE MAIN WORKFLOW
    example_2_aggregate_penetrance()  # Aggregate across papers
    example_3_analyze_individuals()  # Detailed analysis
    example_4_compare_variants()  # Compare variants
    example_5_export_summary_table()  # Publication-ready table

    print("\n" + "=" * 70)
    print("✅ Examples complete!")
    print("\nNext steps:")
    print("  1. Review penetrance_individuals.csv")
    print("  2. Review penetrance_summary_table.csv")
    print("  3. Calculate penetrance for your variants")
    print("=" * 70)
