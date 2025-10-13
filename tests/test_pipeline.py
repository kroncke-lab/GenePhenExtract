from genephenextract.extraction import MockExtractor
from genephenextract.models import PipelineInput
from genephenextract.pipeline import ExtractionPipeline


class DummyPubMedClient:
    def __init__(self) -> None:
        self.search_queries = []

    def search(self, query: str, *, retmax: int = 20):
        self.search_queries.append((query, retmax))
        return ["12345"]

    def fetch_details(self, pmids):
        if "12345" in pmids:
            return {
                "12345": {
                    "title": "Dummy title",
                    "abstract": "This is a dummy abstract containing KCNH2.",
                    "journal": "Test Journal",
                    "publication_date": "2020-01-01",
                }
            }
        return {}

    def fetch_abstract(self, pmid: str):
        return "This is a dummy abstract containing KCNH2." if pmid == "12345" else None

    def close(self):
        pass


def test_pipeline_uses_provided_pmids():
    pipeline = ExtractionPipeline(pubmed_client=DummyPubMedClient(), extractor=MockExtractor())
    payload = PipelineInput(pmids=["12345"], max_results=1)
    results = pipeline.run(payload)
    assert results[0].variant == "KCNH2 p.Tyr54Asn"
    assert results[0].title == "Dummy title"
    assert results[0].journal == "Test Journal"
    assert results[0].publication_date == "2020-01-01"


def test_pipeline_queries_pubmed_when_needed():
    client = DummyPubMedClient()
    pipeline = ExtractionPipeline(pubmed_client=client, extractor=MockExtractor())
    payload = PipelineInput(query="KCNH2", max_results=1)
    pipeline.run(payload)
    assert client.search_queries == [("KCNH2", 1)]


def test_pipeline_enriches_with_hpo_terms():
    class SimpleExtractor(MockExtractor):
        def __init__(self) -> None:
            super().__init__(
                {
                    "variant": "KCNH2 p.Tyr54Asn",
                    "phenotypes": [{"name": "syncope"}],
                }
            )

    pipeline = ExtractionPipeline(pubmed_client=DummyPubMedClient(), extractor=SimpleExtractor())
    payload = PipelineInput(pmids=["12345"], max_results=1)
    result = pipeline.run(payload)[0]
    assert result.phenotypes[0].ontology_id == "HP:0001279"
