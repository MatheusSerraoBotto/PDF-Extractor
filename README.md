# PDF Extraction AI

Serviço de extração inteligente de texto de PDFs usando LLMs para extrair dados estruturados de documentos. Sistema focado em **precisão primeiro, custo segundo, escalabilidade terceiro**.

## Status do Projeto

**Fase Atual**: ESTÁVEL - Entrando em Fase de Otimização ✅

A aplicação atingiu uma base estável e funcional. O pipeline de extração está operacional com:

- ✅ Pipeline de extração funcionando corretamente
- ✅ Cache Redis implementado e testado
- ✅ Integração com OpenAI API estável
- ✅ Tratamento de erros robusto
- ✅ Observabilidade (logs, métricas, token counting)
- ✅ Testes básicos implementados
- ✅ Docker Compose configurado

**Próximos Passos**: Otimização de performance, redução de custos e melhoria de acurácia.

## Visão Geral

Este é um **serviço de extração inteligente** projetado para processar documentos PDF de página única com texto OCR embutido. O sistema utiliza OpenAI LLM para extrair campos estruturados com alta precisão de qualquer tipo de documento.

### Pipeline de Extração

```text
PDF → Cache Check → PDF Extraction (pdfplumber) → LLM (OpenAI) → Post-processing → Cache Write → Result
```

**Características:**

- **Extração com pdfplumber**: Extrai texto linha por linha do PDF
- **LLM OpenAI**: Extração estruturada via API direta
- **Pontuação de confiança**: (0-1) para cada campo extraído
- **Rastreamento de fonte**: indica se veio de LLM ou não resolvido
- **Cache Redis**: evita reprocessamento de documentos idênticos
- **Token counting**: Observabilidade completa de uso de tokens

### Campos Extraídos

O sistema extrai campos estruturados baseados no schema fornecido na requisição. A aplicação é **agnóstica ao tipo de documento** - você define quais campos deseja extrair através do `extraction_schema`.

## Características Principais

- **Stack Dockerizada**: FastAPI + Redis cache pronto para produção
- **Integração OpenAI Direta**: API nativa da OpenAI
- **Extração Estruturada**: JSON mode com structured output
- **Confidence Scoring**: Pontuação de confiança para todos os campos
- **Source Tracking**: Rastreamento de origem (llm/unresolved)
- **Cache Inteligente**: Redis com SHA256 hashing de PDF + schema
- **Observabilidade**: Token counting, timings, metadata detalhada
- **Suite de Testes**: pytest com coverage e testes de integração
- **CI/CD**: GitHub Actions com linting, formatting e testes automáticos

## Arquitetura

### Stack Tecnológica

- **API**: FastAPI com async support
- **LLM**: OpenAI API (gpt-5-mini) com structured JSON output
- **PDF**: pdfplumber para extração de texto
- **Cache**: Redis para cache de resultados
- **Observability**: tiktoken para token counting + logs estruturados
- **Containerization**: Docker + Docker Compose

### Estrutura do Código

```text
src/
├── main.py                    # FastAPI app (/health, /extract, /extract/test)
├── config/settings.py         # Configuração via environment variables
├── models/schema.py           # Request/response models (Pydantic)
├── core/
│   ├── pipeline.py           # Orquestração do pipeline (~140 linhas)
│   ├── extractor.py          # Extração PDF com pdfplumber (~150 linhas)
│   ├── llm_orchestrator.py  # Integração OpenAI API (~240 linhas)
│   ├── postprocess.py        # Validação e normalização
│   ├── cache.py              # Abstração Redis
│   └── evaluation.py         # Cálculo de acurácia para /extract/test
```

**Total**: ~950 linhas de código core (simplificado de ~1400 linhas)

## Requisitos

- Docker + Docker Compose (recomendado)
- Python 3.11+ (para desenvolvimento local)
- OpenAI API Key

## Início Rápido

### 1. Configurar Environment

```bash
cp .env.example .env
```

Edite o arquivo `.env` e adicione sua chave OpenAI:

```bash
OPENAI_API_KEY=sk-...
LLM_MODEL=gpt-5-mini
```

### 2. Iniciar Stack Docker

```bash
docker compose -f docker/docker-compose.yml up --build
```

### 3. Verificar Health

```bash
curl http://localhost:8000/health
```

### 4. Fazer uma Extração

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

### Parar Serviços

```bash
# Parar com Ctrl+C, depois limpar:
docker compose -f docker/docker-compose.yml down
```

## Testes

### Executar Testes no Container

```bash
# Todos os testes
docker exec -it pdf-ai-api pytest -q

# Com coverage
docker exec -it pdf-ai-api pytest --cov=src --cov-report=term-missing

# Teste específico
docker exec -it pdf-ai-api pytest tests/unit/test_extractor_pdf.py -v
```

### Executar Testes Localmente

```bash
pip install -r requirements.txt -r requirements-dev.txt
pytest -q
```

### CI/CD

GitHub Actions executa automaticamente em push/PR:
- Linting (ruff)
- Formatting (black, isort)
- Testes (pytest)

## Performance e Métricas

### Baseline Atual (Estável)

- **Cache Hit**: <10ms (resposta instantânea)
- **Cache Miss**: ~2-5s (processamento LLM completo)
- **Token Usage**: Logado em cada request (input/output/total)
- **Acurácia**: Alta confiança em documentos estruturados
- **Cache TTL**: 600 segundos (configurável)

### Metas de Otimização

| Métrica | Baseline | Meta | Estratégias |
|---------|----------|------|-------------|
| Latência (cache miss) | 2-5s | <1s | Prompt otimization, streaming |
| Custo por extração | Baseline | -30% | Context pruning, field batching |
| Acurácia | Alta | >95% | Better prompts, post-processing |
| Throughput | Sync | Async | Connection pooling, parallelization |

## API Endpoints

### GET /health

Health check do serviço.

```bash
curl http://localhost:8000/health
```

### POST /extract

Extrai campos estruturados de um PDF.

**Query Parameters:**
- `use_cache` (opcional): true/false para controlar cache (default: true)

**Request Body:**
```json
{
  "label": "documento_exemplo",
  "extraction_schema": {
    "campo1": "Descrição do primeiro campo a extrair",
    "campo2": "Descrição do segundo campo a extrair"
  },
  "pdf_path": "documento.pdf"
}
```

**Response:**
```json
{
  "fields": {
    "campo1": {
      "value": "VALOR EXTRAÍDO",
      "confidence": 0.95,
      "rationale": "Extracted from document header",
      "details": {}
    }
  },
  "meta": {
    "timings_seconds": {"extract": 0.1, "llm": 2.3, "total": 2.4},
    "cache_hit": false,
    "trace": {
      "llm_resolved": ["campo1", "campo2"],
      "unresolved": []
    }
  }
}
```

### POST /extract/test

Endpoint de avaliação com ground truth.

**Request Body:**
```json
{
  "items": [
    {
      "label": "documento_exemplo",
      "extraction_schema": {...},
      "pdf_path": "documento.pdf",
      "gt": {"campo1": "VALOR ESPERADO", "campo2": "OUTRO VALOR"}
    }
  ]
}
```

**Response:**
```json
{
  "overall": {
    "mean_accuracy": 0.92,
    "total_documents": 10,
    "avg_time_seconds": 2.3
  },
  "details": [...]
}
```

## Configuração

Variáveis de ambiente principais (`.env`):

```bash
# OpenAI
OPENAI_API_KEY=sk-...
LLM_MODEL=gpt-5-mini
LLM_MAX_OUTPUT_TOKENS=800

# PDF Processing
PDF_BASE_PATH=.samples/files

# Cache
REDIS_HOST=redis
REDIS_PORT=6379

# Debug (opcional)
ENABLE_DEBUGPY=0
```

## Troubleshooting

### LLM não responde

1. Verifique `OPENAI_API_KEY` no `.env`
2. Confirme o modelo: `gpt-5-mini`
3. Verifique logs: `docker compose logs -f api`

### Cache não funciona

1. Verifique se Redis está rodando: `docker compose ps`
2. Teste conexão: `docker exec -it pdf-ai-redis redis-cli ping`

### Extrações vazias

Verifique `meta.trace.unresolved` na resposta. Causas comuns:
- Descrições de campos não claras
- Qualidade OCR do PDF
- LLM retornou null (veja confidence scores)

## Desenvolvimento

### Code Quality

```bash
# Format code
docker exec -it pdf-ai-api black .

# Lint
docker exec -it pdf-ai-api ruff check . --fix

# Sort imports
docker exec -it pdf-ai-api isort .

# Run all checks
ruff check . --fix && black . && isort . && pytest -q
```

### Remote Debugging

Defina `ENABLE_DEBUGPY=1` no `.env` e conecte seu IDE na porta `5678`.

## Roadmap de Otimização

### Fase 1: Performance
- [ ] Streaming responses para reduzir latência percebida
- [ ] Async processing para melhor throughput
- [ ] Connection pooling (Redis, OpenAI)

### Fase 2: Custo
- [ ] Prompt optimization (reduzir tokens)
- [ ] Smart context pruning
- [ ] Field batching strategies

### Fase 3: Acurácia
- [ ] Post-processing rules específicas por tipo de campo
- [ ] Confidence thresholds e retry logic
- [ ] Ground truth dataset expansion

### Fase 4: Escalabilidade
- [ ] Horizontal scaling (múltiplas instâncias)
- [ ] Rate limiting e resource quotas
- [ ] Monitoring e alerting (Prometheus/Grafana)

## Licença

MIT
