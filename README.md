# OTServ Control Panel

[![Linux Build](https://github.com/FelipeArruda/otserver-tibia-site/actions/workflows/docker-linux.yml/badge.svg)](https://github.com/FelipeArruda/otserver-tibia-site/actions/workflows/docker-linux.yml)
[![Windows Build](https://github.com/FelipeArruda/otserver-tibia-site/actions/workflows/docker-windows.yml/badge.svg)](https://github.com/FelipeArruda/otserver-tibia-site/actions/workflows/docker-windows.yml)
[![Quality Checks](https://github.com/FelipeArruda/otserver-tibia-site/actions/workflows/quality.yml/badge.svg)](https://github.com/FelipeArruda/otserver-tibia-site/actions/workflows/quality.yml)

Idioma: PortuguÃªs (Brasil) | [English](README.en.md)

Painel web em Django para gerenciamento e operaÃ§Ã£o de servidores OTServ/Tibia.

## Objetivo

Construir uma plataforma web para:

- autenticaÃ§Ã£o de usuÃ¡rios;
- cadastro e gerenciamento de multiplos servidores OTServ;
- validaÃ§Ã£o de status do servidor (online/offline);
- exibiÃ§Ã£o de players online;
- leitura de entidades do banco do OTServ;
- seleÃ§Ã£o de versÃ£o do servidor;
- shopping integrado;
- sistema de temas com upload e ativaÃ§Ã£o;
- execuÃ§Ã£o local e em containers.

## Stack principal

- Backend: Django
- Frontend: Django Templates + Tailwind CSS
- Banco da aplicaÃ§Ã£o: PostgreSQL (padrÃ£o), com opÃ§Ã£o de MariaDB
- Infra: Docker + Docker Compose

## Build e Deploy (Docker)

### PrÃ©-requisitos

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

O container roda migraÃ§Ãµes automaticamente no startup (`python manage.py migrate --noinput`) antes de iniciar o servidor.

AplicaÃ§Ã£o local: `http://localhost:8000`

### Build manual por Dockerfile

Linux:

```bash
docker build -f Dockerfile.linux -t otserver-tibia-site:linux .
```

Windows:

```powershell
docker build -f Dockerfile.windows -t otserver-tibia-site:windows .
```

ObservaÃ§Ã£o: os Dockerfiles fazem `python -m pip install --upgrade pip` antes da instalaÃ§Ã£o dos pacotes.

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

Secrets obrigatÃ³rios no repositÃ³rio GitHub:

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

DependÃªncias de dev:

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

## AtualizaÃ§Ã£o de DependÃªncias

O Dependabot estÃ¡ habilitado em `.github/dependabot.yml` para monitorar dependÃªncias `pip` (incluindo `requirements.txt`) e abrir PRs semanais de atualizaÃ§Ã£o.

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

