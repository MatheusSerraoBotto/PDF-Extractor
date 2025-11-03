# PDF Extraction AI

Foundational scaffolding for a PDF extraction service that blends deterministic
heuristics with LangChain-driven LLM extraction. The system is opinionated
toward accuracy first, cost second, and scalability third.

## Highlights

- Dockerized development stack (FastAPI API, Redis worker, SQLite service)
- LangChain-ready FastAPI skeleton for LLM-powered extraction flows
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
   ```
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

```
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
