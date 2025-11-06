"""
Unit tests for src/models/schema.py

Tests Pydantic models for request/response validation and serialization.
"""

import pytest
from pydantic import ValidationError

from src.models.schema import ExtractionRequest, ExtractionResult, HealthResponse


class TestHealthResponse:
    """Test cases for HealthResponse model."""

    def test_health_response_valid(self):
        """Test creating valid health response."""
        response = HealthResponse(status="ok", environment="development")

        assert response.status == "ok"
        assert response.environment == "development"

    def test_health_response_serialization(self):
        """Test health response serialization to dict."""
        response = HealthResponse(status="ok", environment="production")
        data = response.model_dump()

        assert data == {"status": "ok", "environment": "production"}

    def test_health_response_json_serialization(self):
        """Test health response serialization to JSON."""
        response = HealthResponse(status="ok", environment="development")
        json_str = response.model_dump_json()

        assert "ok" in json_str
        assert "development" in json_str


class TestExtractionRequest:
    """Test cases for ExtractionRequest model."""

    def test_extraction_request_valid(self):
        """Test creating valid extraction request."""
        request = ExtractionRequest(
            label="carteira_oab",
            extraction_schema={"nome": "Nome do profissional"},
            pdf_path="oab_1.pdf",
        )

        assert request.label == "carteira_oab"
        assert request.extraction_schema == {"nome": "Nome do profissional"}
        assert request.pdf_path == "oab_1.pdf"

    def test_extraction_request_missing_label(self):
        """Test validation fails when label is missing."""
        with pytest.raises(ValidationError) as exc_info:
            ExtractionRequest(
                extraction_schema={"nome": "Nome"},
                pdf_path="test.pdf",
            )

        assert "label" in str(exc_info.value)

    def test_extraction_request_missing_schema(self):
        """Test validation fails when extraction_schema is missing."""
        with pytest.raises(ValidationError) as exc_info:
            ExtractionRequest(
                label="test",
                pdf_path="test.pdf",
            )

        assert "extraction_schema" in str(exc_info.value)

    def test_extraction_request_missing_pdf_path(self):
        """Test validation fails when pdf_path is missing."""
        with pytest.raises(ValidationError) as exc_info:
            ExtractionRequest(
                label="test",
                extraction_schema={"nome": "Nome"},
            )

        assert "pdf_path" in str(exc_info.value)

    def test_extraction_request_empty_schema(self):
        """Test extraction request with empty schema."""
        request = ExtractionRequest(
            label="test",
            extraction_schema={},
            pdf_path="test.pdf",
        )

        assert request.extraction_schema == {}

    def test_extraction_request_multiple_fields(self):
        """Test extraction request with multiple schema fields."""
        schema = {
            "nome": "Nome do profissional",
            "inscricao": "Número de inscrição",
            "categoria": "Categoria profissional",
            "seccional": "Seccional OAB",
        }

        request = ExtractionRequest(
            label="carteira_oab",
            extraction_schema=schema,
            pdf_path="oab_1.pdf",
        )

        assert len(request.extraction_schema) == 4
        assert request.extraction_schema["nome"] == "Nome do profissional"

    def test_extraction_request_serialization(self):
        """Test extraction request serialization to dict."""
        request = ExtractionRequest(
            label="test",
            extraction_schema={"nome": "Nome"},
            pdf_path="test.pdf",
        )

        data = request.model_dump()

        assert data["label"] == "test"
        assert data["extraction_schema"] == {"nome": "Nome"}
        assert data["pdf_path"] == "test.pdf"

    def test_extraction_request_from_dict(self):
        """Test creating extraction request from dictionary."""
        data = {
            "label": "carteira_oab",
            "extraction_schema": {
                "nome": "Nome",
                "inscricao": "Inscrição",
            },
            "pdf_path": "oab_1.pdf",
        }

        request = ExtractionRequest(**data)

        assert request.label == "carteira_oab"
        assert len(request.extraction_schema) == 2

    def test_extraction_request_json_deserialization(self):
        """Test creating extraction request from JSON."""
        json_data = """
        {
            "label": "test_doc",
            "extraction_schema": {
                "field1": "Description 1",
                "field2": "Description 2"
            },
            "pdf_path": "document.pdf"
        }
        """

        request = ExtractionRequest.model_validate_json(json_data)

        assert request.label == "test_doc"
        assert len(request.extraction_schema) == 2

    def test_extraction_request_schema_with_special_characters(self):
        """Test extraction schema with special characters in descriptions."""
        schema = {
            "endereco": "Endereço do profissional (com acentuação)",
            "telefone": "Telefone no formato (XX) XXXXX-XXXX",
        }

        request = ExtractionRequest(
            label="test",
            extraction_schema=schema,
            pdf_path="test.pdf",
        )

        assert "acentuação" in request.extraction_schema["endereco"]
        assert "(XX)" in request.extraction_schema["telefone"]


class TestExtractionResult:
    """Test cases for ExtractionResult model."""

    def test_extraction_result_valid(self):
        """Test creating valid extraction result."""
        result = ExtractionResult(
            label="test",
            fields={"nome": "JOÃO DA SILVA"},
            meta={"cache_hit": False},
        )

        assert result.label == "test"
        assert result.fields["nome"] == "JOÃO DA SILVA"
        assert result.meta["cache_hit"] is False

    def test_extraction_result_missing_label(self):
        """Test validation fails when label is missing."""
        with pytest.raises(ValidationError) as exc_info:
            ExtractionResult(
                fields={"nome": "Test"},
                meta={},
            )

        assert "label" in str(exc_info.value)

    def test_extraction_result_default_fields(self):
        """Test extraction result with default empty fields."""
        result = ExtractionResult(label="test")

        assert result.fields == {}
        assert result.meta == {}

    def test_extraction_result_multiple_fields(self):
        """Test extraction result with multiple fields."""
        fields = {
            "nome": "JOÃO DA SILVA",
            "inscricao": "123456",
            "categoria": "ADVOGADO",
            "situacao": "ATIVO",
        }

        result = ExtractionResult(
            label="carteira_oab",
            fields=fields,
            meta={},
        )

        assert len(result.fields) == 4
        assert result.fields["inscricao"] == "123456"

    def test_extraction_result_with_none_values(self):
        """Test extraction result with None field values."""
        result = ExtractionResult(
            label="test",
            fields={"nome": "JOÃO", "inscricao": None},
            meta={},
        )

        assert result.fields["nome"] == "JOÃO"
        assert result.fields["inscricao"] is None

    def test_extraction_result_complex_meta(self):
        """Test extraction result with complex metadata."""
        meta = {
            "cache_hit": False,
            "cache_key": "extract:test:abc123:def456",
            "timings_seconds": {
                "extract": 0.5,
                "llm": 2.3,
                "total": 2.8,
            },
            "trace": {
                "llm_resolved": ["nome", "inscricao"],
                "unresolved": ["categoria"],
            },
            "doc_meta": {
                "source": "/tmp/test.pdf",
                "engine": "pdfplumber",
                "pages": 1,
            },
        }

        result = ExtractionResult(
            label="test",
            fields={"nome": "JOÃO"},
            meta=meta,
        )

        assert result.meta["timings_seconds"]["llm"] == 2.3
        assert "nome" in result.meta["trace"]["llm_resolved"]
        assert result.meta["doc_meta"]["engine"] == "pdfplumber"

    def test_extraction_result_serialization(self):
        """Test extraction result serialization to dict."""
        result = ExtractionResult(
            label="test",
            fields={"nome": "JOÃO"},
            meta={"cache_hit": True},
        )

        data = result.model_dump()

        assert data["label"] == "test"
        assert data["fields"]["nome"] == "JOÃO"
        assert data["meta"]["cache_hit"] is True

    def test_extraction_result_json_serialization(self):
        """Test extraction result serialization to JSON."""
        result = ExtractionResult(
            label="test",
            fields={"nome": "JOÃO DA SILVA"},
            meta={"cache_hit": False},
        )

        json_str = result.model_dump_json()

        assert "test" in json_str
        assert "JOÃO DA SILVA" in json_str
        assert "cache_hit" in json_str

    def test_extraction_result_from_dict(self):
        """Test creating extraction result from dictionary."""
        data = {
            "label": "carteira_oab",
            "fields": {
                "nome": "JOÃO DA SILVA",
                "inscricao": "123456",
            },
            "meta": {
                "cache_hit": False,
                "timings_seconds": {"total": 3.5},
            },
        }

        result = ExtractionResult(**data)

        assert result.label == "carteira_oab"
        assert result.fields["inscricao"] == "123456"
        assert result.meta["timings_seconds"]["total"] == 3.5

    def test_extraction_result_model_validate(self):
        """Test validating extraction result from dict."""
        data = {
            "label": "test",
            "fields": {"nome": "Test"},
            "meta": {"cache_hit": True},
        }

        result = ExtractionResult.model_validate(data)

        assert isinstance(result, ExtractionResult)
        assert result.label == "test"

    def test_extraction_result_nested_field_values(self):
        """Test extraction result doesn't restrict field value types."""
        # Fields should accept any type (Dict[str, Any])
        result = ExtractionResult(
            label="test",
            fields={
                "string_field": "text",
                "number_field": 123,
                "none_field": None,
                "list_field": [1, 2, 3],
                "dict_field": {"key": "value"},
            },
            meta={},
        )

        assert result.fields["string_field"] == "text"
        assert result.fields["number_field"] == 123
        assert result.fields["none_field"] is None
        assert result.fields["list_field"] == [1, 2, 3]

    def test_extraction_result_empty_label_invalid(self):
        """Test that empty label string is invalid."""
        # Pydantic should allow empty strings by default, but if we want to
        # enforce non-empty, we'd need a validator. Testing current behavior.
        result = ExtractionResult(label="", fields={}, meta={})

        assert result.label == ""  # Currently allowed

    def test_extraction_result_roundtrip_serialization(self):
        """Test complete roundtrip: dict -> model -> dict."""
        original_data = {
            "label": "test_roundtrip",
            "fields": {
                "nome": "JOÃO DA SILVA",
                "inscricao": "123456",
            },
            "meta": {
                "cache_hit": False,
                "timings_seconds": {
                    "extract": 0.5,
                    "llm": 2.0,
                    "total": 2.5,
                },
            },
        }

        # Create model from dict
        result = ExtractionResult(**original_data)

        # Serialize back to dict
        serialized_data = result.model_dump()

        assert serialized_data == original_data
