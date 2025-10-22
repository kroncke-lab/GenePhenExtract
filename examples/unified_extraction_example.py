"""
Comprehensive examples for unified extraction (both cohort and individual data).

This module demonstrates the two extraction approaches:
1. Cohort-level: For papers reporting aggregate counts
2. Individual-level: For papers with detailed patient information

Both approaches can be used together to build comprehensive databases.
"""

from genephenextract import (
    UnifiedExtractor,
    ClaudeExtractor,
    extract_gene_data,
    CohortData,
    FamilyStudy,
    GeneticCohortDatabase,
    VariantPenetranceDatabase
)


# =============================================================================
# Example 1: Cohort-level extraction (aggregate counts)
# =============================================================================

def example_1_cohort_extraction():
    """Extract cohort-level data from a paper reporting aggregate counts."""

    print("=" * 80)
    print("Example 1: Cohort-level extraction")
    print("=" * 80)

    # Sample text from a paper reporting aggregate counts
    cohort_text = """
    We studied 50 unrelated probands with heterozygous KCNH2 variants.
    35 patients (70%) presented with long QT syndrome (QTc > 460ms).
    12 patients (24%) experienced syncope.
    8 patients (16%) had cardiac arrest.
    15 patients (30%) were asymptomatic at diagnosis.

    We also studied 20 family members who were heterozygous carriers.
    8 of these carriers (40%) had long QT syndrome.
    12 carriers (60%) were asymptomatic.
    """

    # Extract with unified extractor
    extractor = UnifiedExtractor(llm_extractor=ClaudeExtractor())
    result = extractor.extract(cohort_text, pmid="12345678", gene="KCNH2")

    # Result will be CohortData or list of CohortData
    if isinstance(result, CohortData):
        cohorts = [result]
    else:
        cohorts = result

    for cohort in cohorts:
        print(f"\nCohort: {cohort.genotype} carriers")
        print(f"Total carriers: {cohort.total_carriers}")
        print(f"Population: {cohort.population or 'Not specified'}")

        for pc in cohort.phenotype_counts:
            affected = pc.affected_count
            unaffected = pc.get_unaffected_count(cohort.total_carriers)
            frequency = affected / cohort.total_carriers

            print(f"\n  {pc.phenotype}:")
            print(f"    Affected: {affected}")
            print(f"    Unaffected: {unaffected}")
            print(f"    Frequency: {frequency:.1%}")


# =============================================================================
# Example 2: Individual-level extraction (detailed patient data)
# =============================================================================

def example_2_individual_extraction():
    """Extract individual-level data from a paper with detailed pedigrees."""

    print("\n" + "=" * 80)
    print("Example 2: Individual-level extraction")
    print("=" * 80)

    # Sample text from a family study with individual details
    family_text = """
    We identified a family with a heterozygous KCNH2 p.Tyr54Asn variant.

    The proband (III-2) is a 23-year-old male who presented with syncope at age 18.
    ECG showed QTc of 480ms. He carries the heterozygous variant.

    His mother (II-1) is a 45-year-old female, also heterozygous for the variant.
    She is asymptomatic with normal QTc (420ms).

    His father (II-2) is 47 years old and does not carry the variant.
    He has no cardiac symptoms.

    The proband's sister (III-1) is 25 years old, heterozygous carrier.
    She was diagnosed with long QT syndrome at age 20 after experiencing palpitations.
    Her QTc is 475ms.
    """

    extractor = UnifiedExtractor(llm_extractor=ClaudeExtractor())
    result = extractor.extract(family_text, pmid="87654321", gene="KCNH2")

    # Result will be a FamilyStudy
    if isinstance(result, FamilyStudy):
        print(f"\nFamily Study: {result.gene} {result.variant}")
        print(f"Total individuals: {len(result.individuals)}")
        print(f"Carriers: {len(result.get_carriers())}")
        print(f"Affected carriers: {len(result.get_affected_carriers())}")
        print(f"Unaffected carriers: {len(result.get_unaffected_carriers())}")

        print("\nIndividual details:")
        for ind in result.individuals:
            carrier_status = "carrier" if ind.is_carrier() else "non-carrier"
            affected_status = "affected" if ind.affected else "unaffected"

            print(f"\n  {ind.individual_id} ({ind.relation or 'unknown relation'}):")
            print(f"    Sex: {ind.sex or 'unknown'}")
            print(f"    Age: {ind.age or 'unknown'}")
            print(f"    Genotype: {ind.genotype} ({carrier_status})")
            print(f"    Status: {affected_status}")

            if ind.phenotypes:
                print(f"    Phenotypes:")
                for pheno in ind.phenotypes:
                    print(f"      - {pheno.phenotype}")

            if ind.age_at_onset:
                print(f"    Age at onset: {ind.age_at_onset}")


# =============================================================================
# Example 3: Extract all data for a gene (both cohort and individual)
# =============================================================================

def example_3_comprehensive_gene_extraction():
    """Extract both cohort and individual data for a gene from PubMed."""

    print("\n" + "=" * 80)
    print("Example 3: Comprehensive gene extraction")
    print("=" * 80)

    # This will search PubMed and extract from multiple papers
    extractor = UnifiedExtractor(llm_extractor=ClaudeExtractor())

    cohort_db, individual_db = extract_gene_data(
        gene="KCNH2",
        extractor=extractor,
        max_papers=20,  # Start small for testing
        date_range=(2020, 2024)  # Recent papers only
    )

    # Analyze cohort data
    print("\n" + "-" * 80)
    print("COHORT DATA SUMMARY")
    print("-" * 80)

    summary = cohort_db.get_summary(genotype="heterozygous")
    print(f"\nGene: {summary['gene']}")
    print(f"Total cohorts: {summary['total_cohorts']}")
    print(f"Total heterozygous carriers: {summary['total_carriers']}")

    print("\nPhenotype frequencies across all cohorts:")
    for phenotype, stats in summary['phenotype_statistics'].items():
        print(f"  {phenotype}:")
        print(f"    Affected: {stats['affected_count']}/{stats['total_carriers']}")
        print(f"    Frequency: {stats['frequency']:.1%}")

    # Analyze individual data
    print("\n" + "-" * 80)
    print("INDIVIDUAL DATA SUMMARY")
    print("-" * 80)

    print(f"\nTotal family studies: {len(individual_db.studies)}")
    print(f"Total individuals: {len(individual_db.get_all_individuals())}")
    print(f"Total carriers: {len(individual_db.get_all_carriers())}")
    print(f"Affected carriers: {len(individual_db.get_affected_carriers())}")
    print(f"Unaffected carriers: {len(individual_db.get_unaffected_carriers())}")

    # Compare by variant if we have data
    if individual_db.variants:
        print("\nBy variant:")
        for variant, data in individual_db.variants.items():
            affected = len(data.get_affected_carriers())
            total = len(data.get_all_carriers())
            if total > 0:
                frequency = affected / total
                print(f"  {variant}: {affected}/{total} affected ({frequency:.1%})")


# =============================================================================
# Example 4: Combining cohort and individual data
# =============================================================================

def example_4_combined_analysis():
    """Demonstrate how to analyze cohort and individual data together."""

    print("\n" + "=" * 80)
    print("Example 4: Combined analysis")
    print("=" * 80)

    # After running example 3, you'll have both databases
    # Here we show how to combine insights from both

    extractor = UnifiedExtractor(llm_extractor=ClaudeExtractor())
    cohort_db, individual_db = extract_gene_data(
        gene="KCNH2",
        extractor=extractor,
        max_papers=10
    )

    phenotype = "long QT syndrome"

    # Get counts from cohort data
    cohort_affected, cohort_total = cohort_db.get_aggregate_phenotype_counts(
        phenotype=phenotype,
        genotype="heterozygous"
    )

    # Get counts from individual data
    individual_affected = len(individual_db.get_affected_carriers(phenotype))
    individual_total = len(individual_db.get_all_carriers())

    # Combined totals
    total_affected = cohort_affected + individual_affected
    total_carriers = cohort_total + individual_total

    print(f"\nPhenotype: {phenotype}")
    print(f"Genotype: heterozygous")

    print(f"\nFrom cohort studies:")
    print(f"  Affected: {cohort_affected}")
    print(f"  Total: {cohort_total}")
    if cohort_total > 0:
        print(f"  Frequency: {cohort_affected/cohort_total:.1%}")

    print(f"\nFrom individual studies:")
    print(f"  Affected: {individual_affected}")
    print(f"  Total: {individual_total}")
    if individual_total > 0:
        print(f"  Frequency: {individual_affected/individual_total:.1%}")

    print(f"\nCombined:")
    print(f"  Affected: {total_affected}")
    print(f"  Total: {total_carriers}")
    if total_carriers > 0:
        print(f"  Overall frequency: {total_affected/total_carriers:.1%}")


# =============================================================================
# Example 5: Export data for further analysis
# =============================================================================

def example_5_export_data():
    """Export both cohort and individual data for analysis."""

    print("\n" + "=" * 80)
    print("Example 5: Export data")
    print("=" * 80)

    extractor = UnifiedExtractor(llm_extractor=ClaudeExtractor())
    cohort_db, individual_db = extract_gene_data(
        gene="KCNH2",
        extractor=extractor,
        max_papers=10
    )

    # Export cohort data
    cohort_db.export_to_json("kcnh2_cohort_data.json")
    print("\nCohort data exported to: kcnh2_cohort_data.json")

    # Export individual data as CSV
    individual_db.export_to_csv("kcnh2_individual_data.csv")
    print("Individual data exported to: kcnh2_individual_data.csv")

    # Also create a summary
    with open("kcnh2_summary.txt", "w") as f:
        f.write("=" * 80 + "\n")
        f.write("KCNH2 Genotype-Phenotype Data Summary\n")
        f.write("=" * 80 + "\n\n")

        # Cohort summary
        summary = cohort_db.get_summary(genotype="heterozygous")
        f.write("COHORT DATA\n")
        f.write("-" * 80 + "\n")
        f.write(f"Total cohorts: {summary['total_cohorts']}\n")
        f.write(f"Total carriers: {summary['total_carriers']}\n\n")
        f.write("Phenotype frequencies:\n")
        for phenotype, stats in summary['phenotype_statistics'].items():
            f.write(f"  {phenotype}: {stats['affected_count']}/{stats['total_carriers']} ({stats['frequency']:.1%})\n")

        # Individual summary
        f.write("\n\nINDIVIDUAL DATA\n")
        f.write("-" * 80 + "\n")
        f.write(f"Total studies: {len(individual_db.studies)}\n")
        f.write(f"Total individuals: {len(individual_db.get_all_individuals())}\n")
        f.write(f"Total carriers: {len(individual_db.get_all_carriers())}\n")
        f.write(f"Affected carriers: {len(individual_db.get_affected_carriers())}\n")
        f.write(f"Unaffected carriers: {len(individual_db.get_unaffected_carriers())}\n")

    print("Summary exported to: kcnh2_summary.txt")


if __name__ == "__main__":
    # Run individual examples
    # Uncomment the ones you want to run:

    # example_1_cohort_extraction()
    # example_2_individual_extraction()
    # example_3_comprehensive_gene_extraction()
    # example_4_combined_analysis()
    # example_5_export_data()

    print("\nTo run examples, uncomment the desired function calls in __main__")
