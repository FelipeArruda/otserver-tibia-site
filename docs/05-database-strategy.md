# 05 — Estratégia de Banco de Dados

## Banco da aplicação
Preferência: PostgreSQL.

## Banco alternativo
MariaDB.

## Banco do OTServ
Externo à aplicação, podendo ser MariaDB/MySQL ou outro schema compatível.

## Estratégia recomendada
- PostgreSQL para o painel;
- conexão dedicada para leitura do banco OTServ;
- adapters por versão.
