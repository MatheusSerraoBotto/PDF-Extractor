# Guia de Setup para Testes Locais

Este guia mostra como configurar e executar os testes do projeto localmente usando `.venv`.

## Pre-requisitos

- Python 3.11+
- Redis rodando localmente (ou via Docker)

## Setup Passo a Passo

### 1. Criar e ativar ambiente virtual

```bash
# Criar ambiente virtual
python -m venv .venv

# Ativar no Linux/Mac
source .venv/bin/activate

# Ativar no Windows
.venv\Scripts\activate
```

### 2. Instalar dependencias

```bash
# Atualizar pip
pip install --upgrade pip

# Instalar dependencias de producao
pip install -r requirements.txt

# Instalar dependencias de desenvolvimento
pip install -r requirements-dev.txt
```

### 3. Subir Redis (via Docker - opcao mais facil)

```bash
# Usando docker-compose do projeto
cd docker
docker-compose up -d redis

# OU usando docker diretamente
docker run -d --name redis-test -p 6379:6379 redis:7-alpine
```

### 4. Configurar variaveis de ambiente

```bash
# Copiar arquivo de exemplo
cp env/dev.env .env

# OU exportar diretamente
export REDIS_HOST=localhost
export REDIS_PORT=6379
export OPENAI_API_KEY=your-key-here  # opcional para testes unitarios
```

### 5. Rodar os testes

```bash
# Todos os testes
pytest

# Testes com output minimo (modo CI)
pytest --maxfail=0 --disable-warnings -q

# Testes com mais detalhes
pytest -v

# Apenas testes unitarios (nao precisa Redis)
pytest tests/unit/

# Apenas testes de integracao
pytest tests/integration/

# Com coverage
pytest --cov=src --cov-report=html
```

## Solucao de Problemas

### Redis connection error

Se voce ver erros de conexao com Redis:

1. Verifique se o Redis esta rodando:
   ```bash
   redis-cli ping
   # Deve retornar: PONG
   ```

2. Verifique as variaveis de ambiente:
   ```bash
   echo $REDIS_HOST
   echo $REDIS_PORT
   ```

3. Se usar Docker, verifique os containers:
   ```bash
   docker ps | grep redis
   ```

### Import errors

Se voce ver erros de import:

1. Verifique se o ambiente virtual esta ativo:
   ```bash
   which python
   # Deve apontar para .venv/bin/python
   ```

2. Reinstale as dependencias:
   ```bash
   pip install -r requirements.txt -r requirements-dev.txt
   ```

### Testes falhando

Se testes especificos falharem:

1. Rode apenas aquele teste:
   ```bash
   pytest tests/unit/test_cache.py::TestCacheClient::test_init_creates_redis_client -v
   ```

2. Verifique os logs:
   ```bash
   pytest -v -s  # -s mostra print statements
   ```

## Estrutura de Testes

```
tests/
├── unit/               # Testes unitarios (mocks, rapidos)
│   ├── test_cache.py
│   ├── test_extractor.py
│   └── test_pipeline.py
├── integration/        # Testes de integracao (Redis real, mais lentos)
│   └── test_api.py
└── fixtures/          # Arquivos de teste (PDFs, etc)
```

## Dicas

1. **Rode testes unitarios primeiro**: Sao mais rapidos e nao precisam de Redis
   ```bash
   pytest tests/unit/ -v
   ```

2. **Use watch mode durante desenvolvimento**:
   ```bash
   pip install pytest-watch
   ptw  # re-executa testes quando arquivos mudam
   ```

3. **Verifique cobertura de codigo**:
   ```bash
   pytest --cov=src --cov-report=term-missing
   ```

4. **Limpe cache do pytest**:
   ```bash
   pytest --cache-clear
   ```

## CI/CD no GitHub Actions

O workflow em [.github/workflows/ci.yml](../.github/workflows/ci.yml) automaticamente:

- Configura Python 3.11
- Instala dependencias
- Sobe container Redis para testes
- Roda linters (ruff, black, isort)
- Executa todos os testes

As variaveis de ambiente no CI:
- `REDIS_HOST=localhost`
- `REDIS_PORT=6379`
- `OPENAI_API_KEY` (secret do GitHub)
