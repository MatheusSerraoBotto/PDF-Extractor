# PDF Extraction AI

**Projeto disponível em**: <http://pdf-extraction-frontend-1762478932.s3-website-sa-east-1.amazonaws.com/>

Serviço de extração inteligente de texto de PDFs usando LLMs para extrair dados estruturados de documentos. Sistema focado em **precisão primeiro, custo segundo, escalabilidade terceiro**.

## Visão Geral

Este é um **serviço de extração inteligente** projetado para processar documentos PDF de página única com texto OCR embutido. O sistema utiliza OpenAI LLM para extrair campos estruturados com alta precisão de qualquer tipo de documento.

### Pipeline de Extração

```text
PDF → Cache Check → PDF Extraction (pdfplumber) → LLM (OpenAI) → Post-processing → Cache Write → Result
```

**Características:**

- **Extração com pdfplumber**: Extrai texto linha por linha do PDF
- **LLM OpenAI**: Extração estruturada via API direta (gpt-5-mini)
- **Cache Redis**: Evita reprocessamento de documentos idênticos
- **Token counting**: Observabilidade completa de uso de tokens
- **Extração Agnóstica**: Você define quais campos deseja extrair através do `extraction_schema`

## Características Principais

- **Stack Dockerizada**: FastAPI + Redis cache pronto para produção
- **Integração OpenAI Direta**: API nativa da OpenAI com structured output
- **Cache Inteligente**: Redis com SHA256 hashing de PDF + schema
- **Observabilidade**: Token counting, timings e metadata detalhada
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
│   ├── pipeline.py           # Orquestração do pipeline
│   ├── extractor.py          # Extração PDF com pdfplumber
│   ├── llm_orchestrator.py  # Integração OpenAI API
│   ├── cache.py              # Abstração Redis
│   └── evaluation.py         # Cálculo de acurácia para /extract/test
```

## Requisitos

- Docker + Docker Compose
- Python 3.11+
- OpenAI API Key

## Instalação

Execute o script de setup automático:

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/MatheusSerraoBotto/PDF-Extractor/main/setup.sh)"
```

O script irá:

1. Verificar Docker e Docker Compose
2. Clonar os repositórios necessários (backend + frontend)
3. Solicitar e configurar sua OpenAI API Key
4. Solicitar o caminho da pasta que contém os arquivos PDF (caminho para pasta samples)
5. Iniciar os containers

## Acesso

Após a instalação:

- **Frontend**: <http://localhost:5173>
- **Backend**: <http://localhost:8000>
- **Documentação da API (Swagger)**: <http://localhost:8000/docs>
- **Documentação da API (ReDoc)**: <http://localhost:8000/redoc>

## Documentação da API

A API possui documentação interativa completa gerada automaticamente pelo FastAPI:

### Swagger UI (OpenAPI)

Acesse <http://localhost:8000/docs> para:

- Visualizar todos os endpoints disponíveis
- Testar requisições diretamente no navegador
- Ver exemplos de request/response
- Explorar os schemas de dados

### ReDoc

Acesse <http://localhost:8000/redoc> para uma documentação alternativa em formato mais limpo e navegável.

### Endpoints Principais

- `GET /health` - Health check básico (liveness probe)
- `GET /health/ready` - Readiness check com validação de dependências
- `POST /extract` - Extração via caminho local do PDF
- `POST /extract/upload` - Extração via upload de arquivo PDF
- `POST /extract/batch` - Extração em batch

## Decisões de Projeto

Esta seção documenta as principais decisões técnicas e o processo de iteração do desenvolvimento.

### 1. Escolha da Biblioteca de Extração de PDF

**Bibliotecas avaliadas**: pdfplumber, pymupdf4llm, pypdf

**Decisão**: **pdfplumber**

**Justificativa**:

- Fornece informações de **localização espacial** das palavras (coordenadas x, y)
- Essas informações são fundamentais para possíveis otimizações futuras
- Após testes comparativos, demonstrou melhor extração de texto para documentos com OCR embutido
- API simples e consistente para extração linha por linha

### 2. Abordagem de Extração: Heurísticas vs LLM Puro

#### Iteração 1: LangChain + Heurísticas

Implementação inicial utilizando:

- LangChain como framework de orquestração
- Heurísticas de localização espacial para mapear campos
- Aproximação por distância (campo mais próximo do valor)
- LLM apenas para campos não resolvidos pelas heurísticas

**Resultado**: Não funcionou bem. Layouts desconhecidos quebravam as heurísticas espaciais.

#### Iteração 2: LLM com Sumário de Heurísticas

Tentativa de melhorar:

- Enviar sumário dos resultados das heurísticas para o LLM
- LLM validaria e completaria campos faltantes

**Resultado**: Ainda insuficiente. Acurácia não atingia nível necessário.

#### Decisão Final: LLM Puro

**Justificativa**:

- Layouts desconhecidos tornam heurísticas espaciais arriscadas e não confiáveis
- LLM demonstrou capacidade de entender contexto e estrutura do documento
- Elimina manutenção de lógica complexa de heurísticas
- **Trade-off consciente**: Maior custo por processamento, mas maior precisão e manutenibilidade

### 3. Migração de LangChain para OpenAI API Direta

**Contexto**: Tempo de resposta inicial > 30s (inaceitável)

**Tentativas de Otimização com LangChain**:

- Otimização de prompts de sistema e user
- Redução de overhead do framework
- **Resultado**: Melhorias insuficientes

**Decisão**: **Migração para OpenAI API nativa**

**Justificativa**:

- Restrição de usar GPT-5-mini (não havia necessidade de abstração multi-provider)
- Controle granular sobre parâmetros do modelo
- Redução de overhead do framework LangChain
- Acesso direto a features específicas da OpenAI

### 4. Structured Outputs da OpenAI

**Descoberta**: [Structured Outputs API](https://platform.openai.com/docs/guides/structured-outputs)

**Implementação**:

- Schema Pydantic convertido para JSON Schema
- API retorna JSON rigorosamente aderente ao schema
- Eliminação de parsing manual e validação de resposta

**Benefícios**:

- **Respostas determinísticas**: Sempre no formato esperado
- **Economia**: Elimina tokens de retry e re-parsing
- **Simplicidade**: Código de validação reduzido drasticamente
- **Confiabilidade**: Sem erros de parsing em produção

### 5. Otimização de Parâmetros do Modelo

**Descoberta**: GPT-5 (e posteriores) mudaram parâmetros de controle

**Parâmetros Legados** (removidos no GPT-5):

- `temperature`
- `top_p`

**Novos Parâmetros**:

- `effort`: Controla quanto "esforço" computacional o modelo aplica
- `verbosity`: Controla quão verboso/conciso é a resposta

**Otimização Aplicada**:

- Ajuste fino de `effort` e `verbosity`
- Medição iterativa de acurácia com ground truth

**Resultados**:

- ✅ **Respostas mais determinísticas**
- ✅ **Latência reduzida** (< 10s em média)
- ✅ **Custo reduzido** por uso mais eficiente do modelo
- ✅ **Acurácia mantida/melhorada**

### 6. Cache Redis

**Decisão**: Implementar cache com chave SHA256(pdf_bytes + extraction_schema)

**Justificativa**:

- Documentos idênticos são comuns (re-uploads, validações)
- Economia significativa de custos de API
- Redução drástica de latência em cache hits
- SHA256 garante unicidade considerando PDF + schema

### 7. Próximas Investigações

**Em análise**:

- **TOON (Token-Oriented Object Notation)**: Nova técnica de formatação de prompts promissora

## Licença

MIT
