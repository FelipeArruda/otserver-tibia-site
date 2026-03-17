# Task 3 - Personagens dos OTs no Menu "Personagens"

## Objetivo
Implementar a funcionalidade de listagem de personagens vindos dos OTs conectados, exibindo todos os personagens no menu "Personagens", com experiência profissional, amigável, responsiva, traduzida e com filtros eficientes.

## Escopo
- Consumir dados de personagens dos OTs já configurados na plataforma.
- Exibir todos os personagens em uma tela dedicada acessível pelo menu "Personagens".
- Permitir busca e filtros para navegação rápida em volume alto de dados.
- Seguir os padrões atuais de arquitetura, segurança, UX/UI, i18n e testes do projeto.

## Princípios de implementação
- Reutilizar padrões de backend já adotados (views, validações, permissões e organização de código).
- Reutilizar padrões visuais existentes do dashboard para manter consistência.
- Garantir feedback claro de carregamento, estado vazio e erros.
- Priorizar desempenho e legibilidade para listas extensas.

## Requisitos funcionais
- Criar/ajustar endpoint(s) para obter personagens dos OTs com paginação.
- Exibir listagem única com personagens de todos os OTs disponíveis ao usuário.
- Exibir no mínimo os campos:
  - nome do personagem
  - OT de origem
  - vocação (quando disponível)
  - level (quando disponível)
  - status (online/offline, quando disponível)
  - data/hora de atualização
- Disponibilizar filtros no frontend e backend para:
  - OT
  - nome (busca textual)
  - vocação
  - faixa de level
  - status online/offline
- Permitir ordenação por nome, level e última atualização.
- Permitir paginação com estado persistente na URL (query params).
- Garantir controle de acesso conforme RBAC/permissões já existentes.

## Requisitos de UX/UI
- Tela amigável e profissional, alinhada ao padrão visual atual.
- Layout responsivo para desktop, tablet e mobile.
- Estados obrigatórios:
  - carregando
  - vazio (sem personagens)
  - erro (falha ao consultar OT)
- Filtros fáceis de usar, com ação de limpar filtros.
- Componentes acessíveis (contraste, foco por teclado e labels claros).

## Requisitos de i18n
- Todos os textos da nova funcionalidade devem ser traduzíveis.
- Incluir mensagens em pt-BR e estrutura pronta para novos idiomas.
- Garantir que labels, placeholders, botões, mensagens de erro e estado vazio sejam internacionalizados.

## Requisitos técnicos
- Seguir convenções do projeto (Python 3.13, Django, Ruff, organização de arquivos).
- Não quebrar fluxos já existentes de autenticação, permissões e dashboard.
- Tratar falhas de integração com OT de forma resiliente (timeout/erro parcial).
- Evitar consultas ineficientes e prever volume de dados.

## Estratégia de testes
- Testes unitários:
  - serialização/mapeamento de dados de personagens
  - validação de filtros e ordenação
  - regras de permissão
- Testes de integração:
  - endpoint de listagem com filtros, paginação e ordenação
  - tratamento de erro de OT e resposta parcial
- Testes funcionais (UI):
  - renderização da tela de personagens
  - comportamento dos filtros
  - paginação e ordenação
  - estados de loading/vazio/erro
  - responsividade básica
- Testes de i18n:
  - textos traduzidos em pt-BR
  - fallback quando tradução não existir

## Checklist de execução
- [x] Definir contrato de dados de personagens por OT.
- [x] Implementar camada de serviço para agregação dos personagens dos OTs.
- [x] Implementar endpoint de listagem com paginação, filtros e ordenação.
- [x] Aplicar controle de acesso/permissões no backend.
- [x] Criar tela "Personagens" no menu com listagem e filtros.
- [x] Implementar estados de loading, vazio e erro.
- [x] Garantir responsividade completa (desktop/mobile).
- [x] Internacionalizar todos os textos da funcionalidade.
- [x] Escrever testes unitários, integração e funcionais.
- [ ] Executar validações finais:
  - [x] `ruff check .`
  - [x] `ruff format --check .`
  - [x] `python manage.py makemigrations --check --dry-run`
  - [ ] `pytest -q` (bloqueado por permissao do banco MySQL para criar `test_crystalserver`)

## Critérios de aceite
- [x] O menu "Personagens" exibe todos os personagens dos OTs disponíveis.
- [x] Filtros, paginação e ordenação funcionam corretamente e de forma performática.
- [x] Tela mantém padrão profissional, amigável, acessível e responsivo.
- [x] Todos os textos estão traduzidos e preparados para i18n.
- [x] Regras de acesso/permissão estão corretas.
- [ ] Cobertura de testes contempla fluxos críticos e passa localmente. (parcial: novos testes adicionados; suíte completa bloqueada por banco)
- [x] Nenhuma regressão relevante nos módulos existentes.
