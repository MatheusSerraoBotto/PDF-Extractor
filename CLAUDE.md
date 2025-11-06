# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Status

**Current Phase**: STABLE - Optimization Phase

The application has reached a stable baseline and is now entering the optimization phase. The core extraction pipeline is functional and reliable, with proper error handling, caching, and observability.

**Next Focus**: Performance optimization, cost reduction, and accuracy improvements while maintaining the stable foundation.

## Project Overview

This is a **simple PDF extraction service** that uses OpenAI's LLM to extract structured data from documents. The system is currently focused on single-page PDFs with embedded OCR text.

**Design Philosophy**: Simple, functional baseline. Direct OpenAI API integration with structured JSON output for measuring pure LLM extraction performance.

## Architecture

### Extraction Pipeline Flow

```
PDF → Cache Check → PDF Extraction (pdfplumber) → LLM (OpenAI) → Post-processing → Cache Write → Result
```

The pipeline is orchestrated in [src/core/pipeline.py](src/core/pipeline.py):

1. **Cache lookup**: SHA256 hash of (PDF bytes + schema) checks Redis
2. **PDF extraction**: [src/core/extractor.py](src/core/extractor.py) uses pdfplumber to extract text line by line
3. **LLM extraction**: [src/core/llm_orchestrator.py](src/core/llm_orchestrator.py) sends all fields to OpenAI with structured JSON output
4. **Post-processing**: [src/core/postprocess.py](src/core/postprocess.py) validates and normalizes results
5. **Cache write**: Result stored in Redis for future requests

### Key Components

- **Pipeline orchestration**: `run_extraction()` in [src/core/pipeline.py](src/core/pipeline.py) coordinates the entire flow
- **LLM orchestrator**: Direct OpenAI API integration with structured JSON output (no LangChain)
- **Confidence tracking**: Every field includes a confidence score (0-1) and source attribution (llm/unresolved)
- **Cache layer**: Redis-backed caching prevents reprocessing identical documents
- **Token counting**: Uses tiktoken for observability (input/output token logging)

### File Structure

```
src/
├── main.py                    # FastAPI app with /health, /extract, /extract/test endpoints
├── config/settings.py         # Pydantic settings from environment variables
├── models/schema.py           # Request/response models (ExtractionRequest, ExtractionResult, etc.)
├── core/
│   ├── pipeline.py           # Orchestrates extraction flow (~140 lines)
│   ├── extractor.py          # PDF extraction with pdfplumber (simple line-by-line extraction)
│   ├── llm_orchestrator.py  # Direct OpenAI API with structured output (~240 lines)
│   ├── postprocess.py        # Validation and normalization (stub)
│   ├── cache.py              # Redis cache abstraction
│   └── evaluation.py         # Accuracy calculation for /extract/test
```

## PDF Extraction with pdfplumber

The extractor module ([src/core/extractor.py](src/core/extractor.py)) is simple and straightforward:

### Key Features

1. **Simple text extraction**: Uses pdfplumber to extract text line by line from first page
2. **Line-based blocks**: Each line becomes a TextBlock with basic metadata
3. **Plain text focus**: Provides full_text and raw_markdown for LLM input
4. **Path resolution**: Supports absolute paths, relative paths, and `PDF_BASE_PATH` configuration
5. **Utility functions**: PDF hashing, schema hashing, byte loading

### ExtractedDocument Structure

```python
@dataclass
class ExtractedDocument:
    blocks: List[TextBlock]         # Structured text blocks with metadata
    meta: Dict[str, Any]             # Extraction metadata (engine, pages, source)
    raw_markdown: str                # Full markdown output
    full_text: str                   # Plain text (markdown formatting removed)
    layout_text: str                 # Text with layout info for LLM
```

### Text Blocks with Metadata

Each `TextBlock` contains:

- `text`: The actual text content (one line from PDF)
- `metadata`: Dict with `type` set to "line"

Simple and straightforward - each line is a block.

### Utility Functions

All PDF-related utilities are in [src/core/extractor.py](src/core/extractor.py):

- `resolve_pdf_path(pdf_path_str)`: Resolves PDF paths with base path support
- `load_pdf_bytes(pdf_path)`: Loads PDF as bytes
- `hash_pdf_bytes(pdf_bytes)`: SHA256 hash for caching
- `hash_extraction_schema(schema)`: Hash of extraction schema for cache keys

## Development Commands

### Docker-based Development (Recommended)

```bash
# Start all services (API, Redis, SQLite)
docker compose -f docker/docker-compose.yml up --build

# Stop services
docker compose -f docker/docker-compose.yml down

# View logs
docker compose -f docker/docker-compose.yml logs -f api
```

The API runs on http://localhost:8000. Health check: http://localhost:8000/health

Port 5678 is exposed for debugpy remote debugging.

### Testing

```bash
# Run tests inside container (preferred for Docker dependencies)
docker exec -it pdf-ai-api pytest -q

# Run tests with coverage
docker exec -it pdf-ai-api pytest --cov=src --cov-report=term-missing

# Run specific test file
docker exec -it pdf-ai-api pytest tests/unit/test_extractor_pdf.py -v

# Run with custom environment
docker exec -it pdf-ai-api env DATABASE_URL=sqlite:////tmp/test.db pytest -q

# Run tests on host (requires local Python setup)
pip install -r requirements.txt -r requirements-dev.txt
pytest -q
```

### Code Quality

```bash
# Format code (inside container)
docker exec -it pdf-ai-api black .

# Lint (inside container)
docker exec -it pdf-ai-api ruff check . --fix

# Sort imports (inside container)
docker exec -it pdf-ai-api isort .

# Run all checks (CI pipeline)
ruff check . --fix && black . && isort . && pytest -q
```

CI runs automatically on push/PR and checks: ruff, black, isort, pytest.

## Configuration

Environment variables are loaded from `.env` (copy from `.env.example`):

### Critical Settings

- **OPENAI_API_KEY**: Required for OpenAI API access
- **LLM_MODEL**: OpenAI model identifier (default: `gpt-5-mini`)
- **LLM_MAX_OUTPUT_TOKENS**: Maximum tokens in LLM output (default: 2000)
- **PDF_BASE_PATH**: Base directory for resolving relative PDF paths (default: `.samples/files`)
- **REDIS_HOST/REDIS_PORT**: Cache connection (default: `redis:6379` in Docker)

### OpenAI Configuration

- Only use gpt-5-mini, change the model is not a choice

```bash
OPENAI_API_KEY=sk-...
LLM_MODEL=gpt-5-mini
LLM_MAX_OUTPUT_TOKENS=800
```

## Extraction Request Format

```json
{
  "label": "documento_exemplo",
  "extraction_schema": {
    "campo1": "Descrição clara do primeiro campo a ser extraído",
    "campo2": "Descrição clara do segundo campo, incluindo localização esperada",
    "campo3": "Descrição do terceiro campo com contexto semântico"
  },
  "pdf_path": "documento.pdf"
}
```

Field descriptions are used by the LLM for semantic understanding during extraction. The application is **document-agnostic** - it works with any PDF type based on the schema you provide.

## LLM Integration

The LLM orchestrator ([src/core/llm_orchestrator.py](src/core/llm_orchestrator.py)) uses direct OpenAI API:

### Key Features

1. **Structured output**: Uses OpenAI's JSON mode (`response_format={"type": "json_object"}`)
2. **Token counting**: Uses tiktoken for observability (logs input/output tokens)
3. **No retries**: Simple baseline - single API call per extraction
4. **No truncation**: Full document sent to LLM (no smart truncation logic)
5. **Error handling**: Returns fallback results on API errors

### Function Signature

```python
def extract_fields(
    label: str,
    extraction_schema: Dict[str, str],
    doc_layout: str,
) -> Dict[str, Any]:
    """Extract all fields using OpenAI API with structured output."""
```

Returns a dict with format:
```python
{
    "field_name": {
        "value": str | None,
        "confidence": float,
        "rationale": str,
        "details": dict
    }
}
```

### Prompt Structure

**System Prompt**: Simple instruction to extract structured data accurately

**User Prompt**:
- List of requested fields with descriptions
- Full document text/layout
- JSON output format specification

## Testing and Evaluation

The `/extract/test` endpoint accepts a JSON dataset for batch extraction and evaluation:

```json
{
  "items": [
    {
      "label": "carteira_oab",
      "extraction_schema": { "nome": "...", "inscricao": "..." },
      "pdf_path": "oab_1.pdf",
      "gt": { "nome": "JOÃO DA SILVA", "inscricao": "123456" }
    }
  ]
}
```

Returns per-document accuracy metrics:
- **Field-level accuracy**: Correct/total fields
- **Document-level accuracy**: Mean across documents
- **Timing**: Average extraction time per document
- **Mismatches**: Lists expected vs predicted for wrong fields

Use this for measuring LLM extraction performance against ground truth datasets.

## Performance Characteristics

### Current Baseline (Stable)

- **Cache hits**: Identical (PDF + schema) returns cached result in <10ms
- **LLM-only extraction**: All fields sent to OpenAI in single request (~2-5 seconds typical)
- **Token usage**: Logged for every request (input/output/total tokens)
- **Redis TTL**: Cache entries expire after 600 seconds (configurable in `CacheClient.set_json()`)
- **Accuracy**: High confidence extraction for well-structured documents
- **Reliability**: Stable error handling and fallback mechanisms

### Optimization Goals

The following areas are targets for optimization in the current phase:

1. **Latency Reduction**
   - Target: <1s average response time for cache misses
   - Strategies: Prompt optimization, parallel processing, streaming responses

2. **Cost Optimization**
   - Target: Minimize token usage without sacrificing accuracy
   - Strategies: Smarter prompt design, field batching, context pruning

3. **Accuracy Improvements**
   - Target: >95% field-level accuracy on ground truth dataset
   - Strategies: Better field descriptions, post-processing rules, confidence thresholds

4. **Scalability**
   - Target: Support concurrent requests efficiently
   - Strategies: Connection pooling, async processing, resource limits

## Common Patterns

### Making an Extraction Request

```bash
curl -X POST http://localhost:8000/extract \
  -H "Content-Type: application/json" \
  -d '{
    "label": "documento_exemplo",
    "extraction_schema": {
      "campo1": "Descrição do primeiro campo",
      "campo2": "Descrição do segundo campo"
    },
    "pdf_path": "documento.pdf"
  }'
```

### Disabling Cache

Add query parameter `?use_cache=false`:

```bash
curl -X POST "http://localhost:8000/extract?use_cache=false" \
  -H "Content-Type: application/json" \
  -d '{ ... }'
```

## Debugging

### Enable Remote Debugging

Set `ENABLE_DEBUGPY=1` in `.env`, then connect your IDE to `localhost:5678`.

### View Extraction Metadata

The `ExtractionResult.meta` field includes:
- `timings_seconds`: Breakdown of extract/llm/total time
- `trace.llm_resolved`: List of fields resolved by LLM
- `trace.unresolved`: List of fields that couldn't be extracted
- `doc_meta`: PDF metadata (pages, source, engine)
- `cache_hit`: Whether result came from cache

### Token Logging

Token counts are logged for every LLM call:
```
INFO: Prompt tokens: 1234 (system=56, user=1178)
INFO: Completion tokens: 234
INFO: Total tokens: 1468
```

### Common Issues

**LLM not responding**: Check that:
1. `OPENAI_API_KEY` is set and valid
2. Model name is correct (e.g., `gpt-5-mini`)
3. Check logs for API errors

**Empty extractions**: Check `trace.unresolved` in result metadata for details. Common causes:
- Field descriptions not clear enough for LLM
- Document text quality issues (OCR problems)
- LLM returned null values (check confidence scores)

**Cache not working**: Ensure Redis is running (`docker compose ps`). Test connection: `docker exec -it pdf-ai-redis redis-cli ping`

## Important Constraints

- **Single-page PDFs only**: Multi-page PDFs will only extract from first page (see [src/core/extractor.py](src/core/extractor.py))
- **OCR pre-required**: PDFs must have embedded text (no OCR engine included)
- **Synchronous pipeline**: Extraction runs in blocking mode (uses `run_in_threadpool` for FastAPI)
- **OpenAI only**: No support for other providers (removed Ollama, custom providers)
- **No retry logic**: Single API call per extraction (simple baseline)

## Working with Different Document Types

The system is **completely document-agnostic**. To extract from any PDF:

1. Create request with appropriate `label` and `extraction_schema`
2. Define clear field descriptions to guide LLM extraction
3. Test with `/extract` endpoint
4. If needed, adjust field descriptions for better accuracy
5. Build ground truth dataset and validate with `/extract/test`

All extraction logic is driven by the schema descriptions you provide - there are no hardcoded document types or field assumptions.

## Code Structure Summary

| File | Lines | Purpose |
|------|-------|---------|
| `src/main.py` | ~230 | FastAPI endpoints |
| `src/core/pipeline.py` | ~140 | Extraction orchestration |
| `src/core/llm_orchestrator.py` | ~240 | OpenAI API integration |
| `src/core/extractor.py` | ~150 | PDF text extraction |
| `src/config/settings.py` | ~50 | Configuration |
| `src/models/schema.py` | ~140 | Data models |

Total core code: ~950 lines (simplified from ~1400 lines)

## Dependencies

**Core**:
- `fastapi` - Web framework
- `pdfplumber` - PDF text extraction
- `openai` - OpenAI API client
- `tiktoken` - Token counting
- `redis` - Caching

**Removed**:
- `langchain`, `langchain-openai`, `langchain-community` - Replaced with direct OpenAI API

See [requirements.txt](requirements.txt) for full dependency list.
