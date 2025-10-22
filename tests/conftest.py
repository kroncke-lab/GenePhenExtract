"""Shared pytest configuration and fixtures for all tests."""

import os
import time
from pathlib import Path
from typing import Dict, List, Optional

import pytest


def pytest_configure(config):
    """Configure custom markers."""
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests (may require network)"
    )
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line("markers", "benchmark: marks tests as benchmarks")


# ==================== Common Fixtures ====================


@pytest.fixture
def sample_pmid():
    """Provide a sample PMID for testing."""
    return "12345678"


@pytest.fixture
def sample_pmids():
    """Provide multiple sample PMIDs for testing."""
    return ["12345678", "87654321", "11111111"]


@pytest.fixture
def sample_variant():
    """Provide a sample genetic variant."""
    return "KCNH2 c.2717C>T p.(Ser906Leu)"


@pytest.fixture
def sample_phenotypes():
    """Provide sample phenotype data."""
    return [
        {"name": "prolonged QT interval", "ontology_id": "HP:0001657"},
        {"name": "syncope", "ontology_id": "HP:0001279"},
        {"name": "cardiac arrhythmia", "ontology_id": "HP:0011675"},
    ]


@pytest.fixture
def sample_abstract():
    """Provide a realistic sample abstract for testing."""
    return """
    Background: Long QT syndrome (LQTS) is characterized by prolonged ventricular
    repolarization and increased risk of arrhythmias and sudden cardiac death.

    Methods: We performed genetic screening on a family with recurrent syncope.

    Results: We identified a novel KCNH2 variant c.2717C>T (p.Ser906Leu) in the
    proband, a 34-year-old female with QTc of 480 ms. The variant segregated with
    disease in the family. Functional studies confirmed loss of channel function.

    Conclusions: This variant is pathogenic for LQTS type 2.
    """


@pytest.fixture
def sample_extraction_payload():
    """Provide a sample extraction payload."""
    return {
        "variant": "KCNH2 c.2717C>T p.(Ser906Leu)",
        "carrier_status": "heterozygous",
        "phenotypes": [
            {"name": "prolonged QT interval", "ontology_id": "HP:0001657"},
            {"name": "syncope", "ontology_id": "HP:0001279"},
        ],
        "age": 34,
        "sex": "female",
        "treatment": "beta-blocker",
        "outcome": "stable",
    }


# ==================== Mock Clients ====================


@pytest.fixture
def mock_pubmed_client():
    """Provide a mock PubMed client for testing."""

    class MockPubMedClient:
        def __init__(self):
            self.search_called = False
            self.fetch_details_called = False
            self.fetch_abstract_called = False

        def search(self, query: str, *, retmax: int = 20) -> List[str]:
            self.search_called = True
            return ["12345", "67890"][:retmax]

        def fetch_details(self, pmids) -> Dict[str, Dict[str, Optional[str]]]:
            self.fetch_details_called = True
            return {
                pmid: {
                    "title": f"Article {pmid}",
                    "abstract": f"Abstract for {pmid}",
                    "journal": "Test Journal",
                    "publication_date": "2023-01-01",
                }
                for pmid in pmids
            }

        def fetch_abstract(self, pmid: str) -> Optional[str]:
            self.fetch_abstract_called = True
            return f"Abstract for PMID {pmid}"

        def close(self):
            pass

    return MockPubMedClient()


@pytest.fixture
def mock_extractor():
    """Provide a mock extractor for testing."""
    from genephenextract.extraction import MockExtractor

    return MockExtractor()


# ==================== Integration Test Helpers ====================


@pytest.fixture
def rate_limit():
    """Add delay between integration tests to avoid rate limiting."""
    yield
    time.sleep(1.0)


@pytest.fixture
def skip_if_no_network():
    """Skip test if network is unavailable."""
    import socket

    try:
        socket.create_connection(("www.google.com", 80), timeout=5)
    except OSError:
        pytest.skip("Network unavailable")


@pytest.fixture
def gemini_api_key():
    """Provide Gemini API key or skip if not available."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        pytest.skip("GEMINI_API_KEY environment variable not set")
    return api_key


# ==================== File System Helpers ====================


@pytest.fixture
def test_data_dir(tmp_path):
    """Create a temporary directory for test data."""
    data_dir = tmp_path / "test_data"
    data_dir.mkdir()
    return data_dir


@pytest.fixture
def sample_pdf_path(test_data_dir):
    """Create a minimal valid PDF for testing."""
    pdf_path = test_data_dir / "sample.pdf"

    # Minimal PDF content
    minimal_pdf = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R
/Resources << /Font << /F1 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> >> >> >>
endobj
4 0 obj
<< /Length 44 >>
stream
BT
/F1 12 Tf
100 700 Td
(Test Content) Tj
ET
endstream
endobj
xref
0 5
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000317 00000 n
trailer
<< /Size 5 /Root 1 0 R >>
startxref
410
%%EOF
"""
    pdf_path.write_bytes(minimal_pdf)
    return pdf_path


@pytest.fixture
def sample_json_schema(test_data_dir):
    """Create a sample JSON schema for testing."""
    import json

    schema_path = test_data_dir / "test_schema.json"
    schema = {
        "variant": "string",
        "carrier_status": "string",
        "phenotypes": [{"name": "string", "ontology_id": "string"}],
        "age": "integer",
        "sex": "string",
    }
    schema_path.write_text(json.dumps(schema, indent=2))
    return schema_path


@pytest.fixture
def sample_hpo_json(test_data_dir):
    """Create a sample HPO mapping JSON for testing."""
    import json

    hpo_path = test_data_dir / "hpo_test.json"
    hpo_data = [
        {
            "id": "HP:0001657",
            "label": "Prolonged QT interval",
            "synonyms": ["QT prolongation", "prolonged QT", "long QT"],
        },
        {
            "id": "HP:0001279",
            "label": "Syncope",
            "synonyms": ["fainting", "blackout"],
        },
    ]
    hpo_path.write_text(json.dumps(hpo_data, indent=2))
    return hpo_path


# ==================== XML Test Data ====================


@pytest.fixture
def sample_pubmed_xml():
    """Provide sample PubMed XML response."""
    return """
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <PMID>12345678</PMID>
      <Article>
        <ArticleTitle>Novel KCNH2 Variant in Long QT Syndrome</ArticleTitle>
        <Journal>
          <JournalIssue>
            <PubDate>
              <Year>2023</Year>
              <Month>Jan</Month>
              <Day>15</Day>
            </PubDate>
          </JournalIssue>
          <Title>Journal of Cardiology</Title>
        </Journal>
        <Abstract>
          <AbstractText>Background: Long QT syndrome is a cardiac disorder.</AbstractText>
          <AbstractText>Results: We identified a novel variant.</AbstractText>
        </Abstract>
      </Article>
    </MedlineCitation>
  </PubmedArticle>
</PubmedArticleSet>
    """.strip()


@pytest.fixture
def sample_pmc_xml():
    """Provide sample PMC full-text XML response."""
    return """
<pmc-articleset>
  <article>
    <front>
      <article-meta>
        <article-id pub-id-type="pmc">1234567</article-id>
        <title-group>
          <article-title>Test Article</article-title>
        </title-group>
      </article-meta>
    </front>
    <body>
      <sec>
        <title>Introduction</title>
        <p>This is the introduction section.</p>
      </sec>
      <sec>
        <title>Methods</title>
        <p>These are the methods.</p>
      </sec>
    </body>
  </article>
</pmc-articleset>
    """.strip()


# ==================== Performance Helpers ====================


@pytest.fixture
def performance_threshold():
    """Provide performance thresholds for benchmarking."""
    return {
        "model_creation": 0.001,  # 1ms
        "hpo_enrichment": 0.010,  # 10ms
        "xml_parsing": 0.005,  # 5ms
        "single_pmid": 0.100,  # 100ms
        "batch_10": 1.0,  # 1 second
    }


# ==================== Cleanup ====================


@pytest.fixture(autouse=True)
def cleanup_temp_files(tmp_path):
    """Automatically cleanup temporary files after each test."""
    yield
    # Cleanup happens automatically with tmp_path


# ==================== Logging Configuration ====================


@pytest.fixture(autouse=True)
def configure_logging():
    """Configure logging for tests."""
    import logging

    # Reduce logging noise during tests
    logging.getLogger("genephenextract").setLevel(logging.WARNING)

    yield

    # Reset logging after test
    logging.getLogger("genephenextract").setLevel(logging.INFO)


# ==================== Coverage Helpers ====================


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers automatically."""
    for item in items:
        # Auto-mark slow tests based on name
        if "stress" in item.nodeid or "large_batch" in item.nodeid:
            item.add_marker(pytest.mark.slow)

        # Auto-mark benchmark tests
        if "benchmark" in item.nodeid:
            item.add_marker(pytest.mark.benchmark)
