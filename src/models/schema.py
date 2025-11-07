"""
Pydantic data models for requests and responses.
These models define the contract between the API layer and the core services.
"""

from typing import Any, Dict, Optional

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

    label: str
    fields: Dict[str, Any] = Field(
        default_factory=dict,
        description="Simple key-value mapping of field names to extracted values.",
    )
    meta: Dict[str, Any] = Field(
        default_factory=dict, description="Timing, cache info, tokens, etc."
    )
