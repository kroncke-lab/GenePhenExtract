import io
import zipfile

import xml.etree.ElementTree as ET

from genephenextract.pubmed import PubMedClient, _decode_supplementary_bytes, _extract_docx_text

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


def _build_minimal_docx(paragraphs):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(
            "[Content_Types].xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>
""",
        )
        archive.writestr(
            "_rels/.rels",
            """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>
""",
        )
        archive.writestr(
            "word/_rels/document.xml.rels",
            """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>
""",
        )

        ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
        document = ET.Element(f"{{{ns}}}document")
        body = ET.SubElement(document, f"{{{ns}}}body")
        for paragraph in paragraphs:
            p = ET.SubElement(body, f"{{{ns}}}p")
            r = ET.SubElement(p, f"{{{ns}}}r")
            t = ET.SubElement(r, f"{{{ns}}}t")
            t.text = paragraph
        document_xml = ET.tostring(document, encoding="utf-8", xml_declaration=True)
        archive.writestr("word/document.xml", document_xml)
    buffer.seek(0)
    return buffer.getvalue()


def test_extract_docx_text_returns_paragraphs():
    docx_bytes = _build_minimal_docx(["First paragraph", "Second paragraph"])
    text = _extract_docx_text(docx_bytes)
    assert text == "First paragraph\nSecond paragraph"


def test_decode_supplementary_bytes_supports_plain_text():
    payload = b"Line one\nLine two"
    text = _decode_supplementary_bytes("table.txt", payload)
    assert "Line two" in text
