"""
Integration tests for FastAPI endpoints.

Tests the /health and /extract endpoints with real HTTP requests.
"""

from unittest.mock import MagicMock, patch

import pytest

from src.core.extractor import ExtractedDocument


@pytest.mark.asyncio
class TestHealthEndpoint:
    """Test cases for /health endpoint."""

    async def test_health_endpoint_returns_ok(self, client):
        """Test health endpoint returns 200 OK."""
        response = await client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "environment" in data

    async def test_health_endpoint_includes_environment(self, client):
        """Test health endpoint includes environment information."""
        response = await client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data["environment"], str)

    async def test_health_endpoint_content_type(self, client):
        """Test health endpoint returns JSON content type."""
        response = await client.get("/health")

        assert response.status_code == 200
        assert "application/json" in response.headers["content-type"]


@pytest.mark.asyncio
class TestExtractEndpoint:
    """Test cases for /extract endpoint."""

    @patch("src.core.pipeline.CacheClient")
    @patch("src.core.pipeline.PdfExtractor")
    @patch("src.core.pipeline.llm_orchestrator.extract_fields")
    @patch("src.core.pipeline.resolve_pdf_path")
    @patch("src.core.pipeline.load_pdf_bytes")
    async def test_extract_endpoint_success(
        self,
        mock_load_bytes,
        mock_resolve,
        mock_extract_fields,
        mock_extractor_class,
        mock_cache_class,
        client,
        tmp_path,
    ):
        """Test successful extraction through API endpoint."""
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
            layout_text="[TOP-LEFT] JOÃO DA SILVA",
            words=[],
            meta={"source": str(test_file), "engine": "pdfplumber", "pages": 1},
        )
        mock_extractor = MagicMock()
        mock_extractor.load.return_value = mock_doc
        mock_extractor_class.return_value = mock_extractor

        # Setup LLM mock
        mock_extract_fields.return_value = {
            "nome": {"value": "JOÃO DA SILVA", "details": {"source": "openai"}},
            "inscricao": {"value": "123456", "details": {"source": "openai"}},
        }

        # Make request
        payload = {
            "label": "carteira_oab",
            "extraction_schema": {
                "nome": "Nome do profissional",
                "inscricao": "Número de inscrição",
            },
            "pdf_path": "test.pdf",
        }

        response = await client.post("/extract", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["label"] == "carteira_oab"
        assert data["fields"]["nome"] == "JOÃO DA SILVA"
        assert data["fields"]["inscricao"] == "123456"
        assert "meta" in data

    async def test_extract_endpoint_missing_fields(self, client):
        """Test extraction endpoint with missing required fields."""
        payload = {
            "label": "test",
            # Missing extraction_schema and pdf_path
        }

        response = await client.post("/extract", json=payload)

        assert response.status_code == 422  # Validation error

    async def test_extract_endpoint_invalid_json(self, client):
        """Test extraction endpoint with invalid JSON."""
        response = await client.post(
            "/extract",
            content="not valid json {",
            headers={"content-type": "application/json"},
        )

        assert response.status_code == 422

    @patch("src.core.pipeline.resolve_pdf_path")
    async def test_extract_endpoint_file_not_found(self, mock_resolve, client):
        """Test extraction endpoint with non-existent PDF file."""
        mock_resolve.side_effect = FileNotFoundError("PDF not found")

        payload = {
            "label": "test",
            "extraction_schema": {"nome": "Nome"},
            "pdf_path": "/nonexistent/file.pdf",
        }

        response = await client.post("/extract", json=payload)

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @patch("src.core.pipeline.CacheClient")
    @patch("src.core.pipeline.resolve_pdf_path")
    @patch("src.core.pipeline.load_pdf_bytes")
    async def test_extract_endpoint_with_cache_hit(
        self,
        mock_load_bytes,
        mock_resolve,
        mock_cache_class,
        client,
        tmp_path,
    ):
        """Test extraction endpoint returns cached result."""
        # Setup file mocks
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"fake pdf")
        mock_resolve.return_value = test_file
        mock_load_bytes.return_value = b"fake pdf"

        # Setup cache mock (cache hit)
        cached_result = {
            "label": "carteira_oab",
            "fields": {"nome": "CACHED VALUE"},
            "meta": {"cache_hit": False},
        }
        mock_cache = MagicMock()
        mock_cache.get_json.return_value = cached_result
        mock_cache_class.return_value = mock_cache

        payload = {
            "label": "carteira_oab",
            "extraction_schema": {"nome": "Nome"},
            "pdf_path": "test.pdf",
        }

        response = await client.post("/extract", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["fields"]["nome"] == "CACHED VALUE"
        assert data["meta"]["cache_hit"] is True

    @patch("src.core.pipeline.CacheClient")
    @patch("src.core.pipeline.PdfExtractor")
    @patch("src.core.pipeline.llm_orchestrator.extract_fields")
    @patch("src.core.pipeline.resolve_pdf_path")
    @patch("src.core.pipeline.load_pdf_bytes")
    async def test_extract_endpoint_use_cache_false(
        self,
        mock_load_bytes,
        mock_resolve,
        mock_extract_fields,
        mock_extractor_class,
        mock_cache_class,
        client,
        tmp_path,
    ):
        """Test extraction endpoint with use_cache=false query parameter."""
        # Setup file mocks
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"fake pdf")
        mock_resolve.return_value = test_file
        mock_load_bytes.return_value = b"fake pdf"

        # Setup cache mock
        mock_cache = MagicMock()
        mock_cache.get_json.return_value = {"cached": "data"}
        mock_cache_class.return_value = mock_cache

        # Setup extractor mock
        mock_doc = ExtractedDocument(
            layout_text="test",
            words=[],
            meta={"source": str(test_file), "pages": 1},
        )
        mock_extractor = MagicMock()
        mock_extractor.load.return_value = mock_doc
        mock_extractor_class.return_value = mock_extractor

        # Setup LLM mock
        mock_extract_fields.return_value = {
            "nome": {"value": "FRESH DATA", "details": {"source": "openai"}},
        }

        payload = {
            "label": "test",
            "extraction_schema": {"nome": "Nome"},
            "pdf_path": "test.pdf",
        }

        response = await client.post("/extract?use_cache=false", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["fields"]["nome"] == "FRESH DATA"
        # Cache check should not have been called
        mock_cache.get_json.assert_not_called()

    @patch("src.core.pipeline.CacheClient")
    @patch("src.core.pipeline.PdfExtractor")
    @patch("src.core.pipeline.llm_orchestrator.extract_fields")
    @patch("src.core.pipeline.resolve_pdf_path")
    @patch("src.core.pipeline.load_pdf_bytes")
    async def test_extract_endpoint_multiple_fields(
        self,
        mock_load_bytes,
        mock_resolve,
        mock_extract_fields,
        mock_extractor_class,
        mock_cache_class,
        client,
        tmp_path,
    ):
        """Test extraction endpoint with multiple fields."""
        # Setup mocks
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"fake pdf")
        mock_resolve.return_value = test_file
        mock_load_bytes.return_value = b"fake pdf"

        mock_cache = MagicMock()
        mock_cache.get_json.return_value = None
        mock_cache_class.return_value = mock_cache

        mock_doc = ExtractedDocument(
            layout_text="test",
            words=[],
            meta={"source": str(test_file), "pages": 1},
        )
        mock_extractor = MagicMock()
        mock_extractor.load.return_value = mock_doc
        mock_extractor_class.return_value = mock_extractor

        mock_extract_fields.return_value = {
            "nome": {"value": "JOÃO DA SILVA", "details": {"source": "openai"}},
            "inscricao": {"value": "123456", "details": {"source": "openai"}},
            "categoria": {"value": "ADVOGADO", "details": {"source": "openai"}},
            "situacao": {"value": "ATIVO", "details": {"source": "openai"}},
        }

        payload = {
            "label": "carteira_oab",
            "extraction_schema": {
                "nome": "Nome",
                "inscricao": "Inscrição",
                "categoria": "Categoria",
                "situacao": "Situação",
            },
            "pdf_path": "test.pdf",
        }

        response = await client.post("/extract", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert len(data["fields"]) == 4
        assert data["fields"]["nome"] == "JOÃO DA SILVA"
        assert data["fields"]["categoria"] == "ADVOGADO"

    @patch("src.core.pipeline.CacheClient")
    @patch("src.core.pipeline.PdfExtractor")
    @patch("src.core.pipeline.llm_orchestrator.extract_fields")
    @patch("src.core.pipeline.resolve_pdf_path")
    @patch("src.core.pipeline.load_pdf_bytes")
    async def test_extract_endpoint_with_none_values(
        self,
        mock_load_bytes,
        mock_resolve,
        mock_extract_fields,
        mock_extractor_class,
        mock_cache_class,
        client,
        tmp_path,
    ):
        """Test extraction endpoint with some fields returning None."""
        # Setup mocks
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"fake pdf")
        mock_resolve.return_value = test_file
        mock_load_bytes.return_value = b"fake pdf"

        mock_cache = MagicMock()
        mock_cache.get_json.return_value = None
        mock_cache_class.return_value = mock_cache

        mock_doc = ExtractedDocument(
            layout_text="test",
            words=[],
            meta={"source": str(test_file), "pages": 1},
        )
        mock_extractor = MagicMock()
        mock_extractor.load.return_value = mock_doc
        mock_extractor_class.return_value = mock_extractor

        mock_extract_fields.return_value = {
            "nome": {"value": "JOÃO DA SILVA", "details": {"source": "openai"}},
            "inscricao": {"value": None, "details": {"source": "openai"}},
        }

        payload = {
            "label": "test",
            "extraction_schema": {
                "nome": "Nome",
                "inscricao": "Inscrição",
            },
            "pdf_path": "test.pdf",
        }

        response = await client.post("/extract", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["fields"]["nome"] == "JOÃO DA SILVA"
        assert data["fields"]["inscricao"] is None

    @patch("src.core.pipeline.CacheClient")
    @patch("src.core.pipeline.PdfExtractor")
    @patch("src.core.pipeline.llm_orchestrator.extract_fields")
    @patch("src.core.pipeline.resolve_pdf_path")
    @patch("src.core.pipeline.load_pdf_bytes")
    async def test_extract_endpoint_returns_metadata(
        self,
        mock_load_bytes,
        mock_resolve,
        mock_extract_fields,
        mock_extractor_class,
        mock_cache_class,
        client,
        tmp_path,
    ):
        """Test extraction endpoint includes metadata in response."""
        # Setup mocks
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"fake pdf")
        mock_resolve.return_value = test_file
        mock_load_bytes.return_value = b"fake pdf"

        mock_cache = MagicMock()
        mock_cache.get_json.return_value = None
        mock_cache_class.return_value = mock_cache

        mock_doc = ExtractedDocument(
            layout_text="test",
            words=[],
            meta={"source": str(test_file), "pages": 1, "engine": "pdfplumber"},
        )
        mock_extractor = MagicMock()
        mock_extractor.load.return_value = mock_doc
        mock_extractor_class.return_value = mock_extractor

        mock_extract_fields.return_value = {
            "nome": {"value": "Test", "details": {"source": "openai"}},
        }

        payload = {
            "label": "test",
            "extraction_schema": {"nome": "Nome"},
            "pdf_path": "test.pdf",
        }

        response = await client.post("/extract", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert "meta" in data
        assert "timings_seconds" in data["meta"]
        assert "cache_hit" in data["meta"]
        assert "trace" in data["meta"]

    @patch("src.main.run_extraction")
    async def test_extract_endpoint_internal_error(self, mock_run, client):
        """Test extraction endpoint handles internal errors."""
        # Mock run_extraction to raise a generic exception
        mock_run.side_effect = Exception("Internal error")

        payload = {
            "label": "test",
            "extraction_schema": {"nome": "Nome"},
            "pdf_path": "test.pdf",
        }

        response = await client.post("/extract", json=payload)

        assert response.status_code == 500
        data = response.json()
        assert "detail" in data
        # Check that error message is included
        assert "error" in data["detail"].lower() or "internal" in data["detail"].lower()

    @patch("src.main.run_extraction")
    async def test_extract_endpoint_empty_schema(self, mock_run, client):
        """Test extraction endpoint with empty extraction schema."""
        # Mock to avoid actual file operations
        mock_run.side_effect = FileNotFoundError("PDF not found")

        payload = {
            "label": "test",
            "extraction_schema": {},
            "pdf_path": "test.pdf",
        }

        # Empty schema is technically valid, so we expect 404 (file not found)
        response = await client.post("/extract", json=payload)

        assert response.status_code == 404

    async def test_extract_endpoint_content_type_json(self, client):
        """Test that extract endpoint requires JSON content type."""
        response = await client.post(
            "/extract",
            content="not json",
            headers={"content-type": "text/plain"},
        )

        assert response.status_code == 422
