"""Utilities for mapping phenotype strings to HPO terms."""

from __future__ import annotations

import json
import logging
import unicodedata
from pathlib import Path
from typing import Dict, Iterable, Optional

from .models import ExtractionResult, PhenotypeObservation

logger = logging.getLogger(__name__)

DEFAULT_HPO_RESOURCE = Path(__file__).resolve().parent / "schema" / "hpo_minimal.json"


def _normalize(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text or "").strip().lower()
    return " ".join(normalized.split())


class PhenotypeOntologyMapper:
    """Lookup helper that enriches phenotypes with HPO identifiers."""

    def __init__(self, index: Dict[str, Dict[str, str]]) -> None:
        self._index = index

    @classmethod
    def from_json(cls, path: Path) -> "PhenotypeOntologyMapper":
        resolved = Path(path).expanduser().resolve()
        if not resolved.exists():
            msg = f"HPO mapping file not found: {resolved}"
            raise FileNotFoundError(msg)
        logger.debug("Loading HPO mapping from %s", resolved)
        raw_entries = json.loads(resolved.read_text())
        index: Dict[str, Dict[str, str]] = {}
        for entry in raw_entries:
            identifier = entry.get("id")
            label = entry.get("label")
            if not identifier or not label:
                logger.debug("Skipping invalid HPO entry: %s", entry)
                continue
            record = {"id": identifier, "label": label}
            synonyms: Iterable[str] = entry.get("synonyms", [])
            for term in {label, *synonyms}:
                key = _normalize(term)
                if not key:
                    continue
                index[key] = record
        return cls(index)

    @classmethod
    def default(cls) -> "PhenotypeOntologyMapper":
        return cls.from_json(DEFAULT_HPO_RESOURCE)

    def lookup(self, phenotype: str) -> Optional[Dict[str, str]]:
        if not phenotype:
            return None
        return self._index.get(_normalize(phenotype))

    def enrich_observation(self, observation: PhenotypeObservation) -> None:
        if observation.ontology_id:
            return
        match = self.lookup(observation.phenotype)
        if not match:
            return
        observation.ontology_id = match["id"]
        observation.phenotype = match["label"]

    def annotate(self, result: ExtractionResult) -> ExtractionResult:
        for phenotype in result.phenotypes:
            self.enrich_observation(phenotype)
        return result


__all__ = ["PhenotypeOntologyMapper"]
