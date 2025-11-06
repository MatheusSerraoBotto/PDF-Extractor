# Test Suite

Suíte completa de testes unitários e de integração para o PDF Extractor.

## Estrutura

```
tests/
├── conftest.py                    # Fixtures compartilhadas
├── unit/                          # Testes unitários
│   ├── test_cache.py             # Testes do cache Redis
│   ├── test_extractor.py         # Testes do extrator PDF
│   ├── test_llm_orchestrator.py  # Testes do orquestrador LLM
│   ├── test_pipeline.py          # Testes do pipeline
│   └── test_schema.py            # Testes dos modelos Pydantic
├── integration/                   # Testes de integração
│   ├── test_api_endpoints.py     # Testes dos endpoints da API
│   └── test_pipeline_integration.py  # Testes do pipeline completo
└── fixtures/                      # Fixtures e arquivos de teste
    ├── create_test_pdfs.py       # Script para gerar PDFs de teste
    └── README.md
```

## Executando os Testes

### Via Docker (Recomendado)

```bash
# Executar todos os testes
docker exec -it pdf-ai-api pytest -v

# Executar apenas testes unitários
docker exec -it pdf-ai-api pytest tests/unit/ -v

# Executar apenas testes de integração
docker exec -it pdf-ai-api pytest tests/integration/ -v

# Executar um arquivo específico
docker exec -it pdf-ai-api pytest tests/unit/test_extractor.py -v

# Executar com cobertura
docker exec -it pdf-ai-api pytest --cov=src --cov-report=term-missing

# Executar com cobertura HTML
docker exec -it pdf-ai-api pytest --cov=src --cov-report=html
```

### Localmente (Requer Python e dependências)

```bash
# Instalar dependências
pip install -r requirements.txt -r requirements-dev.txt

# Executar testes
pytest -v

# Com cobertura
pytest --cov=src --cov-report=term-missing
```

## Opções Úteis do Pytest

```bash
# Executar apenas testes que falharam na última execução
docker exec -it pdf-ai-api pytest --lf

# Parar na primeira falha
docker exec -it pdf-ai-api pytest -x

# Executar testes por palavra-chave
docker exec -it pdf-ai-api pytest -k "extractor" -v

# Mostrar print statements
docker exec -it pdf-ai-api pytest -s

# Executar em paralelo (requer pytest-xdist)
docker exec -it pdf-ai-api pytest -n auto

# Executar com output detalhado
docker exec -it pdf-ai-api pytest -vv
```

## Cobertura de Testes

A suíte cobre os seguintes componentes:

### Testes Unitários (tests/unit/)

- **test_cache.py**: Cache Redis
  - Operações get/set
  - Serialização JSON
  - Tratamento de erros
  - TTL e expiração

- **test_extractor.py**: Extração de PDF
  - Carregamento de PDFs
  - Extração de texto com layout
  - Cálculo de zonas (9-grid)
  - Agrupamento de palavras em linhas
  - Filtragem por palavras-chave
  - Funções utilitárias (hash, resolução de paths)

- **test_llm_orchestrator.py**: Orquestrador LLM
  - Integração com OpenAI API
  - Contagem de tokens
  - Normalização de respostas
  - Tratamento de erros
  - Validação de API key

- **test_pipeline.py**: Pipeline de extração
  - Orquestração completa
  - Integração com cache
  - Geração de metadados
  - Timings e trace
  - Tratamento de erros

- **test_schema.py**: Modelos Pydantic
  - Validação de requests
  - Serialização/deserialização
  - Modelos de response
  - Health check

### Testes de Integração (tests/integration/)

- **test_api_endpoints.py**: Endpoints FastAPI
  - GET /health
  - POST /extract
  - Validação de entrada
  - Tratamento de erros HTTP
  - Query parameters (use_cache)

- **test_pipeline_integration.py**: Pipeline completo
  - Fluxo end-to-end
  - Cache hit/miss
  - Extração real de PDF (mockado)
  - Integração de componentes
  - Geração de cache keys

## Fixtures Compartilhadas

As fixtures em `conftest.py` fornecem:

- `client`: AsyncClient para testes de API
- `mock_redis`: Mock do cliente Redis
- `mock_openai_client`: Mock do cliente OpenAI
- `sample_extraction_schema`: Schema de exemplo
- `sample_extraction_request`: Request de exemplo
- `sample_layout_text`: Texto com layout de exemplo
- `sample_llm_response`: Resposta LLM normalizada
- `mock_pdfplumber_page`: Mock de página PDF
- `mock_pdfplumber_pdf`: Mock de documento PDF
- `temp_test_dir`: Diretório temporário
- `mock_settings`: Settings mockados

## Gerando PDFs de Teste

Para testes que precisam de PDFs reais:

```bash
# Instalar reportlab
pip install reportlab

# Gerar PDFs de teste
python tests/fixtures/create_test_pdfs.py
```

Isso cria:
- `sample_oab.pdf` - Carteira OAB de exemplo
- `simple_document.pdf` - Documento simples
- `multifield_document.pdf` - Documento com múltiplos campos
- `empty_document.pdf` - PDF vazio

## Estratégia de Testes

### Testes Unitários
- Testam componentes isolados
- Usam mocks extensivamente
- Execução rápida
- Alta cobertura de edge cases

### Testes de Integração
- Testam integração entre componentes
- Mockam apenas APIs externas (OpenAI, Redis quando necessário)
- Validam comportamento end-to-end
- Focam em fluxos de usuário reais

## Mocking

A suíte usa mocking estratégico:

- **Sempre mockado**: OpenAI API, Redis (em alguns casos)
- **Nunca mockado**: Lógica de negócio, validação Pydantic
- **Mockado quando apropriado**: Sistema de arquivos, pdfplumber

## Cobertura Esperada

Meta: >90% de cobertura de código

```bash
# Verificar cobertura atual
docker exec -it pdf-ai-api pytest --cov=src --cov-report=term-missing
```

Áreas principais:
- src/core/extractor.py: ~95%
- src/core/cache.py: ~95%
- src/core/llm_orchestrator.py: ~90%
- src/core/pipeline.py: ~95%
- src/models/schema.py: ~100%
- src/main.py: ~90%

## Debugging Testes

```bash
# Executar com debugger (pdb)
docker exec -it pdf-ai-api pytest --pdb

# Mostrar variáveis locais em falhas
docker exec -it pdf-ai-api pytest -l

# Aumentar verbosidade
docker exec -it pdf-ai-api pytest -vv

# Ver traceback completo
docker exec -it pdf-ai-api pytest --tb=long
```

## CI/CD

Os testes rodam automaticamente no CI em:
- Push para qualquer branch
- Pull requests
- Antes de merge

Pipeline CI:
1. Lint (ruff)
2. Format check (black)
3. Import sorting (isort)
4. Unit tests
5. Integration tests
6. Coverage report

## Troubleshooting

### Testes falhando localmente mas passando no CI
- Verificar variáveis de ambiente
- Limpar cache do pytest: `rm -rf .pytest_cache`
- Verificar dependências: `pip install -r requirements-dev.txt`

### Testes lentos
- Usar `-n auto` para paralelização
- Executar apenas testes unitários durante desenvolvimento
- Usar `--lf` para re-executar apenas falhas

### Problemas com fixtures
- Verificar que fixtures estão em `conftest.py`
- Verificar imports corretos
- Verificar escopo das fixtures (function, module, session)

## Contribuindo

Ao adicionar novos recursos:

1. Escreva testes unitários primeiro (TDD quando apropriado)
2. Adicione testes de integração para fluxos completos
3. Mantenha cobertura >90%
4. Use fixtures compartilhadas quando possível
5. Documente testes complexos com docstrings claras

## Recursos

- [Pytest Documentation](https://docs.pytest.org/)
- [pytest-asyncio](https://pytest-asyncio.readthedocs.io/)
- [unittest.mock](https://docs.python.org/3/library/unittest.mock.html)
- [HTTPX AsyncClient](https://www.python-httpx.org/async/)
