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
