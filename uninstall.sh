#!/usr/bin/env bash
set -Eeuo pipefail
export LC_ALL=C

# ===============================
#  TheManager - Uninstaller
# ===============================

# ---------- utils ----------
need() {
  command -v "$1" >/dev/null 2>&1 || { echo "Falta: $1"; exit 1; }
}

# ---------- paths ----------
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

GITEA_DIR="${PROJECT_DIR}/doker/getea"

echo "=============================="
echo "   TheManager - Uninstaller"
echo "=============================="
echo
echo "Este script vai:"
echo "  - Derrubar containers Docker do TheManager (web + db) e do Gitea"
echo "  - Remover arquivos .env gerados automaticamente"
echo "  - Remover dados do Gitea (repos, DB) em doker/getea/gitea/"
echo
echo "Backups .env.bak.* na raiz NÃO serão apagados."
echo

if [[ "${1:-}" != "--force" ]]; then
  read -r -p "Tem certeza que deseja continuar? [y/N] " ans
  ans="${ans:-N}"
  case "$ans" in
    y|Y|yes|YES)
      echo "OK, continuando desinstalação..."
      ;;
    *)
      echo "Cancelado."
      exit 0
      ;;
  esac
fi

need docker

# -------------------------------------------------------------------
# 1) Derrubar containers do Django (web + db) na raiz
# -------------------------------------------------------------------
echo
echo "=============================="
echo "  Passo 1: Derrubando stack do TheManager (docker compose)"
echo "=============================="

if [ -f "${PROJECT_DIR}/docker-compose.yml" ]; then
  echo "-> Encontrado docker-compose.yml na raiz. Rodando: docker compose down -v"
  (cd "$PROJECT_DIR" && docker compose down -v) || {
    echo "⚠ Aviso: falha ao derrubar containers na raiz (ignorando)."
  }
else
  echo "-> Nenhum docker-compose.yml na raiz. Pulando..."
fi

# -------------------------------------------------------------------
# 2) Derrubar stack do Gitea em doker/getea
# -------------------------------------------------------------------
echo
echo "=============================="
echo "  Passo 2: Derrubando stack do Gitea (doker/getea)"
echo "=============================="

if [ -d "$GITEA_DIR" ] && [ -f "${GITEA_DIR}/docker-compose.yml" ]; then
  echo "-> Encontrado docker-compose.yml em doker/getea. Rodando: docker compose down -v"
  (cd "$GITEA_DIR" && docker compose down -v) || {
    echo "⚠ Aviso: falha ao derrubar stack do Gitea (ignorando)."
  }
else
  echo "-> Pasta doker/getea ou docker-compose.yml não encontrados. Pulando..."
fi

# -------------------------------------------------------------------
# 3) Remover arquivos .env e configs geradas
# -------------------------------------------------------------------
echo
echo "=============================="
echo "  Passo 3: Removendo arquivos de configuração gerados"
echo "=============================="

# .env principal
if [ -f "${PROJECT_DIR}/.env" ]; then
  echo "-> Removendo ${PROJECT_DIR}/.env"
  rm -f "${PROJECT_DIR}/.env"
else
  echo "-> .env na raiz não encontrado (talvez já removido)."
fi

# .env.email (se existir)
if [ -f "${PROJECT_DIR}/.env.email" ]; then
  echo "-> Removendo ${PROJECT_DIR}/.env.email"
  rm -f "${PROJECT_DIR}/.env.email"
else
  echo "-> .env.email não encontrado (ok)."
fi

# NÃO remover .env.bak.* (backups)
echo "-> Mantendo backups .env.bak.* na raiz (se existirem)."

# .env do Gitea
if [ -f "${GITEA_DIR}/.env" ]; then
  echo "-> Removendo ${GITEA_DIR}/.env"
  rm -f "${GITEA_DIR}/.env"
fi

# docker-compose.yml do Gitea
if [ -f "${GITEA_DIR}/docker-compose.yml" ]; then
  echo "-> Removendo ${GITEA_DIR}/docker-compose.yml"
  rm -f "${GITEA_DIR}/docker-compose.yml"
fi

# app.ini do Gitea
if [ -f "${GITEA_DIR}/gitea/config/app.ini" ]; then
  echo "-> Removendo ${GITEA_DIR}/gitea/config/app.ini"
  rm -f "${GITEA_DIR}/gitea/config/app.ini"
fi

# -------------------------------------------------------------------
# 4) Remover dados do Gitea (repos, db, config)
# -------------------------------------------------------------------
echo
echo "=============================="
echo "  Passo 4: Removendo dados do Gitea"
echo "=============================="

if [ -d "${GITEA_DIR}/gitea" ]; then
  echo "-> Removendo diretório ${GITEA_DIR}/gitea (data, db, config)"
  rm -rf "${GITEA_DIR}/gitea"
else
  echo "-> Diretório ${GITEA_DIR}/gitea não encontrado (ok)."
fi

echo
echo "============================================="
echo "  Desinstalação concluída."
echo "============================================="
echo "Arquivos preservados:"
echo "  - Backups .env.bak.* na raiz (caso existam)"
echo
echo "Se quiser remover o projeto inteiro, você ainda pode apagar manualmente:"
echo "  - o diretório do TheManager (${PROJECT_DIR})"
echo "============================================="
echo
