#!/usr/bin/env bash
set -Eeuo pipefail
export LC_ALL=C

# =====================================
#  TheManager - Uninstaller (parcial)
# =====================================
# Remove apenas:
#  - containers / network / volumes do TheManager
#  - containers / data do Gitea deste projeto
# NÃO roda nenhum "docker system prune" nem mexe em
# outros projetos Docker do servidor.

need() {
  command -v "$1" >/dev/null 2>&1 || { echo "Falta: $1"; exit 1; }
}

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=============================="
echo "   TheManager - Uninstaller"
echo "=============================="
echo "Projeto em: ${PROJECT_DIR}"
echo

need docker

# ------------------------------------------------
# 1) Derrubar Django + Postgres (raiz do projeto)
# ------------------------------------------------
echo "-> Derrubando stack Django + Postgres (docker compose down -v) ..."
cd "$PROJECT_DIR"

if [ -f docker-compose.yml ]; then
  docker compose down -v || echo "  (aviso) Falha ao derrubar stack Django, talvez já esteja parado."
else
  echo "  (aviso) docker-compose.yml não encontrado na raiz, pulando Django."
fi

# ------------------------------------------------
# 2) Derrubar Gitea deste projeto
# ------------------------------------------------
GITEA_DIR="${PROJECT_DIR}/doker/getea"

echo
echo "-> Derrubando stack Gitea deste projeto ..."
if [ -d "$GITEA_DIR" ] && [ -f "${GITEA_DIR}/docker-compose.yml" ]; then
  cd "$GITEA_DIR"
  docker compose down || echo "  (aviso) Falha ao derrubar stack Gitea, talvez já esteja parado."
else
  echo "  (aviso) Pasta doker/getea ou docker-compose.yml não encontrados, pulando Gitea."
fi

# ------------------------------------------------
# 3) Remover dados locais do Gitea deste projeto
# ------------------------------------------------
echo
echo "-> Removendo dados locais do Gitea (somente deste projeto) ..."

GITEA_DB_DIR="${GITEA_DIR}/gitea/db"
GITEA_DATA_DIR="${GITEA_DIR}/gitea/data"

if [ -d "$GITEA_DB_DIR" ]; then
  echo "   rm -rf ${GITEA_DB_DIR}"
  rm -rf "$GITEA_DB_DIR" || echo "   (aviso) Não foi possível apagar ${GITEA_DB_DIR} (permissão?)."
else
  echo "   (info) ${GITEA_DB_DIR} não existe, nada a remover."
fi

if [ -d "$GITEA_DATA_DIR" ]; then
  echo "   rm -rf ${GITEA_DATA_DIR}"
  rm -rf "$GITEA_DATA_DIR" || echo "   (aviso) Não foi possível apagar ${GITEA_DATA_DIR} (permissão?)."
else
  echo "   (info) ${GITEA_DATA_DIR} não existe, nada a remover."
fi

# ------------------------------------------------
# 4) Remover volume do Postgres do TheManager
# ------------------------------------------------
echo
echo "-> Removendo volume Docker do Postgres do TheManager (se existir) ..."
cd "$PROJECT_DIR"

# Nome padrão do volume conforme docker-compose: themanager_postgres_data
if docker volume inspect themanager_postgres_data >/dev/null 2>&1; then
  docker volume rm themanager_postgres_data || echo "  (aviso) Não foi possível remover volume themanager_postgres_data."
else
  echo "  (info) Volume themanager_postgres_data não existe, nada a remover."
fi

# ------------------------------------------------
# 5) Remover imagem themanager-web (opcional)
# ------------------------------------------------
echo
echo "-> Removendo imagem Docker themanager-web (se existir) ..."
if docker image inspect themanager-web >/dev/null 2>&1; then
  docker rmi themanager-web || echo "  (aviso) Não foi possível remover imagem themanager-web (talvez em uso)."
else
  echo "  (info) Imagem themanager-web não encontrada, nada a remover."
fi

# ------------------------------------------------
# 6) Resumo
# ------------------------------------------------
echo
echo "========================================="
echo " Uninstall parcial concluído."
echo " - Stack Django + Postgres parado e removido"
echo " - Stack Gitea deste projeto parado e removido"
echo " - Volume themanager_postgres_data removido (se existia)"
echo " - Pastas doker/getea/gitea/db e gitea/data limpas (se existiam)"
echo " - Imagem themanager-web removida (se existia)"
echo
echo "Nenhum outro container/volume/docker global foi alterado."
echo "========================================="
