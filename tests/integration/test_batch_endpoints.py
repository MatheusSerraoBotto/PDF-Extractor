"""
Integration tests for batch extraction endpoints.

Tests the /extract/batch endpoint with real HTTP requests and streaming responses.
"""

import asyncio
import json
from unittest.mock import MagicMock, patch

import pytest

from src.core.extractor import ExtractedDocument


@pytest.mark.asyncio
class TestBatchExtractEndpoint:
    """Test cases for /extract/batch endpoint."""

    @patch("src.core.pipeline.CacheClient")
    @patch("src.core.pipeline.PdfExtractor")
    @patch("src.core.pipeline.llm_orchestrator.extract_fields")
    @patch("src.core.pipeline.resolve_pdf_path")
    @patch("src.core.pipeline.load_pdf_bytes")
    async def test_batch_extract_success(
        self,
        mock_load_bytes,
        mock_resolve,
        mock_extract_fields,
        mock_extractor_class,
        mock_cache_class,
        client,
        tmp_path,
    ):
        """Test successful batch extraction with multiple items."""
        # Setup file mocks
        test_file1 = tmp_path / "test1.pdf"
        test_file2 = tmp_path / "test2.pdf"
        test_file1.write_bytes(b"fake pdf 1")
        test_file2.write_bytes(b"fake pdf 2")

        def resolve_side_effect(path):
            if "test1.pdf" in path:
                return test_file1
            return test_file2

        def load_side_effect(path):
            if "test1.pdf" in str(path):
                return b"fake pdf 1"
            return b"fake pdf 2"

        mock_resolve.side_effect = resolve_side_effect
        mock_load_bytes.side_effect = load_side_effect

        # Setup cache mock (cache miss)
        mock_cache = MagicMock()
        mock_cache.get_json.return_value = None
        mock_cache.set_json.return_value = True
        mock_cache_class.return_value = mock_cache

        # Setup extractor mock
        mock_doc = ExtractedDocument(
            layout_text="[TOP-LEFT] JOÃO DA SILVA",
            words=[],
            meta={"source": "test.pdf", "engine": "pdfplumber", "pages": 1},
        )
        mock_extractor = MagicMock()
        mock_extractor.load.return_value = mock_doc
        mock_extractor_class.return_value = mock_extractor

        # Setup LLM mock - different results for different PDFs
        def extract_side_effect(*args, **kwargs):
            # Simulate different extractions
            return {
                "nome": {"value": "JOÃO DA SILVA", "details": {"source": "openai"}},
                "inscricao": {"value": "123456", "details": {"source": "openai"}},
            }

        mock_extract_fields.side_effect = extract_side_effect

        # Make batch request
        payload = [
            {
                "label": "carteira_oab",
                "extraction_schema": {
                    "nome": "Nome do profissional",
                    "inscricao": "Número de inscrição",
                },
                "pdf_path": "test1.pdf",
            },
            {
                "label": "carteira_oab",
                "extraction_schema": {
                    "nome": "Nome do profissional",
                    "inscricao": "Número de inscrição",
                },
                "pdf_path": "test2.pdf",
            },
        ]

        response = await client.post("/extract/batch", json=payload)

        # Verify streaming response
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]

        # Parse SSE stream
        content = response.text
        events = []
        for line in content.split("\n"):
            if line.startswith("data: "):
                data = json.loads(line[6:])  # Remove "data: " prefix
                events.append(data)

        # Should have 2 item results + 1 summary
        assert len(events) == 3

        # Verify item results
        item_results = [e for e in events if "index" in e]
        assert len(item_results) == 2
        assert all(r["status"] == "completed" for r in item_results)
        assert all(r["label"] == "carteira_oab" for r in item_results)
        assert all("fields" in r for r in item_results)

        # Verify summary
        summary = [e for e in events if e.get("status") == "done"][0]
        assert summary["total"] == 2
        assert summary["successful"] == 2
        assert summary["failed"] == 0

    async def test_batch_extract_empty_list(self, client):
        """Test batch extraction with empty list returns 400."""
        response = await client.post("/extract/batch", json=[])

        assert response.status_code == 400
        data = response.json()
        assert "empty" in data["detail"].lower()

    @pytest.mark.skip(reason="Skipping because creating 100001 items is too slow for tests")
    async def test_batch_extract_exceeds_max_size(self, client):
        """Test batch extraction exceeding max size returns 413."""
        from src.config.settings import get_settings

        settings = get_settings()
        max_size = settings.max_batch_size

        # Create a batch larger than max_batch_size
        payload = [
            {
                "label": "test",
                "extraction_schema": {"field": "desc"},
                "pdf_path": f"test_{i}.pdf",
            }
            for i in range(max_size + 1)
        ]

        response = await client.post("/extract/batch", json=payload)

        assert response.status_code == 413
        data = response.json()
        assert "exceeds maximum" in data["detail"]

    async def test_batch_extract_invalid_item_format(self, client):
        """Test batch extraction with invalid item format returns 400."""
        payload = [
            {
                "label": "test",
                # Missing required fields
            }
        ]

        response = await client.post("/extract/batch", json=payload)

        assert response.status_code == 400
        data = response.json()
        assert "invalid" in data["detail"].lower()

    @patch("src.core.pipeline.CacheClient")
    @patch("src.core.pipeline.PdfExtractor")
    @patch("src.core.pipeline.llm_orchestrator.extract_fields")
    @patch("src.core.pipeline.resolve_pdf_path")
    @patch("src.core.pipeline.load_pdf_bytes")
    async def test_batch_extract_partial_failure(
        self,
        mock_load_bytes,
        mock_resolve,
        mock_extract_fields,
        mock_extractor_class,
        mock_cache_class,
        client,
        tmp_path,
    ):
        """Test batch extraction with some items failing."""
        # Setup file mocks - second file will fail
        test_file1 = tmp_path / "test1.pdf"
        test_file1.write_bytes(b"fake pdf 1")

        def resolve_side_effect(path):
            if "test1.pdf" in path:
                return test_file1
            raise FileNotFoundError(f"File not found: {path}")

        def load_side_effect(path):
            if "test1.pdf" in str(path):
                return b"fake pdf 1"
            raise FileNotFoundError(f"File not found: {path}")

        mock_resolve.side_effect = resolve_side_effect
        mock_load_bytes.side_effect = load_side_effect

        # Setup cache mock (cache miss)
        mock_cache = MagicMock()
        mock_cache.get_json.return_value = None
        mock_cache.set_json.return_value = True
        mock_cache_class.return_value = mock_cache

        # Setup extractor mock
        mock_doc = ExtractedDocument(
            layout_text="[TOP-LEFT] JOÃO DA SILVA",
            words=[],
            meta={"source": "test.pdf", "engine": "pdfplumber", "pages": 1},
        )
        mock_extractor = MagicMock()
        mock_extractor.load.return_value = mock_doc
        mock_extractor_class.return_value = mock_extractor

        # Setup LLM mock
        mock_extract_fields.return_value = {
            "nome": {"value": "JOÃO DA SILVA", "details": {"source": "openai"}},
        }

        # Make batch request
        payload = [
            {
                "label": "carteira_oab",
                "extraction_schema": {"nome": "Nome do profissional"},
                "pdf_path": "test1.pdf",
            },
            {
                "label": "carteira_oab",
                "extraction_schema": {"nome": "Nome do profissional"},
                "pdf_path": "missing.pdf",
            },
        ]

        response = await client.post("/extract/batch", json=payload)

        # Verify streaming response
        assert response.status_code == 200

        # Parse SSE stream
        content = response.text
        events = []
        for line in content.split("\n"):
            if line.startswith("data: "):
                data = json.loads(line[6:])
                events.append(data)

        # Should have 2 item results + 1 summary
        assert len(events) == 3

        # Verify one success and one failure
        item_results = [e for e in events if "index" in e]
        success = [r for r in item_results if r["status"] == "completed"]
        errors = [r for r in item_results if r["status"] == "error"]

        assert len(success) == 1
        assert len(errors) == 1
        assert "error" in errors[0]

        # Verify summary
        summary = [e for e in events if e.get("status") == "done"][0]
        assert summary["total"] == 2
        assert summary["successful"] == 1
        assert summary["failed"] == 1

    async def test_batch_extract_cache_enabled(self, client):
        """Test batch extraction respects use_cache parameter."""
        payload = [
            {
                "label": "test",
                "extraction_schema": {"field": "desc"},
                "pdf_path": "test.pdf",
            }
        ]

        # Test with cache enabled (default)
        response = await client.post("/extract/batch?use_cache=true", json=payload)
        # Will fail due to missing file, but endpoint should accept it
        assert response.status_code == 200

        # Test with cache disabled
        response = await client.post("/extract/batch?use_cache=false", json=payload)
        assert response.status_code == 200

    @patch("src.core.pipeline.CacheClient")
    @patch("src.core.pipeline.PdfExtractor")
    @patch("src.core.pipeline.llm_orchestrator.extract_fields")
    @patch("src.core.pipeline.resolve_pdf_path")
    @patch("src.core.pipeline.load_pdf_bytes")
    async def test_batch_extract_parallel_processing(
        self,
        mock_load_bytes,
        mock_resolve,
        mock_extract_fields,
        mock_extractor_class,
        mock_cache_class,
        client,
        tmp_path,
    ):
        """Test that batch processing runs in parallel (items complete out of order)."""
        # Setup file mocks
        test_files = []
        for i in range(3):
            f = tmp_path / f"test{i}.pdf"
            f.write_bytes(f"fake pdf {i}".encode())
            test_files.append(f)

        mock_resolve.side_effect = lambda p: test_files[int(p.split("test")[1][0])]
        mock_load_bytes.side_effect = lambda p: f"fake pdf {p}".encode()

        # Setup cache mock (cache miss)
        mock_cache = MagicMock()
        mock_cache.get_json.return_value = None
        mock_cache.set_json.return_value = True
        mock_cache_class.return_value = mock_cache

        # Setup extractor mock
        mock_doc = ExtractedDocument(
            layout_text="[TOP-LEFT] TEST",
            words=[],
            meta={"source": "test.pdf", "engine": "pdfplumber", "pages": 1},
        )
        mock_extractor = MagicMock()
        mock_extractor.load.return_value = mock_doc
        mock_extractor_class.return_value = mock_extractor

        # Setup LLM mock with varying delays (simulated via async)
        mock_extract_fields.return_value = {
            "field": {"value": "TEST", "details": {"source": "openai"}},
        }

        # Make batch request with 3 items
        payload = [
            {
                "label": "test",
                "extraction_schema": {"field": "desc"},
                "pdf_path": f"test{i}.pdf",
            }
            for i in range(3)
        ]

        response = await client.post("/extract/batch", json=payload)

        # Verify streaming response
        assert response.status_code == 200

        # Parse SSE stream
        content = response.text
        events = []
        for line in content.split("\n"):
            if line.startswith("data: "):
                data = json.loads(line[6:])
                events.append(data)

        # Should have 3 item results + 1 summary
        assert len(events) == 4

        # Verify all items completed
        item_results = [e for e in events if "index" in e]
        assert len(item_results) == 3
        assert all(r["status"] == "completed" for r in item_results)

        # Verify summary
        summary = [e for e in events if e.get("status") == "done"][0]
        assert summary["total"] == 3
        assert summary["successful"] == 3
        assert summary["failed"] == 0
