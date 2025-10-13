"""Interfaces for running LangExtract-based schema-guided extraction."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

try:  # pragma: no cover - optional dependency
    from langextract import LangExtract
except ImportError:  # pragma: no cover - optional dependency
    LangExtract = None  # type: ignore

from .models import ExtractionResult, PhenotypeObservation

logger = logging.getLogger(__name__)

DEFAULT_SCHEMA = Path(__file__).resolve().parent / "schema" / "default_schema.json"


class ExtractorError(RuntimeError):
    """Raised when schema-guided extraction cannot be completed."""


class BaseExtractor:
    """Protocol that all extractor implementations must satisfy."""

    def extract(self, text: str, *, pmid: str, schema_path: Optional[Path] = None) -> ExtractionResult:
        raise NotImplementedError


class LangExtractExtractor(BaseExtractor):
    """Implementation that delegates to the `langextract` Python package."""

    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-1.5-pro") -> None:
        if LangExtract is None:  # pragma: no cover - optional dependency
            msg = "langextract is not installed. Install the extra with `pip install genephenextract[langextract]`."
            raise ImportError(msg)
        self.client = LangExtract(api_key=api_key, model=model)

    def extract(self, text: str, *, pmid: str, schema_path: Optional[Path] = None) -> ExtractionResult:
        schema = _load_schema(schema_path)
        logger.debug("Running LangExtract with schema %s", schema_path or DEFAULT_SCHEMA)
        response = self.client.extract(text=text, schema=schema)  # type: ignore[arg-type]
        return _result_from_payload(response, pmid=pmid)


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
