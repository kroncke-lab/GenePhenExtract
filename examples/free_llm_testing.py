"""
Examples of using FREE LLM APIs for testing GenePhenExtract.

This script demonstrates how to use free LLM providers:
1. Google Gemini (free tier)
2. Groq (free tier, ultra-fast)
3. Ollama (completely free, local)
"""

import os


# =============================================================================
# Example 1: Google Gemini (Free Tier - BEST FOR TESTING)
# =============================================================================

def example_1_gemini_free():
    """Use Google Gemini's generous free tier for testing.

    Free tier: 15 RPM, 1,500 requests/day, no credit card needed!
    """
    print("=" * 80)
    print("Example 1: Google Gemini Free Tier")
    print("=" * 80)

    from genephenextract import GeminiExtractor, UnifiedExtractor, extract_gene_data

    # Setup (one-time):
    # 1. Get free API key: https://makersuite.google.com/app/apikey
    # 2. export GOOGLE_API_KEY="your-key-here"

    if not os.getenv("GOOGLE_API_KEY"):
        print("\n⚠ GOOGLE_API_KEY not set!")
        print("Get your free key at: https://makersuite.google.com/app/apikey")
        print("Then run: export GOOGLE_API_KEY='your-key'")
        return

    # Use fastest free model
    extractor = UnifiedExtractor(llm_extractor=GeminiExtractor(
        model="gemini-1.5-flash"  # Fast and free!
    ))

    print("\n✓ Using Gemini 1.5 Flash (FREE)")
    print("  Rate limit: 15 requests/minute")
    print("  Daily limit: 1,500 requests")
    print("  Cost: $0")

    # Test with small gene list
    print("\nExtracting data for KCNH2...")
    cohort_db, individual_db = extract_gene_data(
        gene="KCNH2",
        extractor=extractor,
        max_papers=5  # Start small for testing
    )

    print(f"\n✓ Extraction complete!")
    print(f"  Cohort studies: {len(cohort_db.cohorts)}")
    print(f"  Family studies: {len(individual_db.studies)}")
    print(f"  Total cost: $0.00")


# =============================================================================
# Example 2: Groq (Free Tier - ULTRA FAST)
# =============================================================================

def example_2_groq_free():
    """Use Groq's free tier for ultra-fast extraction.

    Free tier: 30 RPM, 14,400 requests/day
    10x faster than OpenAI/Claude!
    """
    print("\n" + "=" * 80)
    print("Example 2: Groq Free Tier (Ultra Fast)")
    print("=" * 80)

    from genephenextract import GroqExtractor, UnifiedExtractor, extract_gene_data

    # Setup (one-time):
    # 1. Get free API key: https://console.groq.com/keys
    # 2. pip install groq
    # 3. export GROQ_API_KEY="your-key-here"

    if not os.getenv("GROQ_API_KEY"):
        print("\n⚠ GROQ_API_KEY not set!")
        print("Get your free key at: https://console.groq.com/keys")
        print("Then run:")
        print("  pip install groq")
        print("  export GROQ_API_KEY='your-key'")
        return

    # Use best free model
    extractor = UnifiedExtractor(llm_extractor=GroqExtractor(
        model="llama-3.1-70b-versatile"  # 70B model, ultra-fast!
    ))

    print("\n✓ Using Llama 3.1 70B on Groq (FREE)")
    print("  Rate limit: 30 requests/minute")
    print("  Daily limit: 14,400 requests")
    print("  Speed: 10x faster than OpenAI")
    print("  Cost: $0")

    # Process multiple genes (Groq can handle it!)
    print("\nExtracting data for 3 genes...")
    for gene in ["KCNH2", "SCN5A", "KCNQ1"]:
        cohort_db, individual_db = extract_gene_data(
            gene=gene,
            extractor=extractor,
            max_papers=10
        )
        print(f"\n{gene}: {len(cohort_db.cohorts)} cohorts, {len(individual_db.studies)} families")

    print(f"\n✓ All extractions complete!")
    print(f"  Total cost: $0.00")
    print(f"  With Groq's speed, you can process 100+ genes per day for free!")


# =============================================================================
# Example 3: Ollama (Completely Free, Local)
# =============================================================================

def example_3_ollama_local():
    """Use Ollama to run models locally - completely free, completely private.

    No API costs, no rate limits, works offline.
    """
    print("\n" + "=" * 80)
    print("Example 3: Ollama (Local, Completely Free)")
    print("=" * 80)

    from genephenextract import OllamaExtractor, UnifiedExtractor

    # Setup (one-time):
    # 1. Install Ollama: https://ollama.com
    # 2. ollama pull llama3.1:8b
    # 3. ollama serve

    try:
        extractor = UnifiedExtractor(llm_extractor=OllamaExtractor(
            model="llama3.1:8b"  # 8B model, ~4GB
        ))
    except ConnectionError:
        print("\n⚠ Cannot connect to Ollama!")
        print("Setup:")
        print("  1. Install: curl -fsSL https://ollama.com/install.sh | sh")
        print("  2. Download model: ollama pull llama3.1:8b")
        print("  3. Start server: ollama serve")
        return

    print("\n✓ Using Llama 3.1 8B locally (FREE)")
    print("  Rate limit: None (local)")
    print("  Daily limit: None (local)")
    print("  Privacy: 100% (data never leaves your machine)")
    print("  Cost: $0")

    # Use for sensitive data or offline work
    print("\nExtracting locally...")
    from genephenextract import extract_gene_data

    cohort_db, individual_db = extract_gene_data(
        gene="KCNH2",
        extractor=extractor,
        max_papers=5
    )

    print(f"\n✓ Extraction complete (all local)!")
    print(f"  Cohort studies: {len(cohort_db.cohorts)}")
    print(f"  Family studies: {len(individual_db.studies)}")
    print(f"  Total cost: $0.00")
    print(f"  Data privacy: 100% (never sent to any API)")


# =============================================================================
# Example 4: Compare Free Options
# =============================================================================

def example_4_compare_free_options():
    """Compare all free LLM options side-by-side."""
    print("\n" + "=" * 80)
    print("Example 4: Comparing Free LLM Options")
    print("=" * 80)

    from genephenextract import (
        GeminiExtractor,
        GroqExtractor,
        OllamaExtractor,
        UnifiedExtractor,
    )

    # Test data
    test_text = """
    We studied 50 patients with heterozygous KCNH2 p.Tyr54Asn variants.
    35 patients (70%) had long QT syndrome with QTc > 460ms.
    12 patients (24%) experienced syncope.
    15 patients (30%) were asymptomatic at diagnosis.
    """

    results = {}

    # Test Gemini (if available)
    if os.getenv("GOOGLE_API_KEY"):
        print("\nTesting Gemini...")
        import time
        start = time.time()
        try:
            extractor = UnifiedExtractor(llm_extractor=GeminiExtractor(
                model="gemini-1.5-flash"
            ))
            result = extractor.extract(test_text, pmid="TEST", gene="KCNH2")
            results["Gemini"] = {
                "success": True,
                "time": time.time() - start,
                "cost": "$0 (free tier)"
            }
            print(f"  ✓ Success in {results['Gemini']['time']:.2f}s")
        except Exception as e:
            print(f"  ✗ Failed: {e}")

    # Test Groq (if available)
    if os.getenv("GROQ_API_KEY"):
        print("\nTesting Groq...")
        import time
        start = time.time()
        try:
            extractor = UnifiedExtractor(llm_extractor=GroqExtractor(
                model="llama-3.1-70b-versatile"
            ))
            result = extractor.extract(test_text, pmid="TEST", gene="KCNH2")
            results["Groq"] = {
                "success": True,
                "time": time.time() - start,
                "cost": "$0 (free tier)"
            }
            print(f"  ✓ Success in {results['Groq']['time']:.2f}s")
        except Exception as e:
            print(f"  ✗ Failed: {e}")

    # Test Ollama (if available)
    print("\nTesting Ollama...")
    import time
    start = time.time()
    try:
        extractor = UnifiedExtractor(llm_extractor=OllamaExtractor(
            model="llama3.1:8b"
        ))
        result = extractor.extract(test_text, pmid="TEST", gene="KCNH2")
        results["Ollama"] = {
            "success": True,
            "time": time.time() - start,
            "cost": "$0 (always free)"
        }
        print(f"  ✓ Success in {results['Ollama']['time']:.2f}s")
    except Exception as e:
        print(f"  ✗ Failed: {e}")

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    for provider, info in results.items():
        print(f"\n{provider}:")
        print(f"  Speed: {info['time']:.2f}s")
        print(f"  Cost: {info['cost']}")

    if not results:
        print("\n⚠ No LLM providers configured!")
        print("\nSetup instructions:")
        print("  Gemini: https://makersuite.google.com/app/apikey")
        print("  Groq: https://console.groq.com/keys")
        print("  Ollama: https://ollama.com")


# =============================================================================
# Example 5: Free Tier Cost Optimization
# =============================================================================

def example_5_cost_optimization():
    """Use two-stage extraction to maximize free tier usage."""
    print("\n" + "=" * 80)
    print("Example 5: Cost Optimization with Free Tiers")
    print("=" * 80)

    from genephenextract import (
        GroqExtractor,
        RelevanceFilter,
        MultiStageExtractor,
    )

    if not os.getenv("GROQ_API_KEY"):
        print("\n⚠ GROQ_API_KEY not set!")
        print("Get your free key at: https://console.groq.com/keys")
        return

    # Stage 1: Fast filter with small model (ultra cheap)
    filter = RelevanceFilter(
        provider="groq",  # Use Groq for speed
        model="llama-3.1-8b-instant"  # Smallest, fastest
    )

    # Stage 2: Extract with larger model (only if relevant)
    extractor = MultiStageExtractor(
        filter=filter,
        extractor=GroqExtractor(model="llama-3.1-70b-versatile"),
        min_confidence=0.7
    )

    print("\n✓ Two-stage extraction configured:")
    print("  Stage 1: Filter with Llama 3.1 8B (ultra fast)")
    print("  Stage 2: Extract with Llama 3.1 70B (only if relevant)")
    print("\nThis saves ~75% of API calls by filtering irrelevant papers first!")

    # Use in pipeline
    from genephenextract import extract_gene_data, UnifiedExtractor

    unified = UnifiedExtractor(llm_extractor=extractor)

    print("\nProcessing KCNH2 with cost optimization...")
    cohort_db, individual_db = extract_gene_data(
        gene="KCNH2",
        extractor=unified,
        max_papers=20
    )

    print(f"\n✓ Complete!")
    print(f"  Papers processed: 20")
    print(f"  Estimated API calls saved: ~15 (75%)")
    print(f"  Total cost: $0 (free tier)")


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("GenePhenExtract - Free LLM Testing Examples")
    print("=" * 80)

    # Check which providers are available
    available = []
    if os.getenv("GOOGLE_API_KEY"):
        available.append("Gemini")
    if os.getenv("GROQ_API_KEY"):
        available.append("Groq")

    if not available:
        print("\n⚠ No API keys configured!")
        print("\nGet free API keys:")
        print("  Gemini: https://makersuite.google.com/app/apikey (NO credit card)")
        print("  Groq: https://console.groq.com/keys (NO credit card)")
        print("\nThen run:")
        print("  export GOOGLE_API_KEY='your-key'")
        print("  export GROQ_API_KEY='your-key'")
    else:
        print(f"\n✓ Available: {', '.join(available)}")

    print("\n" + "-" * 80)
    print("Run individual examples:")
    print("  python examples/free_llm_testing.py")
    print("\nOr import and call:")
    print("  from examples.free_llm_testing import example_1_gemini_free")
    print("  example_1_gemini_free()")
    print("-" * 80)

    # Uncomment to run specific examples:
    # example_1_gemini_free()
    # example_2_groq_free()
    # example_3_ollama_local()
    # example_4_compare_free_options()
    # example_5_cost_optimization()
