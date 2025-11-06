"""
Unit tests for PdfExtractor with a real PDF path.
These tests will be skipped if SAMPLE_PDF_PATH is not provided.
"""

import os

import pytest

from src.core.extractor import PdfExtractor, ExtractedDocument

SAMPLE_PDF = os.environ.get("SAMPLE_PDF_PATH", "").strip()


@pytest.mark.skipif(not SAMPLE_PDF, reason="Set SAMPLE_PDF_PATH to a valid PDF to run this test.")
def test_pdf_extractor_loads_and_returns_blocks():
    extractor = PdfExtractor()
    doc: ExtractedDocument = extractor.load(SAMPLE_PDF)

    assert isinstance(doc.blocks, list)
    assert isinstance(doc.meta, dict)
    assert doc.meta.get("engine") == "pymupdf4llm"
    assert doc.meta.get("pages") == 1
    assert hasattr(doc, "raw_markdown")
    assert hasattr(doc, "full_text")
    assert isinstance(doc.raw_markdown, str)
    assert isinstance(doc.full_text, str)


@pytest.mark.skipif(not SAMPLE_PDF, reason="Set SAMPLE_PDF_PATH to a valid PDF to run this test.")
def test_pdf_extractor_blocks_have_metadata():
    extractor = PdfExtractor()
    doc: ExtractedDocument = extractor.load(SAMPLE_PDF)

    # Check that blocks have metadata
    if doc.blocks:
        first_block = doc.blocks[0]
        assert hasattr(first_block, "text")
        assert hasattr(first_block, "metadata")
        assert isinstance(first_block.metadata, dict)
        assert "type" in first_block.metadata


@pytest.mark.skipif(not SAMPLE_PDF, reason="Set SAMPLE_PDF_PATH to a valid PDF to run this test.")
def test_pdf_extractor_text_extraction():
    extractor = PdfExtractor()
    doc: ExtractedDocument = extractor.load(SAMPLE_PDF)

    # Verify text was extracted
    assert doc.full_text is not None
    assert len(doc.full_text) > 0

    # Verify markdown was generated
    assert doc.raw_markdown is not None
    assert len(doc.raw_markdown) > 0
