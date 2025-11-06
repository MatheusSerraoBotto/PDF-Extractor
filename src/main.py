"""
FastAPI application entrypoint.

This module provides a minimal, extendable FastAPI app with a health endpoint.
Keep this file small and focused to serve as a stable import target for tests.
"""

import json
from typing import Any, Dict, List, Optional, Tuple

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import ValidationError

from src.config.settings import settings  # loads environment variables
from src.config.logging import setup_logging

# Initialize logging on startup
setup_logging()
from src.core.evaluation import DocumentEvaluation, aggregate_metrics, evaluate_document
from src.core.pipeline import run_extraction
from src.models.schema import (
    ExtractionRequest,
    ExtractionResult,
    FieldMismatchModel,
    HealthResponse,
    TestDocumentResult,
    TestExtractionRequest,
    TestExtractionResponse,
    TestMetrics,
    TestSummary,
)

app = FastAPI(title="PDF Extraction AI", version="0.1.0")


@app.get("/health", response_model=HealthResponse)
async def health():
    """
    Health endpoint that returns basic service status and environment info.
    """
    return HealthResponse(status="ok", environment=settings.env)


@app.post("/extract", response_model=ExtractionResult)
async def extract(
    request: ExtractionRequest,
    use_cache: bool = Query(True, description="Toggle cache usage for this request."),
):
    """
    Run the full extraction pipeline for a single document.
    """
    try:
        result = await run_in_threadpool(
            run_extraction,
            request,
            use_cache=use_cache,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Extraction pipeline error: {exc}") from exc

    return result


@app.post("/extract/test", response_model=TestExtractionResponse)
async def extract_test(
    dataset: UploadFile = File(..., description="JSON dataset file containing extraction items."),
) -> TestExtractionResponse:
    """
    Execute the extraction pipeline for a batch of documents, optionally
    evaluating predictions against provided ground truth payloads.
    """
    try:
        raw_bytes = await dataset.read()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Failed to read uploaded dataset: {exc}") from exc

    if not raw_bytes:
        raise HTTPException(status_code=400, detail="Uploaded dataset file is empty.")

    try:
        payload_text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="Uploaded dataset must be UTF-8 encoded.") from exc

    try:
        payload = json.loads(payload_text)
    except json.JSONDecodeError as exc:
        location = f"{exc.lineno}:{exc.colno}"
        raise HTTPException(status_code=400, detail=f"Invalid JSON ({location}): {exc.msg}") from exc

    if isinstance(payload, list):
        payload_data: Dict[str, Any] = {"items": payload}
    elif isinstance(payload, dict):
        payload_data = payload
    else:
        raise HTTPException(status_code=400, detail="Dataset JSON must be an object or an array of items.")

    try:
        request_model = TestExtractionRequest.model_validate(payload_data)
    except ValidationError as exc:
        raise HTTPException(
            status_code=400,
            detail={"message": "Dataset payload validation failed.", "errors": exc.errors()},
        ) from exc

    if not request_model.items:
        raise HTTPException(status_code=400, detail="Dataset must include at least one item.")

    document_results: List[DocumentEvaluation] = []

    for item in request_model.items:
        extraction_request = ExtractionRequest(
            label=item.label,
            extraction_schema=item.extraction_schema,
            pdf_path=item.pdf_path,
        )

        prediction: Dict[str, Any] = {}
        total_time_seconds: Optional[float] = None
        error_message: Optional[str] = None

        try:
            extraction_result = await run_in_threadpool(
                run_extraction,
                extraction_request,
                use_cache=False,
            )
            prediction = _build_prediction(extraction_result)
            total_time_seconds = _get_total_time_seconds(extraction_result.meta)
        except FileNotFoundError as exc:
            error_message = str(exc)
        except ValueError as exc:
            error_message = str(exc)
        except Exception as exc:  # noqa: BLE001
            error_message = f"Extraction pipeline error: {exc}"

        evaluation = evaluate_document(
            label=item.label,
            pdf_path=item.pdf_path,
            prediction=prediction,
            ground_truth=item.gt,
            time_seconds=total_time_seconds,
            error=error_message,
        )

        document_results.append(evaluation)

    document_results.sort(key=_document_sort_key)

    metrics, summary = aggregate_metrics(document_results)

    response_documents: List[TestDocumentResult] = []
    for evaluation in document_results:
        response_documents.append(
            TestDocumentResult(
                label=evaluation.label,
                pdf_path=evaluation.pdf_path,
                prediction=evaluation.prediction,
                gt=evaluation.gt,
                has_gt=evaluation.has_gt,
                evaluated=evaluation.evaluated,
                accuracy=evaluation.accuracy,
                fields_total=evaluation.fields_total,
                fields_correct=evaluation.fields_correct,
                correct_fields=evaluation.correct_fields,
                wrong_fields=[
                    FieldMismatchModel(field=mismatch.field, expected=mismatch.expected, predicted=mismatch.predicted)
                    for mismatch in evaluation.wrong_fields
                ],
                missing_fields=evaluation.missing_fields,
                extra_fields=evaluation.extra_fields,
                time_ms=evaluation.time_ms,
                error=evaluation.error,
            )
        )

    return TestExtractionResponse(
        summary=TestSummary(
            items_received=summary.items_received,
            docs_evaluated=summary.docs_evaluated,
            docs_with_gt=summary.docs_with_gt,
            docs_without_gt=summary.docs_without_gt,
            docs_failed=summary.docs_failed,
        ),
        metrics=TestMetrics(
            fields_total=metrics.fields_total,
            fields_correct=metrics.fields_correct,
            accuracy_overall=metrics.accuracy_overall,
            accuracy_mean_docs=metrics.accuracy_mean_docs,
            time_avg_ms=metrics.time_avg_ms,
        ),
        documents=response_documents,
    )


def _build_prediction(result: ExtractionResult) -> Dict[str, Any]:
    """
    Flatten ExtractionResult fields into a simplified prediction dict.
    """
    return {field_name: field_result.value for field_name, field_result in result.fields.items()}


def _get_total_time_seconds(meta: Dict[str, Any]) -> Optional[float]:
    """
    Extract the total timing entry from the metadata, if present.
    """
    if not isinstance(meta, dict):
        return None
    timings = meta.get("timings_seconds")
    if not isinstance(timings, dict):
        return None
    total = timings.get("total")
    if total is None:
        return None
    try:
        return float(total)
    except (TypeError, ValueError):
        return None


def _document_sort_key(evaluation: DocumentEvaluation) -> Tuple[int, int, float]:
    """
    Sort key that prioritizes errored documents and then ascending accuracy.
    """
    error_rank = 0 if evaluation.error is None else -1
    accuracy = float(evaluation.accuracy) if evaluation.accuracy is not None else 1.0
    evaluated_rank = 0 if evaluation.evaluated else 1
    return (error_rank, evaluated_rank, accuracy)
