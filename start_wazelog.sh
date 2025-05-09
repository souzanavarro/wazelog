#!/bin/bash

# Sair imediatamente se um comando falhar
set -e

echo "==> Iniciando servidor OSRM local em background..."
# Navega para o diretório do OSRM e inicia o docker-compose em modo detached (-d)
# Use 'docker-compose up -d osrm-backend' se o pré-processamento já foi feito
# Para garantir que funcione na primeira vez, usamos 'up -d'
# Ajuste o caminho para o diretório do projeto no Ubuntu
OSRM_DIR="/workspaces/Wazelog/routing/osrm_local"
PROJECT_DIR="/workspaces/Wazelog"

cd "${OSRM_DIR}" && docker-compose up -d
# Volta para o diretório raiz do projeto
cd "${PROJECT_DIR}"

echo "==> Aguardando OSRM iniciar (5 segundos)..."
sleep 5

echo "==> Tentando liberar a porta 8000 (FastAPI)..."
PID_8000=$(lsof -t -i:8000 || true)
if [ -n "$PID_8000" ]; then
  echo "Processo encontrado na porta 8000 (PID: $PID_8000). Tentando encerrar..."
  kill -9 $PID_8000 || true
  sleep 1 # Dá um tempo para a porta ser liberada
else
  echo "Porta 8000 parece estar livre."
fi

echo "==> Iniciando backend FastAPI (uvicorn) em background..."
# Inicia o uvicorn em background usando '&' - Usa python3
# Ativa o ambiente virtual se existir
if [ -d "venv" ]; then
    source venv/bin/activate
fi
python -m uvicorn main:app --host 0.0.0.0 --port 8000 &
# Guarda o ID do processo (PID) do uvicorn
UVICORN_PID=$!
echo "Backend FastAPI iniciado com PID: $UVICORN_PID"

echo "==> Aguardando FastAPI iniciar (3 segundos)..."
sleep 3

echo "==> Tentando liberar a porta 8501 (Streamlit)..."
PID_8501=$(lsof -t -i:8501 || true)
if [ -n "$PID_8501" ]; then
  echo "Processo encontrado na porta 8501 (PID: $PID_8501). Tentando encerrar..."
  kill -9 $PID_8501 || true
  sleep 1 # Dá um tempo para a porta ser liberada
else
  echo "Porta 8501 parece estar livre."
fi

echo "==> Iniciando frontend Streamlit em foreground..."
# Inicia o Streamlit. Este comando ficará ativo no terminal.
# Pressione Ctrl+C para parar o Streamlit (e o script). - Usa python3
# Ativa o ambiente virtual se existir (caso não tenha sido ativado antes)
if [ -d "venv" ] && [ -z "$VIRTUAL_ENV" ]; then
    source venv/bin/activate
fi
python -m streamlit run app/app.py --server.port 8501

# Quando o Streamlit (comando acima) for interrompido (Ctrl+C),
# o script continuará a partir daqui.
echo "==> Frontend Streamlit interrompido."

echo "==> Parando backend FastAPI (PID: $UVICORN_PID)..."
# Mata o processo do uvicorn que estava em background
kill $UVICORN_PID || true # Adiciona '|| true' para não falhar se o PID já não existir

echo "==> Parando servidor OSRM..."
# Navega para o diretório do OSRM e para os containers
cd "${OSRM_DIR}" && docker-compose down

echo "==> Wazelog finalizado."