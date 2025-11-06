"""
Unit tests for src/core/llm_orchestrator.py

Tests OpenAI API integration, prompt building, response parsing, and error handling.
"""

from unittest.mock import MagicMock, patch

from pydantic import BaseModel

from src.core.llm_orchestrator import (
    _fallback_error,
    _normalize_pydantic_response,
    _normalize_response,
    count_tokens,
    extract_fields,
)


class TestCountTokens:
    """Test cases for token counting functionality."""

    @patch("src.core.llm_orchestrator.TIKTOKEN_AVAILABLE", True)
    def test_count_tokens_valid_text(self):
        """Test counting tokens for valid text."""
        with patch(
            "src.core.llm_orchestrator.tiktoken.encoding_for_model"
        ) as mock_encoding:
            mock_enc = MagicMock()
            mock_enc.encode.return_value = [1, 2, 3, 4, 5]  # 5 tokens
            mock_encoding.return_value = mock_enc

            result = count_tokens("Hello world, this is a test.")

            assert result == 5

    @patch("src.core.llm_orchestrator.TIKTOKEN_AVAILABLE", True)
    def test_count_tokens_empty_text(self):
        """Test counting tokens for empty text."""
        with patch(
            "src.core.llm_orchestrator.tiktoken.encoding_for_model"
        ) as mock_encoding:
            mock_enc = MagicMock()
            mock_enc.encode.return_value = []
            mock_encoding.return_value = mock_enc

            result = count_tokens("")

            assert result == 0

    @patch("src.core.llm_orchestrator.TIKTOKEN_AVAILABLE", True)
    def test_count_tokens_fallback_encoding(self):
        """Test token counting falls back to cl100k_base for unknown models."""
        with patch(
            "src.core.llm_orchestrator.tiktoken.encoding_for_model"
        ) as mock_model_enc:
            mock_model_enc.side_effect = KeyError("Unknown model")

            with patch(
                "src.core.llm_orchestrator.tiktoken.get_encoding"
            ) as mock_get_enc:
                mock_enc = MagicMock()
                mock_enc.encode.return_value = [1, 2, 3]
                mock_get_enc.return_value = mock_enc

                result = count_tokens("Test text", model="unknown-model")

                assert result == 3
                mock_get_enc.assert_called_once_with("cl100k_base")

    @patch("src.core.llm_orchestrator.TIKTOKEN_AVAILABLE", False)
    def test_count_tokens_unavailable(self):
        """Test token counting when tiktoken is unavailable."""
        result = count_tokens("This should return 0")

        assert result == 0


class TestNormalizePydanticResponse:
    """Test cases for Pydantic response normalization."""

    def test_normalize_pydantic_response_all_fields(self):
        """Test normalizing response with all fields present."""

        # Create a dynamic Pydantic model
        class TestModel(BaseModel):
            nome: str = "JOÃO DA SILVA"
            inscricao: str = "123456"
            categoria: str = "ADVOGADO"

        parsed_data = TestModel()
        schema = {"nome": "Nome", "inscricao": "Inscrição", "categoria": "Categoria"}

        result = _normalize_pydantic_response(parsed_data, schema)

        assert result["nome"]["value"] == "JOÃO DA SILVA"
        assert result["inscricao"]["value"] == "123456"
        assert result["categoria"]["value"] == "ADVOGADO"
        assert all("details" in field for field in result.values())

    def test_normalize_pydantic_response_with_none(self):
        """Test normalizing response with None values."""

        class TestModel(BaseModel):
            nome: str = "JOÃO DA SILVA"
            inscricao: str = None

        parsed_data = TestModel()
        schema = {"nome": "Nome", "inscricao": "Inscrição"}

        result = _normalize_pydantic_response(parsed_data, schema)

        assert result["nome"]["value"] == "JOÃO DA SILVA"
        assert result["inscricao"]["value"] is None

    def test_normalize_pydantic_response_whitespace_handling(self):
        """Test that whitespace-only strings are normalized to None."""

        class TestModel(BaseModel):
            nome: str = "  "
            inscricao: str = "123456"

        parsed_data = TestModel()
        schema = {"nome": "Nome", "inscricao": "Inscrição"}

        result = _normalize_pydantic_response(parsed_data, schema)

        assert result["nome"]["value"] is None  # Whitespace should become None
        assert result["inscricao"]["value"] == "123456"

    def test_normalize_pydantic_response_details_structure(self):
        """Test that details section has correct structure."""

        class TestModel(BaseModel):
            nome: str = "Test"

        parsed_data = TestModel()
        schema = {"nome": "Nome"}

        result = _normalize_pydantic_response(parsed_data, schema)

        assert result["nome"]["details"]["source"] == "openai"
        assert result["nome"]["details"]["method"] == "responses.parse"


class TestNormalizeResponse:
    """Test cases for legacy response normalization."""

    def test_normalize_response_valid_fields(self):
        """Test normalizing valid legacy response."""
        raw_response = {
            "fields": {
                "nome": "JOÃO DA SILVA",
                "inscricao": "123456",
            }
        }
        schema = {"nome": "Nome", "inscricao": "Inscrição"}

        result = _normalize_response(raw_response, schema)

        assert result["nome"]["value"] == "JOÃO DA SILVA"
        assert result["inscricao"]["value"] == "123456"

    def test_normalize_response_missing_fields(self):
        """Test normalizing response with missing fields."""
        raw_response = {"fields": {"nome": "JOÃO DA SILVA"}}
        schema = {"nome": "Nome", "inscricao": "Inscrição"}

        result = _normalize_response(raw_response, schema)

        assert result["nome"]["value"] == "JOÃO DA SILVA"
        assert result["inscricao"]["value"] is None

    def test_normalize_response_whitespace_handling(self):
        """Test whitespace normalization in legacy format."""
        raw_response = {
            "fields": {
                "nome": "  ",
                "inscricao": "  123456  ",
            }
        }
        schema = {"nome": "Nome", "inscricao": "Inscrição"}

        result = _normalize_response(raw_response, schema)

        assert result["nome"]["value"] is None
        assert result["inscricao"]["value"] == "123456"


class TestFallbackError:
    """Test cases for fallback error handling."""

    def test_fallback_error_creates_all_fields(self):
        """Test that fallback creates entries for all schema fields."""
        schema = {"nome": "Nome", "inscricao": "Inscrição", "categoria": "Categoria"}

        result = _fallback_error(schema, "test_error")

        assert len(result) == 3
        assert "nome" in result
        assert "inscricao" in result
        assert "categoria" in result

    def test_fallback_error_all_values_none(self):
        """Test that all fallback values are None."""
        schema = {"nome": "Nome", "inscricao": "Inscrição"}

        result = _fallback_error(schema, "test_error")

        assert result["nome"]["value"] is None
        assert result["inscricao"]["value"] is None

    def test_fallback_error_includes_reason(self):
        """Test that fallback includes error reason in details."""
        schema = {"nome": "Nome"}

        result = _fallback_error(schema, "openai_api_error")

        assert result["nome"]["details"]["error"] == "openai_api_error"


class TestExtractFields:
    """Test cases for main extract_fields function."""

    @patch("src.core.llm_orchestrator.OpenAI")
    @patch("src.core.llm_orchestrator.TIKTOKEN_AVAILABLE", False)
    def test_extract_fields_success(self, mock_openai_class, mock_settings):
        """Test successful field extraction."""

        # Create mock Pydantic response
        class MockModel(BaseModel):
            nome: str = "JOÃO DA SILVA"
            inscricao: str = "123456"

        mock_response = MagicMock()
        mock_response.output_parsed = MockModel()
        mock_response.usage.total_tokens = 1500

        mock_client = MagicMock()
        mock_client.responses.parse.return_value = mock_response
        mock_openai_class.return_value = mock_client

        schema = {"nome": "Nome", "inscricao": "Inscrição"}
        layout = "[TOP-LEFT] [x:100-200, y:50] JOÃO DA SILVA"

        result = extract_fields("test_doc", schema, layout)

        assert result["nome"]["value"] == "JOÃO DA SILVA"
        assert result["inscricao"]["value"] == "123456"

    def test_extract_fields_missing_api_key(self, monkeypatch):
        """Test extraction fails gracefully without API key."""
        # Set empty API key
        monkeypatch.setenv("OPENAI_API_KEY", "")

        # Clear and reload settings
        from src.config.settings import get_settings

        get_settings.cache_clear()

        # Patch settings at module level
        with patch("src.core.llm_orchestrator.settings") as mock_settings:
            mock_settings.openai_api_key = None

            schema = {"nome": "Nome"}
            layout = "test layout"

            result = extract_fields("test_doc", schema, layout)

            # Should return fallback with error
            assert result["nome"]["value"] is None
            assert "error" in result["nome"]["details"]

    @patch("src.core.llm_orchestrator.OpenAI")
    def test_extract_fields_api_error(self, mock_openai_class, mock_settings):
        """Test extraction handles API errors gracefully."""
        mock_client = MagicMock()
        mock_client.responses.parse.side_effect = Exception("API Error")
        mock_openai_class.return_value = mock_client

        schema = {"nome": "Nome", "inscricao": "Inscrição"}
        layout = "test layout"

        result = extract_fields("test_doc", schema, layout)

        # Should return fallback with all fields None
        assert result["nome"]["value"] is None
        assert result["inscricao"]["value"] is None
        assert result["nome"]["details"]["error"] == "openai_api_error"

    @patch("src.core.llm_orchestrator.OpenAI")
    def test_extract_fields_empty_response(self, mock_openai_class, mock_settings):
        """Test extraction handles empty parsed response."""
        mock_response = MagicMock()
        mock_response.output_parsed = None
        mock_response.usage = None

        mock_client = MagicMock()
        mock_client.responses.parse.return_value = mock_response
        mock_openai_class.return_value = mock_client

        schema = {"nome": "Nome"}
        layout = "test layout"

        result = extract_fields("test_doc", schema, layout)

        assert result["nome"]["value"] is None
        assert result["nome"]["details"]["error"] == "empty_response"

    @patch("src.core.llm_orchestrator.OpenAI")
    @patch("src.core.llm_orchestrator.TIKTOKEN_AVAILABLE", True)
    def test_extract_fields_logs_token_counts(self, mock_openai_class, mock_settings):
        """Test that token counts are logged when tiktoken is available."""

        class MockModel(BaseModel):
            nome: str = "Test"

        mock_response = MagicMock()
        mock_response.output_parsed = MockModel()
        mock_response.usage.total_tokens = 1500

        mock_client = MagicMock()
        mock_client.responses.parse.return_value = mock_response
        mock_openai_class.return_value = mock_client

        with patch("src.core.llm_orchestrator.count_tokens") as mock_count:
            mock_count.return_value = 100

            schema = {"nome": "Nome"}
            layout = "test layout"

            extract_fields("test_doc", schema, layout)

            # Should call count_tokens for system and user prompts
            assert mock_count.call_count >= 2

    @patch("src.core.llm_orchestrator.OpenAI")
    def test_extract_fields_uses_correct_model(self, mock_openai_class, mock_settings):
        """Test that extraction uses the configured model."""

        class MockModel(BaseModel):
            nome: str = "Test"

        mock_response = MagicMock()
        mock_response.output_parsed = MockModel()
        mock_response.usage.total_tokens = 1000

        mock_client = MagicMock()
        mock_client.responses.parse.return_value = mock_response
        mock_openai_class.return_value = mock_client

        schema = {"nome": "Nome"}
        layout = "test layout"

        extract_fields("test_doc", schema, layout)

        # Verify model parameter
        call_kwargs = mock_client.responses.parse.call_args[1]
        assert call_kwargs["model"] == mock_settings.llm_model

    @patch("src.core.llm_orchestrator.OpenAI")
    def test_extract_fields_prompt_includes_label(
        self, mock_openai_class, mock_settings
    ):
        """Test that prompts include document label."""

        class MockModel(BaseModel):
            nome: str = "Test"

        mock_response = MagicMock()
        mock_response.output_parsed = MockModel()
        mock_response.usage.total_tokens = 1000

        mock_client = MagicMock()
        mock_client.responses.parse.return_value = mock_response
        mock_openai_class.return_value = mock_client

        schema = {"nome": "Nome"}
        layout = "test layout"

        extract_fields("carteira_oab", schema, layout)

        # Check system prompt includes label
        call_kwargs = mock_client.responses.parse.call_args[1]
        messages = call_kwargs["input"]
        system_message = messages[0]["content"]

        assert "carteira_oab" in system_message

    @patch("src.core.llm_orchestrator.OpenAI")
    def test_extract_fields_prompt_includes_schema(
        self, mock_openai_class, mock_settings
    ):
        """Test that prompts include all schema fields."""

        class MockModel(BaseModel):
            nome: str = "Test"
            inscricao: str = "123"

        mock_response = MagicMock()
        mock_response.output_parsed = MockModel()
        mock_response.usage.total_tokens = 1000

        mock_client = MagicMock()
        mock_client.responses.parse.return_value = mock_response
        mock_openai_class.return_value = mock_client

        schema = {
            "nome": "Nome do profissional",
            "inscricao": "Número de inscrição",
        }
        layout = "test layout"

        extract_fields("test_doc", schema, layout)

        # Check user prompt includes all fields
        call_kwargs = mock_client.responses.parse.call_args[1]
        messages = call_kwargs["input"]
        user_message = messages[1]["content"]

        assert "nome" in user_message
        assert "inscricao" in user_message
        assert "Nome do profissional" in user_message

    @patch("src.core.llm_orchestrator.OpenAI")
    def test_extract_fields_prompt_includes_layout(
        self, mock_openai_class, mock_settings
    ):
        """Test that prompts include document layout."""

        class MockModel(BaseModel):
            nome: str = "Test"

        mock_response = MagicMock()
        mock_response.output_parsed = MockModel()
        mock_response.usage.total_tokens = 1000

        mock_client = MagicMock()
        mock_client.responses.parse.return_value = mock_response
        mock_openai_class.return_value = mock_client

        schema = {"nome": "Nome"}
        layout = "[TOP-LEFT] [x:100-200, y:50] JOÃO DA SILVA"

        extract_fields("test_doc", schema, layout)

        # Check user prompt includes layout
        call_kwargs = mock_client.responses.parse.call_args[1]
        messages = call_kwargs["input"]
        user_message = messages[1]["content"]

        assert layout in user_message
