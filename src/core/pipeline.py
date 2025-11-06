"""
High-level extraction pipeline orchestration.

Runs the end-to-end flow:
1. Cache lookup
2. PDF text/layout extraction
3. LLM extraction (all fields)
4. Post-processing and normalization
5. Cache population
"""

from __future__ import annotations

from time import perf_counter
from typing import Any, Dict

from src.core import llm_orchestrator
from src.core.cache import CacheClient
from src.core.extractor import (
    PdfExtractor,
    hash_extraction_schema,
    hash_pdf_bytes,
    load_pdf_bytes,
    resolve_pdf_path,
)
from src.models.schema import ExtractionRequest, ExtractionResult


def run_extraction(
    request: ExtractionRequest,
    use_cache: bool = True,
) -> ExtractionResult:
    """
    Execute the extraction pipeline synchronously.

    Raises:
        FileNotFoundError when the PDF is missing.
        ValueError for invalid inputs.
    """
    if not request.pdf_path:
        raise ValueError("pdf_path is required until direct uploads are supported.")

    pdf_path = resolve_pdf_path(request.pdf_path)
    pdf_bytes = load_pdf_bytes(pdf_path)
    pdf_hash = hash_pdf_bytes(pdf_bytes)
    schema_hash = hash_extraction_schema(request.extraction_schema)
    cache_key = f"extract:{request.label}:{pdf_hash}:{schema_hash}"

    cache_client = CacheClient()

    if use_cache:
        cached_payload = cache_client.get_json(cache_key)
        if cached_payload:
            cached_payload.setdefault("meta", {})
            cached_payload["meta"]["cache_hit"] = True
            cached_payload["meta"]["cache_key"] = cache_key
            return ExtractionResult.model_validate(cached_payload)

    timings: Dict[str, float] = {}
    total_start = perf_counter()

    # Extract PDF text and layout
    extractor = PdfExtractor()
    extract_start = perf_counter()
    doc = extractor.load(str(pdf_path))
    timings["extract"] = perf_counter() - extract_start

    # Use layout_text directly from extractor
    layout_text = doc.layout_text

    # Call LLM for ALL fields (no heuristics)
    llm_start = perf_counter()
    llm_results = llm_orchestrator.extract_fields(
        label=request.label,
        extraction_schema=request.extraction_schema,
        doc_layout=layout_text,
    )
    timings["llm"] = perf_counter() - llm_start

    # Build final field results (simple key-value)
    fields: Dict[str, Any] = {}
    for field_name, data in llm_results.items():
        fields[field_name] = data.get("value")

    timings["total"] = perf_counter() - total_start

    # Build metadata
    trace_info = {
        "llm_resolved": [f for f, d in llm_results.items() if d.get("value")],
        "unresolved": [f for f, d in llm_results.items() if not d.get("value")],
    }

    meta: Dict[str, Any] = {
        "cache_hit": False,
        "cache_key": cache_key,
        "pdf_hash": pdf_hash,
        "schema_hash": schema_hash,
        "timings_seconds": timings,
        "doc_meta": doc.meta,
        "trace": trace_info,
    }

    result = ExtractionResult(
        label=request.label,
        fields=fields,
        meta=meta,
    )

    cache_client.set_json(cache_key, result.model_dump())

    return result
