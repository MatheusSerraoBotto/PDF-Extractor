# PDF Extraction AI

Serviço de extração inteligente de texto de PDFs que combina heurísticas determinísticas com modelos de linguagem (LLMs) para extrair dados estruturados de documentos. Sistema opinionado focado em **precisão primeiro, custo segundo, escalabilidade terceiro**.

## Visão Geral

Este é um **serviço de extração inteligente** projetado para processar **carteiras da OAB** (Ordem dos Advogados do Brasil) - documentos de página única com texto OCR embutido. O sistema utiliza uma abordagem híbrida que maximiza precisão enquanto minimiza custos de processamento.

### Abordagem Híbrida

```text
PDF → Cache? → Extração → Heurísticas → LLM (só se necessário) → Resultado
                   ↓                                                  ↓
              pdfplumber                                          Cache
```

**Características:**

- Tenta extração **determinística rápida** primeiro (heurísticas)
- Usa **LLM apenas para campos não resolvidos** (economia de custo)
- Inclui **pontuação de confiança** (0-1) para cada campo
- **Rastreamento de fonte**: indica se veio de heurística ou LLM
- **Cache Redis**: evita reprocessamento de documentos idênticos

### Campos Extraídos (OAB)

O sistema extrai 8 campos específicos de carteiras da OAB:

- `nome`, `inscricao`, `seccional`, `subsecao`
- `categoria`, `endereco_profissional`, `telefone_profissional`, `situacao`

## Highlights

- Dockerized development stack (FastAPI API, Redis cache, SQLite service)
- LangChain-ready FastAPI skeleton for LLM-powered extraction flows
- Hybrid extraction: deterministic heuristics + LLM fallback
- Confidence scoring and source tracking for all extracted fields
- Multi-provider LLM support (OpenAI, Ollama, custom)
- Test harness with `pytest` and `httpx`
- GitHub Actions pipeline for style checks and tests

## Requirements

- Docker + Docker Compose (for the default workflow)

## Getting Started

1. Create your environment file:

   ```bash
   cp .env.example .env
   ```

   Fill in any required secrets (e.g., `OPENAI_API_KEY`).

2. Launch the local stack:

   ```bash
   docker compose -f docker/docker-compose.yml up --build
   ```

3. Check the health endpoint:

   ```text
   http://localhost:8000/health
   ```

4. (Optional) Run the tests on your host machine:

   ```bash
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   pytest -q
   ```

Stop the services with `Ctrl+C`, then clean up containers and volumes when you
are done:

```bash
docker compose -f docker/docker-compose.yml down
```

## Tests

- Execute tests inside the running API container (useful when relying on Docker-only deps):

  ```bash
  docker exec -it pdf-ai-api pytest -q
  ```

- Override configuration for ad-hoc runs by prefixing environment variables:

  ```bash
  docker exec -it pdf-ai-api env DATABASE_URL=sqlite:////tmp/test.db pytest -q
  ```

- CI runs formatting (`black --check`), linting (`ruff`), and tests on every push.

## Project Layout

```text
src/              # Application source code
tests/            # Unit and integration tests
docker/           # Dockerfiles and compose definitions
.github/          # CI workflows
.env.example      # Environment variable template
requirements*.txt # Python dependencies
```

## Operational Notes

- SQLite is containerized; data persists via the shared `sqlite_data` volume.
- `Settings` fall back to `.env.example` when `.env` is absent, so keep defaults up to date.
- LangChain requires valid API keys; never commit real credentials—use `.env` locally and CI/CD secrets remotely.
- After dependency or configuration changes, rebuild the Docker images:  
  `docker compose -f docker/docker-compose.yml up --build`
