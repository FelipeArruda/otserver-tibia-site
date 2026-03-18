# 04 - Modulos do Sistema

## Modulos sugeridos
- Accounts
- Servers
- OT Versions
- Monitoring
- OT Catalog
- Characters
- Public Portal
- Themes
- Shop
- Audit

## Accounts (estado atual)
- Autenticacao por e-mail (login, cadastro e recuperacao de senha).
- RBAC inicial com grupos padrao (Owner, Game Master, Support e Viewer).
- Gestao administrativa de usuarios com filtros, criacao, edicao e ativacao/desativacao.
- Gestao de papeis e grupos com controle de permissao por rota/menu.
- Configuracoes gerais da plataforma em `/accounts/settings/`:
  - Nome da plataforma (branding basico)
  - Idioma padrao global
  - Fuso horario padrao
  - Cor primaria
  - URL de logo
- Fallback global de idioma via middleware quando o usuario ainda nao selecionou idioma.

## Criterios de qualidade para modulos de configuracao
- Telas amigaveis, responsivas e visualmente consistentes com o design system atual.
- Validacoes explicitas no backend (formularios, permissoes e persistencia).
- Cobertura de testes para sucesso, negacao por permissao e regressao de fluxo.

## Requisitos de responsividade (obrigatorio)
- Toda listagem com muitas colunas deve ter duas apresentacoes:
- Mobile (`< md`): cards empilhados, com informacoes principais e acoes visiveis sem scroll horizontal.
- Desktop (`>= md`): tabela completa.
- O breakpoint minimo aceito para validacao visual e 390x844 (referencia de iPhone 12).
- Toda entrega de UI que altere listagens deve incluir teste automatizado garantindo a presenca da estrutura mobile e desktop no HTML renderizado.
