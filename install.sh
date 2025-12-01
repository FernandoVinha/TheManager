#!/usr/bin/env bash
set -Eeuo pipefail
export LC_ALL=C

# ===============================
#  TheManager - Installer
# ===============================

# ---------- utils ----------
need() {
  command -v "$1" >/dev/null 2>&1 || { echo "Falta: $1"; exit 1; }
}

rand_hex () {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex "${1:-32}" | tr -d '\n'
  else
    head -c "${1:-32}" /dev/urandom | od -An -tx1 | tr -d ' \n'
  fi
}

get_host_ip() {
  # tenta IP da rede local
  if ip route get 1.1.1.1 >/dev/null 2>&1; then
    ip route get 1.1.1.1 | awk '{for(i=1;i<=NF;i++) if($i=="src"){print $(i+1); exit}}'
    return
  fi
  # fallback
  hostname -I 2>/dev/null | awk '{print $1}'
}

# ---------- paths ----------
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

HOST_IP="$(get_host_ip || echo "127.0.0.1")"
echo "=============================="
echo "   TheManager - Installer"
echo "=============================="
echo "IP detectado: ${HOST_IP}"
echo

# -------------------------------------------------------------------
# Passo 1: Gitea (doker/getea/intsall_gitea.sh)
# -------------------------------------------------------------------
echo "=============================="
echo "   Passo 1: Gitea"
echo "=============================="

GITEA_DIR="${PROJECT_DIR}/doker/getea"
if [ ! -d "$GITEA_DIR" ]; then
  echo "ERRO: pasta ${GITEA_DIR} não encontrada."
  exit 1
fi

need docker
need curl

echo "-> Entrando em doker/getea e rodando intsall_gitea.sh ..."
cd "$GITEA_DIR"
chmod +x ./intsall_gitea.sh
./intsall_gitea.sh

# Carrega token do Gitea (se existir)
GITEA_ENV_FILE="${GITEA_DIR}/.env"
GITEA_TOKEN=""
if [ -f "$GITEA_ENV_FILE" ]; then
  GITEA_TOKEN="$(grep -E '^GITEA_ADMIN_TOKEN=' "$GITEA_ENV_FILE" | tail -n1 | cut -d= -f2- || true)"
fi

cd "$PROJECT_DIR"
echo

# -------------------------------------------------------------------
# Passo 2: Django + Postgres
# -------------------------------------------------------------------
echo "=============================="
echo "   Passo 2: Django + Postgres"
echo "=============================="

ENV_FILE="${PROJECT_DIR}/.env"
if [ -f "$ENV_FILE" ]; then
  TS="$(date +%Y%m%d%H%M%S)"
  echo "Arquivo .env já existe. Fazendo backup em .env.bak.${TS}"
  cp "$ENV_FILE" ".env.bak.${TS}"
fi

POSTGRES_DB="themanager"
POSTGRES_USER="themanager"
POSTGRES_PASSWORD="$(rand_hex 16)"
DJANGO_SECRET_KEY="django-insecure-$(rand_hex 32)"
ALLOWED_HOSTS="127.0.0.1,localhost,${HOST_IP}"

# Gitea ficará acessível pelo IP da máquina na porta 3000
GITEA_BASE_URL="http://${HOST_IP}:3000"

echo "-> Criando .env na raiz do projeto..."
cat > "$ENV_FILE" <<EOF
# =====================
# Ambiente do TheManager
# =====================

# Banco de dados Postgres
POSTGRES_DB=${POSTGRES_DB}
POSTGRES_USER=${POSTGRES_USER}
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
POSTGRES_HOST=db
POSTGRES_PORT=5432

# Django
DJANGO_SECRET_KEY=${DJANGO_SECRET_KEY}
DJANGO_DEBUG=1

# Hosts permitidos (lidos no settings.py)
ALLOWED_HOSTS=${ALLOWED_HOSTS}

# Integração Gitea
GITEA_BASE_URL=${GITEA_BASE_URL}
GITEA_ADMIN_TOKEN=${GITEA_TOKEN}
EOF

echo "Arquivo .env criado."
echo
echo "---------------------------------------------"
echo " Postgres:"
echo "   DB:       ${POSTGRES_DB}"
echo "   User:     ${POSTGRES_USER}"
echo "   Password: ${POSTGRES_PASSWORD}"
echo
echo " Django SECRET_KEY:"
echo "   ${DJANGO_SECRET_KEY}"
echo
echo " ALLOWED_HOSTS:"
echo "   ${ALLOWED_HOSTS}"
echo
echo " GITEA_BASE_URL:"
echo "   ${GITEA_BASE_URL}"
echo "---------------------------------------------"
echo

# -------------------------------------------------------------------
# Subir containers Django
# -------------------------------------------------------------------
echo "Subindo containers do Django (web + db)..."
cd "$PROJECT_DIR"
docker compose up -d --build

echo
echo "Aguardando container web iniciar (alguns segundos)..."
sleep 15

# -------------------------------------------------------------------
# Criar superusuário admin/admin via createsuperuser
# (isso também dispara criação no Gitea via signals)
# -------------------------------------------------------------------
echo "=============================="
echo "   Passo 3: Superusuário"
echo "=============================="
echo "-> Criando superusuário admin/admin no Django (e Gitea via signal)..."

set +e
docker compose exec \
  -e DJANGO_SUPERUSER_USERNAME=admin \
  -e DJANGO_SUPERUSER_EMAIL=admin@admin.com \
  -e DJANGO_SUPERUSER_PASSWORD=admin \
  web python manage.py createsuperuser --noinput
RET_SU=$?
set -e
:

# -------------------------------------------------------------------
# Criar superusuário admin/admin via createsuperuser
# (isso também dispara criação no Gitea via signals)
# -------------------------------------------------------------------
echo "=============================="
echo "   Passo 3: Superusuário"
echo "=============================="
echo "-> Criando superusuário admin/admin no Django (e Gitea via signal)..."

set +e
docker compose exec \
  -e DJANGO_SUPERUSER_USERNAME=admin \
  -e DJANGO_SUPERUSER_EMAIL=admin@admin.com \
  -e DJANGO_SUPERUSER_PASSWORD=admin \
  web python manage.py createsuperuser --noinput
RET_SU=$?
set -e

:

# -------------------------------------------------------------------
# Criar superusuário admin/admin via createsuperuser
# (isso também dispara criação no Gitea via signals)
# -------------------------------------------------------------------
echo "=============================="
echo "   Passo 3: Superusuário"
echo "=============================="
echo "-> Criando superusuário admin/admin no Django (e Gitea via signal)..."

set +e
docker compose exec \
  -e DJANGO_SUPERUSER_USERNAME=admin \
  -e DJANGO_SUPERUSER_EMAIL=admin@admin.com \
  -e DJANGO_SUPERUSER_PASSWORD=admin \
  web python manage.py createsuperuser --noinput
RET_SU=$?
set -e

if [ "$RET_SU" -eq 0 ]; then
  echo "✔ Superusuário admin/admin criado com sucesso."
else
  echo "⚠ Não foi possível criar o superusuário automaticamente."
  echo "   Talvez ele já exista. Você pode rodar manualmente:"
  echo "   docker compose exec web python manage.py createsuperuser"
fi

:

# -------------------------------------------------------------------
# Criar superusuário admin/admin via createsuperuser
# (isso também dispara criação no Gitea via signals)
# -------------------------------------------------------------------
echo "=============================="
echo "   Passo 3: Superusuário"
echo "=============================="
echo "-> Criando superusuário admin/admin no Django (e Gitea via signal)..."

set +e
docker compose exec \
  -e DJANGO_SUPERUSER_USERNAME=admin \
  -e DJANGO_SUPERUSER_EMAIL=admin@admin.com \
  -e DJANGO_SUPERUSER_PASSWORD=admin \
  web python manage.py createsuperuser --noinput
RET_SU=$?
set -e

if [ "$RET_SU" -eq 0 ]; then
  echo "✔ Superusuário admin/admin criado com sucesso."
else
  echo "⚠ Não foi possível criar o superusuário automaticamente."
  echo "   Talvez ele já exista. Você pode rodar manualmente:"
  echo "   docker compose exec web python manage.py createsuperuser"
fi

echo
echo "============================================="
echo " TheManager iniciado com sucesso!"
echo " Acesse via:"
echo "   -> http://${HOST_IP}:8000"
echo "   -> ou http://localhost:8000 (na própria máquina)"
echo "============================================="
echo
~
(END)

# -------------------------------------------------------------------
# Criar superusuário admin/admin via createsuperuser
# (isso também dispara criação no Gitea via signals)
# -------------------------------------------------------------------
echo "=============================="
echo "   Passo 3: Superusuário"
echo "=============================="
echo "-> Criando superusuário admin/admin no Django (e Gitea via signal)..."

set +e
docker compose exec \
  -e DJANGO_SUPERUSER_USERNAME=admin \
  -e DJANGO_SUPERUSER_EMAIL=admin@admin.com \
  -e DJANGO_SUPERUSER_PASSWORD=admin \
  web python manage.py createsuperuser --noinput
RET_SU=$?
set -e

if [ "$RET_SU" -eq 0 ]; then
  echo "✔ Superusuário admin/admin criado com sucesso."
else
  echo "⚠ Não foi possível criar o superusuário automaticamente."
  echo "   Talvez ele já exista. Você pode rodar manualmente:"
  echo "   docker compose exec web python manage.py createsuperuser"
fi

echo
echo "============================================="
echo " TheManager iniciado com sucesso!"
echo " Acesse via:"
echo "   -> http://${HOST_IP}:8000"
echo "   -> ou http://localhost:8000 (na própria máquina)"
echo "============================================="
echo
~
~
~
~
~
~
~
(END)

# -------------------------------------------------------------------
# Criar superusuário admin/admin via createsuperuser
# (isso também dispara criação no Gitea via signals)
# -------------------------------------------------------------------
echo "=============================="
echo "   Passo 3: Superusuário"
echo "=============================="
echo "-> Criando superusuário admin/admin no Django (e Gitea via signal)..."

set +e
docker compose exec \
  -e DJANGO_SUPERUSER_USERNAME=admin \
  -e DJANGO_SUPERUSER_EMAIL=admin@admin.com \
  -e DJANGO_SUPERUSER_PASSWORD=admin \
  web python manage.py createsuperuser --noinput
RET_SU=$?
set -e

if [ "$RET_SU" -eq 0 ]; then
  echo "✔ Superusuário admin/admin criado com sucesso."
else
  echo "⚠ Não foi possível criar o superusuário automaticamente."
  echo "   Talvez ele já exista. Você pode rodar manualmente:"
  echo "   docker compose exec web python manage.py createsuperuser"
fi

echo
echo "============================================="
echo " TheManager iniciado com sucesso!"
echo " Acesse via:"
echo "   -> http://${HOST_IP}:8000"
echo "   -> ou http://localhost:8000 (na própria máquina)"
echo "============================================="
echo
~
~
~
~
~
~
~
~
~
~
(END)

# -------------------------------------------------------------------
# Criar superusuário admin/admin via createsuperuser
# (isso também dispara criação no Gitea via signals)
# -------------------------------------------------------------------
echo "=============================="
echo "   Passo 3: Superusuário"
echo "=============================="
echo "-> Criando superusuário admin/admin no Django (e Gitea via signal)..."

set +e
docker compose exec \
  -e DJANGO_SUPERUSER_USERNAME=admin \
  -e DJANGO_SUPERUSER_EMAIL=admin@admin.com \
  -e DJANGO_SUPERUSER_PASSWORD=admin \
  web python manage.py createsuperuser --noinput
RET_SU=$?
set -e

if [ "$RET_SU" -eq 0 ]; then
  echo "✔ Superusuário admin/admin criado com sucesso."
else
  echo "⚠ Não foi possível criar o superusuário automaticamente."
  echo "   Talvez ele já exista. Você pode rodar manualmente:"
  echo "   docker compose exec web python manage.py createsuperuser"
fi

echo
echo "============================================="
echo " TheManager iniciado com sucesso!"
echo " Acesse via:"
echo "   -> http://${HOST_IP}:8000"
echo "   -> ou http://localhost:8000 (na própria máquina)"
echo "============================================="
echo
~
~
~
~
~
~
~
~
~
~
~
~
(END)

# -------------------------------------------------------------------
# Criar superusuário admin/admin via createsuperuser
# (isso também dispara criação no Gitea via signals)
# -------------------------------------------------------------------
echo "=============================="
echo "   Passo 3: Superusuário"
echo "=============================="
echo "-> Criando superusuário admin/admin no Django (e Gitea via signal)..."

set +e
docker compose exec \
  -e DJANGO_SUPERUSER_USERNAME=admin \
  -e DJANGO_SUPERUSER_EMAIL=admin@admin.com \
  -e DJANGO_SUPERUSER_PASSWORD=admin \
  web python manage.py createsuperuser --noinput
RET_SU=$?
set -e

if [ "$RET_SU" -eq 0 ]; then
  echo "✔ Superusuário admin/admin criado com sucesso."
else
  echo "⚠ Não foi possível criar o superusuário automaticamente."
  echo "   Talvez ele já exista. Você pode rodar manualmente:"
  echo "   docker compose exec web python manage.py createsuperuser"
fi

echo
echo "============================================="
echo " TheManager iniciado com sucesso!"
echo " Acesse via:"
echo "   -> http://${HOST_IP}:8000"
echo "   -> ou http://localhost:8000 (na própria máquina)"
echo "============================================="
echo
~
~
~
~
~
~
~
~
~
~
~
~
~
(END)

# -------------------------------------------------------------------
# Criar superusuário admin/admin via createsuperuser
# (isso também dispara criação no Gitea via signals)
# -------------------------------------------------------------------
echo "=============================="
echo "   Passo 3: Superusuário"
echo "=============================="
echo "-> Criando superusuário admin/admin no Django (e Gitea via signal)..."

set +e
docker compose exec \
  -e DJANGO_SUPERUSER_USERNAME=admin \
  -e DJANGO_SUPERUSER_EMAIL=admin@admin.com \
  -e DJANGO_SUPERUSER_PASSWORD=admin \
  web python manage.py createsuperuser --noinput
RET_SU=$?
set -e

if [ "$RET_SU" -eq 0 ]; then
  echo "✔ Superusuário admin/admin criado com sucesso."
else
  echo "⚠ Não foi possível criar o superusuário automaticamente."
  echo "   Talvez ele já exista. Você pode rodar manualmente:"
  echo "   docker compose exec web python manage.py createsuperuser"
fi

echo
echo "============================================="
echo " TheManager iniciado com sucesso!"
echo " Acesse via:"
echo "   -> http://${HOST_IP}:8000"
echo "   -> ou http://localhost:8000 (na própria máquina)"
echo "============================================="
echo
~
~
~
~
~
~
~
~
~
~
~
~
~
~
(END)

# -------------------------------------------------------------------
# Criar superusuário admin/admin via createsuperuser
# (isso também dispara criação no Gitea via signals)
# -------------------------------------------------------------------
echo "=============================="
echo "   Passo 3: Superusuário"
echo "=============================="
echo "-> Criando superusuário admin/admin no Django (e Gitea via signal)..."

set +e
docker compose exec \
  -e DJANGO_SUPERUSER_USERNAME=admin \
  -e DJANGO_SUPERUSER_EMAIL=admin@admin.com \
  -e DJANGO_SUPERUSER_PASSWORD=admin \
  web python manage.py createsuperuser --noinput
RET_SU=$?
set -e

if [ "$RET_SU" -eq 0 ]; then
  echo "✔ Superusuário admin/admin criado com sucesso."
else
  echo "⚠ Não foi possível criar o superusuário automaticamente."
  echo "   Talvez ele já exista. Você pode rodar manualmente:"
  echo "   docker compose exec web python manage.py createsuperuser"
fi

echo
echo "============================================="
echo " TheManager iniciado com sucesso!"
echo " Acesse via:"
echo "   -> http://${HOST_IP}:8000"
echo "   -> ou http://localhost:8000 (na própria máquina)"
echo "============================================="
echo