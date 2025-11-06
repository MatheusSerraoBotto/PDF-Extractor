"""
OpenAI Responses API extraction with Pydantic structured outputs.

Provides direct OpenAI Responses API integration using responses.parse:
- Uses responses.parse with Pydantic for strict schema validation
- Dynamic Pydantic model creation from extraction schema
- Type-safe structured outputs with automatic validation
- Spatial layout-aware prompts (leverages position and coordinate metadata)
- Token counting for observability
- No retry or truncation logic (simple baseline)

The prompt engineering approach:
- Educates the LLM about rich spatial layout information (positions, coordinates)
- Uses clear role definition and extraction strategy
- Simplifies output format (field:value only, no confidence/rationale from LLM)
- Emphasizes exact text preservation and spatial disambiguation

Output structure:
- Each field returns: {"value": str|None, "details": {"source": "openai", "method": "responses.parse"}}
- Confidence and rationale removed for simplicity
- Pydantic validation ensures type safety
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from openai import OpenAI
from pydantic import BaseModel, Field, create_model

from src.config.settings import settings

logger = logging.getLogger(__name__)

# Tiktoken for token counting
try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False
    logger.warning("tiktoken not installed; token counting disabled. Install with: pip install tiktoken")


SYSTEM_PROMPT_TEMPLATE = """You are a specialized document data extraction assistant for '{label}' documents.

Your task is to extract structured information from documents with high precision.

## Core Principles
1. Extract ONLY information explicitly present in the document
2. Return null for fields that are not found or unclear
3. Use spatial layout information to disambiguate similar text
4. Return valid JSON only - no explanations or commentary

## Understanding the Document Layout
The document text includes rich spatial metadata in this format:
- [POSITION] indicates where text appears: TOP-LEFT, TOP-RIGHT, CENTER, BOTTOM-LEFT, etc.
- [x:start-end, y:position] shows precise coordinates on the page
- Text closer to target field descriptions (by position) is more likely to be the answer

## Extraction Strategy
1. Read the field description to understand what to look for
2. Scan the document layout for matching patterns
3. Use position clues to locate relevant areas
4. Extract the exact text value without modification
5. If multiple candidates exist, prefer text in positions matching the field description"""

USER_PROMPT_TEMPLATE = """## Extraction Task

Extract the following fields from the document below.

### Fields to Extract
```
{fields}
```

### Document Layout with Spatial Information
```
{layout}
```

## Instructions
- Extract each field value as it appears in the document
- Return null for fields that are not found or unclear
- Use the spatial coordinates to locate the correct values
- Preserve exact text formatting (capitalization, spacing, punctuation)"""


def count_tokens(text: str, model: str = "gpt-4") -> int:
    """
    Count tokens in text using tiktoken.

    Args:
        text: Text to count tokens for
        model: Model name (used to select appropriate encoding)

    Returns:
        Number of tokens in text (0 if tiktoken unavailable)
    """
    if not TIKTOKEN_AVAILABLE:
        return 0

    try:
        # Try to get encoding for specific model
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        # Fallback to cl100k_base (used by gpt-4, gpt-3.5-turbo, etc)
        encoding = tiktoken.get_encoding("cl100k_base")

    return len(encoding.encode(text))


def extract_fields(
    label: str,
    extraction_schema: Dict[str, str],
    doc_layout: str,
) -> Dict[str, Any]:
    """
    Extract all fields using OpenAI Responses API with Pydantic structured output.

    Uses responses.parse with dynamically created Pydantic models for strict schema validation.
    Leverages spatial layout information (positions and coordinates) for accurate field extraction.

    Args:
        label: Document type label (e.g., "carteira_oab")
        extraction_schema: Dict mapping field names to descriptions
        doc_layout: Full document text with spatial metadata (positions, coordinates)

    Returns:
        Dict mapping field names to extraction results with simplified format:
        {
            "field_name": {
                "value": str | None,
                "details": {"source": "openai"}
            }
        }

    Note:
        Uses responses.parse with Pydantic for type-safe structured outputs.
        Automatically validates schema and provides parsed objects.
    """
    if not settings.openai_api_key:
        logger.error("OPENAI_API_KEY not configured")
        return _fallback_error(extraction_schema, "openai_key_missing")

    # Build prompts
    fields_text = "\n".join([f"- {name}: {desc}" for name, desc in extraction_schema.items()])
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(label=label)
    user_prompt = USER_PROMPT_TEMPLATE.format(fields=fields_text, layout=doc_layout)

    # Log token counts for observability
    if TIKTOKEN_AVAILABLE:
        system_tokens = count_tokens(system_prompt, settings.llm_model)
        user_tokens = count_tokens(user_prompt, settings.llm_model)
        total_input_tokens = system_tokens + user_tokens
        logger.info(
            f"Prompt tokens: {total_input_tokens} "
            f"(system={system_tokens}, user={user_tokens})"
        )

    # Create dynamic Pydantic model from extraction schema
    pydantic_fields = {
        field_name: (Optional[str], Field(description=description))
        for field_name, description in extraction_schema.items()
    }
    ExtractionModel = create_model("ExtractionModel", **pydantic_fields)

    # Call OpenAI Responses API with Pydantic structured output
    try:
        client = OpenAI(api_key=settings.openai_api_key)

        logger.info(f"model={settings.llm_model}, max_tokens={settings.llm_max_output_tokens}")

        # Log system and user messages for debugging
        logger.debug(f"System prompt: {system_prompt}")
        logger.debug(f"User prompt: {user_prompt}")

        # Responses API with parse for strict Pydantic validation
        response = client.responses.parse(
            model=settings.llm_model,
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            text_format=ExtractionModel,
        )

        # Log response tokens
        usage = response.usage
        if usage:
            logger.info(f"Total tokens: {usage.total_tokens}")

        # Extract parsed Pydantic object
        parsed_data = response.output_parsed
        if not parsed_data:
            logger.warning("Empty parsed response from OpenAI")
            return _fallback_error(extraction_schema, "empty_response")

        # Convert Pydantic model to normalized dict
        return _normalize_pydantic_response(parsed_data, extraction_schema)

    except Exception as exc:  # noqa: BLE001
        logger.error(f"OpenAI API call failed: {exc}")
        return _fallback_error(extraction_schema, "openai_api_error")


def _normalize_pydantic_response(parsed_data: BaseModel, schema: Dict[str, str]) -> Dict[str, Any]:
    """
    Normalize Pydantic response from responses.parse to simplified standard format.

    Args:
        parsed_data: Pydantic BaseModel instance from response.output_parsed
        schema: Expected field schema (for validation)

    Returns:
        Normalized dict with simplified structure: {"field": {"value": ..., "details": {...}}}
    """
    normalized = {}

    for field_name in schema.keys():
        # Get value from Pydantic model
        raw_value = getattr(parsed_data, field_name, None)

        # Normalize value (handle string whitespace, None, etc.)
        if isinstance(raw_value, str):
            value = raw_value.strip() or None
        else:
            value = raw_value

        # Simplified structure: only value and details
        normalized[field_name] = {
            "value": value,
            "details": {"source": "openai", "method": "responses.parse"},
        }

    return normalized


def _normalize_response(result: Dict[str, Any], schema: Dict[str, str]) -> Dict[str, Any]:
    """
    Normalize LLM response to simplified standard format (legacy, kept for compatibility).

    Args:
        result: Raw JSON response from OpenAI (format: {"fields": {"field": "value"}})
        schema: Expected field schema

    Returns:
        Normalized dict with simplified structure: {"field": {"value": ..., "details": {...}}}
    """
    fields_section = result.get("fields", {})
    normalized = {}

    for field_name in schema.keys():
        raw_value = fields_section.get(field_name)

        # Normalize value (handle string whitespace, None, etc.)
        if isinstance(raw_value, str):
            value = raw_value.strip() or None
        else:
            value = raw_value

        # Simplified structure: only value and details
        normalized[field_name] = {
            "value": value,
            "details": {"source": "openai"},
        }

    return normalized


def _fallback_error(schema: Dict[str, str], reason: str) -> Dict[str, Any]:
    """
    Return fallback results when OpenAI call fails.

    Args:
        schema: Expected field schema
        reason: Error reason string

    Returns:
        Dict with all fields set to None and error details
    """
    results = {}
    for field_name in schema.keys():
        results[field_name] = {
            "value": None,
            "details": {"error": reason},
        }
    return results
