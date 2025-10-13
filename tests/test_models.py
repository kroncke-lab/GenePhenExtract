from datetime import datetime

import pytest

from genephenextract.models import ExtractionResult, PhenotypeObservation


def test_phenotype_strips_whitespace():
    phenotype = PhenotypeObservation(phenotype="  QT prolongation  ")
    assert phenotype.phenotype == "QT prolongation"


def test_phenotype_blank_validation():
    with pytest.raises(ValueError):
        PhenotypeObservation(phenotype="   ")


def test_extraction_result_defaults():
    result = ExtractionResult(
        pmid=123456,
        variant="KCNH2 p.Tyr54Asn",
        phenotypes=[PhenotypeObservation(phenotype="QT prolongation")],
    )
    assert result.pmid == "123456"
    assert isinstance(result.extracted_at, datetime)
    payload = result.to_dict()
    assert "title" in payload
