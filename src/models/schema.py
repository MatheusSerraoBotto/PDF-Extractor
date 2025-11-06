"""
Pydantic data models for requests and responses.
These models define the contract between the API layer and the core services.
"""

from typing import Any, Dict

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
