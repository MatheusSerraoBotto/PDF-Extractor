"""
Pydantic data models for requests and responses.
These models define the contract between the API layer and the core services.
"""

from typing import Dict, Optional, Any, List
from pydantic import BaseModel, Field

class HealthResponse(BaseModel):
    """Health check response model."""
    status: str
    environment: str

class ExtractionRequest(BaseModel):
    """Input contract for an extraction request."""

    model_config = {
        "json_schema_extra": {
            "example": {
                "label": "carteira_oab",
                "extraction_schema": {
                    "nome": "Nome do profissional, normalmente no canto superior esquerdo da imagem",
                    "inscricao": "Número de inscrição do profissional",
                    "seccional": "Seccional do profissional",
                    "subsecao": "Subseção à qual o profissional faz parte",
                    "categoria": "Categoria, pode ser ADVOGADO, ADVOGADA, SUPLEMENTAR, ESTAGIARIO, ESTAGIARIA",
                    "endereco_profissional": "Endereço do profissional",
                    "telefone_profissional": "Telefone do profissional",
                    "situacao": "Situação do profissional, normalmente no canto inferior direito.",
                },
                "pdf_path": "oab_1.pdf",
            }
        }
    }

    label: str = Field(..., description="Document label, e.g., 'carteira_oab'.")
    extraction_schema: Dict[str, str] = Field(
        ..., description="Field name -> description mapping."
    )
    pdf_path: str = Field(
        ..., description="Local path to the PDF file (single page, OCR embedded)."
    )
    # If you later support bytes upload, add: pdf_bytes: Optional[bytes]


class FieldResult(BaseModel):
    """Represents a single field extraction result (simplified structure)."""
    value: Optional[str]
    details: Dict[str, Any] = Field(
        default_factory=dict, description="Metadata about extraction (source, errors, etc.)."
    )


class ExtractionResult(BaseModel):
    """Output contract of the extraction pipeline."""
    label: str
    fields: Dict[str, FieldResult]
    meta: Dict[str, Any] = Field(
        default_factory=dict,
        description="Timing, cache info, tokens, etc."
    )


class TestExtractionItem(ExtractionRequest):
    """Single dataset item used for batch testing."""

    gt: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Ground truth values expected for this document.",
    )


class TestExtractionRequest(BaseModel):
    """Payload for the /extract/test route."""

    items: List[TestExtractionItem] = Field(
        ..., description="Items to extract and optionally evaluate."
    )


class FieldMismatchModel(BaseModel):
    """Represents a mismatch between prediction and expected value."""

    field: str
    expected: Any
    predicted: Any


class TestDocumentResult(BaseModel):
    """Per-document result in the /extract/test response."""

    label: str
    pdf_path: str
    prediction: Dict[str, Any] = Field(default_factory=dict)
    gt: Optional[Dict[str, Any]] = None
    has_gt: bool = False
    evaluated: bool = False
    accuracy: Optional[float] = None
    fields_total: int = 0
    fields_correct: int = 0
    correct_fields: List[str] = Field(default_factory=list)
    wrong_fields: List[FieldMismatchModel] = Field(default_factory=list)
    missing_fields: List[str] = Field(default_factory=list)
    extra_fields: List[str] = Field(default_factory=list)
    time_ms: Optional[float] = None
    error: Optional[str] = None


class TestMetrics(BaseModel):
    """Aggregated metrics across the dataset."""

    fields_total: int = 0
    fields_correct: int = 0
    accuracy_overall: Optional[float] = None
    accuracy_mean_docs: Optional[float] = None
    time_avg_ms: Optional[float] = None


class TestSummary(BaseModel):
    """High-level counters summarizing the batch run."""

    items_received: int = 0
    docs_evaluated: int = 0
    docs_with_gt: int = 0
    docs_without_gt: int = 0
    docs_failed: int = 0


class TestExtractionResponse(BaseModel):
    """Response model for the /extract/test endpoint."""

    summary: TestSummary
    metrics: TestMetrics
    documents: List[TestDocumentResult]
