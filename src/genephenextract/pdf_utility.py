"""Utilities for parsing PDF files."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Union

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None  # type: ignore

logger = logging.getLogger(__name__)


class PDFParserError(RuntimeError):
    """Raised when PDF parsing fails."""


def extract_text_from_pdf(pdf_path: Union[str, Path]) -> str:
    """
    Extract text content from a PDF file.
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        Extracted text content
        
    Raises:
        PDFParserError: If PDF cannot be parsed
    """
    if PdfReader is None:
        msg = "pypdf is not installed. Install it with `pip install pypdf`."
        raise ImportError(msg)
    
    path = Path(pdf_path)
    if not path.exists():
        raise PDFParserError(f"PDF file not found: {path}")
    
    try:
        reader = PdfReader(str(path))
        text_parts = []
        
        for page_num, page in enumerate(reader.pages, 1):
            try:
                text = page.extract_text()
                if text.strip():
                    text_parts.append(text.strip())
            except Exception as exc:
                logger.warning("Failed to extract text from page %d: %s", page_num, exc)
                continue
        
        if not text_parts:
            raise PDFParserError(f"No text content extracted from PDF: {path}")
        
        full_text = "\n\n".join(text_parts)
        logger.info("Extracted %d characters from %d pages of %s", 
                   len(full_text), len(reader.pages), path.name)
        return full_text
        
    except Exception as exc:
        raise PDFParserError(f"Failed to parse PDF {path}: {exc}") from exc


def download_pdf(url: str, output_path: Union[str, Path]) -> Path:
    """
    Download a PDF from a URL.
    
    Args:
        url: URL of the PDF
        output_path: Where to save the PDF
        
    Returns:
        Path to the downloaded PDF
    """
    import urllib.request
    
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        urllib.request.urlretrieve(url, output)
        logger.info("Downloaded PDF from %s to %s", url, output)
        return output
    except Exception as exc:
        raise PDFParserError(f"Failed to download PDF from {url}: {exc}") from exc
