#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# --- Variáveis ---
PROJECT_SOURCE="/tmp/WazeLog-main" # Onde você copiou os arquivos do projeto
PROJECT_DEST="/root/wazelog"      # Diretório final do projeto

# --- Atualizar Sistema ---
echo ">>> Atualizando pacotes do sistema..."
apt update
apt upgrade -y

# --- Instalar Dependências Básicas (Python, Pip, Venv, Git, Curl) ---
echo ">>> Instalando Python3, Pip, Venv, Git, Curl..."
apt install -y python3 python3-pip python3-venv git curl

# --- Instalar Docker ---
echo ">>> Instalando Docker..."
# Remove versões antigas se existirem
for pkg in docker.io docker-doc docker-compose docker-compose-v2 podman-docker containerd runc; do apt-get remove -y $pkg; done
# Adiciona repositório oficial do Docker
apt-get update
apt-get install -y ca-certificates curl
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
# Adiciona o repositório às fontes do Apt:
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo \"$VERSION_CODENAME\") stable" | \
  tee /etc/apt/sources.list.d/docker.list > /dev/null
apt-get update
# Instala Docker Engine
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

echo ">>> Verificando instalação do Docker..."
docker --version

# --- Instalar Docker Compose (Standalone - v2 já vem com o plugin acima, mas garantimos) ---
# Nota: docker-compose-plugin geralmente é suficiente, mas instalamos standalone para garantir compatibilidade
DOCKER_COMPOSE_VERSION=$(curl -s https://api.github.com/repos/docker/compose/releases/latest | grep '"tag_name":' | sed -E 's/.*"([^"]+)".*/\1/')
echo ">>> Instalando Docker Compose standalone ${DOCKER_COMPOSE_VERSION}..."
DESTINATION=/usr/local/bin/docker-compose
curl -L "https://github.com/docker/compose/releases/download/${DOCKER_COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" -o $DESTINATION
chmod +x $DESTINATION
docker-compose --version

# --- Preparar Diretório do Projeto ---
echo ">>> Criando diretório do projeto em ${PROJECT_DEST}..."
mkdir -p "${PROJECT_DEST}"

echo ">>> Copiando arquivos do projeto de ${PROJECT_SOURCE} para ${PROJECT_DEST}..."
# Copia todo o conteúdo, incluindo arquivos ocultos (exceto . e ..)
cp -rT "${PROJECT_SOURCE}" "${PROJECT_DEST}"
# Alternativa com rsync (melhor se for re-executar):
# rsync -av --exclude='.git' "${PROJECT_SOURCE}/" "${PROJECT_DEST}/"

# --- Configurar Ambiente Virtual e Dependências Python ---
echo ">>> Configurando ambiente virtual Python..."
cd "${PROJECT_DEST}"
python3 -m venv venv

echo ">>> Instalando dependências Python de requirements.txt..."
# Usa o pip do venv diretamente
venv/bin/pip install --upgrade pip
venv/bin/pip install -r requirements.txt

# --- Definir Permissões ---
echo ">>> Definindo permissões de execução para start_wazelog.sh..."
chmod +x start_wazelog.sh

# --- (Opcional) Iniciar OSRM Backend ---
OSRM_DIR="${PROJECT_DEST}/routing/osrm_local"
if [ -f "${OSRM_DIR}/docker-compose.yml" ]; then
  echo ">>> Verificando dados OSRM em ${OSRM_DIR}/data/..."
  if [ -z "$(ls -A ${OSRM_DIR}/data/)" ]; then
     echo "AVISO: Diretório de dados OSRM (${OSRM_DIR}/data/) está vazio."
     echo "AVISO: Você precisará baixar/gerar os arquivos .osm.pbf e .osrm.* e colocá-los lá."
     echo "AVISO: O backend OSRM não será iniciado automaticamente."
  else
     echo ">>> Iniciando container OSRM em background (docker compose up -d)..."
     cd "${OSRM_DIR}"
     docker compose up -d
     cd "${PROJECT_DEST}" # Volta para o diretório principal
  fi
else
  echo ">>> Arquivo docker-compose.yml não encontrado em ${OSRM_DIR}. Pulando inicialização do OSRM."
fi

# --- Finalização ---
echo ""
echo "-----------------------------------------------------"
echo ">>> Instalação concluída!"
echo ">>> O projeto WazeLog está em: ${PROJECT_DEST}"
echo ""
echo ">>> Para iniciar a aplicação:"
echo "1. Navegue até o diretório: cd ${PROJECT_DEST}"
echo "2. (Opcional, se não estiver ativo) Ative o ambiente virtual: source venv/bin/activate"
echo "3. Execute o script de inicialização: ./start_wazelog.sh"
echo ""
echo ">>> Para iniciar o Streamlit manualmente (se start_wazelog.sh não fizer isso):"
echo "   streamlit run app/app.py"
echo ""
echo ">>> Lembre-se de verificar se os dados OSRM estão corretos em ${OSRM_DIR}/data/ se o container não iniciou."
echo "-----------------------------------------------------"

exit 0