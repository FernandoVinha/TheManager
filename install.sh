#!/usr/bin/env bash
set -Eeuo pipefail

echo "=============================="
echo "   TheManager - Installer"
echo "=============================="

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

# ---------- utils ----------
need() {
  command -v "$1" >/dev/null 2>&1 || { echo "Falta: $1"; exit 1; }
}

need docker
if ! docker compose version >/dev/null 2>&1; then
  echo "Preciso do Docker Compose v2 (comando 'docker compose')."
  exit 1
fi

if ! command -v openssl >/dev/null 2>&1; then
  echo "⚠️  openssl não encontrado. Vou usar /dev/urandom como fallback."
fi

# ---------- detectar IP da máquina ----------
HOST_IP=$(hostname -I 2>/dev/null | awk '{print $1}')

if [ -z "$HOST_IP" ]; then
  echo "Não consegui detectar o IP automaticamente. Usando 127.0.0.1 como fallback."
  HOST_IP="127.0.0.1"
fi

echo "IP detectado: $HOST_IP"
echo

# =====================================================
# 1) Instalar / subir Gitea primeiro
# =====================================================
echo "=============================="
echo "   Passo 1: Gitea"
echo "=============================="

if [ -d "doker/getea" ]; then
  echo "-> Entrando em doker/getea e rodando intsall_gitea.sh ..."
  (
    cd doker/getea
    chmod +x intsall_gitea.sh || true
    ./intsall_gitea.sh
  )
else
  echo "⚠️  Pasta doker/getea não encontrada. Pulando instalação do Gitea."
fi

# =====================================================
# 2) Gerar .env do Django / Postgres
# =====================================================
echo
echo "=============================="
echo "   Passo 2: Django + Postgres"
echo "=============================="

ENV_FILE=".env"

# backup se já existir
if [ -f "$ENV_FILE" ]; then
  BAK_FILE=".env.bak.$(date +%Y%m%d%H%M%S)"
  echo "Arquivo .env já existe. Fazendo backup em $BAK_FILE"
  mv "$ENV_FILE" "$BAK_FILE"
fi

# senha Postgres / secret key
if command -v openssl >/dev/null 2>&1; then
  POSTGRES_PASSWORD=$(openssl rand -hex 16)
  DJANGO_SECRET_KEY="django-insecure-$(openssl rand -hex 32)"
else
  POSTGRES_PASSWORD="$(tr -dc 'A-Za-z0-9' </dev/urandom | head -c 32)"
  DJANGO_SECRET_KEY="django-insecure-$(tr -dc 'A-Za-z0-9' </dev/urandom | head -c 64)"
fi

echo "-> Criando .env na raiz do projeto..."

cat > "$ENV_FILE" <<EOF
# =====================
# Ambiente do TheManager
# =====================

# Banco de dados Postgres
POSTGRES_DB=themanager
POSTGRES_USER=themanager
POSTGRES_PASSWORD=$POSTGRES_PASSWORD
POSTGRES_HOST=db
POSTGRES_PORT=5432

# Django
DJANGO_SECRET_KEY=$DJANGO_SECRET_KEY
DJANGO_DEBUG=1

# Hosts permitidos (lidos no settings.py)
ALLOWED_HOSTS=127.0.0.1,localhost,$HOST_IP

EOF

echo "Arquivo .env criado."
echo

echo "---------------------------------------------"
echo " Postgres:"
echo "   DB:       themanager"
echo "   User:     themanager"
echo "   Password: $POSTGRES_PASSWORD"
echo
echo " Django SECRET_KEY:"
echo "   $DJANGO_SECRET_KEY"
echo
echo " ALLOWED_HOSTS:"
echo "   127.0.0.1, localhost, $HOST_IP"
echo "---------------------------------------------"
echo

# =====================================================
# 3) Subir containers do Django
# =====================================================

echo "Subindo containers do Django (web + db)..."
docker compose up -d --build

echo
echo "============================================="
echo " TheManager iniciado com sucesso!"
echo " Acesse via:"
echo "   -> http://$HOST_IP:8000"
echo "   -> ou http://localhost:8000 (na própria máquina)"
echo "============================================="
