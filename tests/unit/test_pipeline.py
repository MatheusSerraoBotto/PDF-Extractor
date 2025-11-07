"""
Unit tests for src/core/pipeline.py

Tests the extraction pipeline orchestration, cache integration, and error handling.
"""

from unittest.mock import MagicMock, patch

import pytest

from src.core.extractor import ExtractedDocument
from src.core.pipeline import run_extraction
from src.models.schema import ExtractionRequest, ExtractionResult


class TestRunExtraction:
    """Test cases for run_extraction pipeline function."""

    def test_run_extraction_missing_pdf_path(self):
        """Test pipeline raises ValueError when pdf_path is missing."""
        request = ExtractionRequest(
            label="test",
            extraction_schema={"nome": "Nome"},
            pdf_path="",
        )

        with pytest.raises(ValueError, match="Either pdf_path or pdf_bytes must be provided"):
            run_extraction(request)

    @patch("src.core.pipeline.CacheClient")
    @patch("src.core.pipeline.resolve_pdf_path")
    def test_run_extraction_file_not_found(self, mock_resolve, mock_cache_class):
        """Test pipeline raises FileNotFoundError for missing PDF."""
        mock_resolve.side_effect = FileNotFoundError("PDF not found")

        request = ExtractionRequest(
            label="test",
            extraction_schema={"nome": "Nome"},
            pdf_path="/nonexistent/file.pdf",
        )

        with pytest.raises(FileNotFoundError):
            run_extraction(request)

    @patch("src.core.pipeline.CacheClient")
    @patch("src.core.pipeline.resolve_pdf_path")
    @patch("src.core.pipeline.load_pdf_bytes")
    def test_run_extraction_cache_hit(
        self, mock_load_bytes, mock_resolve, mock_cache_class, tmp_path
    ):
        """Test pipeline returns cached result when available."""
        # Setup mocks
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"fake pdf")
        mock_resolve.return_value = test_file
        mock_load_bytes.return_value = b"fake pdf"

        cached_result = {
            "label": "test",
            "fields": {"nome": "JOÃO DA SILVA"},
            "meta": {"cache_hit": False},
        }

        mock_cache = MagicMock()
        mock_cache.get_json.return_value = cached_result
        mock_cache_class.return_value = mock_cache

        request = ExtractionRequest(
            label="test",
            extraction_schema={"nome": "Nome"},
            pdf_path="test.pdf",
        )

        result = run_extraction(request, use_cache=True)

        assert isinstance(result, ExtractionResult)
        assert result.fields["nome"] == "JOÃO DA SILVA"
        assert result.meta["cache_hit"] is True
        mock_cache.get_json.assert_called_once()

    @patch("src.core.pipeline.CacheClient")
    @patch("src.core.pipeline.PdfExtractor")
    @patch("src.core.pipeline.llm_orchestrator.extract_fields")
    @patch("src.core.pipeline.resolve_pdf_path")
    @patch("src.core.pipeline.load_pdf_bytes")
    def test_run_extraction_cache_miss(
        self,
        mock_load_bytes,
        mock_resolve,
        mock_extract_fields,
        mock_extractor_class,
        mock_cache_class,
        tmp_path,
    ):
        """Test pipeline executes full extraction on cache miss."""
        # Setup file mocks
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"fake pdf")
        mock_resolve.return_value = test_file
        mock_load_bytes.return_value = b"fake pdf"

        # Setup cache mock (cache miss)
        mock_cache = MagicMock()
        mock_cache.get_json.return_value = None
        mock_cache.set_json.return_value = True
        mock_cache_class.return_value = mock_cache

        # Setup extractor mock
        mock_doc = ExtractedDocument(
            layout_text="[TOP-LEFT] [x:100-200, y:50] JOÃO DA SILVA",
            words=[],
            meta={"source": str(test_file), "engine": "pdfplumber", "pages": 1},
        )
        mock_extractor = MagicMock()
        mock_extractor.load.return_value = mock_doc
        mock_extractor_class.return_value = mock_extractor

        # Setup LLM mock
        mock_extract_fields.return_value = {
            "nome": {"value": "JOÃO DA SILVA", "details": {"source": "openai"}},
        }

        request = ExtractionRequest(
            label="test",
            extraction_schema={"nome": "Nome"},
            pdf_path="test.pdf",
        )

        result = run_extraction(request, use_cache=True)

        assert isinstance(result, ExtractionResult)
        assert result.fields["nome"] == "JOÃO DA SILVA"
        assert result.meta["cache_hit"] is False
        mock_cache.set_json.assert_called_once()

    @patch("src.core.pipeline.CacheClient")
    @patch("src.core.pipeline.PdfExtractor")
    @patch("src.core.pipeline.llm_orchestrator.extract_fields")
    @patch("src.core.pipeline.resolve_pdf_path")
    @patch("src.core.pipeline.load_pdf_bytes")
    def test_run_extraction_use_cache_false(
        self,
        mock_load_bytes,
        mock_resolve,
        mock_extract_fields,
        mock_extractor_class,
        mock_cache_class,
        tmp_path,
    ):
        """Test pipeline bypasses cache when use_cache=False."""
        # Setup file mocks
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"fake pdf")
        mock_resolve.return_value = test_file
        mock_load_bytes.return_value = b"fake pdf"

        # Setup cache mock
        mock_cache = MagicMock()
        mock_cache.get_json.return_value = {"label": "cached"}  # Should be ignored
        mock_cache.set_json.return_value = True
        mock_cache_class.return_value = mock_cache

        # Setup extractor mock
        mock_doc = ExtractedDocument(
            layout_text="[TOP-LEFT] JOÃO",
            words=[],
            meta={"source": str(test_file), "engine": "pdfplumber", "pages": 1},
        )
        mock_extractor = MagicMock()
        mock_extractor.load.return_value = mock_doc
        mock_extractor_class.return_value = mock_extractor

        # Setup LLM mock
        mock_extract_fields.return_value = {
            "nome": {"value": "FRESH EXTRACTION", "details": {"source": "openai"}},
        }

        request = ExtractionRequest(
            label="test",
            extraction_schema={"nome": "Nome"},
            pdf_path="test.pdf",
        )

        result = run_extraction(request, use_cache=False)

        assert result.fields["nome"] == "FRESH EXTRACTION"
        assert result.meta["cache_hit"] is False
        mock_cache.get_json.assert_not_called()  # Should not check cache

    @patch("src.core.pipeline.CacheClient")
    @patch("src.core.pipeline.PdfExtractor")
    @patch("src.core.pipeline.llm_orchestrator.extract_fields")
    @patch("src.core.pipeline.resolve_pdf_path")
    @patch("src.core.pipeline.load_pdf_bytes")
    def test_run_extraction_includes_timings(
        self,
        mock_load_bytes,
        mock_resolve,
        mock_extract_fields,
        mock_extractor_class,
        mock_cache_class,
        tmp_path,
    ):
        """Test pipeline includes timing information in result."""
        # Setup mocks
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"fake pdf")
        mock_resolve.return_value = test_file
        mock_load_bytes.return_value = b"fake pdf"

        mock_cache = MagicMock()
        mock_cache.get_json.return_value = None
        mock_cache_class.return_value = mock_cache

        mock_doc = ExtractedDocument(
            layout_text="test", words=[], meta={"source": str(test_file), "pages": 1}
        )
        mock_extractor = MagicMock()
        mock_extractor.load.return_value = mock_doc
        mock_extractor_class.return_value = mock_extractor

        mock_extract_fields.return_value = {
            "nome": {"value": "Test", "details": {"source": "openai"}},
        }

        request = ExtractionRequest(
            label="test",
            extraction_schema={"nome": "Nome"},
            pdf_path="test.pdf",
        )

        result = run_extraction(request)

        assert "timings_seconds" in result.meta
        assert "extract" in result.meta["timings_seconds"]
        assert "llm" in result.meta["timings_seconds"]
        assert "total" in result.meta["timings_seconds"]
        assert all(
            isinstance(t, float) for t in result.meta["timings_seconds"].values()
        )

    @patch("src.core.pipeline.CacheClient")
    @patch("src.core.pipeline.PdfExtractor")
    @patch("src.core.pipeline.llm_orchestrator.extract_fields")
    @patch("src.core.pipeline.resolve_pdf_path")
    @patch("src.core.pipeline.load_pdf_bytes")
    def test_run_extraction_includes_trace_info(
        self,
        mock_load_bytes,
        mock_resolve,
        mock_extract_fields,
        mock_extractor_class,
        mock_cache_class,
        tmp_path,
    ):
        """Test pipeline includes trace information in metadata."""
        # Setup mocks
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"fake pdf")
        mock_resolve.return_value = test_file
        mock_load_bytes.return_value = b"fake pdf"

        mock_cache = MagicMock()
        mock_cache.get_json.return_value = None
        mock_cache_class.return_value = mock_cache

        mock_doc = ExtractedDocument(
            layout_text="test", words=[], meta={"source": str(test_file), "pages": 1}
        )
        mock_extractor = MagicMock()
        mock_extractor.load.return_value = mock_doc
        mock_extractor_class.return_value = mock_extractor

        # LLM returns some resolved, some unresolved
        mock_extract_fields.return_value = {
            "nome": {"value": "JOÃO", "details": {"source": "openai"}},
            "inscricao": {"value": None, "details": {"source": "openai"}},
        }

        request = ExtractionRequest(
            label="test",
            extraction_schema={"nome": "Nome", "inscricao": "Inscrição"},
            pdf_path="test.pdf",
        )

        result = run_extraction(request)

        assert "trace" in result.meta
        assert "llm_resolved" in result.meta["trace"]
        assert "unresolved" in result.meta["trace"]
        assert "nome" in result.meta["trace"]["llm_resolved"]
        assert "inscricao" in result.meta["trace"]["unresolved"]

    @patch("src.core.pipeline.CacheClient")
    @patch("src.core.pipeline.PdfExtractor")
    @patch("src.core.pipeline.llm_orchestrator.extract_fields")
    @patch("src.core.pipeline.resolve_pdf_path")
    @patch("src.core.pipeline.load_pdf_bytes")
    def test_run_extraction_includes_cache_key(
        self,
        mock_load_bytes,
        mock_resolve,
        mock_extract_fields,
        mock_extractor_class,
        mock_cache_class,
        tmp_path,
    ):
        """Test pipeline includes cache key in metadata."""
        # Setup mocks
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"fake pdf")
        mock_resolve.return_value = test_file
        mock_load_bytes.return_value = b"fake pdf"

        mock_cache = MagicMock()
        mock_cache.get_json.return_value = None
        mock_cache_class.return_value = mock_cache

        mock_doc = ExtractedDocument(
            layout_text="test", words=[], meta={"source": str(test_file), "pages": 1}
        )
        mock_extractor = MagicMock()
        mock_extractor.load.return_value = mock_doc
        mock_extractor_class.return_value = mock_extractor

        mock_extract_fields.return_value = {
            "nome": {"value": "Test", "details": {"source": "openai"}},
        }

        request = ExtractionRequest(
            label="test_label",
            extraction_schema={"nome": "Nome"},
            pdf_path="test.pdf",
        )

        result = run_extraction(request)

        assert "cache_key" in result.meta
        assert result.meta["cache_key"].startswith("extract:test_label:")

    @patch("src.core.pipeline.CacheClient")
    @patch("src.core.pipeline.PdfExtractor")
    @patch("src.core.pipeline.llm_orchestrator.extract_fields")
    @patch("src.core.pipeline.resolve_pdf_path")
    @patch("src.core.pipeline.load_pdf_bytes")
    @patch("src.core.pipeline.hash_pdf_bytes")
    @patch("src.core.pipeline.hash_extraction_schema")
    def test_run_extraction_cache_key_format(
        self,
        mock_hash_schema,
        mock_hash_pdf,
        mock_load_bytes,
        mock_resolve,
        mock_extract_fields,
        mock_extractor_class,
        mock_cache_class,
        tmp_path,
    ):
        """Test cache key format includes label, pdf_hash, and schema_hash."""
        # Setup mocks
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"fake pdf")
        mock_resolve.return_value = test_file
        mock_load_bytes.return_value = b"fake pdf"
        mock_hash_pdf.return_value = "pdf123"
        mock_hash_schema.return_value = "schema456"

        mock_cache = MagicMock()
        mock_cache.get_json.return_value = None
        mock_cache_class.return_value = mock_cache

        mock_doc = ExtractedDocument(
            layout_text="test", words=[], meta={"source": str(test_file), "pages": 1}
        )
        mock_extractor = MagicMock()
        mock_extractor.load.return_value = mock_doc
        mock_extractor_class.return_value = mock_extractor

        mock_extract_fields.return_value = {
            "nome": {"value": "Test", "details": {"source": "openai"}},
        }

        request = ExtractionRequest(
            label="my_label",
            extraction_schema={"nome": "Nome"},
            pdf_path="test.pdf",
        )

        result = run_extraction(request)

        expected_key = "extract:my_label:pdf123:schema456"
        assert result.meta["cache_key"] == expected_key

    @patch("src.core.pipeline.CacheClient")
    @patch("src.core.pipeline.PdfExtractor")
    @patch("src.core.pipeline.llm_orchestrator.extract_fields")
    @patch("src.core.pipeline.resolve_pdf_path")
    @patch("src.core.pipeline.load_pdf_bytes")
    def test_run_extraction_caches_result(
        self,
        mock_load_bytes,
        mock_resolve,
        mock_extract_fields,
        mock_extractor_class,
        mock_cache_class,
        tmp_path,
    ):
        """Test pipeline caches extraction result after processing."""
        # Setup mocks
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"fake pdf")
        mock_resolve.return_value = test_file
        mock_load_bytes.return_value = b"fake pdf"

        mock_cache = MagicMock()
        mock_cache.get_json.return_value = None
        mock_cache.set_json.return_value = True
        mock_cache_class.return_value = mock_cache

        mock_doc = ExtractedDocument(
            layout_text="test", words=[], meta={"source": str(test_file), "pages": 1}
        )
        mock_extractor = MagicMock()
        mock_extractor.load.return_value = mock_doc
        mock_extractor_class.return_value = mock_extractor

        mock_extract_fields.return_value = {
            "nome": {"value": "JOÃO", "details": {"source": "openai"}},
        }

        request = ExtractionRequest(
            label="test",
            extraction_schema={"nome": "Nome"},
            pdf_path="test.pdf",
        )

        run_extraction(request)

        # Verify cache was written
        mock_cache.set_json.assert_called_once()
        call_args = mock_cache.set_json.call_args
        cache_key = call_args[0][0]
        cached_data = call_args[0][1]

        assert cache_key.startswith("extract:test:")
        assert cached_data["label"] == "test"
        assert cached_data["fields"]["nome"] == "JOÃO"

    @patch("src.core.pipeline.CacheClient")
    @patch("src.core.pipeline.PdfExtractor")
    @patch("src.core.pipeline.llm_orchestrator.extract_fields")
    @patch("src.core.pipeline.resolve_pdf_path")
    @patch("src.core.pipeline.load_pdf_bytes")
    def test_run_extraction_multiple_fields(
        self,
        mock_load_bytes,
        mock_resolve,
        mock_extract_fields,
        mock_extractor_class,
        mock_cache_class,
        tmp_path,
    ):
        """Test pipeline handles extraction with multiple fields."""
        # Setup mocks
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"fake pdf")
        mock_resolve.return_value = test_file
        mock_load_bytes.return_value = b"fake pdf"

        mock_cache = MagicMock()
        mock_cache.get_json.return_value = None
        mock_cache_class.return_value = mock_cache

        mock_doc = ExtractedDocument(
            layout_text="test", words=[], meta={"source": str(test_file), "pages": 1}
        )
        mock_extractor = MagicMock()
        mock_extractor.load.return_value = mock_doc
        mock_extractor_class.return_value = mock_extractor

        mock_extract_fields.return_value = {
            "nome": {"value": "JOÃO DA SILVA", "details": {"source": "openai"}},
            "inscricao": {"value": "123456", "details": {"source": "openai"}},
            "categoria": {"value": "ADVOGADO", "details": {"source": "openai"}},
        }

        request = ExtractionRequest(
            label="test",
            extraction_schema={
                "nome": "Nome",
                "inscricao": "Inscrição",
                "categoria": "Categoria",
            },
            pdf_path="test.pdf",
        )

        result = run_extraction(request)

        assert len(result.fields) == 3
        assert result.fields["nome"] == "JOÃO DA SILVA"
        assert result.fields["inscricao"] == "123456"
        assert result.fields["categoria"] == "ADVOGADO"
