"""Performance benchmarks for GenePhenExtract.

Run with: pytest tests/test_benchmarks.py --benchmark-only
"""

import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from genephenextract import ExtractionPipeline, PipelineInput, MockExtractor
from genephenextract.extraction import _result_from_payload
from genephenextract.hpo import PhenotypeOntologyMapper
from genephenextract.models import ExtractionResult, PhenotypeObservation
from genephenextract.pubmed import (
    PubMedClient,
    _extract_text_from_element,
    _parse_publication_date,
)


@pytest.fixture
def sample_abstract():
    """Generate a sample abstract for benchmarking."""
    return """
    Background: Long QT syndrome (LQTS) is a cardiac channelopathy characterized by
    prolonged ventricular repolarization and increased risk of sudden cardiac death.
    KCNH2 mutations are a common cause of type 2 LQTS.

    Methods: We identified a family with recurrent syncope and sudden death. Genetic
    screening revealed a novel KCNH2 variant c.2717C>T (p.Ser906Leu) in affected members.

    Results: The proband, a 34-year-old female, presented with recurrent syncope and
    a corrected QT interval of 480 ms. She was found to be heterozygous for the variant.
    Family screening identified three additional carriers, all with prolonged QT intervals
    ranging from 460-490 ms. One carrier had experienced cardiac arrest at age 28.

    Functional studies demonstrated that the p.Ser906Leu variant causes loss of function
    of the KCNH2 channel, consistent with a pathogenic mechanism. All affected individuals
    were started on beta-blocker therapy and advised to avoid QT-prolonging medications.

    Conclusions: The KCNH2 p.Ser906Leu variant is a pathogenic mutation causing
    autosomal dominant LQTS with high penetrance and severe clinical phenotype.
    """


@pytest.fixture
def sample_xml_article():
    """Generate sample XML for benchmarking."""
    return """
    <PubmedArticleSet>
      <PubmedArticle>
        <MedlineCitation>
          <PMID>12345678</PMID>
          <Article>
            <ArticleTitle>Novel KCNH2 Mutation in Long QT Syndrome</ArticleTitle>
            <Journal>
              <JournalIssue>
                <PubDate>
                  <Year>2023</Year>
                  <Month>06</Month>
                  <Day>15</Day>
                </PubDate>
              </JournalIssue>
              <Title>Journal of Cardiology</Title>
            </Journal>
            <Abstract>
              <AbstractText>Sample abstract text here.</AbstractText>
              <AbstractText>More abstract text.</AbstractText>
            </Abstract>
          </Article>
        </MedlineCitation>
      </PubmedArticle>
    </PubmedArticleSet>
    """


@pytest.fixture
def complex_payload():
    """Generate complex extraction payload for benchmarking."""
    return {
        "variant": "KCNH2 c.2717C>T p.(Ser906Leu)",
        "carrier_status": "heterozygous",
        "phenotypes": [
            {
                "name": "prolonged QT interval",
                "ontology_id": "HP:0001657",
                "onset_age": 28,
                "notes": "QTc 480ms",
            },
            {"name": "syncope", "ontology_id": "HP:0001279", "onset_age": 30},
            {"name": "cardiac arrest", "ontology_id": "HP:0001695", "onset_age": 28},
            {"name": "torsades de pointes", "ontology_id": "HP:0001664"},
        ],
        "age": 34,
        "sex": "female",
        "treatment": "beta-blocker therapy",
        "outcome": "stable on treatment",
        "title": "Novel KCNH2 Mutation in Long QT Syndrome",
        "journal": "Journal of Cardiology",
        "publication_date": "2023-06-15",
    }


class DummyPubMedClient:
    """Fast dummy client for benchmarking."""

    def search(self, query: str, *, retmax: int = 20):
        return [f"{i:08d}" for i in range(retmax)]

    def fetch_details(self, pmids):
        return {
            pmid: {
                "title": f"Article {pmid}",
                "abstract": "This is a sample abstract for benchmarking purposes.",
                "journal": "Test Journal",
                "publication_date": "2023-01-01",
            }
            for pmid in pmids
        }

    def fetch_abstract(self, pmid: str):
        return "This is a sample abstract for benchmarking purposes."

    def close(self):
        pass


# ==================== Model Creation Benchmarks ====================


@pytest.mark.benchmark
def test_benchmark_phenotype_observation_creation(benchmark):
    """Benchmark creating PhenotypeObservation instances."""

    def create_observation():
        return PhenotypeObservation(
            phenotype="prolonged QT interval",
            ontology_id="HP:0001657",
            onset_age=30,
            notes="QTc 480ms",
        )

    result = benchmark(create_observation)
    assert result.phenotype == "prolonged QT interval"


@pytest.mark.benchmark
def test_benchmark_extraction_result_creation(benchmark):
    """Benchmark creating ExtractionResult instances."""

    def create_result():
        return ExtractionResult(
            pmid="12345678",
            variant="KCNH2 p.Tyr54Asn",
            carrier_status="heterozygous",
            phenotypes=[
                PhenotypeObservation(phenotype="syncope", ontology_id="HP:0001279")
            ],
            age=34,
            sex="female",
        )

    result = benchmark(create_result)
    assert result.pmid == "12345678"


@pytest.mark.benchmark
def test_benchmark_extraction_result_to_dict(benchmark):
    """Benchmark converting ExtractionResult to dict."""
    result = ExtractionResult(
        pmid="12345678",
        variant="KCNH2 p.Tyr54Asn",
        phenotypes=[
            PhenotypeObservation(phenotype="syncope", ontology_id="HP:0001279")
        ],
    )

    output = benchmark(result.to_dict)
    assert "pmid" in output


# ==================== Extraction Benchmarks ====================


@pytest.mark.benchmark
def test_benchmark_mock_extractor(benchmark, sample_abstract):
    """Benchmark MockExtractor performance."""
    extractor = MockExtractor()

    result = benchmark(extractor.extract, sample_abstract, pmid="12345")
    assert result.variant is not None


@pytest.mark.benchmark
def test_benchmark_result_from_payload_simple(benchmark):
    """Benchmark converting simple payload to ExtractionResult."""
    payload = {"variant": "KCNH2 p.Tyr54Asn", "phenotypes": []}

    result = benchmark(_result_from_payload, payload, pmid="12345")
    assert result.pmid == "12345"


@pytest.mark.benchmark
def test_benchmark_result_from_payload_complex(benchmark, complex_payload):
    """Benchmark converting complex payload to ExtractionResult."""
    result = benchmark(_result_from_payload, complex_payload, pmid="99999")
    assert len(result.phenotypes) == 4


# ==================== HPO Mapping Benchmarks ====================


@pytest.mark.benchmark
def test_benchmark_hpo_mapper_initialization(benchmark):
    """Benchmark initializing HPO mapper."""

    def init_mapper():
        return PhenotypeOntologyMapper.default()

    mapper = benchmark(init_mapper)
    assert mapper is not None


@pytest.mark.benchmark
def test_benchmark_hpo_single_enrichment(benchmark):
    """Benchmark enriching a single phenotype observation."""
    mapper = PhenotypeOntologyMapper.default()
    observation = PhenotypeObservation(phenotype="syncope")

    benchmark(mapper.enrich_observation, observation)


@pytest.mark.benchmark
def test_benchmark_hpo_multiple_enrichments(benchmark):
    """Benchmark enriching multiple phenotypes."""
    mapper = PhenotypeOntologyMapper.default()

    def enrich_multiple():
        result = ExtractionResult(
            pmid="12345",
            variant="Test",
            phenotypes=[
                PhenotypeObservation(phenotype="syncope"),
                PhenotypeObservation(phenotype="prolonged QT interval"),
                PhenotypeObservation(phenotype="cardiac arrhythmia"),
                PhenotypeObservation(phenotype="sudden cardiac death"),
            ],
        )
        mapper.annotate(result)
        return result

    result = benchmark(enrich_multiple)
    assert len(result.phenotypes) == 4


# ==================== PubMed Client Benchmarks ====================


@pytest.mark.benchmark
def test_benchmark_pubmed_xml_parsing(benchmark, sample_xml_article):
    """Benchmark XML parsing performance."""
    import xml.etree.ElementTree as ET

    def parse_xml():
        root = ET.fromstring(sample_xml_article)
        article = root.find(".//PubmedArticle")
        return article

    result = benchmark(parse_xml)
    assert result is not None


@pytest.mark.benchmark
def test_benchmark_parse_publication_date(benchmark, sample_xml_article):
    """Benchmark publication date parsing."""
    import xml.etree.ElementTree as ET

    root = ET.fromstring(sample_xml_article)
    article = root.find(".//PubmedArticle")

    result = benchmark(_parse_publication_date, article)
    assert result is not None


@pytest.mark.benchmark
def test_benchmark_extract_text_from_element(benchmark):
    """Benchmark text extraction from XML elements."""
    import xml.etree.ElementTree as ET

    element = ET.fromstring(
        """
        <section>
            <title>Background</title>
            <p>Long QT syndrome is a cardiac disorder.</p>
            <p>It is characterized by prolonged repolarization.</p>
        </section>
        """
    )

    result = benchmark(_extract_text_from_element, element)
    assert "Long QT" in result


# ==================== Pipeline Benchmarks ====================


@pytest.mark.benchmark
def test_benchmark_pipeline_single_pmid(benchmark):
    """Benchmark pipeline processing a single PMID."""
    pipeline = ExtractionPipeline(
        pubmed_client=DummyPubMedClient(), extractor=MockExtractor()
    )
    payload = PipelineInput(pmids=["12345678"])

    results = benchmark(pipeline.run, payload)
    assert len(results) == 1


@pytest.mark.benchmark
def test_benchmark_pipeline_ten_pmids(benchmark):
    """Benchmark pipeline processing 10 PMIDs."""
    pipeline = ExtractionPipeline(
        pubmed_client=DummyPubMedClient(), extractor=MockExtractor()
    )
    payload = PipelineInput(pmids=[f"{i:08d}" for i in range(10)])

    results = benchmark(pipeline.run, payload)
    assert len(results) == 10


@pytest.mark.benchmark
def test_benchmark_pipeline_with_query(benchmark):
    """Benchmark pipeline with query-based search."""
    pipeline = ExtractionPipeline(
        pubmed_client=DummyPubMedClient(), extractor=MockExtractor()
    )
    payload = PipelineInput(query="KCNH2 AND long QT", max_results=5)

    results = benchmark(pipeline.run, payload)
    assert len(results) > 0


@pytest.mark.benchmark
def test_benchmark_pipeline_with_hpo(benchmark):
    """Benchmark pipeline including HPO enrichment."""

    class SyncopeMockExtractor(MockExtractor):
        def __init__(self):
            super().__init__({"variant": "Test", "phenotypes": [{"name": "syncope"}]})

    pipeline = ExtractionPipeline(
        pubmed_client=DummyPubMedClient(),
        extractor=SyncopeMockExtractor(),
        phenotype_mapper=PhenotypeOntologyMapper.default(),
    )
    payload = PipelineInput(pmids=["12345678"])

    results = benchmark(pipeline.run, payload)
    assert results[0].phenotypes[0].ontology_id is not None


# ==================== Stress Tests ====================


@pytest.mark.benchmark
@pytest.mark.slow
def test_benchmark_pipeline_100_pmids(benchmark):
    """Stress test: process 100 PMIDs."""
    pipeline = ExtractionPipeline(
        pubmed_client=DummyPubMedClient(), extractor=MockExtractor()
    )
    payload = PipelineInput(pmids=[f"{i:08d}" for i in range(100)])

    results = benchmark.pedantic(pipeline.run, args=(payload,), iterations=1, rounds=3)
    assert len(results) == 100


@pytest.mark.benchmark
@pytest.mark.slow
def test_benchmark_hpo_enrichment_large_batch(benchmark):
    """Stress test: HPO enrichment on large batch."""
    mapper = PhenotypeOntologyMapper.default()

    def enrich_large_batch():
        results = []
        for i in range(50):
            result = ExtractionResult(
                pmid=f"{i:08d}",
                variant="Test",
                phenotypes=[
                    PhenotypeObservation(phenotype="syncope"),
                    PhenotypeObservation(phenotype="prolonged QT interval"),
                ],
            )
            mapper.annotate(result)
            results.append(result)
        return results

    results = benchmark.pedantic(enrich_large_batch, iterations=1, rounds=3)
    assert len(results) == 50


# ==================== Comparison Benchmarks ====================


@pytest.mark.benchmark
@pytest.mark.parametrize("num_phenotypes", [1, 5, 10, 20])
def test_benchmark_phenotype_scaling(benchmark, num_phenotypes):
    """Benchmark how performance scales with number of phenotypes."""

    def create_result_with_n_phenotypes():
        phenotypes = [
            PhenotypeObservation(phenotype=f"phenotype_{i}", ontology_id=f"HP:{i:07d}")
            for i in range(num_phenotypes)
        ]
        return ExtractionResult(pmid="12345", variant="Test", phenotypes=phenotypes)

    result = benchmark(create_result_with_n_phenotypes)
    assert len(result.phenotypes) == num_phenotypes


@pytest.mark.benchmark
@pytest.mark.parametrize("batch_size", [1, 5, 10, 25])
def test_benchmark_batch_scaling(benchmark, batch_size):
    """Benchmark how pipeline scales with batch size."""
    pipeline = ExtractionPipeline(
        pubmed_client=DummyPubMedClient(), extractor=MockExtractor()
    )

    def process_batch():
        payload = PipelineInput(pmids=[f"{i:08d}" for i in range(batch_size)])
        return pipeline.run(payload)

    results = benchmark(process_batch)
    assert len(results) == batch_size
