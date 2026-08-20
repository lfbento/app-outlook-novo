#!/bin/bash
# ==========================================
# CARACOL Pipeline - Setup Ubuntu
# ==========================================
# Uso: chmod +x setup_ubuntu.sh && ./setup_ubuntu.sh
# ==========================================

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  CARACOL Pipeline - Setup Ubuntu${NC}"
echo -e "${GREEN}========================================${NC}"

# 1. Atualizar sistema
echo -e "\n${YELLOW}[1/6] Atualizando pacotes...${NC}"
sudo apt update && sudo apt upgrade -y

# 2. Instalar dependências do sistema
echo -e "\n${YELLOW}[2/6] Instalando dependências do sistema...${NC}"
sudo apt install -y \
    python3 python3-pip python3-venv \
    docker.io docker-compose-v2 \
    curl wget git \
    build-essential

# 3. Configurar Docker
echo -e "\n${YELLOW}[3/6] Configurando Docker...${NC}"
sudo usermod -aG docker $USER
sudo systemctl enable docker
sudo systemctl start docker
echo -e "${GREEN}Docker instalado. Faça logout/login para usar sem sudo.${NC}"

# 4. Criar ambiente virtual Python
echo -e "\n${YELLOW}[4/6] Criando ambiente virtual Python...${NC}"
cd "$(dirname "$0")"
python3 -m venv venv
source venv/bin/activate

# 5. Instalar dependências Python
echo -e "\n${YELLOW}[5/6] Instalando dependências Python...${NC}"
pip install --upgrade pip
pip install -r requirements.txt

# 6. Criar estrutura de diretórios
echo -e "\n${YELLOW}[6/6] Criando estrutura de dados...${NC}"
mkdir -p data/obsidian
mkdir -p data/extractions
mkdir -p data/db/chroma
mkdir -p data/neo4j/{data,logs,import,plugins}

# 7. Verificar .env
if [ ! -f .env ]; then
    echo -e "\n${YELLOW}Criando .env de exemplo...${NC}"
    cat > .env << 'EOF'
GROQ_API_KEY=gsk_sua_chave_aqui
DEEPSEEK_API_KEY=sk-sua_chave_aqui
NEO4J_URI=bolt://127.0.0.1:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=caracol_admin
EOF
    echo -e "${YELLOW}>>> EDITE o arquivo .env com suas chaves de API!${NC}"
fi

echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}  Setup concluído!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Próximos passos:"
echo "  1. Edite o arquivo .env com suas chaves de API"
echo "  2. Log out/in do sistema (para Docker sem sudo)"
echo "  3. Inicie o Neo4j:"
echo "     cd pipeline && docker compose up -d"
echo "  4. Aguarde ~2min e teste:"
echo "     source venv/bin/activate"
echo "     python pipeline/neo4j_loader_http_v1.py"
echo ""
