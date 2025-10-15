"""Interfaces for running LLM-based schema-guided extraction."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

try:  # pragma: no cover - optional dependency
    import google.generativeai as genai
except ImportError:  # pragma: no cover - optional dependency
    genai = None  # type: ignore

from .models import ExtractionResult, PhenotypeObservation

logger = logging.getLogger(__name__)

DEFAULT_SCHEMA = Path(__file__).resolve().parent / "schema" / "default_schema.json"


class ExtractorError(RuntimeError):
    """Raised when schema-guided extraction cannot be completed."""


class BaseExtractor:
    """Protocol that all extractor implementations must satisfy."""

    def extract(self, text: str, *, pmid: str, schema_path: Optional[Path] = None) -> ExtractionResult:
        raise NotImplementedError


# Allow deployments to override the Gemini model at import time via an
# environment variable. This accommodates accounts that do not yet have access
# to the newest Gemini releases.
DEFAULT_GEMINI_MODEL = os.getenv("GENEPHENEXTRACT_GEMINI_MODEL", "gemini-pro")


class GeminiExtractor(BaseExtractor):
    """Implementation that uses Google's Gemini API directly for extraction."""

    def __init__(self, api_key: Optional[str] = None, model: str = DEFAULT_GEMINI_MODEL) -> None:
        if genai is None:  # pragma: no cover - optional dependency
            msg = "google-generativeai is not installed. Install it with `pip install google-generativeai`."
            raise ImportError(msg)
        
        if not api_key:
            msg = "API key is required for GeminiExtractor"
            raise ValueError(msg)
        
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model)
        self.model_name = model

    def extract(self, text: str, *, pmid: str, schema_path: Optional[Path] = None) -> ExtractionResult:
        schema = _load_schema(schema_path)
        logger.debug("Running Gemini extraction with schema %s", schema_path or DEFAULT_SCHEMA)
        
        # Create the prompt for Gemini
        prompt = self._create_extraction_prompt(text, schema)
        
        try:
            response = self.model.generate_content(prompt)
            result_text = response.text
            
            # Parse the JSON response
            # Remove markdown code blocks if present
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0].strip()
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0].strip()
            
            result_data = json.loads(result_text)
            logger.debug("Successfully extracted data from text")
            
        except json.JSONDecodeError as e:
            logger.error("Failed to parse JSON from Gemini response: %s", e)
            logger.debug("Response text: %s", result_text)
            raise ExtractorError(f"Failed to parse extraction result: {e}") from e
        except Exception as e:
            logger.error("Gemini API error: %s", e)
            hint = ""
            if self.model_name:
                hint = (
                    " The model '%s' may not be available to your account. "
                    "Set the GENEPHENEXTRACT_GEMINI_MODEL environment variable or pass "
                    "--model to the CLI with a supported identifier."
                ) % self.model_name
            raise ExtractorError(f"Gemini extraction failed: {e}.{hint}") from e
        
        return _result_from_payload(result_data, pmid=pmid)

    def _create_extraction_prompt(self, text: str, schema: Dict[str, Any]) -> str:
        """Create a prompt for Gemini to extract structured data."""
        prompt = f"""You are a medical text extraction expert. Extract structured information from the following scientific text about genetic variants and phenotypes.

Extract the following information according to this JSON schema:
{json.dumps(schema, indent=2)}

Text to analyze:
{text}

Requirements:
1. Extract the genetic variant (gene and mutation) mentioned in the text
2. Extract all phenotypes (clinical symptoms or conditions) mentioned
3. If mentioned, extract carrier status (heterozygous, homozygous, compound heterozygous)
4. If mentioned, extract patient age, sex, treatment, and outcome
5. For phenotypes, provide the phenotype name. Ontology IDs are optional.

Return ONLY a valid JSON object matching the schema. Do not include any explanation or markdown formatting.

Example output format:
{{
  "variant": "KCNH2 c.2717C>T p.(Ser906Leu)",
  "carrier_status": "heterozygous",
  "phenotypes": [
    {{"name": "prolonged QT interval"}},
    {{"name": "syncope"}}
  ],
  "age": 45,
  "sex": "female",
  "treatment": "beta-blocker",
  "outcome": "stable"
}}

Now extract from the provided text:"""
        
        return prompt


def _load_schema(schema_path: Optional[Path]) -> Dict[str, Any]:
    if schema_path is None:
        schema_path = DEFAULT_SCHEMA
    resolved = Path(schema_path).expanduser().resolve()
    if not resolved.exists():
        msg = f"Schema file not found: {resolved}"
        raise ExtractorError(msg)
    logger.debug("Loading schema from %s", resolved)
    return json.loads(resolved.read_text())


def _result_from_payload(payload: Dict[str, Any], *, pmid: str) -> ExtractionResult:
    fields = {
        "pmid": pmid,
        "variant": payload.get("variant", ""),
        "carrier_status": payload.get("carrier_status"),
        "age": payload.get("age"),
        "sex": payload.get("sex"),
        "treatment": payload.get("treatment"),
        "outcome": payload.get("outcome"),
        "title": payload.get("title"),
        "journal": payload.get("journal"),
        "publication_date": payload.get("publication_date"),
        "abstract": payload.get("abstract"),
    }

    phenotypes: Iterable[Dict[str, Any]] = payload.get("phenotypes", [])
    fields["phenotypes"] = [
        PhenotypeObservation(
            phenotype=phenotype.get("name", ""),
            ontology_id=phenotype.get("ontology_id"),
            onset_age=phenotype.get("onset_age"),
            notes=phenotype.get("notes"),
        )
        for phenotype in phenotypes
    ]
    return ExtractionResult(**fields)


class MockExtractor(BaseExtractor):
    """Simple extractor used for tests and local development."""

    def __init__(self, canned_response: Optional[Dict[str, Any]] = None) -> None:
        self.canned_response = canned_response or {
            "variant": "KCNH2 p.Tyr54Asn",
            "carrier_status": "heterozygous",
            "phenotypes": [
                {
                    "name": "prolonged QT interval",
                    "ontology_id": "HP:0001657",
                }
            ],
            "age": 34,
            "sex": "female",
            "treatment": "beta-blocker",
        }

    def extract(self, text: str, *, pmid: str, schema_path: Optional[Path] = None) -> ExtractionResult:
        del text, schema_path
        return _result_from_payload(self.canned_response, pmid=pmid)
