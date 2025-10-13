import json

from genephenextract.hpo import PhenotypeOntologyMapper
from genephenextract.models import ExtractionResult, PhenotypeObservation


def test_mapper_finds_synonym(tmp_path):
    mapper = PhenotypeOntologyMapper.default()
    observation = PhenotypeObservation(phenotype="QT prolongation")
    mapper.enrich_observation(observation)
    assert observation.ontology_id == "HP:0001657"
    assert observation.phenotype == "Prolonged QT interval"


def test_mapper_handles_custom_resource(tmp_path):
    custom_resource = tmp_path / "custom_hpo.json"
    custom_resource.write_text(
        json.dumps(
            [
                {
                    "id": "HP:1234567",
                    "label": "Custom Phenotype",
                    "synonyms": ["example"],
                }
            ]
        )
    )
    mapper = PhenotypeOntologyMapper.from_json(custom_resource)
    result = ExtractionResult(
        pmid="1",
        variant="VAR",
        phenotypes=[PhenotypeObservation(phenotype="example")],
    )
    mapper.annotate(result)
    assert result.phenotypes[0].ontology_id == "HP:1234567"
