# Task - Gestão de Versões do Tibia

## Objetivo
Criar um modulo completo para manutencao de versoes do Tibia no painel administrativo, com fluxo de listagem, criacao, edicao e remocao segura.

## Escopo funcional
- Criar menu dedicado para "Versões do Tibia" dentro de "Gestão de OTServers" (submenu).
- Criar tela de listagem com filtros.
- Criar tela de formulario (criar/editar).
- Criar acao de remocao com validacoes de integridade.
- Exibir versão padrão e status de suporte de forma clara.

## Requisitos de desenvolvimento (obrigatorios)

### Traducao (i18n)
- Todas as labels, botoes, mensagens de sucesso/erro e textos de apoio devem ter suporte EN e PT-BR.
- Não deixar texto hardcoded em apenas um idioma nas telas novas.
- Mensagens de validacao de formulario devem ser traduziveis.

### Responsividade
- Layout mobile-first.
- Listagens devem ter:
- Mobile (`< md`): cards legiveis com dados principais e acoes.
- Desktop (`>= md`): tabela completa.
- Validar visualmente no breakpoint 390x844 (referencia iPhone 12).

### UX amigavel e profissional
- Filtros claros com "Aplicar" e "Limpar".
- Estados de vazio com orientacao objetiva.
- Confirmacao para acao destrutiva (remover).
- Feedback de sucesso/erro via mensagens padronizadas.
- Consistencia visual com design system atual do projeto.

### Qualidade e testes
- Adicionar testes de permissao por rota (403 sem permissao).
- Adicionar testes de fluxo CRUD (criar, editar, remover).
- Adicionar testes de traducao para EN e PT-BR.
- Adicionar testes de responsividade estrutural (presenca de blocos mobile/desktop no HTML).
- Garantir `ruff check .`, `ruff format --check .` e `pytest -q` verdes.

## Regras de negocio sugeridas
- Campo principal da versão: `code` (ex.: `15.30`).
- Permitir marcar `is_supported` (ativa/inativa para uso).
- Permitir `sort_order` para ordenar exibicao.
- Impedir exclusão de versão em uso por OTServer ou por registros relacionados (tratamento amigável).
- Permitir definir qual versão é padrão (se aplicável ao fluxo atual).

## Telas previstas

### 1) Listagem de versoes
- Colunas (desktop): versão, ordem, suportada, quantidade de OTServers vinculados, ações.
- Mobile: card por versão com status e ações.
- Filtros: busca por codigo, status de suporte.

### 2) Formulário de versão
- Campos: `code`, `sort_order`, `is_supported`.
- Validacoes:
- `code` obrigatorio e formato valido.
- `sort_order` inteiro nao negativo.
- Unicidade de `code`.

## Permissoes
- `view_tibiaversion` para visualizar listagem.
- `add_tibiaversion` para criar.
- `change_tibiaversion` para editar.
- `delete_tibiaversion` para remover.
- Exibir/ocultar acoes no frontend conforme permissao.

## Navegacao e menu (obrigatorio)
- Inserir item "Versões do Tibia" como filho do menu pai "Gestão de OTServers".
- Ao acessar telas de versoes, manter:
- Menu pai "Gestao de OTServers" expandido.
- Item filho "Versões do Tibia" destacado como ativo.
- Garantir traducao do label do menu (EN/PT-BR) e consistencia visual com os demais itens do grupo.

## Rotas (proposta)
- `accounts:tibia_versions` (GET listagem)
- `accounts:tibia_version_create` (GET/POST criar)
- `accounts:tibia_version_update` (GET/POST editar)
- `accounts:tibia_version_delete` (POST remover)

## Auditoria
- Registrar eventos no `AuditLog`:
- `tibia_version.create`
- `tibia_version.update`
- `tibia_version.delete`
- Incluir alvo e detalhes relevantes.

## Criterios de aceite
- Menu de versoes visivel para usuarios com permissao.
- CRUD funcional com mensagens traduzidas.
- Telas legiveis em mobile e desktop.
- Nenhuma quebra de layout no iPhone 12 (390x844).
- Testes automatizados cobrindo permissao, fluxo, traducao e responsividade.
- Pipeline local passa com lint, format e testes.
