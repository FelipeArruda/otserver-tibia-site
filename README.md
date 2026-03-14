# OTServ Control Panel

Painel web em **Django + Tailwind CSS** para gerenciamento e operação de servidores **OTServ/Tibia**, com proposta semelhante ao MyAAC em algumas áreas da experiência do usuário, mas com foco em uma arquitetura moderna, modular, extensível e pronta para rodar **localmente** e via **Docker**.

## Objetivo

Construir uma plataforma web que permita:

- autenticação de usuários;
- cadastro e gerenciamento de múltiplos servidores OTServ;
- validação de status do servidor (online/offline);
- exibição de quantidade de players online;
- conexão com banco de dados do servidor OTServ para leitura de personagens, itens, monstros e demais entidades;
- seleção da versão do servidor por **combo box** para adaptar regras, loaders e compatibilidade;
- shopping integrado;
- sistema de **temas** com upload e ativação por administradores;
- suporte a execução em ambiente local e em containers;
- suporte a banco **PostgreSQL** ou **MariaDB**.

## Stack principal

- **Backend:** Django
- **Frontend:** Django Templates + Tailwind CSS
- **Banco da aplicação:** PostgreSQL (padrão) com opção de MariaDB
- **Integração com OTServ:** leitura de banco externo do servidor OTServ
- **Infra container:** Docker + Docker Compose
- **Jobs assíncronos (recomendado):** Celery + Redis

## Estrutura sugerida

```text
otserv-control/
├── README.md
├── docs/
│   ├── 01-product-vision.md
│   ├── 02-architecture.md
│   ├── 03-domain-model.md
│   ├── 04-modules.md
│   ├── 05-database-strategy.md
│   ├── 06-otserv-integration.md
│   ├── 07-theming-system.md
│   ├── 08-local-and-docker-setup.md
│   ├── 09-roadmap-mvp.md
│   └── 10-backlog.md
```

## Resumo do MVP

- login de usuário;
- cadastro de servidor OTServ;
- seleção de versão por combo box;
- verificação de online/offline;
- exibição de players online;
- leitura de personagens, itens e monstros via banco;
- portal estilo MyAAC;
- shopping integrado;
- upload e ativação de temas;
- execução local e via Docker.

## Recomendação de banco

- **Aplicação Django:** PostgreSQL
- **Banco do OTServ conectado:** MariaDB/MySQL conforme o servidor

## Próximos passos

1. Aprovar a arquitetura.
2. Definir versões OTServ suportadas.
3. Mapear schema do banco do servidor.
4. Detalhar models, services, views e rotas.
