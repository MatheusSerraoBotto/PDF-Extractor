"""
FastAPI application entrypoint with production-ready security and monitoring.

This module provides a production-ready FastAPI app with:
- Dynamic CORS configuration
- Security headers
- Enhanced health checks (liveness/readiness)
- Request timeout handling
- Error tracking
"""

import asyncio
import json
import logging

from fastapi import (FastAPI, File, Form, HTTPException, Query, Request,
                     UploadFile, status)
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from src.config.logging import setup_logging
from src.config.settings import settings  # loads environment variables
from src.core.batch import process_batch_parallel
from src.core.cache import CacheClient
from src.core.pipeline import run_extraction
from src.models.schema import (BatchItemResult, BatchSummary,
                               ExtractionRequest, ExtractionResult,
                               HealthResponse)

# Initialize logging on startup
setup_logging()

logger = logging.getLogger(__name__)

# FastAPI app configuration
app = FastAPI(
    title="PDF Extraction AI",
    description="""
## Serviço de Extração Inteligente de PDFs

API para extração de dados estruturados de documentos PDF usando LLMs.

### Características Principais

* **Extração Estruturada**: Define seus próprios campos de extração via schema customizado
* **Cache Inteligente**: Redis cache para evitar reprocessamento
* **Observabilidade**: Token counting e métricas detalhadas
* **Alta Precisão**: Utiliza OpenAI GPT-5-mini para extração precisa

### Como Usar

1. **Via Upload de Arquivo**: Use `/extract/upload` para enviar PDFs diretamente
2. **Via Caminho Local**: Use `/extract` com `pdf_path` para processar arquivos locais

### Formato de Schema

O `extraction_schema` define quais campos você deseja extrair:

```json
{
  "nome": "Nome completo do profissional",
  "inscricao": "Número de inscrição OAB",
  "categoria": "Categoria profissional (ADVOGADO, ESTAGIARIO, etc)"
}
```

    """,
    version="1.0.0",
    debug=settings.debug,
    docs_url="/docs" if settings.is_development else None,  # Disable docs in prod
    redoc_url="/redoc" if settings.is_development else None,
    contact={
        "name": "PDF Extraction AI",
        "url": "http://pdf-extraction-frontend-1762478932.s3-website-sa-east-1.amazonaws.com/",
    },
    license_info={
        "name": "MIT",
    },
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


@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["Health"],
    summary="Health Check",
    description="Verifica se o serviço está rodando (liveness probe)",
    responses={
        200: {
            "description": "Serviço está operacional",
            "content": {
                "application/json": {
                    "example": {"status": "ok", "environment": "development"}
                }
            },
        }
    },
)
async def health():
    """
    **Liveness Probe** - Verifica se o serviço está ativo.

    Retorna status 200 se o serviço está rodando normalmente.
    Este endpoint é ideal para health checks básicos de orquestradores como Kubernetes.
    """
    return HealthResponse(status="ok", environment=settings.env)


@app.get(
    "/health/ready",
    tags=["Health"],
    summary="Readiness Check",
    description="Verifica se o serviço está pronto para receber tráfego",
    responses={
        200: {
            "description": "Serviço está pronto",
            "content": {
                "application/json": {
                    "example": {
                        "status": "ready",
                        "checks": {"redis": "ok", "openai": "configured"},
                        "environment": "development",
                    }
                }
            },
        },
        503: {
            "description": "Serviço não está pronto",
            "content": {
                "application/json": {
                    "example": {
                        "status": "not_ready",
                        "checks": {"redis": "error: connection refused"},
                    }
                }
            },
        },
    },
)
async def readiness():
    """
    **Readiness Probe** - Verifica se o serviço pode aceitar requisições.

    Valida:
    - Conexão com Redis (cache)
    - Configuração da OpenAI API Key

    Retorna 200 se pronto, 503 se não estiver pronto para receber tráfego.
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


@app.post(
    "/extract",
    response_model=ExtractionResult,
    tags=["Extraction"],
    summary="Extração de PDF (via path local)",
    description="Processa um PDF usando caminho local do arquivo no servidor",
    responses={
        200: {
            "description": "Extração realizada com sucesso",
            "content": {
                "application/json": {
                    "example": {
                        "label": "carteira_oab",
                        "fields": {
                            "nome": "João Silva Santos",
                            "inscricao": "123456",
                            "categoria": "ADVOGADO",
                        },
                        "meta": {
                            "cache_hit": False,
                            "tokens_used": 1250,
                            "processing_time_seconds": 2.34,
                        },
                    }
                }
            },
        },
        400: {"description": "Requisição inválida"},
        404: {"description": "Arquivo PDF não encontrado"},
        500: {"description": "Erro no pipeline de extração"},
    },
)
async def extract(
    request: ExtractionRequest,
    use_cache: bool = Query(True, description="Habilitar cache Redis para esta requisição"),
):
    """
    **Executa o pipeline completo de extração** para um documento PDF.

    ### Parâmetros

    - **request**: Objeto com label, extraction_schema e pdf_path
    - **use_cache**: Se True, verifica cache antes de processar (padrão: True)

    ### Exemplo de Payload

    ```json
    {
      "label": "carteira_oab",
      "extraction_schema": {
        "nome": "Nome completo do profissional",
        "inscricao": "Número de inscrição OAB"
      },
      "pdf_path": "oab_1.pdf"
    }
    ```

    ### Resposta

    Retorna um objeto ExtractionResult com:
    - **label**: Rótulo do documento
    - **fields**: Campos extraídos do PDF
    - **meta**: Metadados (cache hit, tokens usados, tempo de processamento)
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


@app.post(
    "/extract/upload",
    response_model=ExtractionResult,
    tags=["Extraction"],
    summary="Extração de PDF (via upload)",
    description="Processa um PDF enviado via upload de arquivo (multipart/form-data)",
    responses={
        200: {
            "description": "Extração realizada com sucesso",
            "content": {
                "application/json": {
                    "example": {
                        "label": "carteira_oab",
                        "fields": {
                            "nome": "Maria Oliveira Costa",
                            "inscricao": "654321",
                            "categoria": "ADVOGADA",
                        },
                        "meta": {
                            "cache_hit": False,
                            "tokens_used": 1180,
                            "processing_time_seconds": 2.56,
                        },
                    }
                }
            },
        },
        400: {"description": "Arquivo inválido ou schema JSON malformado"},
        500: {"description": "Erro no pipeline de extração"},
    },
)
async def extract_upload(
    file: UploadFile = File(..., description="Arquivo PDF para extração (apenas PDFs)"),
    label: str = Form(..., description="Rótulo do documento, ex: 'carteira_oab'"),
    extraction_schema: str = Form(
        ...,
        description="JSON string com mapeamento campo -> descrição",
        example='{"nome":"Nome completo","inscricao":"Número de inscrição"}',
    ),
    use_cache: bool = Query(True, description="Habilitar cache Redis para esta requisição"),
):
    """
    **Executa o pipeline completo de extração** com upload de arquivo.

    Este endpoint aceita **multipart/form-data** para upload direto de PDFs.

    ### Parâmetros

    - **file**: Arquivo PDF (Content-Type: application/pdf)
    - **label**: Rótulo identificador do documento
    - **extraction_schema**: String JSON com campos a extrair
    - **use_cache**: Se True, verifica cache antes de processar (padrão: True)

    ### Exemplo com cURL

    ```bash
    curl -X POST "http://localhost:8000/extract/upload" \\
      -F "file=@documento.pdf" \\
      -F "label=carteira_oab" \\
      -F 'extraction_schema={"nome":"Nome completo","inscricao":"Número OAB"}'
    ```

    ### Exemplo com Python

    ```python
    import requests

    files = {'file': open('documento.pdf', 'rb')}
    data = {
        'label': 'carteira_oab',
        'extraction_schema': '{"nome":"Nome completo","inscricao":"Número OAB"}'
    }

    response = requests.post(
        'http://localhost:8000/extract/upload',
        files=files,
        data=data
    )
    print(response.json())
    ```

    ### Resposta

    Retorna um objeto ExtractionResult com:
    - **label**: Rótulo do documento
    - **fields**: Campos extraídos do PDF
    - **meta**: Metadados (cache hit, tokens usados, tempo de processamento)
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


@app.post(
    "/extract/batch",
    tags=["Extraction"],
    summary="Extração de PDF em Lote (processamento paralelo)",
    description="Processa múltiplos PDFs em paralelo com streaming de resultados via Server-Sent Events",
    responses={
        200: {
            "description": "Stream de resultados (Server-Sent Events)",
            "content": {
                "text/event-stream": {
                    "example": """data: {"index": 0, "status": "completed", "label": "carteira_oab", "fields": {...}}

data: {"index": 1, "status": "completed", "label": "tela_sistema", "fields": {...}}

data: {"status": "done", "total": 2, "successful": 2, "failed": 0}"""
                }
            },
        },
        400: {"description": "Requisição inválida ou lote vazio"},
        413: {"description": "Lote excede o tamanho máximo permitido"},
    },
)
async def extract_batch(
    items: list[dict],
    use_cache: bool = Query(True, description="Habilitar cache Redis para as requisições"),
):
    """
    **Processa múltiplos PDFs em paralelo** com streaming de resultados.

    ### Características

    - **Processamento paralelo**: Múltiplos PDFs processados simultaneamente
    - **Streaming via SSE**: Resultados retornados assim que ficam prontos (< 10s para o primeiro)
    - **Independência**: Erros em um item não afetam os outros
    - **Controle de concorrência**: Limita paralelismo para não sobrecarregar APIs

    ### Parâmetros

    - **items**: Lista de objetos com `label`, `extraction_schema` e `pdf_path`
    - **use_cache**: Se True, verifica cache antes de processar (padrão: True)

    ### Exemplo de Payload

    ```json
    [
      {
        "label": "carteira_oab",
        "extraction_schema": {
          "nome": "Nome do profissional",
          "inscricao": "Número de inscrição"
        },
        "pdf_path": "oab_1.pdf"
      },
      {
        "label": "tela_sistema",
        "extraction_schema": {
          "data_base": "Data base da operação",
          "produto": "Produto da operação"
        },
        "pdf_path": "tela_sistema_1.pdf"
      }
    ]
    ```

    ### Formato de Resposta (SSE Stream)

    A resposta é um stream de eventos Server-Sent Events (SSE).
    Cada linha começa com `data:` seguido de um JSON.

    **Resultado individual:**
    ```json
    {
      "index": 0,
      "status": "completed",
      "label": "carteira_oab",
      "fields": {"nome": "João Silva", "inscricao": "123456"},
      "meta": {"cache_hit": false, "processing_time_seconds": 2.1}
    }
    ```

    **Resultado com erro:**
    ```json
    {
      "index": 2,
      "status": "error",
      "label": "carteira_oab",
      "error": "FileNotFoundError: PDF not found: oab_3.pdf"
    }
    ```

    **Sumário final:**
    ```json
    {
      "status": "done",
      "total": 6,
      "successful": 5,
      "failed": 1
    }
    ```

    ### Exemplo com Python

    ```python
    import requests
    import json

    batch_items = [
        {
            "label": "carteira_oab",
            "extraction_schema": {"nome": "Nome", "inscricao": "Número"},
            "pdf_path": "oab_1.pdf"
        },
        {
            "label": "tela_sistema",
            "extraction_schema": {"data_base": "Data base"},
            "pdf_path": "tela_1.pdf"
        }
    ]

    response = requests.post(
        'http://localhost:8000/extract/batch',
        json=batch_items,
        stream=True  # Important for SSE
    )

    # Process streaming results
    for line in response.iter_lines():
        if line:
            # Remove "data: " prefix
            data = line.decode('utf-8').replace('data: ', '')
            result = json.loads(data)
            print(result)
    ```

    ### Exemplo com cURL

    ```bash
    curl -X POST "http://localhost:8000/extract/batch" \\
      -H "Content-Type: application/json" \\
      -d '[
        {
          "label": "carteira_oab",
          "extraction_schema": {"nome": "Nome"},
          "pdf_path": "oab_1.pdf"
        }
      ]' \\
      --no-buffer
    ```

    ### Limitações

    - Máximo de items por lote: configurável via `max_batch_size` (padrão: 100)
    - Concorrência máxima: configurável via `max_concurrent_extractions` (padrão: 5)
    """
    # Validate batch size
    if not items or len(items) == 0:
        raise HTTPException(
            status_code=400,
            detail="Batch cannot be empty. Provide at least one item.",
        )

    if len(items) > settings.max_batch_size:
        raise HTTPException(
            status_code=413,
            detail=f"Batch size ({len(items)}) exceeds maximum allowed ({settings.max_batch_size})",
        )

    # Parse items into BatchExtractionItem models
    try:
        from src.models.schema import BatchExtractionItem

        batch_items = [BatchExtractionItem(**item) for item in items]
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid batch item format: {exc}",
        ) from exc

    # Create SSE stream generator
    async def generate_sse():
        """Generate Server-Sent Events stream with guaranteed delivery."""
        try:
            logger.info(f"SSE: Starting batch processing for {len(batch_items)} items")

            event_num = 0
            # Stream results as they complete (true streaming)
            async for result in process_batch_parallel(batch_items, use_cache):
                event_num += 1
                json_data = result.model_dump_json()

                # Log with more details
                if isinstance(result, BatchItemResult):
                    logger.info(f"SSE: Sending event #{event_num} (BatchItemResult): index={result.index}, status={result.status}, label={result.label}")
                elif isinstance(result, BatchSummary):
                    logger.info(f"SSE: Sending event #{event_num} (BatchSummary): total={result.total}, successful={result.successful}, failed={result.failed}")

                # Yield the SSE event
                yield f"data: {json_data}\n\n"

                # Give a tiny moment for the buffer to flush
                # This ensures each event is transmitted before the next one
                # await asyncio.sleep(0.01)

            logger.info(f"SSE: Completed streaming {event_num} events")

        except Exception as exc:
            logger.error(f"Batch processing error: {exc}", exc_info=True)
            error_event = {
                "status": "error",
                "error": f"Batch processing failed: {str(exc)}",
            }
            yield f"data: {json.dumps(error_event)}\n\n"

    return StreamingResponse(
        generate_sse(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )
