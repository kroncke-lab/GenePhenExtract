"""Integration tests with real PubMed data.

These tests make real API calls to PubMed and should be run with
caution to avoid rate limiting. Use pytest -m integration to run them.
"""

import os
import time

import pytest

from genephenextract import ExtractionPipeline, PipelineInput, MockExtractor
from genephenextract.extraction import GeminiExtractor
from genephenextract.pubmed import PubMedClient


# Real PMIDs for testing (publicly available articles)
TEST_PMIDS = {
    "kcnh2_long_qt": "17310262",  # Well-known KCNH2 variant paper
    "recent": "38000000",  # A recent article (may or may not exist)
    "old": "10072428",  # Classic genetics paper
}


@pytest.fixture
def pubmed_client():
    """Create a PubMed client for integration tests."""
    return PubMedClient(timeout=30.0)


@pytest.fixture
def rate_limit():
    """Add delay between tests to avoid rate limiting."""
    yield
    time.sleep(1.0)  # Wait 1 second between tests


class TestPubMedSearch:
    """Integration tests for PubMed search functionality."""

    @pytest.mark.integration
    def test_search_returns_results(self, pubmed_client, rate_limit):
        """Should return PMIDs for a simple search query."""
        pmids = pubmed_client.search("KCNH2 AND long QT syndrome", retmax=5)

        assert isinstance(pmids, list)
        assert len(pmids) > 0
        assert all(isinstance(pmid, str) for pmid in pmids)

    @pytest.mark.integration
    def test_search_respects_max_results(self, pubmed_client, rate_limit):
        """Should respect the retmax parameter."""
        pmids = pubmed_client.search("heart", retmax=3)

        assert len(pmids) <= 3

    @pytest.mark.integration
    def test_search_with_complex_query(self, pubmed_client, rate_limit):
        """Should handle complex PubMed queries."""
        query = '("KCNH2"[Gene]) AND ("long QT syndrome"[MeSH Terms]) AND 2020:2023[pdat]'
        pmids = pubmed_client.search(query, retmax=10)

        assert isinstance(pmids, list)

    @pytest.mark.integration
    @pytest.mark.slow
    def test_search_with_large_retmax(self, pubmed_client, rate_limit):
        """Should handle large result sets."""
        pmids = pubmed_client.search("genetics", retmax=100)

        assert isinstance(pmids, list)
        # May return fewer than 100 depending on query


class TestPubMedFetchDetails:
    """Integration tests for fetching article details."""

    @pytest.mark.integration
    def test_fetch_single_article(self, pubmed_client, rate_limit):
        """Should fetch details for a single PMID."""
        pmid = TEST_PMIDS["old"]
        details = pubmed_client.fetch_details([pmid])

        assert pmid in details
        article = details[pmid]
        assert "title" in article
        assert "abstract" in article
        assert article["title"] is not None

    @pytest.mark.integration
    def test_fetch_multiple_articles(self, pubmed_client, rate_limit):
        """Should fetch details for multiple PMIDs at once."""
        pmids = [TEST_PMIDS["old"], TEST_PMIDS["kcnh2_long_qt"]]
        details = pubmed_client.fetch_details(pmids)

        assert len(details) >= 1  # At least one should be found
        for pmid in pmids:
            if pmid in details:
                assert details[pmid]["title"] is not None

    @pytest.mark.integration
    def test_fetch_details_includes_metadata(self, pubmed_client, rate_limit):
        """Should include journal and publication date."""
        pmid = TEST_PMIDS["old"]
        details = pubmed_client.fetch_details([pmid])

        article = details[pmid]
        assert "journal" in article
        assert "publication_date" in article

    @pytest.mark.integration
    def test_fetch_nonexistent_pmid(self, pubmed_client, rate_limit):
        """Should handle non-existent PMIDs gracefully."""
        pmids = ["99999999999"]  # Unlikely to exist
        details = pubmed_client.fetch_details(pmids)

        # Should return empty or skip the invalid PMID
        assert isinstance(details, dict)


class TestPubMedFullText:
    """Integration tests for full-text retrieval."""

    @pytest.mark.integration
    @pytest.mark.slow
    def test_pmid_to_pmcid_conversion(self, pubmed_client, rate_limit):
        """Should convert PMID to PMCID when available."""
        # Use a PMID that likely has a PMC version
        pmid = TEST_PMIDS["old"]
        pmcid = pubmed_client.pmid_to_pmcid(pmid)

        # May or may not have PMC version
        if pmcid:
            assert pmcid.startswith("PMC")
            assert pmcid[3:].isdigit()

    @pytest.mark.integration
    @pytest.mark.slow
    def test_fetch_full_text_when_available(self, pubmed_client, rate_limit):
        """Should fetch full-text when PMC version exists."""
        # Try with a known open-access article
        pmid = TEST_PMIDS["old"]
        full_text = pubmed_client.fetch_full_text(pmid)

        if full_text:
            assert isinstance(full_text, str)
            assert len(full_text) > 1000  # Should have substantial content
        else:
            # It's okay if full-text isn't available
            pytest.skip(f"Full-text not available for PMID {pmid}")

    @pytest.mark.integration
    @pytest.mark.slow
    def test_fetch_text_prefers_full_text(self, pubmed_client, rate_limit):
        """Should prefer full-text over abstract when requested."""
        pmid = TEST_PMIDS["old"]

        text, source = pubmed_client.fetch_text(pmid, prefer_full_text=True)

        assert isinstance(text, str)
        assert len(text) > 0
        assert source in ["full_text", "abstract"]

    @pytest.mark.integration
    def test_fetch_text_abstract_fallback(self, pubmed_client, rate_limit):
        """Should fall back to abstract when full-text unavailable."""
        pmid = TEST_PMIDS["kcnh2_long_qt"]

        text, source = pubmed_client.fetch_text(pmid, prefer_full_text=False)

        assert isinstance(text, str)
        assert source == "abstract"


class TestEndToEndPipeline:
    """End-to-end integration tests using the full pipeline."""

    @pytest.mark.integration
    def test_pipeline_with_query(self, pubmed_client, rate_limit):
        """Should run full pipeline from query to results."""
        pipeline = ExtractionPipeline(
            pubmed_client=pubmed_client, extractor=MockExtractor()
        )

        payload = PipelineInput(query="KCNH2 AND long QT", max_results=2)
        results = pipeline.run(payload)

        assert len(results) > 0
        for result in results:
            assert result.pmid is not None
            assert result.variant is not None
            assert result.abstract is not None

    @pytest.mark.integration
    def test_pipeline_with_specific_pmids(self, pubmed_client, rate_limit):
        """Should process specific PMIDs."""
        pipeline = ExtractionPipeline(
            pubmed_client=pubmed_client, extractor=MockExtractor()
        )

        pmids = [TEST_PMIDS["old"]]
        payload = PipelineInput(pmids=pmids)
        results = pipeline.run(payload)

        assert len(results) == 1
        assert results[0].pmid == TEST_PMIDS["old"]

    @pytest.mark.integration
    def test_pipeline_enriches_with_metadata(self, pubmed_client, rate_limit):
        """Should enrich results with article metadata."""
        pipeline = ExtractionPipeline(
            pubmed_client=pubmed_client, extractor=MockExtractor()
        )

        pmids = [TEST_PMIDS["old"]]
        payload = PipelineInput(pmids=pmids)
        results = pipeline.run(payload)

        result = results[0]
        assert result.title is not None
        assert result.journal is not None

    @pytest.mark.integration
    @pytest.mark.slow
    def test_pipeline_with_hpo_mapping(self, pubmed_client, rate_limit):
        """Should map phenotypes to HPO terms."""
        from genephenextract.extraction import MockExtractor

        class CustomMockExtractor(MockExtractor):
            def __init__(self):
                super().__init__(
                    {
                        "variant": "Test",
                        "phenotypes": [{"name": "syncope"}],
                    }
                )

        pipeline = ExtractionPipeline(
            pubmed_client=pubmed_client, extractor=CustomMockExtractor()
        )

        pmids = [TEST_PMIDS["old"]]
        payload = PipelineInput(pmids=pmids)
        results = pipeline.run(payload)

        # Should have mapped syncope to HPO
        if results[0].phenotypes:
            assert results[0].phenotypes[0].ontology_id is not None


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.skipif(
    not os.getenv("GEMINI_API_KEY"), reason="GEMINI_API_KEY not set"
)
class TestGeminiIntegration:
    """Integration tests with real Gemini API (requires API key)."""

    def test_gemini_extraction_on_real_abstract(self, pubmed_client, rate_limit):
        """Should perform real extraction using Gemini."""
        api_key = os.getenv("GEMINI_API_KEY")
        extractor = GeminiExtractor(api_key=api_key)

        pmid = TEST_PMIDS["kcnh2_long_qt"]
        abstract = pubmed_client.fetch_abstract(pmid)

        if not abstract:
            pytest.skip("Could not fetch abstract")

        result = extractor.extract(abstract, pmid=pmid)

        assert result.pmid == pmid
        # Real extraction should find something
        assert result.variant or result.phenotypes

    def test_full_pipeline_with_gemini(self, pubmed_client, rate_limit):
        """Should run full pipeline with Gemini extractor."""
        api_key = os.getenv("GEMINI_API_KEY")
        extractor = GeminiExtractor(api_key=api_key)

        pipeline = ExtractionPipeline(pubmed_client=pubmed_client, extractor=extractor)

        payload = PipelineInput(pmids=[TEST_PMIDS["kcnh2_long_qt"]])
        results = pipeline.run(payload)

        assert len(results) == 1
        result = results[0]
        assert result.pmid == TEST_PMIDS["kcnh2_long_qt"]


class TestErrorHandling:
    """Integration tests for error handling."""

    @pytest.mark.integration
    def test_handles_network_timeout_gracefully(self):
        """Should handle network timeouts."""
        client = PubMedClient(timeout=0.001, max_retries=1)  # Very short timeout

        from genephenextract.pubmed import PubMedError

        with pytest.raises(PubMedError):
            client.search("genetics", retmax=10)

    @pytest.mark.integration
    def test_pipeline_skips_missing_abstracts(self, pubmed_client, rate_limit):
        """Should skip PMIDs with no abstract."""
        pipeline = ExtractionPipeline(
            pubmed_client=pubmed_client, extractor=MockExtractor()
        )

        # Mix of valid and potentially invalid PMIDs
        payload = PipelineInput(pmids=["99999999999", TEST_PMIDS["old"]])
        results = pipeline.run(payload)

        # Should get at least the valid one
        assert len(results) >= 1
