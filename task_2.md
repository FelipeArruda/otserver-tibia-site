# Task 2 - Cadastro e Gestao de OTServers

## Checklist de etapas
- [x] Etapa 1: Base do modulo OTServer (modelo, CRUD, listagem, RBAC, auditoria basica, paginação e filtros).
- [x] Etapa 2: Teste de conexao com banco (MySQL/MariaDB) e validacao de API.
- [ ] Etapa 3: Seguranca avancada de credenciais (protecao/criptografia) e mascaramento completo.
- [ ] Etapa 4: UX refinada, mensagens finais, cobertura de testes ampliada e documentacao final.

## Objetivo
Implementar um modulo completo para cadastro, visualizacao, edicao e remocao de OTServers, com foco em conectividade com banco de dados do servidor de jogo e validacoes operacionais.

## Escopo funcional

### 1. CRUD de OTServer
- Criar OTServer com formulario completo.
- Listar OTServers com busca, filtros e paginacao.
- Visualizar detalhes do OTServer (somente leitura).
- Editar configuracoes do OTServer.
- Remover OTServer com confirmacao explicita.
- Ativar/desativar OTServer sem remover.

### 2. Dados obrigatorios
- Nome do OTServer.
- Ambiente: production, staging, development.
- Tipo de banco: MySQL ou MariaDB.
- Host do banco.
- Porta do banco (default 3306).
- Nome do banco.
- Usuario do banco.
- Senha do banco.
- Charset e collation.
- SSL do banco.
- URL base da API (opcional).
- Token/API key (opcional e sensivel).
- Timezone do OTServer.
- Status de monitoramento.

### 3. Teste de conexao (Etapa 2)
- Botao de teste no cadastro e edicao.
- Teste de conexao MySQL/MariaDB.
- Resultado detalhado (sucesso/falha, latencia, erro amigavel).
- Teste de API quando endpoint for informado.
- Historico do ultimo teste por OTServer.

### 4. Seguranca
- Senhas e tokens nunca exibidos em texto puro.
- Mascaramento de campos sensiveis.
- Segredos fora de logs.
- Permissoes por perfil/grupo para ver/criar/editar/remover/testar.

### 5. Auditoria
- Registrar create/update/delete/toggle/test-connection.
- Salvar ator, acao, alvo, data/hora e resumo sem segredos.

### 6. UI/UX
- Seguir layout e cores atuais do sistema.
- Tela amigavel e responsiva.
- Mensagens claras e traduzidas (PT-BR/EN).
- Paginacao de 10 itens e filtros persistentes.

## Requisitos tecnicos
- Suporte inicial a MySQL e MariaDB.
- DSN seguro e tratamento de timeout/erro.
- Validacoes de formulario no backend e frontend.
- Cobertura de testes para CRUD, RBAC, filtros e paginacao.

## Criterios de aceite
- CRUD funcional com RBAC.
- Listagem com filtros e paginacao funcionando.
- Auditoria basica ativa sem vazar segredos.
- Traducao base PT-BR/EN aplicada.
- Testes e quality passando.
