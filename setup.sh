#!/bin/bash

set -e

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "========================================="
echo "  PDF Extractor - Script de Instalação  "
echo "========================================="
echo ""

# 1. Verificar se Docker está instalado
echo -e "${YELLOW}[1/6]${NC} Verificando Docker..."
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker não encontrado!${NC}"
    echo "Por favor, instale o Docker antes de continuar."
    echo "Visite: https://docs.docker.com/get-docker/"
    exit 1
fi
echo -e "${GREEN}✓ Docker encontrado${NC}"

# 2. Verificar se Docker Compose está instalado
echo -e "${YELLOW}[2/6]${NC} Verificando Docker Compose..."
if ! command -v docker compose &> /dev/null && ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}❌ Docker Compose não encontrado!${NC}"
    echo "Por favor, instale o Docker Compose antes de continuar."
    echo "Visite: https://docs.docker.com/compose/install/"
    exit 1
fi
echo -e "${GREEN}✓ Docker Compose encontrado${NC}"

# 3. Baixar repositório principal
echo -e "${YELLOW}[3/6]${NC} Baixando repositório principal..."
REPO_DIR="PDF-Extractor"
if [ -d "$REPO_DIR" ]; then
    echo -e "${YELLOW}⚠ Diretório $REPO_DIR já existe. Removendo...${NC}"
    rm -rf "$REPO_DIR"
fi
git clone https://github.com/MatheusSerraoBotto/PDF-Extractor.git
echo -e "${GREEN}✓ Repositório principal baixado${NC}"

# 4. Entrar no repositório e baixar frontend
echo -e "${YELLOW}[4/6]${NC} Baixando repositório do frontend..."
cd "$REPO_DIR"
if [ -d "frontend" ]; then
    echo -e "${YELLOW}⚠ Diretório frontend já existe. Removendo...${NC}"
    rm -rf "frontend"
fi
git clone https://github.com/MatheusSerraoBotto/PDF-Extractor-Frontend.git frontend
echo -e "${GREEN}✓ Frontend baixado${NC}"

# 5. Configurar OPENAI_API_KEY
echo -e "${YELLOW}[5/6]${NC} Configurando OPENAI_API_KEY..."
echo ""
echo -e "${YELLOW}Por favor, cole sua chave da API OpenAI:${NC}"
read -r OPENAI_KEY

if [ -z "$OPENAI_KEY" ]; then
    echo -e "${RED}❌ Chave não pode estar vazia!${NC}"
    exit 1
fi

# Substituir a chave no arquivo dev.env
if [ -f "env/dev.env" ]; then
    sed -i "s/your_openai_api_key_here/$OPENAI_KEY/" env/dev.env
    echo -e "${GREEN}✓ Chave configurada no dev.env${NC}"
else
    echo -e "${RED}❌ Arquivo dev.env não encontrado!${NC}"
    exit 1
fi

# 6. Executar Docker Compose
echo -e "${YELLOW}[6/6]${NC} Iniciando containers Docker..."
docker compose -f docker/docker-compose.yml up -d
echo -e "${GREEN}✓ Containers iniciados com sucesso!${NC}"

echo ""
echo "========================================="
echo -e "${GREEN}✓ Instalação concluída com sucesso!${NC}"
echo "========================================="
echo ""
echo -e "${GREEN}Frontend disponível em:${NC} http://localhost:5173"
echo -e "${GREEN}Backend disponível em:${NC}  http://localhost:8000"
echo ""
echo -e "${YELLOW}ℹ Para mais informações sobre como usar as rotas do backend,"
echo -e "  consulte o arquivo README.md${NC}"
echo ""
echo -e "${YELLOW}⚠ ATENÇÃO:${NC} Altere a variável PDF_BASE_PATH no arquivo env/dev.env"
echo -e "  com o caminho onde estão contidos os PDFs que serão analisados."
echo ""
