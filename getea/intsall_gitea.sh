#!/usr/bin/env bash
set -Eeuo pipefail
export LC_ALL=C

# ===============================
# Gitea all-in-one installer
# ===============================

# ---------- utils ----------
need() { command -v "$1" >/dev/null 2>&1 || { echo "Falta: $1"; exit 1; }; }

rand_hex () {
  if command -v openssl >/dev/null 2>&1; then openssl rand -hex "${1:-64}" | tr -d '\n'
  else head -c "${1:-64}" /dev/urandom | od -An -tx1 | tr -d ' \n'; fi
}
rand_pw () {
  tr -dc 'A-Za-z0-9!@#%^_+=-' < /dev/urandom | head -c "${1:-24}"
  echo
}

detect_tz() {
  if [ -n "${TZ:-}" ]; then echo "$TZ"; return; fi
  if [ -f /etc/timezone ]; then cat /etc/timezone && return; fi
  if [ -L /etc/localtime ]; then readlink /etc/localtime | sed 's|.*/zoneinfo/||' && return; fi
  echo "America/Sao_Paulo"
}

# ---------- defaults ----------
ROOT_DOMAIN="${ROOT_DOMAIN:-localhost}"
HTTP_PORT="${HTTP_PORT:-3000}"
SSH_PORT="${SSH_PORT:-222}"

PUID="${PUID:-1000}"
PGID="${PGID:-1000}"
TZ_VAL="$(detect_tz)"

GITEA_DB_NAME="${GITEA_DB_NAME:-gitea}"
GITEA_DB_USER="${GITEA_DB_USER:-gitea}"

GITEA_ADMIN_USER="${GITEA_ADMIN_USER:-manager}"
GITEA_ADMIN_EMAIL="${GITEA_ADMIN_EMAIL:-manager@vinha.ai}"

# ---------- gerar segredos ----------
echo "-> Gerando segredos…"
SECRET_KEY="$(rand_hex 64)"
INTERNAL_TOKEN="$(rand_hex 64)"
JWT_SECRET="$(rand_hex 64)"

MYSQL_ROOT_PASSWORD="$(rand_pw 24)"
MYSQL_PASSWORD="$(rand_pw 24)"
GITEA_ADMIN_PASSWORD="$(rand_pw 20)"

ROOT_URL="http://${ROOT_DOMAIN}:${HTTP_PORT}/"

mkdir -p gitea/config

ENV_FILE=".env"
APPINI_FILE="gitea/config/app.ini"
COMPOSE_FILE="docker-compose.yml"

# ---------- escrever .env ----------
echo "-> Escrevendo ${ENV_FILE}"
cat > "${ENV_FILE}" <<EOF
TZ=${TZ_VAL}

PUID=${PUID}
PGID=${PGID}

HTTP_PORT=${HTTP_PORT}
SSH_PORT=${SSH_PORT}

GITEA_DB_NAME=${GITEA_DB_NAME}
GITEA_DB_USER=${GITEA_DB_USER}
MYSQL_ROOT_PASSWORD=${MYSQL_ROOT_PASSWORD}
MYSQL_PASSWORD=${MYSQL_PASSWORD}

GITEA_SECRET_KEY=${SECRET_KEY}
GITEA_INTERNAL_TOKEN=${INTERNAL_TOKEN}
GITEA_JWT_SECRET=${JWT_SECRET}

GITEA_ADMIN_USER=${GITEA_ADMIN_USER}
GITEA_ADMIN_PASS=${GITEA_ADMIN_PASSWORD}

ROOT_DOMAIN=${ROOT_DOMAIN}
ROOT_URL=${ROOT_URL}
EOF

# ---------- escrever docker-compose.yml ----------
echo "-> Escrevendo ${COMPOSE_FILE}"
cat > "${COMPOSE_FILE}" <<'EOF'
services:
  gitea-db:
    image: mariadb:10.11
    restart: unless-stopped
    env_file: .env
    environment:
      MARIADB_ROOT_PASSWORD: ${MYSQL_ROOT_PASSWORD}
      MYSQL_ROOT_PASSWORD: ${MYSQL_ROOT_PASSWORD}
      MARIADB_USER: ${GITEA_DB_USER}
      MARIADB_PASSWORD: ${MYSQL_PASSWORD}
      MARIADB_DATABASE: ${GITEA_DB_NAME}
      TZ: ${TZ}
    command:
      - "--character-set-server=utf8mb4"
      - "--collation-server=utf8mb4_unicode_ci"
    volumes:
      - gitea_db_data:/var/lib/mysql
    healthcheck:
      test: ["CMD-SHELL", "mysqladmin ping -h 127.0.0.1 -uroot -p\"${MYSQL_ROOT_PASSWORD}\" || exit 1"]
      interval: 5s
      timeout: 5s
      retries: 30
      start_period: 30s

  gitea:
    image: gitea/gitea:latest
    container_name: gitea
    restart: unless-stopped
    depends_on:
      gitea-db:
        condition: service_healthy
    env_file: .env
    environment:
      USER_UID: ${PUID}
      USER_GID: ${PGID}
      TZ: ${TZ}
    ports:
      - "${HTTP_PORT}:3000"
      - "${SSH_PORT}:22"
    volumes:
      - gitea_data:/data
      - ./gitea/config/app.ini:/data/gitea/conf/app.ini

volumes:
  gitea_data:
  gitea_db_data:
EOF

# ---------- escrever app.ini ----------
echo "-> Escrevendo ${APPINI_FILE}"
cat > "${APPINI_FILE}" <<EOF
WORK_PATH = /data/gitea

[security]
INSTALL_LOCK = true
SECRET_KEY = ${SECRET_KEY}
INTERNAL_TOKEN = ${INTERNAL_TOKEN}

[oauth2]
JWT_SECRET = ${JWT_SECRET}

[database]
DB_TYPE = mysql
HOST = gitea-db:3306
NAME = ${GITEA_DB_NAME}
USER = ${GITEA_DB_USER}
PASSWD = ${MYSQL_PASSWORD}

[server]
DOMAIN = ${ROOT_DOMAIN}
ROOT_URL = ${ROOT_URL}
HTTP_PORT = 3000
SSH_PORT = 22
EOF

# ---------- subir containers ----------
need docker
if ! docker compose version >/dev/null 2>&1; then
  echo "Instale docker compose V2."
  exit 1
fi

echo "-> docker compose up -d"
docker compose up -d

# ---------- aguardar responder ----------
need curl
echo "-> Aguardando Gitea subir…"
for i in {1..60}; do
  if curl -fsS "${ROOT_URL}" >/dev/null 2>&1; then
    echo "   OK"
    break
  fi
  sleep 2
done

# ---------- criar admin ----------
echo "-> Criando admin…"
set +e
docker exec -u "${PUID}:${PGID}" -i gitea gitea admin user create \
  --username "${GITEA_ADMIN_USER}" \
  --password "${GITEA_ADMIN_PASSWORD}" \
  --email "${GITEA_ADMIN_EMAIL}" \
  --admin \
  --must-change-password=false \
  --config /data/gitea/conf/app.ini
set -e

# ---------- gerar token ----------
echo "-> Gerando token admin…"
ADMIN_TOKEN="$(
  docker exec -u "${PUID}:${PGID}" -i gitea \
    gitea admin user generate-access-token \
    --username "${GITEA_ADMIN_USER}" \
    --token-name "bootstrap-api" \
    --scopes "all" \
    --raw
)"

if [ -n "$ADMIN_TOKEN" ]; then
  echo "GITEA_ADMIN_TOKEN=${ADMIN_TOKEN}" >> "${ENV_FILE}"
  echo "-> Token salvo no .env"
else
  echo "-> NÃO FOI POSSÍVEL gerar token!"
fi

echo ""
echo "✅ FINALIZADO"
echo "URL: ${ROOT_URL}"
echo "Admin: ${GITEA_ADMIN_USER}"
echo "Senha: ${GITEA_ADMIN_PASSWORD}"
echo "Token salvo no .env"
