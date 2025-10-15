from genephenextract.pubmed import PubMedClient

SAMPLE_XML = """
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <PMID>12345</PMID>
      <Article>
        <ArticleTitle>Sample Title</ArticleTitle>
        <Journal>
          <JournalIssue>
            <PubDate>
              <Year>2021</Year>
              <Month>Feb</Month>
              <Day>10</Day>
            </PubDate>
          </JournalIssue>
          <Title>Example Journal</Title>
        </Journal>
        <Abstract>
          <AbstractText>First sentence.</AbstractText>
          <AbstractText>Second sentence.</AbstractText>
        </Abstract>
      </Article>
    </MedlineCitation>
  </PubmedArticle>
</PubmedArticleSet>
""".strip()


class StubPubMedClient(PubMedClient):
    def __init__(self) -> None:
        super().__init__()

    def _request(self, endpoint, params):  # type: ignore[override]
        assert endpoint == "efetch.fcgi"
        return SAMPLE_XML


def test_fetch_details_parses_metadata():
    client = StubPubMedClient()
    details = client.fetch_details(["12345"])
    assert details["12345"]["title"] == "Sample Title"
    assert details["12345"]["journal"] == "Example Journal"
    assert details["12345"]["publication_date"] == "2021-02-10"
    assert details["12345"]["abstract"] == "First sentence.\nSecond sentence."


PMC_SUPPLEMENT_XML = """
<article xmlns:xlink="http://www.w3.org/1999/xlink">
  <front>
    <article-meta>
      <title-group>
        <article-title>Supplement Title</article-title>
      </title-group>
      <abstract>
        <p>Supplement abstract.</p>
      </abstract>
    </article-meta>
  </front>
  <body>
    <sec>
      <title>Introduction</title>
      <p>Body text.</p>
    </sec>
  </body>
  <back>
    <supplementary-material id="sup1">
      <label>Supplementary Table 1</label>
      <media xlink:href="sup1.docx" />
    </supplementary-material>
  </back>
</article>
""".strip()


class SupplementStubPubMedClient(PubMedClient):
    def __init__(self) -> None:
        super().__init__()

    def _request(self, endpoint, params):  # type: ignore[override]
        assert endpoint == "efetch.fcgi"
        assert params["db"] == "pmc"
        return PMC_SUPPLEMENT_XML


def test_fetch_pmc_full_text_includes_supplementary(monkeypatch):
    captured = {}

    def fake_download(pmcid, href, label, timeout):  # type: ignore[override]
        captured["called_with"] = (pmcid, href, label, timeout)
        return "Supplemental content"

    monkeypatch.setattr(
        "genephenextract.pubmed._download_supplementary_text",
        fake_download,
    )

    client = SupplementStubPubMedClient()
    text = client.fetch_pmc_full_text("PMC123")

    assert text is not None
    assert "## Supplementary Materials" in text
    assert "### Supplementary Table 1" in text
    assert "Supplemental content" in text
    assert captured["called_with"][1] == "sup1.docx"
