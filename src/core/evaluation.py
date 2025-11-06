"""
Utilities to evaluate extraction results against ground-truth annotations.

This module provides helpers to compute per-document accuracy metrics and
aggregate dataset-level statistics that can be reused by API layers or tests.
"""

from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


@dataclass
class FieldMismatch:
    """Represents a field mismatch with the expectation and the predicted value."""

    field: str
    expected: Any
    predicted: Any


@dataclass
class DocumentEvaluation:
    """Per-document evaluation outcome."""

    label: str
    pdf_path: str
    prediction: Dict[str, Any]
    gt: Optional[Dict[str, Any]]
    has_gt: bool
    evaluated: bool
    accuracy: Optional[float]
    fields_total: int
    fields_correct: int
    correct_fields: List[str] = field(default_factory=list)
    wrong_fields: List[FieldMismatch] = field(default_factory=list)
    missing_fields: List[str] = field(default_factory=list)
    extra_fields: List[str] = field(default_factory=list)
    time_ms: Optional[float] = None
    error: Optional[str] = None


@dataclass
class AggregateMetrics:
    """Dataset-level aggregate metrics."""

    fields_total: int
    fields_correct: int
    accuracy_overall: Optional[float]
    accuracy_mean_docs: Optional[float]
    time_avg_ms: Optional[float]


@dataclass
class SummaryCounters:
    """Counters to describe which documents were evaluated or skipped."""

    items_received: int
    docs_evaluated: int
    docs_with_gt: int
    docs_without_gt: int
    docs_failed: int


def _strip_accents(text: str) -> str:
    """
    Remove diacritics from a string by decomposing and dropping combining marks.
    """
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


_WHITESPACE_RE = re.compile(r"\s+")


def normalize_value(value: Any) -> str:
    """
    Normalize values for comparison.

    Numbers and booleans are stringified; strings are lower-cased,
    accents stripped, and extra whitespace collapsed.
    Complex structures (dict/list) are JSON-like stringified.
    """
    if value is None:
        return ""

    if isinstance(value, bool):
        # Represent as lower-case "true"/"false"
        return "true" if value else "false"

    if isinstance(value, (int, float)):
        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            return ""
        return str(value).strip()

    if isinstance(value, (dict, list, tuple, set)):
        # Recurse on iterables by converting to sorted tuples when possible.
        if isinstance(value, dict):
            items = sorted(value.items())
            return normalize_value(items)
        iterable = list(value)
        normalized_parts = [normalize_value(item) for item in iterable]
        return "[" + ", ".join(normalized_parts) + "]"

    text = str(value)
    text = _strip_accents(text)
    text = text.lower()
    text = _WHITESPACE_RE.sub(" ", text)
    return text.strip()


def values_match(expected: Any, predicted: Any) -> bool:
    """
    Decide whether two values match according to normalization rules.
    """
    if expected is None:
        return predicted is None or normalize_value(predicted) == ""

    return normalize_value(expected) == normalize_value(predicted)


def evaluate_document(
    *,
    label: str,
    pdf_path: str,
    prediction: Dict[str, Any],
    ground_truth: Optional[Dict[str, Any]],
    time_seconds: Optional[float],
    error: Optional[str] = None,
) -> DocumentEvaluation:
    """
    Evaluate a single document prediction payload against its ground truth.
    """
    if error is not None:
        return DocumentEvaluation(
            label=label,
            pdf_path=pdf_path,
            prediction=prediction,
            gt=ground_truth,
            has_gt=ground_truth is not None,
            evaluated=False,
            accuracy=None,
            fields_total=len(ground_truth or {}),
            fields_correct=0,
            time_ms=_seconds_to_ms(time_seconds),
            error=error,
        )

    has_gt = ground_truth is not None
    fields_total = len(ground_truth or {})
    correct_fields: List[str] = []
    wrong_fields: List[FieldMismatch] = []
    missing_fields: List[str] = []

    if not has_gt or fields_total == 0:
        # No GT available, nothing to evaluate.
        return DocumentEvaluation(
            label=label,
            pdf_path=pdf_path,
            prediction=prediction,
            gt=ground_truth,
            has_gt=has_gt,
            evaluated=False,
            accuracy=None,
            fields_total=fields_total,
            fields_correct=0,
            correct_fields=[],
            wrong_fields=[],
            missing_fields=[],
            extra_fields=_compute_extra_fields(prediction.keys(), []),
            time_ms=_seconds_to_ms(time_seconds),
        )

    # Evaluate fields present in ground truth.
    for field_name, expected_value in (ground_truth or {}).items():
        if field_name not in prediction:
            missing_fields.append(field_name)
            continue

        predicted_value = prediction[field_name]
        if values_match(expected_value, predicted_value):
            correct_fields.append(field_name)
        else:
            wrong_fields.append(
                FieldMismatch(
                    field=field_name,
                    expected=expected_value,
                    predicted=predicted_value,
                )
            )

    fields_correct = len(correct_fields)
    accuracy = fields_correct / fields_total if fields_total else None

    extra_fields = _compute_extra_fields(prediction.keys(), (ground_truth or {}).keys())

    return DocumentEvaluation(
        label=label,
        pdf_path=pdf_path,
        prediction=prediction,
        gt=ground_truth,
        has_gt=has_gt,
        evaluated=True,
        accuracy=accuracy,
        fields_total=fields_total,
        fields_correct=fields_correct,
        correct_fields=correct_fields,
        wrong_fields=wrong_fields,
        missing_fields=missing_fields,
        extra_fields=extra_fields,
        time_ms=_seconds_to_ms(time_seconds),
    )


def aggregate_metrics(documents: Sequence[DocumentEvaluation]) -> Tuple[AggregateMetrics, SummaryCounters]:
    """
    Aggregate per-document evaluations into dataset-level metrics and counters.
    """
    docs_evaluated = [doc for doc in documents if doc.evaluated]
    fields_total = sum(doc.fields_total for doc in docs_evaluated)
    fields_correct = sum(doc.fields_correct for doc in docs_evaluated)

    if fields_total:
        accuracy_overall = fields_correct / fields_total
    else:
        accuracy_overall = None

    doc_accuracies = [doc.accuracy for doc in docs_evaluated if doc.accuracy is not None]
    accuracy_mean_docs = (
        sum(doc_accuracies) / len(doc_accuracies) if doc_accuracies else None
    )

    timings = [doc.time_ms for doc in documents if doc.time_ms is not None and doc.error is None]
    time_avg_ms = sum(timings) / len(timings) if timings else None

    counters = SummaryCounters(
        items_received=len(documents),
        docs_evaluated=len(docs_evaluated),
        docs_with_gt=sum(1 for doc in documents if doc.has_gt),
        docs_without_gt=sum(1 for doc in documents if not doc.has_gt),
        docs_failed=sum(1 for doc in documents if doc.error is not None),
    )

    metrics = AggregateMetrics(
        fields_total=fields_total,
        fields_correct=fields_correct,
        accuracy_overall=accuracy_overall,
        accuracy_mean_docs=accuracy_mean_docs,
        time_avg_ms=time_avg_ms,
    )

    return metrics, counters


def _seconds_to_ms(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None

    try:
        return float(value) * 1000.0
    except (TypeError, ValueError):
        return None


def _compute_extra_fields(
    prediction_keys: Iterable[str],
    gt_keys: Iterable[str],
) -> List[str]:
    pred_set = set(prediction_keys)
    gt_set = set(gt_keys)
    extra = sorted(pred_set - gt_set)
    return extra
