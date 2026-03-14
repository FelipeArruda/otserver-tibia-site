# OTServ Control Panel

Painel web em Django para gerenciamento e operacao de servidores OTServ/Tibia.

## Objetivo

Construir uma plataforma web para:

- autenticacao de usuarios;
- cadastro e gerenciamento de multiplos servidores OTServ;
- validacao de status do servidor (online/offline);
- exibicao de players online;
- leitura de entidades do banco do OTServ;
- selecao de versao do servidor;
- shopping integrado;
- sistema de temas com upload e ativacao;
- execucao local e em containers.

## Stack principal

- Backend: Django
- Frontend: Django Templates + Tailwind CSS
- Banco da aplicacao: PostgreSQL (padrao), com opcao de MariaDB
- Infra: Docker + Docker Compose

## Build e Deploy (Docker)

### Pre requisitos

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

O container roda migracoes automaticamente no startup (`python manage.py migrate --noinput`) antes de iniciar o servidor.

Aplicacao local: `http://localhost:8000`

### Build manual por Dockerfile

Linux:

```bash
docker build -f Dockerfile.linux -t otserver-tibia-site:linux .
```

Windows:

```powershell
docker build -f Dockerfile.windows -t otserver-tibia-site:windows .
```

## CI/CD (GitHub Actions + Docker Hub)

Workflows:

- `.github/workflows/docker-linux.yml`
- `.github/workflows/docker-windows.yml`

Disparo:

- `push` para branch `main`
- `workflow_dispatch` manual

Secrets obrigatorios no repositorio GitHub:

- `DOCKERHUB_USERNAME`
- `DOCKERHUB_TOKEN`

Tags publicadas:

- Linux: `linux-<sha>` e `latest-linux`
- Windows: `windows-<sha>` e `latest-windows`

## Estrutura atual

```text
.
|-- core/
|-- docs/
|-- .github/workflows/
|-- Dockerfile.linux
|-- Dockerfile.windows
|-- docker-compose.yml
|-- entrypoint.sh
|-- entrypoint.ps1
|-- manage.py
|-- requirements.txt
`-- README.md
```
