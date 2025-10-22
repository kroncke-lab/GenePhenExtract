"""Advanced tests for extraction module with edge cases."""

import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from genephenextract.extraction import (
    BaseExtractor,
    ExtractorError,
    MockExtractor,
    _canonicalize_model_name,
    _result_from_payload,
)
from genephenextract.models import ExtractionResult, PhenotypeObservation


class TestCanonicalizeModelName:
    """Tests for model name canonicalization."""

    def test_strips_models_prefix(self):
        assert _canonicalize_model_name("models/gemini-pro") == "gemini-pro"

    def test_strips_tuned_models_prefix(self):
        assert _canonicalize_model_name("tunedModels/my-model") == "my-model"

    def test_handles_bare_model_names(self):
        assert _canonicalize_model_name("gemini-pro") == "gemini-pro"

    def test_handles_multiple_prefixes(self):
        # Edge case: what if someone provides a weird format?
        assert _canonicalize_model_name("models/gemini-1.5-pro") == "gemini-1.5-pro"

    def test_raises_on_empty_string(self):
        with pytest.raises(ValueError, match="must be a non-empty string"):
            _canonicalize_model_name("")

    def test_raises_on_none(self):
        with pytest.raises((ValueError, AttributeError)):
            _canonicalize_model_name(None)


class TestResultFromPayload:
    """Tests for converting API payloads to ExtractionResult."""

    def test_minimal_payload(self):
        """Should handle minimal valid payload."""
        payload = {"variant": "KCNH2 p.Tyr54Asn"}
        result = _result_from_payload(payload, pmid="12345")

        assert result.pmid == "12345"
        assert result.variant == "KCNH2 p.Tyr54Asn"
        assert result.phenotypes == []

    def test_payload_with_all_fields(self):
        """Should handle payload with all possible fields."""
        payload = {
            "variant": "KCNH2 p.Tyr54Asn",
            "carrier_status": "heterozygous",
            "age": 45,
            "sex": "female",
            "treatment": "beta-blocker",
            "outcome": "stable",
            "title": "Test Article",
            "journal": "Test Journal",
            "publication_date": "2023-01-15",
            "abstract": "Test abstract text",
            "phenotypes": [
                {"name": "prolonged QT interval", "ontology_id": "HP:0001657"},
                {"name": "syncope", "onset_age": 30, "notes": "recurrent"},
            ],
        }
        result = _result_from_payload(payload, pmid="99999")

        assert result.pmid == "99999"
        assert result.variant == "KCNH2 p.Tyr54Asn"
        assert result.carrier_status == "heterozygous"
        assert result.age == 45
        assert result.sex == "female"
        assert result.treatment == "beta-blocker"
        assert result.outcome == "stable"
        assert result.title == "Test Article"
        assert result.journal == "Test Journal"
        assert result.publication_date == "2023-01-15"
        assert len(result.phenotypes) == 2
        assert result.phenotypes[0].phenotype == "prolonged QT interval"
        assert result.phenotypes[0].ontology_id == "HP:0001657"
        assert result.phenotypes[1].onset_age == 30

    def test_empty_phenotypes_list(self):
        """Should handle empty phenotypes list."""
        payload = {"variant": "SCN5A p.Arg1193Gln", "phenotypes": []}
        result = _result_from_payload(payload, pmid="11111")

        assert result.phenotypes == []

    def test_missing_phenotype_fields(self):
        """Should handle phenotypes with missing optional fields."""
        payload = {
            "variant": "KCNQ1 p.Arg190Gln",
            "phenotypes": [{"name": "torsades de pointes"}],
        }
        result = _result_from_payload(payload, pmid="22222")

        assert len(result.phenotypes) == 1
        assert result.phenotypes[0].phenotype == "torsades de pointes"
        assert result.phenotypes[0].ontology_id is None
        assert result.phenotypes[0].onset_age is None
        assert result.phenotypes[0].notes is None

    def test_handles_missing_variant_gracefully(self):
        """Should set empty string for missing variant."""
        payload = {"phenotypes": [{"name": "arrhythmia"}]}
        result = _result_from_payload(payload, pmid="33333")

        assert result.variant == ""


class TestMockExtractor:
    """Enhanced tests for MockExtractor."""

    def test_ignores_input_text(self):
        """MockExtractor should return canned response regardless of input."""
        extractor = MockExtractor()

        result1 = extractor.extract("Random text about genes", pmid="111")
        result2 = extractor.extract("Completely different text", pmid="222")

        assert result1.variant == result2.variant

    def test_custom_canned_response(self):
        """Should allow custom canned responses."""
        custom = {
            "variant": "Custom Variant",
            "carrier_status": "homozygous",
            "phenotypes": [{"name": "custom phenotype", "ontology_id": "HP:9999999"}],
        }
        extractor = MockExtractor(canned_response=custom)

        result = extractor.extract("any text", pmid="999")

        assert result.variant == "Custom Variant"
        assert result.carrier_status == "homozygous"
        assert len(result.phenotypes) == 1
        assert result.phenotypes[0].phenotype == "custom phenotype"

    def test_schema_path_ignored(self, tmp_path):
        """MockExtractor should ignore schema_path parameter."""
        extractor = MockExtractor()
        schema_path = tmp_path / "dummy_schema.json"

        result = extractor.extract("text", pmid="123", schema_path=schema_path)

        assert result.pmid == "123"

    def test_empty_canned_response(self):
        """Empty dict triggers default response (due to 'or' operator)."""
        extractor = MockExtractor(canned_response={})
        result = extractor.extract("text", pmid="999")

        # Empty dict is falsy, so default response is used
        assert result.variant == "KCNH2 p.Tyr54Asn"


class TestBaseExtractor:
    """Tests for BaseExtractor protocol."""

    def test_base_extractor_not_implemented(self):
        """BaseExtractor.extract should raise NotImplementedError."""
        extractor = BaseExtractor()

        with pytest.raises(NotImplementedError):
            extractor.extract("text", pmid="123")


class TestGeminiExtractorEdgeCases:
    """Edge case tests for GeminiExtractor (mocked)."""

    def test_init_requires_api_key(self):
        """GeminiExtractor should require API key."""
        try:
            from genephenextract.extraction import GeminiExtractor

            with pytest.raises(ValueError, match="API key is required"):
                GeminiExtractor(api_key=None)

            with pytest.raises(ValueError, match="API key is required"):
                GeminiExtractor(api_key="")
        except ImportError:
            pytest.skip("google-generativeai not installed")

    def test_extract_handles_json_parsing_errors(self):
        """Should raise ExtractorError when JSON parsing fails."""
        try:
            from genephenextract.extraction import GeminiExtractor

            with patch("genephenextract.extraction.genai") as mock_genai:
                # Mock the configuration and model
                mock_model = Mock()
                mock_response = Mock()
                mock_response.text = "This is not valid JSON!"
                mock_model.generate_content.return_value = mock_response
                mock_genai.GenerativeModel.return_value = mock_model
                mock_genai.list_models.return_value = []

                extractor = GeminiExtractor(api_key="test-key")

                with pytest.raises(ExtractorError, match="Failed to parse extraction result"):
                    extractor.extract("Some medical text", pmid="12345")
        except ImportError:
            pytest.skip("google-generativeai not installed")

    def test_extract_handles_markdown_json_blocks(self):
        """Should handle JSON wrapped in markdown code blocks."""
        try:
            from genephenextract.extraction import GeminiExtractor

            with patch("genephenextract.extraction.genai") as mock_genai:
                mock_model = Mock()
                mock_response = Mock()
                # Simulate Gemini returning JSON in markdown format
                mock_response.text = """```json
{
  "variant": "KCNH2 p.Tyr54Asn",
  "phenotypes": []
}
```"""
                mock_model.generate_content.return_value = mock_response
                mock_genai.GenerativeModel.return_value = mock_model
                mock_genai.list_models.return_value = []

                extractor = GeminiExtractor(api_key="test-key")
                result = extractor.extract("Text", pmid="12345")

                assert result.variant == "KCNH2 p.Tyr54Asn"
        except ImportError:
            pytest.skip("google-generativeai not installed")


class TestExtractorError:
    """Tests for ExtractorError exception."""

    def test_extractorerror_is_runtime_error(self):
        """ExtractorError should be a RuntimeError."""
        error = ExtractorError("Test error")
        assert isinstance(error, RuntimeError)

    def test_extractorerror_message(self):
        """Should preserve error message."""
        msg = "Extraction failed due to invalid schema"
        error = ExtractorError(msg)
        assert str(error) == msg
