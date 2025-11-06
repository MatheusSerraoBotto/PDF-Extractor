"""
Integration tests for the full extraction pipeline.

Tests end-to-end extraction flow with real components (minus external APIs).
"""

from unittest.mock import MagicMock, patch

import pytest

from src.core.pipeline import run_extraction
from src.models.schema import ExtractionRequest


class TestPipelineIntegration:
    """Integration tests for complete extraction pipeline."""

    @patch("src.core.pipeline.CacheClient")
    @patch("src.core.pipeline.llm_orchestrator.extract_fields")
    @patch("src.core.extractor.pdfplumber.open")
    def test_full_pipeline_without_cache(
        self,
        mock_pdfplumber,
        mock_extract_fields,
        mock_cache_class,
        mock_pdfplumber_pdf,
        tmp_path,
    ):
        """Test complete pipeline flow from PDF to result without cache."""
        # Create real PDF file
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"fake pdf content")

        # Mock pdfplumber
        mock_pdfplumber.return_value = mock_pdfplumber_pdf

        # Mock cache (miss)
        mock_cache = MagicMock()
        mock_cache.get_json.return_value = None
        mock_cache.set_json.return_value = True
        mock_cache_class.return_value = mock_cache

        # Mock LLM extraction
        mock_extract_fields.return_value = {
            "nome": {"value": "JOÃO DA SILVA", "details": {"source": "openai"}},
            "inscricao": {"value": "123456", "details": {"source": "openai"}},
        }

        # Create request
        request = ExtractionRequest(
            label="carteira_oab",
            extraction_schema={
                "nome": "Nome do profissional",
                "inscricao": "Número de inscrição",
            },
            pdf_path=str(test_file),
        )

        # Run pipeline
        result = run_extraction(request, use_cache=False)

        # Verify result
        assert result.label == "carteira_oab"
        assert result.fields["nome"] == "JOÃO DA SILVA"
        assert result.fields["inscricao"] == "123456"
        assert result.meta["cache_hit"] is False

        # Verify pipeline stages executed
        mock_pdfplumber.assert_called_once()
        mock_extract_fields.assert_called_once()
        mock_cache.set_json.assert_called_once()

    @patch("src.core.pipeline.CacheClient")
    @patch("src.core.pipeline.llm_orchestrator.extract_fields")
    @patch("src.core.extractor.pdfplumber.open")
    def test_full_pipeline_with_cache_hit(
        self,
        mock_pdfplumber,
        mock_extract_fields,
        mock_cache_class,
        tmp_path,
    ):
        """Test pipeline returns cached result without processing."""
        # Create real PDF file
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"fake pdf content")

        # Mock cache (hit)
        cached_result = {
            "label": "carteira_oab",
            "fields": {
                "nome": "CACHED NAME",
                "inscricao": "CACHED NUMBER",
            },
            "meta": {
                "cache_hit": False,
                "timings_seconds": {"total": 1.5},
            },
        }
        mock_cache = MagicMock()
        mock_cache.get_json.return_value = cached_result
        mock_cache_class.return_value = mock_cache

        # Create request
        request = ExtractionRequest(
            label="carteira_oab",
            extraction_schema={
                "nome": "Nome",
                "inscricao": "Inscrição",
            },
            pdf_path=str(test_file),
        )

        # Run pipeline
        result = run_extraction(request, use_cache=True)

        # Verify cached result returned
        assert result.fields["nome"] == "CACHED NAME"
        assert result.fields["inscricao"] == "CACHED NUMBER"
        assert result.meta["cache_hit"] is True

        # Verify PDF extraction and LLM were NOT called
        mock_pdfplumber.assert_not_called()
        mock_extract_fields.assert_not_called()

    @patch("src.core.pipeline.CacheClient")
    @patch("src.core.pipeline.llm_orchestrator.extract_fields")
    @patch("src.core.extractor.pdfplumber.open")
    def test_pipeline_with_real_extractor(
        self,
        mock_pdfplumber,
        mock_extract_fields,
        mock_cache_class,
        mock_pdfplumber_pdf,
        tmp_path,
    ):
        """Test pipeline uses real PdfExtractor for document processing."""
        # Create real PDF file
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"fake pdf content")

        # Mock pdfplumber to return words
        mock_pdfplumber.return_value = mock_pdfplumber_pdf

        # Mock cache
        mock_cache = MagicMock()
        mock_cache.get_json.return_value = None
        mock_cache_class.return_value = mock_cache

        # Mock LLM
        mock_extract_fields.return_value = {
            "nome": {"value": "Test", "details": {"source": "openai"}},
        }

        # Create request
        request = ExtractionRequest(
            label="test",
            extraction_schema={"nome": "Nome"},
            pdf_path=str(test_file),
        )

        # Run pipeline (should use real PdfExtractor)
        result = run_extraction(request, use_cache=False)

        # Verify extractor was used
        assert result.meta["doc_meta"]["engine"] == "pdfplumber"
        assert result.meta["doc_meta"]["pages"] == 1

        # Verify LLM received layout text
        call_args = mock_extract_fields.call_args
        doc_layout = call_args[1]["doc_layout"]
        assert isinstance(doc_layout, str)
        assert len(doc_layout) > 0

    @patch("src.core.pipeline.CacheClient")
    @patch("src.core.pipeline.llm_orchestrator.extract_fields")
    @patch("src.core.extractor.pdfplumber.open")
    def test_pipeline_timing_metadata(
        self,
        mock_pdfplumber,
        mock_extract_fields,
        mock_cache_class,
        mock_pdfplumber_pdf,
        tmp_path,
    ):
        """Test pipeline records accurate timing information."""
        # Create real PDF file
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"fake pdf content")

        # Mock components
        mock_pdfplumber.return_value = mock_pdfplumber_pdf

        mock_cache = MagicMock()
        mock_cache.get_json.return_value = None
        mock_cache_class.return_value = mock_cache

        mock_extract_fields.return_value = {
            "nome": {"value": "Test", "details": {"source": "openai"}},
        }

        # Create request
        request = ExtractionRequest(
            label="test",
            extraction_schema={"nome": "Nome"},
            pdf_path=str(test_file),
        )

        # Run pipeline
        result = run_extraction(request)

        # Verify timing metadata
        timings = result.meta["timings_seconds"]
        assert "extract" in timings
        assert "llm" in timings
        assert "total" in timings

        # Verify timings are positive numbers
        assert timings["extract"] >= 0
        assert timings["llm"] >= 0
        assert timings["total"] >= 0

        # Total should be >= sum of stages
        assert timings["total"] >= timings["extract"] + timings["llm"]

    @patch("src.core.pipeline.CacheClient")
    @patch("src.core.pipeline.llm_orchestrator.extract_fields")
    @patch("src.core.extractor.pdfplumber.open")
    def test_pipeline_trace_information(
        self,
        mock_pdfplumber,
        mock_extract_fields,
        mock_cache_class,
        mock_pdfplumber_pdf,
        tmp_path,
    ):
        """Test pipeline tracks which fields were resolved/unresolved."""
        # Create real PDF file
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"fake pdf content")

        # Mock components
        mock_pdfplumber.return_value = mock_pdfplumber_pdf

        mock_cache = MagicMock()
        mock_cache.get_json.return_value = None
        mock_cache_class.return_value = mock_cache

        # LLM resolves some fields, not others
        mock_extract_fields.return_value = {
            "nome": {"value": "JOÃO DA SILVA", "details": {"source": "openai"}},
            "inscricao": {"value": "123456", "details": {"source": "openai"}},
            "categoria": {"value": None, "details": {"source": "openai"}},
        }

        # Create request
        request = ExtractionRequest(
            label="test",
            extraction_schema={
                "nome": "Nome",
                "inscricao": "Inscrição",
                "categoria": "Categoria",
            },
            pdf_path=str(test_file),
        )

        # Run pipeline
        result = run_extraction(request)

        # Verify trace information
        trace = result.meta["trace"]
        assert "nome" in trace["llm_resolved"]
        assert "inscricao" in trace["llm_resolved"]
        assert "categoria" in trace["unresolved"]

    @patch("src.core.pipeline.CacheClient")
    @patch("src.core.pipeline.llm_orchestrator.extract_fields")
    @patch("src.core.extractor.pdfplumber.open")
    def test_pipeline_cache_key_generation(
        self,
        mock_pdfplumber,
        mock_extract_fields,
        mock_cache_class,
        mock_pdfplumber_pdf,
        tmp_path,
    ):
        """Test pipeline generates consistent cache keys."""
        # Create real PDF file
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"fake pdf content")

        # Mock components
        mock_pdfplumber.return_value = mock_pdfplumber_pdf

        mock_cache = MagicMock()
        mock_cache.get_json.return_value = None
        mock_cache.set_json.return_value = True
        mock_cache_class.return_value = mock_cache

        mock_extract_fields.return_value = {
            "nome": {"value": "Test", "details": {"source": "openai"}},
        }

        # Create request
        request = ExtractionRequest(
            label="test_label",
            extraction_schema={"nome": "Nome"},
            pdf_path=str(test_file),
        )

        # Run pipeline twice with same inputs
        result1 = run_extraction(request, use_cache=False)
        result2 = run_extraction(request, use_cache=False)

        # Cache keys should be identical
        assert result1.meta["cache_key"] == result2.meta["cache_key"]

    @patch("src.core.pipeline.CacheClient")
    @patch("src.core.pipeline.llm_orchestrator.extract_fields")
    @patch("src.core.extractor.pdfplumber.open")
    def test_pipeline_different_schemas_different_cache_keys(
        self,
        mock_pdfplumber,
        mock_extract_fields,
        mock_cache_class,
        mock_pdfplumber_pdf,
        tmp_path,
    ):
        """Test different extraction schemas generate different cache keys."""
        # Create real PDF file
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"fake pdf content")

        # Mock components
        mock_pdfplumber.return_value = mock_pdfplumber_pdf

        mock_cache = MagicMock()
        mock_cache.get_json.return_value = None
        mock_cache_class.return_value = mock_cache

        mock_extract_fields.return_value = {
            "field": {"value": "value", "details": {"source": "openai"}},
        }

        # Request with schema 1
        request1 = ExtractionRequest(
            label="test",
            extraction_schema={"nome": "Nome"},
            pdf_path=str(test_file),
        )
        result1 = run_extraction(request1, use_cache=False)

        # Request with schema 2
        request2 = ExtractionRequest(
            label="test",
            extraction_schema={"inscricao": "Inscrição"},
            pdf_path=str(test_file),
        )
        result2 = run_extraction(request2, use_cache=False)

        # Cache keys should be different
        assert result1.meta["cache_key"] != result2.meta["cache_key"]

    @patch("src.core.pipeline.CacheClient")
    @patch("src.core.pipeline.llm_orchestrator.extract_fields")
    @patch("src.core.extractor.pdfplumber.open")
    def test_pipeline_stores_result_in_cache(
        self,
        mock_pdfplumber,
        mock_extract_fields,
        mock_cache_class,
        mock_pdfplumber_pdf,
        tmp_path,
    ):
        """Test pipeline stores extraction result in cache."""
        # Create real PDF file
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"fake pdf content")

        # Mock components
        mock_pdfplumber.return_value = mock_pdfplumber_pdf

        mock_cache = MagicMock()
        mock_cache.get_json.return_value = None
        mock_cache.set_json.return_value = True
        mock_cache_class.return_value = mock_cache

        mock_extract_fields.return_value = {
            "nome": {"value": "JOÃO", "details": {"source": "openai"}},
        }

        # Create request
        request = ExtractionRequest(
            label="test",
            extraction_schema={"nome": "Nome"},
            pdf_path=str(test_file),
        )

        # Run pipeline
        run_extraction(request, use_cache=True)

        # Verify cache.set_json was called
        mock_cache.set_json.assert_called_once()

        # Verify cached data structure
        call_args = mock_cache.set_json.call_args
        cache_key = call_args[0][0]
        cached_data = call_args[0][1]

        assert cache_key.startswith("extract:test:")
        assert cached_data["label"] == "test"
        assert cached_data["fields"]["nome"] == "JOÃO"
        assert "meta" in cached_data

    @patch("src.core.pipeline.CacheClient")
    @patch("src.core.extractor.pdfplumber.open")
    def test_pipeline_handles_extractor_errors(
        self,
        mock_pdfplumber,
        mock_cache_class,
        tmp_path,
    ):
        """Test pipeline propagates extractor errors."""
        # Create real PDF file
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"fake pdf content")

        # Mock pdfplumber to raise error
        mock_pdfplumber.side_effect = Exception("PDF extraction error")

        mock_cache = MagicMock()
        mock_cache.get_json.return_value = None
        mock_cache_class.return_value = mock_cache

        # Create request
        request = ExtractionRequest(
            label="test",
            extraction_schema={"nome": "Nome"},
            pdf_path=str(test_file),
        )

        # Run pipeline should raise error
        with pytest.raises(Exception, match="PDF extraction error"):
            run_extraction(request, use_cache=False)

    @patch("src.core.pipeline.CacheClient")
    @patch("src.core.pipeline.llm_orchestrator.extract_fields")
    @patch("src.core.extractor.pdfplumber.open")
    def test_pipeline_handles_llm_errors_gracefully(
        self,
        mock_pdfplumber,
        mock_extract_fields,
        mock_cache_class,
        mock_pdfplumber_pdf,
        tmp_path,
    ):
        """Test pipeline handles LLM extraction errors."""
        # Create real PDF file
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"fake pdf content")

        # Mock components
        mock_pdfplumber.return_value = mock_pdfplumber_pdf

        mock_cache = MagicMock()
        mock_cache.get_json.return_value = None
        mock_cache_class.return_value = mock_cache

        # LLM returns fallback error response
        mock_extract_fields.return_value = {
            "nome": {"value": None, "details": {"error": "openai_api_error"}},
        }

        # Create request
        request = ExtractionRequest(
            label="test",
            extraction_schema={"nome": "Nome"},
            pdf_path=str(test_file),
        )

        # Run pipeline (should not raise error)
        result = run_extraction(request, use_cache=False)

        # Verify result has None values
        assert result.fields["nome"] is None
        assert "nome" in result.meta["trace"]["unresolved"]

    @patch("src.core.pipeline.CacheClient")
    @patch("src.core.pipeline.llm_orchestrator.extract_fields")
    @patch("src.core.extractor.pdfplumber.open")
    def test_pipeline_preserves_field_order(
        self,
        mock_pdfplumber,
        mock_extract_fields,
        mock_cache_class,
        mock_pdfplumber_pdf,
        tmp_path,
    ):
        """Test pipeline preserves extraction schema field order."""
        # Create real PDF file
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"fake pdf content")

        # Mock components
        mock_pdfplumber.return_value = mock_pdfplumber_pdf

        mock_cache = MagicMock()
        mock_cache.get_json.return_value = None
        mock_cache_class.return_value = mock_cache

        mock_extract_fields.return_value = {
            "field1": {"value": "value1", "details": {"source": "openai"}},
            "field2": {"value": "value2", "details": {"source": "openai"}},
            "field3": {"value": "value3", "details": {"source": "openai"}},
        }

        # Create request with ordered schema
        schema = {
            "field1": "Field 1",
            "field2": "Field 2",
            "field3": "Field 3",
        }
        request = ExtractionRequest(
            label="test",
            extraction_schema=schema,
            pdf_path=str(test_file),
        )

        # Run pipeline
        result = run_extraction(request, use_cache=False)

        # Verify all fields present
        assert list(result.fields.keys()) == ["field1", "field2", "field3"]
