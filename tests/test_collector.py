from pathlib import Path
from typing import Sequence

import pytest

from gene_literature.collector import LiteratureCollector, build_gene_query
from gene_literature.pubmed_client import PubMedClient
from gene_literature.writer import write_metadata


class DummyPubMedClient(PubMedClient):
    def __init__(self, pmids: Sequence[str], xml_payload: str) -> None:
        super().__init__(api_key=None, email=None)
        self._pmids = list(pmids)
        self._xml_payload = xml_payload

    def search(self, query: str, *, retmax: int = 100):  # type: ignore[override]
        return self._pmids

    def _request(self, endpoint: str, params: dict) -> str:  # type: ignore[override]
        return self._xml_payload


SAMPLE_XML = """
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <PMID>12345</PMID>
      <Article>
        <ArticleTitle>Gene ABC case report</ArticleTitle>
        <Abstract>
          <AbstractText>We describe patients carrying ABC variants.</AbstractText>
        </Abstract>
        <Journal>
          <JournalIssue>
            <PubDate>
              <Year>2020</Year>
            </PubDate>
          </JournalIssue>
          <Title>Genetics Journal</Title>
        </Journal>
        <AuthorList>
          <Author>
            <LastName>Doe</LastName>
            <ForeName>Jane</ForeName>
          </Author>
        </AuthorList>
      </Article>
    </MedlineCitation>
    <PubmedData>
      <ArticleIdList>
        <ArticleId IdType="pmid">12345</ArticleId>
        <ArticleId IdType="pmcid">PMC999999</ArticleId>
      </ArticleIdList>
    </PubmedData>
  </PubmedArticle>
</PubmedArticleSet>
"""

# Sample XML using IdType='pmc' (newer PubMed format)
SAMPLE_XML_PMC_FORMAT = """
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <PMID>67890</PMID>
      <Article>
        <ArticleTitle>Gene XYZ clinical study</ArticleTitle>
        <Abstract>
          <AbstractText>Clinical cohort study of XYZ variants.</AbstractText>
        </Abstract>
        <Journal>
          <JournalIssue>
            <PubDate>
              <Year>2023</Year>
            </PubDate>
          </JournalIssue>
          <Title>Medical Genetics</Title>
        </Journal>
        <AuthorList>
          <Author>
            <LastName>Smith</LastName>
            <ForeName>John</ForeName>
          </Author>
        </AuthorList>
      </Article>
    </MedlineCitation>
    <PubmedData>
      <ArticleIdList>
        <ArticleId IdType="pubmed">67890</ArticleId>
        <ArticleId IdType="pmc">PMC123456</ArticleId>
        <ArticleId IdType="doi">10.1234/example.doi</ArticleId>
      </ArticleIdList>
    </PubmedData>
  </PubmedArticle>
</PubmedArticleSet>
"""


@pytest.mark.parametrize(
    "gene,synonyms,expected",
    [
        ("ABC1", None, '"ABC1"[Title/Abstract]'),
        ("ABC1", ["Gene ABC", "ABCD"], '"ABC1"[Title/Abstract] OR "Gene ABC"[Title/Abstract] OR "ABCD"[Title/Abstract]'),
    ],
)
def test_build_gene_query(gene, synonyms, expected):
    assert build_gene_query(gene, synonyms) == expected


def test_collect_and_write_metadata(tmp_path: Path):
    client = DummyPubMedClient(["12345"], SAMPLE_XML)
    collector = LiteratureCollector(client)
    results = collector.collect("ABC1")
    assert len(results) == 1
    record = results[0]
    assert record.pmid == "12345"
    assert record.first_author == "Jane Doe"
    assert record.publication_year == 2020
    assert record.journal == "Genetics Journal"
    assert record.xml_available is True
    assert record.patient_level_evidence is True

    output_json = tmp_path / "results.json"
    write_metadata(results, output_json, fmt="json")
    assert output_json.exists()

    output_csv = tmp_path / "results.csv"
    write_metadata(results, output_csv, fmt="csv")
    assert output_csv.read_text(encoding="utf-8").startswith("pmid,title")

    output_sqlite = tmp_path / "results.sqlite"
    write_metadata(results, output_sqlite, fmt="sqlite")
    assert output_sqlite.exists()


def test_build_gene_query_requires_term():
    with pytest.raises(ValueError):
        build_gene_query("", [])


def test_pmcid_detection_with_pmc_idtype(tmp_path: Path):
    """Test that PMCID detection works with IdType='pmc' (newer PubMed format)."""
    client = DummyPubMedClient(["67890"], SAMPLE_XML_PMC_FORMAT)
    collector = LiteratureCollector(client)
    results = collector.collect("XYZ")
    assert len(results) == 1
    record = results[0]
    assert record.pmid == "67890"
    assert record.pmcid == "PMC123456"
    assert record.xml_available is True
    assert record.doi == "10.1234/example.doi"
    assert record.pmc_url == "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC123456/"
    assert record.pmc_pdf_url == "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC123456/pdf/"
