"""
Pytest fixtures for unit and integration tests.

Provides shared fixtures for:
- AsyncClient for API integration tests
- Mock Redis client for cache tests
- Mock OpenAI client for LLM tests
- Sample PDF files and test data
"""

import sys
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock

import pytest
import pytest_asyncio
from httpx import AsyncClient

# Ensure project root is available for src.* imports when tests run in Docker.
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Import the FastAPI app instance (must be created in src/main.py)
from src.main import app  # noqa: E402


@pytest_asyncio.fixture
async def client():
    """Provide an HTTPX AsyncClient connected to the FastAPI app."""
    async with AsyncClient(app=app, base_url="http://testserver") as ac:
        yield ac


@pytest.fixture
def mock_redis():
    """Provide a mock Redis client for cache tests."""
    mock = MagicMock()
    mock.get.return_value = None
    mock.set.return_value = True
    mock.setex.return_value = True
    return mock


@pytest.fixture
def mock_openai_client():
    """Provide a mock OpenAI client for LLM tests."""
    mock = MagicMock()

    # Mock responses.parse response structure
    mock_response = MagicMock()
    mock_response.usage.total_tokens = 1500
    mock_response.output_parsed = None
    mock.responses.parse.return_value = mock_response

    return mock


@pytest.fixture
def sample_extraction_schema() -> Dict[str, str]:
    """Provide a sample extraction schema for tests."""
    return {
        "nome": "Nome do profissional",
        "inscricao": "Número de inscrição",
        "categoria": "Categoria profissional",
    }


@pytest.fixture
def sample_extraction_request(sample_extraction_schema) -> Dict[str, Any]:
    """Provide a sample extraction request payload."""
    return {
        "label": "test_document",
        "extraction_schema": sample_extraction_schema,
        "pdf_path": "test.pdf",
    }


@pytest.fixture
def sample_extracted_words() -> list:
    """Provide sample word data with bounding boxes."""
    return [
        {
            "text": "JOÃO",
            "x0": 100.0,
            "top": 50.0,
            "x1": 150.0,
            "bottom": 70.0,
        },
        {
            "text": "DA",
            "x0": 155.0,
            "top": 50.0,
            "x1": 175.0,
            "bottom": 70.0,
        },
        {
            "text": "SILVA",
            "x0": 180.0,
            "top": 50.0,
            "x1": 230.0,
            "bottom": 70.0,
        },
        {
            "text": "Inscrição:",
            "x0": 100.0,
            "top": 100.0,
            "x1": 170.0,
            "bottom": 120.0,
        },
        {
            "text": "123456",
            "x0": 175.0,
            "top": 100.0,
            "x1": 230.0,
            "bottom": 120.0,
        },
    ]


@pytest.fixture
def sample_layout_text() -> str:
    """Provide sample layout text for LLM tests."""
    return """[TOP-LEFT] [x:100-230, y:50] JOÃO DA SILVA
[TOP-LEFT] [x:100-170, y:100] Inscrição:
[TOP-LEFT] [x:175-230, y:100] 123456
[CENTER] [x:200-400, y:300] ADVOGADO
[BOTTOM-RIGHT] [x:450-550, y:700] ATIVO"""


@pytest.fixture
def sample_llm_response() -> Dict[str, Any]:
    """Provide a sample normalized LLM response."""
    return {
        "nome": {
            "value": "JOÃO DA SILVA",
            "details": {"source": "openai", "method": "responses.parse"},
        },
        "inscricao": {
            "value": "123456",
            "details": {"source": "openai", "method": "responses.parse"},
        },
        "categoria": {
            "value": "ADVOGADO",
            "details": {"source": "openai", "method": "responses.parse"},
        },
    }


@pytest.fixture
def temp_test_dir(tmp_path):
    """Create a temporary directory for test files."""
    test_dir = tmp_path / "test_pdfs"
    test_dir.mkdir(exist_ok=True)
    return test_dir


@pytest.fixture
def mock_settings(monkeypatch):
    """Provide mock settings for tests."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-12345")
    monkeypatch.setenv("LLM_MODEL", "gpt-5-mini")
    monkeypatch.setenv("REDIS_HOST", "localhost")
    monkeypatch.setenv("REDIS_PORT", "6379")
    monkeypatch.setenv("PDF_BASE_PATH", "/tmp/test_pdfs")

    # Force settings reload
    from src.config.settings import get_settings

    get_settings.cache_clear()

    return get_settings()


@pytest.fixture
def mock_pdfplumber_page():
    """Provide a mock pdfplumber page object."""
    mock_page = MagicMock()
    mock_page.width = 595.0  # A4 width in points
    mock_page.height = 842.0  # A4 height in points

    # Sample words with bbox data
    mock_page.extract_words.return_value = [
        {
            "text": "JOÃO",
            "x0": 100.0,
            "top": 50.0,
            "x1": 150.0,
            "bottom": 70.0,
        },
        {
            "text": "DA",
            "x0": 155.0,
            "top": 50.0,
            "x1": 175.0,
            "bottom": 70.0,
        },
        {
            "text": "SILVA",
            "x0": 180.0,
            "top": 50.0,
            "x1": 230.0,
            "bottom": 70.0,
        },
    ]

    # Mock table detection
    mock_page.find_tables.return_value = []

    return mock_page


@pytest.fixture
def mock_pdfplumber_pdf(mock_pdfplumber_page):
    """Provide a mock pdfplumber PDF object."""
    mock_pdf = MagicMock()
    mock_pdf.pages = [mock_pdfplumber_page]
    mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
    mock_pdf.__exit__ = MagicMock(return_value=False)
    return mock_pdf
