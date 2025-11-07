"""
Pydantic data models for requests and responses.
These models define the contract between the API layer and the core services.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


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
    pdf_path: Optional[str] = Field(
        None,
        description="Local path to the PDF file (single page, OCR embedded). Required if pdf_bytes is not provided.",
    )
    pdf_bytes: Optional[bytes] = Field(
        None,
        description="Raw PDF bytes for direct upload. Required if pdf_path is not provided.",
    )

    @model_validator(mode="after")
    def validate_pdf_source(self):
        """Ensure either pdf_path or pdf_bytes is provided, but not both."""
        if self.pdf_path is None and self.pdf_bytes is None:
            raise ValueError("Either pdf_path or pdf_bytes must be provided.")
        if self.pdf_path is not None and self.pdf_bytes is not None:
            raise ValueError(
                "Cannot provide both pdf_path and pdf_bytes. Use only one."
            )
        return self


class ExtractionResult(BaseModel):
    """Output contract of the extraction pipeline."""

    model_config = {
        "json_schema_extra": {
            "example": {
                "label": "carteira_oab",
                "fields": {
                    "nome": "João Silva Santos",
                    "inscricao": "123456",
                    "seccional": "São Paulo",
                    "categoria": "ADVOGADO",
                    "situacao": "REGULAR",
                },
                "meta": {
                    "cache_hit": False,
                    "tokens_used": 1250,
                    "processing_time_seconds": 2.34,
                    "model": "gpt-5-mini",
                },
            }
        }
    }

    label: str = Field(..., description="Rótulo identificador do documento processado")
    fields: Dict[str, Any] = Field(
        default_factory=dict,
        description="Mapeamento campo -> valor extraído do PDF",
    )
    meta: Dict[str, Any] = Field(
        default_factory=dict,
        description="Metadados: cache hit, tokens usados, tempo de processamento, etc.",
    )


class BatchExtractionItem(BaseModel):
    """Single item in a batch extraction request."""

    model_config = {
        "json_schema_extra": {
            "example": {
                "label": "carteira_oab",
                "extraction_schema": {
                    "nome": "Nome do profissional, normalmente no canto superior esquerdo da imagem",
                    "inscricao": "Número de inscrição do profissional",
                    "seccional": "Seccional do profissional",
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
        ...,
        description="Local path to the PDF file (single page, OCR embedded).",
    )


class BatchExtractionRequest(BaseModel):
    """Input contract for batch extraction request."""

    model_config = {
        "json_schema_extra": {
            "example": [
                {
                    "label": "carteira_oab",
                    "extraction_schema": {
                        "nome": "Nome do profissional",
                        "inscricao": "Número de inscrição",
                    },
                    "pdf_path": "oab_1.pdf",
                },
                {
                    "label": "tela_sistema",
                    "extraction_schema": {
                        "data_base": "Data base da operação",
                        "produto": "Produto da operação",
                    },
                    "pdf_path": "tela_sistema_1.pdf",
                },
            ]
        }
    }

    items: List[BatchExtractionItem] = Field(
        ...,
        description="List of extraction items to process in parallel",
        min_length=1,
    )


class BatchItemResult(BaseModel):
    """Result for a single item in batch processing."""

    index: int = Field(..., description="Index of the item in the original batch")
    status: str = Field(..., description="Status: 'completed' or 'error'")
    label: str = Field(..., description="Document label")
    fields: Optional[Dict[str, Any]] = Field(
        None, description="Extracted fields (null if error)"
    )
    meta: Optional[Dict[str, Any]] = Field(
        None, description="Metadata (null if error)"
    )
    error: Optional[str] = Field(None, description="Error message if failed")


class BatchSummary(BaseModel):
    """Summary of batch processing results."""

    status: str = Field("done", description="Overall status")
    total: int = Field(..., description="Total number of items processed")
    successful: int = Field(..., description="Number of successful extractions")
    failed: int = Field(..., description="Number of failed extractions")
