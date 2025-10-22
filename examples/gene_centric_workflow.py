#!/usr/bin/env python3
"""
Gene-centric workflow example - THE ideal workflow for the project's core mission.

Mission: Extract phenotypes for individuals HETEROZYGOUS for variants in specific genes.

This demonstrates the workflow you should actually use for variant curation.
"""

import json
import os
from pathlib import Path

from genephenextract import ClaudeExtractor, OpenAIExtractor
from genephenextract.gene_pipeline import GeneCentricPipeline


def example_1_heterozygous_only():
    """Example 1: Extract ONLY heterozygous carriers (the core use case)."""
    print("=" * 70)
    print("Example 1: Extract Phenotypes for Heterozygous Carriers Only")
    print("=" * 70)

    # Define genes of interest for your study
    genes = ["KCNH2", "SCN5A", "KCNQ1"]  # Long QT syndrome genes

    # Set up extractor (use Claude for best accuracy, or OpenAI for cost)
    if os.getenv("ANTHROPIC_API_KEY"):
        extractor = ClaudeExtractor(model="claude-3-5-sonnet-20241022")
        print("Using Claude 3.5 Sonnet (best accuracy)")
    elif os.getenv("OPENAI_API_KEY"):
        extractor = OpenAIExtractor(model="gpt-4o-mini")
        print("Using GPT-4o-mini (cost-effective)")
    else:
        print("ERROR: Set ANTHROPIC_API_KEY or OPENAI_API_KEY")
        return

    # Create gene-centric pipeline with HETEROZYGOUS-ONLY filter
    with GeneCentricPipeline(
        extractor=extractor,
        filter_genotypes=["heterozygous"],  # 🔥 THE KEY PARAMETER
    ) as pipeline:
        # Extract for all genes (only het carriers!)
        print(f"\nExtracting heterozygous carriers for: {', '.join(genes)}")
        print("This will:")
        print("  1. Search PubMed for each gene")
        print("  2. Extract variant and phenotype data")
        print("  3. FILTER to only heterozygous carriers")
        print("  4. Aggregate results per variant")

        database = pipeline.extract_for_genes(
            genes=genes,
            max_papers_per_gene=20,  # Adjust based on your needs
            date_range=(2010, 2024),  # Recent publications only
            prefer_full_text=True,  # Use PMC full-text when available
        )

    # Display results
    print(f"\n{'=' * 70}")
    print("RESULTS")
    print(f"{'=' * 70}")
    print(f"Total unique variants (het only): {len(database.variants)}")
    print(f"Total associations: {len(database.associations)}\n")

    # Show results for each gene
    for gene in genes:
        gene_variants = database.filter_by_gene(gene)
        print(f"\n{gene}: {len(gene_variants)} heterozygous variants")

        for variant_summary in gene_variants[:5]:  # Top 5 per gene
            print(f"\n  {variant_summary.variant}")
            print(f"    Papers: {variant_summary.n_papers}")
            print(f"    Heterozygous carriers: {variant_summary.total_carriers}")

            # Top phenotypes for THIS variant in heterozygous carriers
            print(f"    Top phenotypes (het carriers):")
            for pheno in variant_summary.top_phenotypes(n=3):
                pct = (
                    f"{pheno.penetrance:.1%}"
                    if pheno.penetrance
                    else f"{pheno.count} papers"
                )
                print(f"      - {pheno.name}: {pct}")

    # Export to CSV for analysis
    output_path = "heterozygous_variants.csv"
    database.export_to_csv(output_path)
    print(f"\n✅ Exported to {output_path}")


def example_2_compare_genotypes():
    """Example 2: Compare heterozygous vs homozygous phenotypes."""
    print("\n" + "=" * 70)
    print("Example 2: Compare Heterozygous vs Homozygous Phenotypes")
    print("=" * 70)

    if not os.getenv("ANTHROPIC_API_KEY"):
        print("Skipping: requires ANTHROPIC_API_KEY")
        return

    gene = "KCNH2"

    # Extract heterozygous carriers
    print(f"\nExtracting HETEROZYGOUS carriers for {gene}...")
    with GeneCentricPipeline(
        extractor=ClaudeExtractor(), filter_genotypes=["heterozygous"]
    ) as pipeline:
        het_database = pipeline.extract_for_genes(
            genes=[gene], max_papers_per_gene=30
        )

    # Extract homozygous carriers
    print(f"Extracting HOMOZYGOUS carriers for {gene}...")
    with GeneCentricPipeline(
        extractor=ClaudeExtractor(), filter_genotypes=["homozygous"]
    ) as pipeline:
        hom_database = pipeline.extract_for_genes(
            genes=[gene], max_papers_per_gene=30
        )

    print(f"\n{'=' * 70}")
    print("COMPARISON")
    print(f"{'=' * 70}")
    print(f"Heterozygous variants: {len(het_database.variants)}")
    print(f"Homozygous variants: {len(hom_database.variants)}")

    # Compare specific variant
    test_variant = None
    het_variants = het_database.filter_by_gene(gene)
    if het_variants:
        test_variant = het_variants[0].variant

        print(f"\nComparing: {test_variant}")

        het_summary = het_database.get_variant_summary(test_variant, "heterozygous")
        hom_summary = hom_database.get_variant_summary(test_variant, "homozygous")

        if het_summary:
            print("\n  Heterozygous carriers:")
            for pheno in het_summary.top_phenotypes(n=5):
                print(f"    - {pheno.name} ({pheno.count} papers)")

        if hom_summary:
            print("\n  Homozygous carriers:")
            for pheno in hom_summary.top_phenotypes(n=5):
                print(f"    - {pheno.name} ({pheno.count} papers)")


def example_3_specific_variant():
    """Example 3: Deep dive into a specific variant (het carriers)."""
    print("\n" + "=" * 70)
    print("Example 3: Extract for Specific Variant")
    print("=" * 70)

    if not os.getenv("ANTHROPIC_API_KEY"):
        print("Skipping: requires ANTHROPIC_API_KEY")
        return

    # Known variant to investigate
    variant = "KCNH2 p.Ser906Leu"

    print(f"\nInvestigating: {variant}")
    print("Extracting HETEROZYGOUS carriers only...")

    with GeneCentricPipeline(
        extractor=ClaudeExtractor(), filter_genotypes=["heterozygous"]
    ) as pipeline:
        # Extract for this specific variant
        associations = pipeline.extract_for_variant(
            variant=variant, genotype="heterozygous", max_papers=50
        )

    print(f"\nFound {len(associations)} heterozygous associations")
    print(f"From {len(set(a.pmid for a in associations))} unique papers\n")

    # Group phenotypes
    phenotype_counts = {}
    for assoc in associations:
        pheno = assoc.phenotype.phenotype
        phenotype_counts[pheno] = phenotype_counts.get(pheno, 0) + 1

    print("Phenotypes in heterozygous carriers:")
    for pheno, count in sorted(
        phenotype_counts.items(), key=lambda x: x[1], reverse=True
    ):
        print(f"  {pheno}: {count} papers")

    # Show some example associations
    print("\nExample associations:")
    for assoc in associations[:3]:
        print(f"\n  PMID {assoc.pmid}: {assoc.title}")
        print(f"    Phenotype: {assoc.phenotype.phenotype}")
        if assoc.age_at_onset:
            print(f"    Age at onset: {assoc.age_at_onset}")


def example_4_production_workflow():
    """Example 4: Production workflow with cost optimization."""
    print("\n" + "=" * 70)
    print("Example 4: Production Workflow (Cost-Optimized)")
    print("=" * 70)

    if not (os.getenv("OPENAI_API_KEY") and os.getenv("ANTHROPIC_API_KEY")):
        print("Skipping: requires both OPENAI_API_KEY and ANTHROPIC_API_KEY")
        return

    # Use FILTERING to save money
    from genephenextract import MultiStageExtractor, RelevanceFilter

    # Stage 1: Cheap filter
    relevance_filter = RelevanceFilter(provider="openai", model="gpt-4o-mini")

    # Stage 2: Expensive extractor (only if relevant)
    expensive_extractor = ClaudeExtractor(model="claude-3-5-sonnet-20241022")

    # Combine
    multi_stage = MultiStageExtractor(
        filter=relevance_filter,
        extractor=expensive_extractor,
        min_confidence=0.7,
    )

    # Process multiple genes, het only
    genes = ["KCNH2", "SCN5A", "KCNQ1", "KCNE1", "KCNE2"]

    print(f"\nProcessing {len(genes)} genes with cost optimization:")
    print("  - Cheap filter (gpt-4o-mini) screens all articles")
    print("  - Expensive extraction (Claude) only on relevant articles")
    print("  - Extracting HETEROZYGOUS carriers only\n")

    with GeneCentricPipeline(
        extractor=multi_stage, filter_genotypes=["heterozygous"]
    ) as pipeline:
        database = pipeline.extract_for_genes(
            genes=genes, max_papers_per_gene=50  # 250 total papers
        )

    # Show filter statistics
    if hasattr(multi_stage, "get_stats"):
        stats = multi_stage.get_stats()
        total = stats["extracted"] + stats["skipped"]
        if total > 0:
            savings_pct = 100 * stats["skipped"] / total
            print(f"Filter Statistics:")
            print(f"  Total articles: {total}")
            print(f"  Relevant (extracted): {stats['extracted']}")
            print(f"  Filtered out: {stats['skipped']}")
            print(f"  Cost savings: {savings_pct:.1f}%\n")

    print(f"Results:")
    print(f"  Unique heterozygous variants: {len(database.variants)}")

    # Export
    database.export_to_csv("production_results.csv")
    print(f"  ✅ Exported to production_results.csv")

    # Save detailed JSON
    output = {
        "genes": genes,
        "filter": "heterozygous",
        "database": database.to_dict(),
    }
    Path("production_results.json").write_text(json.dumps(output, indent=2))
    print(f"  ✅ Exported to production_results.json")


def example_5_load_and_analyze():
    """Example 5: Load exported CSV and analyze."""
    print("\n" + "=" * 70)
    print("Example 5: Analyze Exported Results")
    print("=" * 70)

    csv_file = "heterozygous_variants.csv"

    if not Path(csv_file).exists():
        print(f"{csv_file} not found. Run example 1 first.")
        return

    try:
        import pandas as pd
    except ImportError:
        print("pandas required. Install with: pip install pandas")
        return

    # Load data
    df = pd.read_csv(csv_file)

    print(f"\nLoaded {len(df)} variant-phenotype associations")
    print(f"Genes: {df['gene'].unique()}")
    print(f"Unique variants: {df['variant'].nunique()}")
    print(f"Unique phenotypes: {df['phenotype'].nunique()}")

    # Most common phenotypes across all heterozygous carriers
    print("\nTop 10 phenotypes in heterozygous carriers:")
    top_phenotypes = df.groupby("phenotype")["n_papers"].sum().sort_values(
        ascending=False
    )
    for pheno, count in top_phenotypes.head(10).items():
        print(f"  {pheno}: {count} papers")

    # Variants with highest penetrance
    print("\nVariants with highest penetrance (heterozygous):")
    high_penetrance = (
        df[df["penetrance"].notna()].sort_values("penetrance", ascending=False).head(10)
    )

    for _, row in high_penetrance.iterrows():
        print(
            f"  {row['variant']}: {row['phenotype']} ({row['penetrance']:.1%} penetrance)"
        )


if __name__ == "__main__":
    print("\n🧬 GENE-CENTRIC EXTRACTION WORKFLOW 🧬")
    print("=" * 70)
    print("Optimized for: Extract phenotypes for HETEROZYGOUS variant carriers")
    print("=" * 70)

    print("\nSet API keys first:")
    print("  export ANTHROPIC_API_KEY='...'  # For Claude (best accuracy)")
    print("  export OPENAI_API_KEY='...'     # For GPT (cost-effective)")

    # Run examples
    example_1_heterozygous_only()  # THE MAIN WORKFLOW
    example_2_compare_genotypes()
    example_3_specific_variant()
    example_4_production_workflow()  # For large-scale studies
    example_5_load_and_analyze()

    print("\n" + "=" * 70)
    print("✅ Examples complete!")
    print("\nNext steps:")
    print("  1. Review heterozygous_variants.csv")
    print("  2. Customize gene list for your study")
    print("  3. Adjust max_papers_per_gene based on your needs")
    print("  4. Use cost optimization (example 4) for large studies")
