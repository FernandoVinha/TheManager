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
  # tenta IP da rede local (para mensagens e ALLOWED_HOSTS)
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
NETWORK_NAME="themanager-net"

echo "=============================="
echo "   TheManager - Installer"
echo "=============================="
echo "IP detectado (host): ${HOST_IP}"
echo

# -------------------------------------------------------------------
# Verificações básicas: docker e docker compose
# -------------------------------------------------------------------
need docker
if ! docker compose version >/dev/null 2>&1; then
  echo "ERRO: Docker Compose v2 não encontrado (comando 'docker compose')."
  echo "Instale ou atualize o Docker para uma versão com 'docker compose' integrado."
  exit 1
fi

# -------------------------------------------------------------------
# Criar rede Docker compartilhada (themanager-net)
# -------------------------------------------------------------------
echo "=============================="
echo "   Rede Docker compartilhada"
echo "=============================="
echo "Criando rede Docker '${NETWORK_NAME}' se ainda não existir..."
if ! docker network inspect "${NETWORK_NAME}" >/dev/null 2>&1; then
  docker network create "${NETWORK_NAME}"
  echo "-> Rede ${NETWORK_NAME} criada."
else
  echo "-> Rede ${NETWORK_NAME} já existe."
fi
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

need curl

echo "-> Entrando em doker/getea e rodando intsall_gitea.sh ..."
cd "$GITEA_DIR"
chmod +x ./intsall_gitea.sh

# ROOT_DOMAIN é usado só pra URL externa (navegador);
# Django falará com Gitea via http://host.docker.internal:3000 (ver GITEA_BASE_URL abaixo).
ROOT_DOMAIN="127.0.0.1" HTTP_PORT="3000" NETWORK_NAME="${NETWORK_NAME}" ./intsall_gitea.sh

# Carrega token do Gitea (se existir) a partir de doker/getea/.env
GITEA_ENV_FILE="${GITEA_DIR}/.env"
GITEA_TOKEN=""
if [ -f "$GITEA_ENV_FILE" ]; then
  GITEA_TOKEN="$(grep -E '^GITEA_ADMIN_TOKEN=' "$GITEA_ENV_FILE" | tail -n1 | cut -d= -f2- || true)"
fi

cd "$PROJECT_DIR"
echo

if [ -z "$GITEA_TOKEN" ]; then
  echo "⚠️  Atenção: GITEA_ADMIN_TOKEN não encontrado em doker/getea/.env."
  echo "    A integração automática (criação de usuários/repos no Gitea) ficará limitada"
  echo "    até você configurar um token de admin no .env."
  echo
else
  echo "-> GITEA_ADMIN_TOKEN detectado a partir de doker/getea/.env."
  echo
fi

# -------------------------------------------------------------------
# Passo 2: Django + Postgres (.env)
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

# O Django (container 'web') acessa o Gitea exposto no host (porta 3000)
# através de host.docker.internal (mapeado em extra_hosts no docker-compose).
GITEA_BASE_URL="http://host.docker.internal:3000"

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
USE_EXTERNAL_GITEA=0
EOF

# Só escreve o token no .env da raiz se realmente tiver sido gerado
if [ -n "$GITEA_TOKEN" ]; then
  echo "GITEA_ADMIN_TOKEN=${GITEA_TOKEN}" >> "$ENV_FILE"
fi

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
echo " GITEA_BASE_URL (dentro do Docker):"
echo "   ${GITEA_BASE_URL}"
if [ -n "$GITEA_TOKEN" ]; then
  echo
  echo " GITEA_ADMIN_TOKEN:"
  echo "   (foi detectado e gravado no .env)"
else
  echo
  echo " GITEA_ADMIN_TOKEN:"
  echo "   <não gerado automaticamente – veja aviso acima>"
fi
echo "---------------------------------------------"
echo

# -------------------------------------------------------------------
# Passo 3: Subir containers Django
# -------------------------------------------------------------------
echo "Subindo containers do Django (web + db)..."
cd "$PROJECT_DIR"
docker compose up -d --build

echo
echo "Aguardando container web iniciar (alguns segundos)..."
sleep 15

# -------------------------------------------------------------------
# Passo 4: Criar superusuário admin/admin (via createsuperuser)
# -------------------------------------------------------------------
echo "=============================="
echo "   Passo 3: Superusuário"
echo "=============================="
echo "-> Criando superusuário admin/admin no Django (e Gitea via signal)..."

set +e
docker compose exec \
  -e DJANGO_SUPERUSER_USERNAME=TheManager \
  -e DJANGO_SUPERUSER_EMAIL=TheManager@vinha.ai \
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
echo
echo " Acesse o Django via navegador:"
echo "   -> http://${HOST_IP}:8000"
echo "   -> ou http://localhost:8000 (na própria máquina)"
echo
echo " Acesse o Gitea via navegador:"
echo "   -> http://127.0.0.1:3000"
echo
echo " Dentro do Django (.env), o Gitea está configurado como:"
echo "   -> ${GITEA_BASE_URL}"
if [ -z "$GITEA_TOKEN" ]; then
  echo
  echo " ⚠ Observação:"
  echo "   O GITEA_ADMIN_TOKEN não foi gerado automaticamente."
  echo "   - Você ainda pode usar o Gitea normalmente via navegador."
  echo "   - Para habilitar criação automática de usuários/repos pelo Django:"
  echo "       1) Gere um token de admin no Gitea (Settings -> Applications)."
  echo "       2) Adicione GITEA_ADMIN_TOKEN=SEU_TOKEN no arquivo .env da raiz."
fi
echo "============================================="
echo
