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
