# 🧩 Agile Team Manager — Sistema de Gerenciamento de Equipes e Código-Fonte

O **Agile Team Manager** é um sistema desenvolvido em **Django** voltado para o **gerenciamento de equipes de desenvolvimento de software** e acompanhamento de **projetos ágeis**, integrando práticas do **Scrum**, **Kanban** e **Extreme Programming (XP)**.  

O objetivo é oferecer uma plataforma central para **organizar tarefas, acompanhar produtividade, registrar horas, controlar versões de código** e **facilitar a comunicação técnica** entre desenvolvedores, líderes e clientes.

---

## 🚀 Visão Geral do Projeto

O sistema serve como um **hub operacional para equipes de TI**, unificando gestão de pessoas, projetos, tarefas e métricas de desenvolvimento.  

Ele foi pensado para **times reais de desenvolvimento**, com papéis, permissões e fluxos de trabalho inspirados em metodologias ágeis modernas.

**Pilares principais:**
- 📊 **Scrum** — Sprints, backlog, burndown e retrospectivas.  
- 🔁 **Kanban** — Fluxo contínuo e controle de gargalos por colunas visuais.  
- ⚙️ **XP (Extreme Programming)** — Qualidade técnica, pair programming, TDD e integração contínua.  

---

## 🧠 Estrutura Modular

O projeto é dividido em módulos independentes, permitindo evolução contínua e integração futura com ferramentas externas (como GitHub, GitLab, Bitbucket e CI/CD).

| Módulo | Função |
|--------|--------|
| **accounts** | Autenticação e controle de acesso (manager, employee, client). |
| **projects** | Gerenciamento de projetos, times e papéis por projeto. |
| **tasks** | Registro de tarefas, bugs, features e histórias de usuário. |
| **board** | Interface Kanban/Scrum com arrastar e soltar (drag & drop). |
| **reports** | Relatórios de horas, produtividade, velocity e ciclo de desenvolvimento. |
| **xp_tools** | Ferramentas técnicas: pareamento, commits, cobertura de testes, integração contínua. |

---

## 🧱 Funcionalidades Principais

### 🔐 Controle de Usuários
- Login por **email e senha** (sem username).
- **Papéis globais:**  
  - `System Manager` — gerencia todo o sistema.  
  - `Employee` — desenvolvedor ou colaborador interno.  
  - `Client` — acesso de leitura restrito ao progresso do projeto.
- **Avatar** e perfil pessoal.
- Permissões granulares e middleware que bloqueia quem não tem papel ativo.

### 📦 Gestão de Projetos
- Cadastro de projetos, equipes e responsáveis.
- Relacionamento entre **usuários e projetos** (membros, líderes, clientes).
- Controle de status e prioridade.

### 📋 Planejamento Ágil
- **Scrum:** backlog, sprints, histórias, story points e burndown charts.  
- **Kanban:** quadros dinâmicos com limites WIP, lead time e cycle time.  
- **XP:** registro de pares, integração contínua e feedback técnico.

### ⏱️ Registro de Horas
- Timer automático por tarefa.
- Aprovação de horas por líderes.
- Relatórios por membro, projeto e sprint.

### 📊 Relatórios e Métricas
- Velocity média por sprint.  
- Lead time / cycle time (Kanban).  
- Taxa de sucesso de builds e testes (XP).  
- Exportação CSV/PDF.

---

## 🧰 Tecnologias Utilizadas

| Área | Tecnologias |
|------|--------------|
| **Backend** | Python 3.12 · Django 5.2 · SQLite/PostgreSQL |
| **Frontend** | HTML5 · Bootstrap 5 · JS (Drag & Drop) |
| **Autenticação** | Django Auth + Custom User (email-based) |
| **Relatórios** | Chart.js · Matplotlib (PDFs) |
| **CI/CD (futuro)** | GitHub Actions / Jenkins / GitLab CI |
| **Infraestrutura (futuro)** | Docker · Nginx · Gunicorn |

---

## 🧩 Metodologias Implementadas

### 🌀 **Scrum**
- Sprints com metas definidas.  
- Planejamento e retrospectivas.  
- Burndown automático.  
- Velocity do time e histórico de entregas.

### 🧩 **Kanban**
- Colunas configuráveis: *To Do / Doing / Review / Done*.  
- Limite WIP e alertas de gargalo.  
- Métricas de fluxo (CFD, lead time, cycle time).

### ⚡ **Extreme Programming (XP)**
- Registro de **pair programming**.  
- Acompanhamento de **testes automatizados**.  
- Monitoramento de builds e qualidade do código.  
- Registro de feedbacks técnicos.

---

## 🧭 Papéis de Usuário

| Papel | Descrição | Acesso |
|--------|------------|---------|
| **System Manager** | Gerencia o sistema inteiro | Total |
| **Employee** | Desenvolvedor / colaborador | Projetos internos |
| **Client** | Cliente ou contratante | Visualização e feedback |
| **Sem papel** | Usuário sem função ativa | Nenhum acesso |

---

## ⚙️ Instalação e Execução Local

```bash
# 1. Crie o ambiente virtual
python -m venv venv
source venv/bin/activate  # ou venv\\Scripts\\activate (Windows)

# 2. Instale dependências
pip install django pillow

# 3. Rode as migrações
python manage.py makemigrations
python manage.py migrate

# 4. Crie o superusuário
python manage.py createsuperuser --email admin@local.com

# 5. Inicie o servidor
python manage.py runserver
