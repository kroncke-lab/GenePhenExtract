#!/usr/bin/env python3
"""
Example script demonstrating multi-LLM support and cost optimization.

This script shows:
1. Using different LLM providers
2. Two-stage extraction with filtering
3. Cost tracking and comparison
4. PDF integration
"""

import json
import os
from pathlib import Path

from genephenextract import (
    ClaudeExtractor,
    ExtractionPipeline,
    GeminiExtractor,
    MockExtractor,
    MultiStageExtractor,
    OpenAIExtractor,
    PipelineInput,
    PubMedClient,
    RelevanceFilter,
)


def example_1_basic_extractors():
    """Example 1: Compare different LLM extractors."""
    print("=" * 60)
    print("Example 1: Basic Extractor Comparison")
    print("=" * 60)

    # Sample query
    query = "KCNH2 AND long QT syndrome"
    max_results = 2

    client = PubMedClient()

    # Test with different extractors
    extractors = {
        "Mock (free, instant)": MockExtractor(),
    }

    # Add real extractors if API keys are available
    if os.getenv("OPENAI_API_KEY"):
        extractors["OpenAI GPT-4o-mini ($)"] = OpenAIExtractor(model="gpt-4o-mini")

    if os.getenv("ANTHROPIC_API_KEY"):
        extractors["Claude 3.5 Sonnet ($$$)"] = ClaudeExtractor(
            model="claude-3-5-sonnet-20241022"
        )

    if os.getenv("GOOGLE_API_KEY"):
        extractors["Gemini 1.5 Flash ($)"] = GeminiExtractor(model="gemini-1.5-flash")

    for name, extractor in extractors.items():
        print(f"\n--- Using {name} ---")

        with ExtractionPipeline(pubmed_client=client, extractor=extractor) as pipeline:
            results = pipeline.run(PipelineInput(query=query, max_results=max_results))

        for result in results:
            print(f"PMID: {result.pmid}")
            print(f"  Variant: {result.variant}")
            print(f"  Phenotypes: {[p.phenotype for p in result.phenotypes]}")


def example_2_cost_optimization():
    """Example 2: Two-stage extraction for cost savings."""
    print("\n" + "=" * 60)
    print("Example 2: Cost Optimization with Filtering")
    print("=" * 60)

    # Skip if no API keys
    if not os.getenv("OPENAI_API_KEY") or not os.getenv("ANTHROPIC_API_KEY"):
        print("Skipping: requires OPENAI_API_KEY and ANTHROPIC_API_KEY")
        return

    query = "genetics"  # Broad query will return many irrelevant articles
    max_results = 20

    # Cheap filter
    relevance_filter = RelevanceFilter(provider="openai", model="gpt-4o-mini")

    # Expensive extractor
    expensive_extractor = ClaudeExtractor(model="claude-3-5-sonnet-20241022")

    # Combine
    multi_stage = MultiStageExtractor(
        filter=relevance_filter, extractor=expensive_extractor, min_confidence=0.7
    )

    client = PubMedClient()

    print(f"\nProcessing {max_results} articles with two-stage extraction...")
    print("Stage 1: Cheap filter (gpt-4o-mini)")
    print("Stage 2: Expensive extraction (claude-3-5-sonnet) if relevant")

    with ExtractionPipeline(pubmed_client=client, extractor=multi_stage) as pipeline:
        results = pipeline.run(PipelineInput(query=query, max_results=max_results))

    # Show statistics
    stats = multi_stage.get_stats()
    total = stats["extracted"] + stats["skipped"]

    print(f"\n--- Cost Optimization Results ---")
    print(f"Total articles: {total}")
    print(f"Passed filter (extracted): {stats['extracted']}")
    print(f"Filtered out (skipped): {stats['skipped']}")

    if total > 0:
        savings_pct = 100 * stats["skipped"] / total
        print(f"Cost savings: {savings_pct:.1f}%")

        # Estimate costs (rough approximation)
        avg_abstract_tokens = 300
        filter_cost_per_1m = 0.15  # gpt-4o-mini
        extract_cost_per_1m = 3.00  # claude-3-5-sonnet

        without_filter = (total * avg_abstract_tokens * extract_cost_per_1m) / 1_000_000
        with_filter = (
            total * avg_abstract_tokens * filter_cost_per_1m / 1_000_000
            + stats["extracted"] * avg_abstract_tokens * extract_cost_per_1m / 1_000_000
        )

        print(f"\nEstimated costs:")
        print(f"  Without filtering: ${without_filter:.4f}")
        print(f"  With filtering: ${with_filter:.4f}")
        print(f"  Savings: ${without_filter - with_filter:.4f}")

    # Show sample results
    print(f"\n--- Sample Extracted Results ---")
    for result in results[:3]:
        if result.variant:  # Skip filtered-out articles
            print(f"\nPMID: {result.pmid}")
            print(f"  Title: {result.title}")
            print(f"  Variant: {result.variant}")


def example_3_pdf_integration():
    """Example 3: Extract from PDF files."""
    print("\n" + "=" * 60)
    print("Example 3: PDF Integration")
    print("=" * 60)

    from genephenextract import extract_text_from_pdf

    # This example uses a sample PDF - replace with your own
    pdf_path = Path("sample_paper.pdf")

    if not pdf_path.exists():
        print(f"PDF not found: {pdf_path}")
        print("Create a sample PDF or provide your own path")
        return

    print(f"Extracting text from: {pdf_path}")
    text = extract_text_from_pdf(pdf_path)

    print(f"Extracted {len(text)} characters")
    print(f"\nFirst 500 characters:")
    print(text[:500])

    # Use extracted text with any extractor
    if os.getenv("OPENAI_API_KEY"):
        print("\nRunning extraction on PDF content...")
        extractor = OpenAIExtractor(model="gpt-4o-mini")
        result = extractor.extract(text, pmid="PDF")

        print(f"\nExtracted from PDF:")
        print(f"  Variant: {result.variant}")
        print(f"  Phenotypes: {[p.phenotype for p in result.phenotypes]}")
    else:
        print("Set OPENAI_API_KEY to run extraction")


def example_4_full_text_vs_abstract():
    """Example 4: Compare extraction from abstract vs full-text."""
    print("\n" + "=" * 60)
    print("Example 4: Full-Text vs Abstract Comparison")
    print("=" * 60)

    pmid = "17310262"  # A PMID that likely has full-text

    if not os.getenv("OPENAI_API_KEY"):
        print("Skipping: requires OPENAI_API_KEY")
        return

    client = PubMedClient()
    extractor = OpenAIExtractor(model="gpt-4o-mini")

    # Extract from abstract
    print(f"\n--- Extracting from abstract (PMID: {pmid}) ---")
    abstract = client.fetch_abstract(pmid)
    if abstract:
        result_abstract = extractor.extract(abstract, pmid=pmid)
        print(f"Variant: {result_abstract.variant}")
        print(f"Phenotypes: {len(result_abstract.phenotypes)}")

    # Try full-text
    print(f"\n--- Attempting full-text extraction ---")
    full_text = client.fetch_full_text(pmid)
    if full_text:
        print(f"Full-text available: {len(full_text)} characters")
        result_fulltext = extractor.extract(full_text, pmid=pmid)
        print(f"Variant: {result_fulltext.variant}")
        print(f"Phenotypes: {len(result_fulltext.phenotypes)}")

        print(f"\n--- Comparison ---")
        print(f"Abstract phenotypes: {len(result_abstract.phenotypes)}")
        print(f"Full-text phenotypes: {len(result_fulltext.phenotypes)}")

        improvement = len(result_fulltext.phenotypes) - len(result_abstract.phenotypes)
        if improvement > 0:
            print(f"Full-text provided {improvement} additional phenotypes!")
    else:
        print("Full-text not available for this PMID")


def example_5_batch_with_resume():
    """Example 5: Batch processing with resume capability."""
    print("\n" + "=" * 60)
    print("Example 5: Batch Processing with Resume")
    print("=" * 60)

    pmids = ["12345678", "87654321", "11111111", "22222222"]
    output_file = Path("batch_results.json")

    # Load existing results
    existing_results = []
    processed_pmids = set()

    if output_file.exists():
        with open(output_file) as f:
            existing_results = json.load(f)
            processed_pmids = {r["pmid"] for r in existing_results}
        print(f"Resuming: found {len(existing_results)} existing results")

    # Filter to unprocessed PMIDs
    remaining_pmids = [p for p in pmids if p not in processed_pmids]

    if not remaining_pmids:
        print("All PMIDs already processed!")
        return

    print(f"Processing {len(remaining_pmids)} remaining PMIDs...")

    # Use mock extractor for demo (replace with real extractor)
    extractor = MockExtractor()
    client = PubMedClient()

    for i, pmid in enumerate(remaining_pmids, 1):
        print(f"  {i}/{len(remaining_pmids)}: {pmid}")

        try:
            with ExtractionPipeline(pubmed_client=client, extractor=extractor) as pipeline:
                result = pipeline.run(PipelineInput(pmids=[pmid]))[0]
                existing_results.append(result.to_dict())

            # Save after each extraction (in case of interruption)
            with open(output_file, "w") as f:
                json.dump(existing_results, f, indent=2)

        except Exception as e:
            print(f"    Error: {e}")
            continue

    print(f"\nCompleted! Results saved to {output_file}")


if __name__ == "__main__":
    print("GenePhenExtract Multi-LLM Examples")
    print("=" * 60)
    print("\nSet environment variables for API keys:")
    print("  export OPENAI_API_KEY='...'")
    print("  export ANTHROPIC_API_KEY='...'")
    print("  export GOOGLE_API_KEY='...'")

    # Run examples
    example_1_basic_extractors()
    example_2_cost_optimization()
    example_3_pdf_integration()
    example_4_full_text_vs_abstract()
    example_5_batch_with_resume()

    print("\n" + "=" * 60)
    print("Examples complete!")
