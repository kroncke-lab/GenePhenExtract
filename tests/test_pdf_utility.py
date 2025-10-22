"""Tests for PDFUtility module."""

import io
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from PDFUtility import PDFParserError, extract_text_from_pdf, download_pdf


class TestExtractTextFromPDF:
    """Tests for extract_text_from_pdf function."""

    def test_extract_text_from_nonexistent_file(self, tmp_path):
        """Should raise PDFParserError for non-existent file."""
        non_existent = tmp_path / "does_not_exist.pdf"
        with pytest.raises(PDFParserError, match="PDF file not found"):
            extract_text_from_pdf(non_existent)

    def test_extract_text_from_valid_pdf(self, tmp_path):
        """Should extract text from a valid PDF."""
        # Create a minimal PDF
        pdf_path = tmp_path / "test.pdf"

        # This is a minimal valid PDF structure
        minimal_pdf = b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj
2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj
3 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
/Contents 4 0 R
/Resources <<
/Font <<
/F1 <<
/Type /Font
/Subtype /Type1
/BaseFont /Helvetica
>>
>>
>>
>>
endobj
4 0 obj
<<
/Length 44
>>
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
<<
/Size 5
/Root 1 0 R
>>
startxref
410
%%EOF
"""
        pdf_path.write_bytes(minimal_pdf)

        text = extract_text_from_pdf(pdf_path)
        assert text is not None
        assert len(text) > 0

    def test_extract_text_with_string_path(self, tmp_path):
        """Should handle string paths in addition to Path objects."""
        pdf_path = tmp_path / "test.pdf"

        # Write minimal PDF
        minimal_pdf = b"%PDF-1.4\n%%EOF"
        pdf_path.write_bytes(minimal_pdf)

        # Should not raise when given a string path
        # (may raise PDFParserError if content is invalid, but not a path error)
        try:
            extract_text_from_pdf(str(pdf_path))
        except PDFParserError as e:
            # Expected if minimal PDF is too minimal
            assert "Failed to parse PDF" in str(e) or "No text content" in str(e)

    @patch("PDFUtility.PdfReader", None)
    def test_extract_text_when_pypdf_not_installed(self, tmp_path):
        """Should raise ImportError when pypdf is not available."""
        pdf_path = tmp_path / "test.pdf"
        pdf_path.touch()

        with pytest.raises(ImportError, match="pypdf is not installed"):
            extract_text_from_pdf(pdf_path)


class TestDownloadPDF:
    """Tests for download_pdf function."""

    def test_download_pdf_creates_parent_directories(self, tmp_path):
        """Should create parent directories if they don't exist."""
        nested_path = tmp_path / "subdir" / "nested" / "file.pdf"

        with patch("urllib.request.urlretrieve") as mock_retrieve:
            mock_retrieve.return_value = None
            download_pdf("http://example.com/test.pdf", nested_path)

            assert nested_path.parent.exists()
            mock_retrieve.assert_called_once_with("http://example.com/test.pdf", nested_path)

    def test_download_pdf_returns_path(self, tmp_path):
        """Should return the Path object of downloaded file."""
        output_path = tmp_path / "output.pdf"

        with patch("urllib.request.urlretrieve") as mock_retrieve:
            mock_retrieve.return_value = None
            result = download_pdf("http://example.com/test.pdf", output_path)

            assert isinstance(result, Path)
            assert result == output_path

    def test_download_pdf_handles_network_errors(self, tmp_path):
        """Should raise PDFParserError on network failures."""
        output_path = tmp_path / "output.pdf"

        with patch("urllib.request.urlretrieve") as mock_retrieve:
            mock_retrieve.side_effect = Exception("Network error")

            with pytest.raises(PDFParserError, match="Failed to download PDF"):
                download_pdf("http://example.com/test.pdf", output_path)

    def test_download_pdf_accepts_string_path(self, tmp_path):
        """Should accept string paths in addition to Path objects."""
        output_path = str(tmp_path / "output.pdf")

        with patch("urllib.request.urlretrieve") as mock_retrieve:
            mock_retrieve.return_value = None
            result = download_pdf("http://example.com/test.pdf", output_path)

            assert isinstance(result, Path)
            assert str(result) == output_path
