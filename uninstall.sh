#!/usr/bin/env bash
set -Eeuo pipefail
export LC_ALL=C

echo "========================================="
echo "     DEEP UNINSTALL - SAFE PROJECT CLEAN"
echo "========================================="

need() {
  command -v "$1" >/dev/null 2>&1 || { echo "Falta: $1"; exit 1; }
}

need docker

echo
echo "Digite o NOME DO PROJETO a ser removido:"
echo "(ex: TheManager, getea, omniguardian, flybiohub)"
read -r PROJECT_NAME

if [ -z "$PROJECT_NAME" ]; then
  echo "ERRO: nome inválido."
  exit 1
fi

echo
echo "=== PROCURANDO QUALQUER STACK DOCKER RELACIONADA A: $PROJECT_NAME ==="
echo

# --------------------------------------------
# 1. Remover containers relacionados
# --------------------------------------------
echo "-> Derrubando containers relacionados ao projeto..."
docker ps -a --format "{{.ID}} {{.Names}}" | grep -i "$PROJECT_NAME" | while read -r ID NAME; do
  echo "   - Removendo container: $NAME"
  docker rm -f "$ID" >/dev/null 2>&1 || true
done

# --------------------------------------------
# 2. Remover imagens relacionadas
# --------------------------------------------
echo "-> Removendo imagens relacionadas..."
docker images --format "{{.ID}} {{.Repository}}" | grep -i "$PROJECT_NAME" | while read -r ID REPO; do
  echo "   - Removendo imagem: $REPO"
  docker rmi -f "$ID" >/dev/null 2>&1 || true
done

# --------------------------------------------
# 3. Remover volumes relacionados
# --------------------------------------------
echo "-> Removendo volumes relacionados..."
docker volume ls --format "{{.Name}}" | grep -i "$PROJECT_NAME" | while read -r VOL; do
  echo "   - Removendo volume: $VOL"
  docker volume rm -f "$VOL" >/dev/null 2>&1 || true
done

# --------------------------------------------
# 4. Remover redes relacionadas
# --------------------------------------------
echo "-> Removendo redes relacionadas..."
docker network ls --format "{{.Name}}" | grep -i "$PROJECT_NAME" | while read -r NET; do
  echo "   - Removendo rede: $NET"
  docker network rm "$NET" >/dev/null 2>&1 || true
done

# --------------------------------------------
# 5. Remover pastas e arquivos da instalação antiga
# --------------------------------------------
SEARCH_DIRS=(
  "$PROJECT_NAME"
  "doker/$PROJECT_NAME"
  "docker/$PROJECT_NAME"
  "docker-compose-$PROJECT_NAME"
)

echo "-> Apagando pastas relacionadas..."
for DIR in "${SEARCH_DIRS[@]}"; do
  if [ -d "$DIR" ]; then
    echo "   - Removendo pasta: $DIR"
    rm -rf "$DIR"
  fi
done

echo "-> Apagando arquivos .env relacionados..."
find . -maxdepth 3 -type f -iname "*${PROJECT_NAME}*.env*" -print -delete 2>/dev/null || true

echo "-> Removendo caches, venvs e build lixos..."
find . -type d -iname "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type d -iname "venv" -exec rm -rf {} + 2>/dev/null || true
find . -type d -iname "env" -exec rm -rf {} + 2>/dev/null || true
find . -type d -iname "build" -exec rm -rf {} + 2>/dev/null || true
find . -type d -iname "dist" -exec rm -rf {} + 2>/dev/null || true

echo
echo "========================================="
echo "    REMOÇÃO COMPLETA FINALIZADA!"
echo "    Projeto limpo: $PROJECT_NAME"
echo "========================================="
echo
