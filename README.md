# OTServ Control Panel

[![Linux Build](https://github.com/FelipeArruda/otserver-tibia-site/actions/workflows/docker-linux.yml/badge.svg)](https://github.com/FelipeArruda/otserver-tibia-site/actions/workflows/docker-linux.yml)
[![Windows Build](https://github.com/FelipeArruda/otserver-tibia-site/actions/workflows/docker-windows.yml/badge.svg)](https://github.com/FelipeArruda/otserver-tibia-site/actions/workflows/docker-windows.yml)
[![Quality Checks](https://github.com/FelipeArruda/otserver-tibia-site/actions/workflows/quality.yml/badge.svg)](https://github.com/FelipeArruda/otserver-tibia-site/actions/workflows/quality.yml)

Idioma: Português (Brasil) | [English](README.en.md)

Painel web em Django para gerenciamento e operação de servidores OTServ/Tibia.

## Objetivo

Construir uma plataforma web para:

- autenticação de usuários;
- cadastro e gerenciamento de multiplos servidores OTServ;
- validação de status do servidor (online/offline);
- exibição de players online;
- leitura de entidades do banco do OTServ;
- seleção de versão do servidor;
- shopping integrado;
- sistema de temas com upload e ativação;
- execução local e em containers.

## Stack principal

- Backend: Django
- Frontend: Django Templates + Tailwind CSS
- Banco da aplicação: PostgreSQL (padrão), com opção de MariaDB
- Infra: Docker + Docker Compose

## Build e Deploy (Docker)

### Pré-requisitos

- Docker
- Docker Compose

### Build local (Linux image)

```bash
docker compose build
```

### Subir local

```bash
docker compose up -d
```

O container roda migrações automaticamente no startup (`python manage.py migrate --noinput`) antes de iniciar o servidor.

Aplicação local: `http://localhost:8000`

Com a stack atual, o `docker compose` também sobe:

- `redis` (broker/result backend);
- `celery_worker` (execução de tarefas assíncronas);
- `celery_beat` (agendamento periódico).

A rotina de `health check` dos OTServers roda automaticamente via Celery Beat, respeitando o intervalo configurado por OTServer.

### Build manual por Dockerfile

Linux:

```bash
docker build -f Dockerfile.linux -t otserver-tibia-site:linux .
```

Windows:

```powershell
docker build -f Dockerfile.windows -t otserver-tibia-site:windows .
```

Observação: os Dockerfiles fazem `python -m pip install --upgrade pip` antes da instalação dos pacotes.

## CI/CD (GitHub Actions + Docker Hub)

Workflows:

- `.github/workflows/docker-linux.yml`
- `.github/workflows/docker-windows.yml`
- `.github/workflows/quality.yml`
- `.github/workflows/release.yml`

Disparo:

- `push` para branch `main`
- `pull_request` para validar build de Linux e Windows sem publicar imagem
- `workflow_dispatch` manual

Secrets obrigatórios no repositório GitHub:

- `DOCKERHUB_USERNAME`
- `DOCKERHUB_TOKEN`

Tags publicadas:

- Linux: `linux-<sha>` e `latest-linux`
- Windows: `windows-<sha>` e `latest-windows`

Comportamento por evento:

- `pull_request`: builda Linux e Windows apenas para validacao, sem login no Docker Hub e sem `push`
- `push` em `main` e `workflow_dispatch`: builda e publica as imagens

Release automatizado:

- gera tag no formato `vYYYY.MM.DD.N` (ex.: `v2026.03.16.1`)
- se houver novo release no mesmo dia, incrementa `N` (`v2026.03.16.2`, `v20260316.3`, ...)
- publica imagens no Docker Hub com a versao do release:
  - `${DOCKERHUB_USERNAME}/otserver-tibia-site:vYYYY.MM.DD.N-linux`
  - `${DOCKERHUB_USERNAME}/otserver-tibia-site:vYYYY.MM.DD.N-windows`

Observacao sobre build local do Dockerfile de Windows:

- em host Docker Linux, o `Dockerfile.windows` nao consegue ser executado de ponta a ponta porque a imagem base e Windows-only
- a validacao real desse Dockerfile acontece no runner `windows-2022` do GitHub Actions

## Qualidade e Testes

Dependências de dev:

```bash
pip install -r requirements-dev.txt
```

Checks locais:

```bash
ruff check .
ruff format --check .
python manage.py makemigrations --check --dry-run
pytest -q
```

O workflow `quality.yml` roda esses checks automaticamente em push/PR para manter o projeto funcional.

## Atualização de Dependências

O Dependabot está habilitado em `.github/dependabot.yml` para monitorar dependências `pip` (incluindo `requirements.txt`) e abrir PRs semanais de atualização.

## Estrutura atual

```text
.
|-- core/
|-- docs/
|-- .github/
|-- Dockerfile.linux
|-- Dockerfile.windows
|-- docker-compose.yml
|-- entrypoint.sh
|-- entrypoint.ps1
|-- manage.py
|-- requirements.txt
|-- requirements-dev.txt
|-- pyproject.toml
|-- pytest.ini
|-- tests/
|-- README.en.md
`-- README.md
```

## Idiomas (i18n)

O seletor de idioma usa o endpoint `/i18n/setlang/` e cookie `django_language`.

Sempre que alterar traducoes (`locale/*/LC_MESSAGES/django.po`) ou textos com `{% trans %}`, compile os catalogos:

```bash
python scripts/compile_messages.py
```

Sem esse passo, a mudanca de idioma pode salvar o cookie mas nao refletir no HTML renderizado.

