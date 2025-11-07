"""
FastAPI application entrypoint with production-ready security and monitoring.

This module provides a production-ready FastAPI app with:
- Dynamic CORS configuration
- Security headers
- Enhanced health checks (liveness/readiness)
- Request timeout handling
- Error tracking
"""

import json
import logging

from fastapi import (FastAPI, File, Form, HTTPException, Query, Request,
                     UploadFile, status)
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.config.logging import setup_logging
from src.config.settings import settings  # loads environment variables
from src.core.cache import CacheClient
from src.core.pipeline import run_extraction
from src.models.schema import (ExtractionRequest, ExtractionResult,
                               HealthResponse)

# Initialize logging on startup
setup_logging()

logger = logging.getLogger(__name__)

# FastAPI app configuration
app = FastAPI(
    title="PDF Extraction AI",
    version="0.1.0",
    debug=settings.debug,
    docs_url="/docs" if settings.is_development else None,  # Disable docs in prod
    redoc_url="/redoc" if settings.is_development else None,
)

# Parse allowed origins from settings
allowed_origins = [origin.strip() for origin in settings.allowed_origins.split(",")]

# Configure CORS for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,  # More secure for production
    allow_methods=["GET", "POST", "OPTIONS"],  # Explicit methods only
    allow_headers=["Content-Type", "Authorization", settings.api_key_header],
)


# Security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Add security headers to all responses."""
    response = await call_next(request)

    # Security headers
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

    # HSTS for production with HTTPS
    if settings.is_production:
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )

    return response


@app.on_event("startup")
async def startup_event():
    """Application startup event - log configuration."""
    logger.info(f"Starting PDF Extraction API in {settings.env} mode")
    logger.info(f"Debug mode: {settings.debug}")
    logger.info(f"CORS origins: {settings.allowed_origins}")
    logger.info(f"Workers configured: {settings.workers}")


@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown event - cleanup resources."""
    logger.info("Shutting down PDF Extraction API")


@app.get("/health", response_model=HealthResponse)
async def health():
    """
    Liveness probe - basic health check that service is running.
    Returns 200 if service is alive.
    """
    return HealthResponse(status="ok", environment=settings.env)


@app.get("/health/ready")
async def readiness():
    """
    Readiness probe - checks if service can accept traffic.
    Validates Redis connection and configuration.
    Returns 200 if ready, 503 if not ready.
    """
    checks = {}

    # Check Redis connection
    try:
        cache = CacheClient()
        if cache.health_check():
            checks["redis"] = "ok"
        else:
            checks["redis"] = "unhealthy"
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"status": "not_ready", "checks": checks},
            )
    except Exception as e:
        logger.error(f"Redis readiness check failed: {e}")
        checks["redis"] = f"error: {str(e)}"
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "not_ready", "checks": checks},
        )

    # Check OpenAI API key configuration
    if not settings.openai_api_key:
        checks["openai"] = "error: API key not configured"
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "not_ready", "checks": checks},
        )
    checks["openai"] = "configured"

    return {"status": "ready", "checks": checks, "environment": settings.env}


@app.post("/extract", response_model=ExtractionResult)
async def extract(
    request: ExtractionRequest,
    use_cache: bool = Query(True, description="Toggle cache usage for this request."),
):
    """
    Run the full extraction pipeline for a single document.
    Accepts either pdf_path (local file) or pdf_bytes (uploaded content).
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
        raise HTTPException(
            status_code=500, detail=f"Extraction pipeline error: {exc}"
        ) from exc

    return result


@app.post("/extract/upload", response_model=ExtractionResult)
async def extract_upload(
    file: UploadFile = File(..., description="PDF file to extract data from"),
    label: str = Form(..., description="Document label, e.g., 'carteira_oab'"),
    extraction_schema: str = Form(
        ..., description="JSON string of field name -> description mapping"
    ),
    use_cache: bool = Query(True, description="Toggle cache usage for this request."),
):
    """
    Run the full extraction pipeline with file upload.
    This endpoint accepts multipart/form-data for direct file uploads from frontend.

    Example usage:
    ```
    curl -X POST "http://localhost:8000/extract/upload" \
      -F "file=@document.pdf" \
      -F "label=carteira_oab" \
      -F 'extraction_schema={"nome":"Nome completo","inscricao":"Número de inscrição"}'
    ```
    """
    # Validate file type
    if not file.content_type == "application/pdf":
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type: {file.content_type}. Only PDF files are supported.",
        )

    # Read file bytes
    try:
        pdf_bytes = await file.read()
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=f"Failed to read uploaded file: {exc}"
        ) from exc

    # Validate PDF has content
    if len(pdf_bytes) == 0:
        raise HTTPException(status_code=400, detail="Uploaded PDF file is empty")

    # Parse extraction schema JSON
    try:
        schema_dict = json.loads(extraction_schema)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=400, detail=f"Invalid extraction_schema JSON: {exc}"
        ) from exc

    # Create extraction request with bytes
    request = ExtractionRequest(
        label=label, extraction_schema=schema_dict, pdf_bytes=pdf_bytes
    )

    # Run extraction pipeline
    try:
        result = await run_in_threadpool(
            run_extraction,
            request,
            use_cache=use_cache,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500, detail=f"Extraction pipeline error: {exc}"
        ) from exc

    return result
