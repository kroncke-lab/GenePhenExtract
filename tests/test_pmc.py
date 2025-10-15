#!/usr/bin/env python3
"""Test script for PMC full-text extraction."""

import pytest
from genephenextract import PubMedClient
from genephenextract.extraction import MockExtractor


@pytest.mark.integration
def test_pmc_full_text_retrieval():
    """Test PMC full-text retrieval functionality."""
    client = PubMedClient()
    pmcid = "PMC8234567"

    full_text = client.fetch_pmc_full_text(pmcid)

    # Verify we got text
    assert full_text is not None
    assert len(full_text) > 1000  # Should have substantial content

    # Verify basic structure
    assert "Abstract" in full_text or "abstract" in full_text.lower()


@pytest.mark.integration
def test_pmc_extraction_with_mock():
    """Test extraction on PMC full-text with MockExtractor."""
    client = PubMedClient()
    pmcid = "PMC8234567"

    full_text = client.fetch_pmc_full_text(pmcid)
    if not full_text:
        pytest.skip(f"Could not fetch full-text for {pmcid}")

    # Test extraction
    extractor = MockExtractor()
    result = extractor.extract(full_text, pmid=pmcid)

    assert result.pmid == pmcid
    assert result.variant is not None
    assert len(result.phenotypes) > 0


# Keep the script functionality
def test_pmc_extraction(pmcid: str, use_mock: bool = True, api_key: str = None):
    """
    Test extraction with PMC full-text.

    Args:
        pmcid: PMC ID (with or without 'PMC' prefix)
        use_mock: Whether to use MockExtractor (True) or Gemini (False)
        api_key: API key for Gemini (required if use_mock=False)
    """
    from genephenextract.extraction import GeminiExtractor
    import json

    client = PubMedClient()

    print(f"Fetching full-text for {pmcid}...")
    full_text = client.fetch_pmc_full_text(pmcid)

    if not full_text:
        print(f"❌ Could not retrieve full-text for {pmcid}")
        return None

    print(f"✓ Retrieved {len(full_text):,} characters")
    print(f"\nFirst 300 characters:\n{'-' * 50}")
    print(full_text[:300])
    print(f"{'-' * 50}\n")

    # Select extractor
    if use_mock:
        print("Using MockExtractor...")
        extractor = MockExtractor()
    else:
        if not api_key:
            print("❌ API key required for Gemini")
            return None
        print("Using GeminiExtractor...")
        extractor = GeminiExtractor(api_key=api_key)

    # Run extraction
    print("Running extraction...")
    result = extractor.extract(full_text, pmid=pmcid)

    print("\n" + "=" * 60)
    print("EXTRACTION RESULTS")
    print("=" * 60)

    print(json.dumps(result.to_dict(), indent=2))

    return result


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python test_pmc.py <PMCID> [--gemini API_KEY]")
        print("Example: python test_pmc.py PMC8234567")
        print("Example: python test_pmc.py PMC10026256 --gemini YOUR_API_KEY")
        sys.exit(1)

    pmcid = sys.argv[1]
    use_mock = True
    api_key = None

    if len(sys.argv) > 2 and sys.argv[2] == "--gemini":
        use_mock = False
        api_key = sys.argv[3] if len(sys.argv) > 3 else None

    test_pmc_extraction(pmcid, use_mock=use_mock, api_key=api_key)