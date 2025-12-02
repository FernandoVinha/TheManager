# System Settings – Centralized Configuration for Email, Gitea, and OpenAI

This module provides the full administrative system for configuring **email delivery**, **Gitea integration**, and **OpenAI/LLM access** directly from the UI.  
All settings are securely written to `.env` files, enabling complete platform configuration without manually editing the server.

---

## ✨ Key Features

### ✔️ 1. Email Configuration Panel

A dedicated interface for managing all SMTP settings used by TheManager:

- `EMAIL_BACKEND`  
- `EMAIL_HOST`, `EMAIL_PORT`  
- `EMAIL_USE_TLS`, `EMAIL_USE_SSL`  
- `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`  
- `DEFAULT_FROM_EMAIL`, `SERVER_EMAIL`  

Saving the form automatically **rewrites `.env.email`** and triggers a **Django autoreload**.

---

### ✔️ 2. Gitea Configuration (External or Local)

Supports both **external** Gitea servers and **self-hosted Docker-based** setups.

#### 🔹 External Gitea Mode
Only requires:

- `GITEA_BASE_URL`  
- `GITEA_ADMIN_TOKEN`  

No Docker actions are performed.

#### 🔹 Local Gitea Docker Mode
Manages the entire local Gitea stack via `doker/getea/.env`, including:

##### **Database**
- `GITEA_DB_NAME`  
- `GITEA_DB_USER`  
- `MYSQL_ROOT_PASSWORD`  
- `MYSQL_PASSWORD`  

##### **Internal Secrets**
- `GITEA_SECRET_KEY`  
- `GITEA_INTERNAL_TOKEN`  
- `GITEA_JWT_SECRET`  

##### **Initial Admin User**
- `GITEA_ADMIN_USER`  
- `GITEA_ADMIN_PASS`  
- `GITEA_ADMIN_EMAIL` 