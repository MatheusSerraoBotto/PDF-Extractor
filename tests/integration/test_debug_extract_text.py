"""
Integration test for PDF extraction via API.
Skips if SAMPLE_PDF_PATH is not provided or file does not exist.
"""

import os
import pathlib

import pytest
from httpx import AsyncClient

from src.main import app

SAMPLE_PDF = os.environ.get("SAMPLE_PDF_PATH", "").strip()


@pytest.mark.asyncio
@pytest.mark.skipif(
    not SAMPLE_PDF or not pathlib.Path(SAMPLE_PDF).exists(),
    reason="Set SAMPLE_PDF_PATH to an existing file.",
)
async def test_extract_endpoint_with_sample_pdf():
    """Test the /extract endpoint with a sample PDF."""
    async with AsyncClient(app=app, base_url="http://testserver") as client:
        # Create extraction request
        request_payload = {
            "label": "test_document",
            "extraction_schema": {
                "nome": "Nome completo",
                "email": "Endereço de email",
            },
            "pdf_path": SAMPLE_PDF,
        }

        response = await client.post("/extract", json=request_payload)
        assert response.status_code == 200

        payload = response.json()
        assert "label" in payload
        assert "fields" in payload
        assert "meta" in payload
        assert isinstance(payload["fields"], dict)
        assert payload["meta"]["engine"] == "pymupdf4llm"
