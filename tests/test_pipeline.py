from genephenextract.extraction import MockExtractor
from genephenextract.models import PipelineInput
from genephenextract.pipeline import ExtractionPipeline


class DummyPubMedClient:
    def __init__(self) -> None:
        self.search_queries = []

    def search(self, query: str, *, retmax: int = 20):
        self.search_queries.append((query, retmax))
        return ["12345"]

    def fetch_abstract(self, pmid: str):
        return "This is a dummy abstract containing KCNH2." if pmid == "12345" else None

    def close(self):
        pass


def test_pipeline_uses_provided_pmids():
    pipeline = ExtractionPipeline(pubmed_client=DummyPubMedClient(), extractor=MockExtractor())
    payload = PipelineInput(pmids=["12345"], max_results=1)
    results = pipeline.run(payload)
    assert results[0].variant == "KCNH2 p.Tyr54Asn"


def test_pipeline_queries_pubmed_when_needed():
    client = DummyPubMedClient()
    pipeline = ExtractionPipeline(pubmed_client=client, extractor=MockExtractor())
    payload = PipelineInput(query="KCNH2", max_results=1)
    pipeline.run(payload)
    assert client.search_queries == [("KCNH2", 1)]
