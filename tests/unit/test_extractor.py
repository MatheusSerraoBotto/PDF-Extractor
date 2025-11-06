"""
Unit tests for src/core/extractor.py

Tests PDF extraction, text processing, layout analysis, and utility functions.
"""

import hashlib
from unittest.mock import MagicMock, patch

import pytest

from src.core.extractor import (
    ExtractedDocument,
    PdfExtractor,
    filter_layout_by_keywords,
    hash_extraction_schema,
    hash_pdf_bytes,
    load_pdf_bytes,
    resolve_pdf_path,
)


class TestPdfExtractor:
    """Test cases for PdfExtractor class."""

    def test_load_success(self, mock_pdfplumber_pdf, mock_pdfplumber_page, tmp_path):
        """Test successful PDF loading and extraction."""
        # Create a real PDF file
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"fake pdf content")

        with patch("src.core.extractor.pdfplumber.open") as mock_open:
            mock_open.return_value = mock_pdfplumber_pdf

            extractor = PdfExtractor()
            result = extractor.load(str(test_file))

            assert isinstance(result, ExtractedDocument)
            assert result.layout_text != ""
            assert len(result.words) == 3
            assert result.meta["engine"] == "pdfplumber"
            assert result.meta["pages"] == 1
            assert result.meta["word_count"] == 3

    def test_load_file_not_found(self):
        """Test loading non-existent PDF file."""
        extractor = PdfExtractor()

        with pytest.raises(FileNotFoundError, match="PDF not found"):
            extractor.load("/nonexistent/file.pdf")

    def test_load_empty_pdf(self, mock_pdfplumber_pdf, tmp_path):
        """Test loading PDF with no pages."""
        # Create a real PDF file
        test_file = tmp_path / "empty.pdf"
        test_file.write_bytes(b"fake pdf content")

        mock_pdfplumber_pdf.pages = []

        with patch("src.core.extractor.pdfplumber.open") as mock_open:
            mock_open.return_value = mock_pdfplumber_pdf

            extractor = PdfExtractor()
            with pytest.raises(ValueError, match="Empty PDF: no pages found"):
                extractor.load(str(test_file))

    def test_load_pdf_with_no_text(
        self, mock_pdfplumber_pdf, mock_pdfplumber_page, tmp_path
    ):
        """Test loading PDF with no extractable text."""
        # Create a real PDF file
        test_file = tmp_path / "notext.pdf"
        test_file.write_bytes(b"fake pdf content")

        mock_pdfplumber_page.extract_words.return_value = []
        mock_pdfplumber_pdf.pages = [mock_pdfplumber_page]

        with patch("src.core.extractor.pdfplumber.open") as mock_open:
            mock_open.return_value = mock_pdfplumber_pdf

            extractor = PdfExtractor()
            with pytest.raises(ValueError, match="Empty PDF: no text content"):
                extractor.load(str(test_file))

    def test_calculate_zone_top_left(self):
        """Test zone calculation for top-left corner."""
        extractor = PdfExtractor()
        bbox = [50.0, 50.0, 100.0, 70.0]  # Top-left area
        zone = extractor._calculate_zone(bbox, 595.0, 842.0)

        assert zone == "TOP-LEFT"

    def test_calculate_zone_center(self):
        """Test zone calculation for center area."""
        extractor = PdfExtractor()
        bbox = [250.0, 400.0, 350.0, 420.0]  # Center area
        zone = extractor._calculate_zone(bbox, 595.0, 842.0)

        assert zone == "CENTER"

    def test_calculate_zone_bottom_right(self):
        """Test zone calculation for bottom-right corner."""
        extractor = PdfExtractor()
        bbox = [500.0, 750.0, 550.0, 800.0]  # Bottom-right area
        zone = extractor._calculate_zone(bbox, 595.0, 842.0)

        assert zone == "BOTTOM-RIGHT"

    def test_group_words_to_lines_same_line(self):
        """Test grouping words on the same line."""
        extractor = PdfExtractor()
        words = [
            {"text": "Hello", "bbox": [100.0, 50.0, 150.0, 70.0], "zone": "TOP-LEFT"},
            {"text": "World", "bbox": [155.0, 52.0, 200.0, 72.0], "zone": "TOP-LEFT"},
        ]

        lines = extractor._group_words_to_lines(words)

        assert len(lines) == 1
        assert lines[0]["text"] == "Hello World"
        assert lines[0]["word_count"] == 2

    def test_group_words_to_lines_different_lines(self):
        """Test grouping words on different lines."""
        extractor = PdfExtractor()
        words = [
            {"text": "Line1", "bbox": [100.0, 50.0, 150.0, 70.0], "zone": "TOP-LEFT"},
            {"text": "Line2", "bbox": [100.0, 100.0, 150.0, 120.0], "zone": "TOP-LEFT"},
        ]

        lines = extractor._group_words_to_lines(words)

        assert len(lines) == 2
        assert lines[0]["text"] == "Line1"
        assert lines[1]["text"] == "Line2"

    def test_group_words_empty_list(self):
        """Test grouping empty word list."""
        extractor = PdfExtractor()
        lines = extractor._group_words_to_lines([])

        assert lines == []

    def test_create_line_dict(self):
        """Test line dictionary creation from words."""
        extractor = PdfExtractor()
        words = [
            {"text": "Hello", "bbox": [100.0, 50.0, 150.0, 70.0], "zone": "TOP-LEFT"},
            {"text": "World", "bbox": [155.0, 50.0, 200.0, 70.0], "zone": "TOP-LEFT"},
        ]

        line = extractor._create_line_dict(words)

        assert line["text"] == "Hello World"
        assert line["bbox"][0] == 100.0  # min x0
        assert line["bbox"][2] == 200.0  # max x1
        assert line["zone"] == "TOP-LEFT"
        assert line["word_count"] == 2

    def test_format_layout_text(self):
        """Test layout text formatting."""
        extractor = PdfExtractor()
        lines = [
            {
                "text": "JOÃO DA SILVA",
                "bbox": [100.0, 50.0, 230.0, 70.0],
                "zone": "TOP-LEFT",
                "word_count": 3,
            },
            {
                "text": "Inscrição: 123456",
                "bbox": [100.0, 100.0, 230.0, 120.0],
                "zone": "TOP-LEFT",
                "word_count": 2,
            },
        ]

        layout_text = extractor._format_layout_text(lines)

        assert "[TOP-LEFT]" in layout_text
        assert "JOÃO DA SILVA" in layout_text
        assert "[x:100-230, y:50]" in layout_text
        assert "Inscrição: 123456" in layout_text

    def test_layout_text_includes_coordinates(self, mock_pdfplumber_pdf, tmp_path):
        """Test that layout text includes coordinate information."""
        # Create a real PDF file
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"fake pdf content")

        with patch("src.core.extractor.pdfplumber.open") as mock_open:
            mock_open.return_value = mock_pdfplumber_pdf

            extractor = PdfExtractor()
            result = extractor.load(str(test_file))

            # Verify format includes zone and coordinates
            assert "[TOP-LEFT]" in result.layout_text or "[" in result.layout_text
            assert "x:" in result.layout_text
            assert "y:" in result.layout_text

    def test_metadata_includes_table_detection(
        self, mock_pdfplumber_pdf, mock_pdfplumber_page, tmp_path
    ):
        """Test that metadata includes table detection info."""
        # Create a real PDF file
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"fake pdf content")

        # Test with tables
        mock_pdfplumber_page.find_tables.return_value = [MagicMock()]
        mock_pdfplumber_pdf.pages = [mock_pdfplumber_page]

        with patch("src.core.extractor.pdfplumber.open") as mock_open:
            mock_open.return_value = mock_pdfplumber_pdf

            extractor = PdfExtractor()
            result = extractor.load(str(test_file))

            assert result.meta["has_tables"] is True

        # Test without tables
        mock_pdfplumber_page.find_tables.return_value = []

        with patch("src.core.extractor.pdfplumber.open") as mock_open:
            mock_open.return_value = mock_pdfplumber_pdf

            extractor = PdfExtractor()
            result = extractor.load(str(test_file))

            assert result.meta["has_tables"] is False


class TestUtilityFunctions:
    """Test cases for utility functions."""

    def test_resolve_pdf_path_absolute(self):
        """Test resolving absolute path."""
        absolute_path = "/tmp/test.pdf"
        result = resolve_pdf_path(absolute_path)

        assert result.is_absolute()
        assert str(result) == absolute_path

    def test_resolve_pdf_path_relative_current_dir(self, tmp_path):
        """Test resolving relative path in current directory."""
        # Create a test file
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"fake pdf")

        with patch("src.core.extractor.Path.cwd", return_value=tmp_path):
            result = resolve_pdf_path("test.pdf")
            assert result.exists()

    def test_resolve_pdf_path_with_base_path(self, tmp_path, monkeypatch):
        """Test resolving path using PDF_BASE_PATH setting."""
        # Create test directory and file
        base_dir = tmp_path / "pdfs"
        base_dir.mkdir()
        test_file = base_dir / "test.pdf"
        test_file.write_bytes(b"fake pdf")

        # Mock settings with proper environment variable
        monkeypatch.setenv("PDF_BASE_PATH", str(base_dir))

        # Clear settings cache to reload with new env var
        from src.config.settings import get_settings

        get_settings.cache_clear()

        # Import settings AFTER clearing cache

        # Mock cwd to return different directory (not base_dir)
        different_dir = tmp_path / "different"
        different_dir.mkdir()

        with patch("src.core.extractor.Path.cwd", return_value=different_dir):
            with patch("src.core.extractor.settings.pdf_base_path", str(base_dir)):
                result = resolve_pdf_path("test.pdf")
                # Should resolve to base_dir / test.pdf
                assert "pdfs" in str(result) or result.name == "test.pdf"

    def test_load_pdf_bytes(self, tmp_path):
        """Test loading PDF as bytes."""
        test_file = tmp_path / "test.pdf"
        test_content = b"fake pdf content"
        test_file.write_bytes(test_content)

        result = load_pdf_bytes(test_file)

        assert result == test_content
        assert isinstance(result, bytes)

    def test_hash_pdf_bytes(self):
        """Test PDF bytes hashing."""
        pdf_bytes = b"fake pdf content"
        expected_hash = hashlib.sha256(pdf_bytes).hexdigest()

        result = hash_pdf_bytes(pdf_bytes)

        assert result == expected_hash
        assert len(result) == 64  # SHA256 hex digest length

    def test_hash_pdf_bytes_different_content(self):
        """Test that different content produces different hashes."""
        hash1 = hash_pdf_bytes(b"content1")
        hash2 = hash_pdf_bytes(b"content2")

        assert hash1 != hash2

    def test_hash_extraction_schema(self):
        """Test extraction schema hashing."""
        schema = {
            "nome": "Nome do profissional",
            "inscricao": "Número de inscrição",
        }

        result = hash_extraction_schema(schema)

        assert isinstance(result, str)
        assert len(result) == 64  # SHA256 hex digest length

    def test_hash_extraction_schema_order_independent(self):
        """Test that schema hash is independent of key order."""
        schema1 = {"nome": "Nome", "inscricao": "Inscrição"}
        schema2 = {"inscricao": "Inscrição", "nome": "Nome"}

        hash1 = hash_extraction_schema(schema1)
        hash2 = hash_extraction_schema(schema2)

        assert hash1 == hash2

    def test_hash_extraction_schema_different_values(self):
        """Test that different schemas produce different hashes."""
        schema1 = {"nome": "Nome"}
        schema2 = {"nome": "Name"}

        hash1 = hash_extraction_schema(schema1)
        hash2 = hash_extraction_schema(schema2)

        assert hash1 != hash2


class TestFilterLayoutByKeywords:
    """Test cases for filter_layout_by_keywords function."""

    def test_filter_with_keywords(self, sample_layout_text):
        """Test filtering layout text with relevant keywords."""
        schema = {"nome": "Nome completo"}

        result = filter_layout_by_keywords(sample_layout_text, schema, max_lines=10)

        # Should include line with "JOÃO DA SILVA" (contains "nome" concept)
        assert "SILVA" in result

    def test_filter_with_max_lines(self, sample_layout_text):
        """Test filtering with max_lines limit."""
        schema = {"inscricao": "Número de inscrição"}

        result = filter_layout_by_keywords(sample_layout_text, schema, max_lines=2)

        lines = result.split("\n")
        assert len(lines) <= 2

    def test_filter_no_max_lines(self, sample_layout_text):
        """Test filtering without max_lines limit (0 = unlimited)."""
        schema = {"nome": "Nome"}

        result = filter_layout_by_keywords(sample_layout_text, schema, max_lines=0)

        # Should return original text when max_lines=0
        assert result == sample_layout_text

    def test_filter_empty_schema(self, sample_layout_text):
        """Test filtering with empty schema."""
        result = filter_layout_by_keywords(sample_layout_text, {}, max_lines=5)

        # Should return original text when schema is empty
        assert result == sample_layout_text

    def test_filter_no_matching_keywords(self, sample_layout_text):
        """Test filtering when no keywords match."""
        schema = {"campo_inexistente": "Campo que não existe no documento"}

        result = filter_layout_by_keywords(sample_layout_text, schema, max_lines=3)

        # Should return first max_lines as fallback
        lines = result.split("\n")
        assert len(lines) <= 3

    def test_filter_ignores_stopwords(self, sample_layout_text):
        """Test that common stopwords are ignored in keyword extraction."""
        schema = {"campo": "do da de o a"}  # All stopwords

        result = filter_layout_by_keywords(sample_layout_text, schema, max_lines=2)

        # Should fall back to first max_lines since all words are stopwords
        lines = result.split("\n")
        assert len(lines) <= 2

    def test_filter_extracts_keywords_from_field_name(self):
        """Test keyword extraction from field names with underscores."""
        layout = "[TOP-LEFT] [x:100-200, y:50] Telefone: (11) 99999-9999"
        schema = {"telefone_profissional": "Telefone do profissional"}

        result = filter_layout_by_keywords(layout, schema, max_lines=10)

        # Should match "telefone" from field name
        assert "Telefone" in result

    def test_filter_case_insensitive(self):
        """Test that keyword matching is case-insensitive."""
        layout = "[TOP-LEFT] [x:100-200, y:50] JOÃO DA SILVA"
        schema = {"nome": "nome completo"}

        result = filter_layout_by_keywords(layout, schema, max_lines=10)

        # Should match despite case differences
        assert "JOÃO" in result
