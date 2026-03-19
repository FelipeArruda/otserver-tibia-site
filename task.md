# Task: Enriquecer Tela de Personagens com Dados da Conta (`account`)

## Contexto
A listagem de personagens já traz dados básicos (nome, OTServer, vocação, level, status e atualização), mas ainda não expõe informações da conta associada do jogo (tabela `account` no banco do OTServer).

## Objetivo
Exibir na tela de personagens os dados da conta vinculada a cada personagem, com suporte a:

- tradução (PT-BR/EN);
- responsividade (desktop e mobile);
- filtros/pesquisa;
- testes automatizados de regressão.

## Escopo Funcional
1. Mapear relacionamento entre `players` e `account` no banco do OTServer.
2. Ajustar consulta de personagens para fazer `JOIN` com `account`.
3. Trazer e normalizar campos da conta na estrutura retornada para a UI.
4. Exibir novos campos na tela de personagens.
5. Incluir filtros por dados de conta (MVP: ID e e-mail da conta).
6. Garantir textos traduzidos e acentuados em PT-BR.

## Campos de Conta (MVP)
- `account_id`
- `account_name` (quando disponível no schema)
- `account_email` (quando disponível no schema)
- `account_type` (quando disponível no schema)
- `account_created_at` (quando disponível no schema)
- `account_last_login` (quando disponível no schema)

## Regras Técnicas
1. Não quebrar compatibilidade com schemas diferentes.
2. Detectar colunas dinamicamente e aplicar fallback para `NULL`.
3. Preservar fallback atual em caso de erro por fonte.
4. Não expor dados sensíveis.

## Testes Obrigatórios
1. Serviço: cobertura da detecção de `JOIN` com `account` e filtros por conta.
2. View/template: renderização dos novos campos na listagem.
3. Tradução PT-BR: labels com acentuação correta.
4. Regressão: manter filtros e paginação existentes.

## Critérios de Aceite
1. Tela de personagens mostra dados de conta por personagem.
2. Funciona para múltiplos OTServers ativos.
3. Não quebra quando colunas de conta não existem.
4. Labels e textos em PT-BR/EN corretos.
5. Testes atualizados e passando.
