# 07 - Sistema de Temas

## Objetivo
Documentar como criar, publicar e selecionar temas visuais para a home publica (`/`) do sistema.

## Estado atual da feature
O sistema hoje suporta dois tipos de tema para a home publica:
- Tema nativo padrao: `tibia-latest-news`
- Tema customizado via upload de arquivo HTML em `/accounts/settings/`

Campos relacionados no menu **Accounts > Settings**:
- `Home page template` (seletor)
- `Upload HTML template` (upload de `.html`/`.htm`)

## Como funciona tecnicamente
- O campo `PlatformSetting.home_page_template` guarda a chave do tema ativo.
- Temas enviados pelo usuario sao salvos em `HomePageTemplate`.
- A rota `/` usa `PublicNewsHomeView`:
  - Se a chave for `tibia-latest-news`, renderiza o template interno:
    - `templates/accounts/public/home_tibia_latest_news.html`
  - Se for um tema enviado por upload, renderiza o HTML salvo.
  - Em caso de erro/falha, aplica fallback para o tema interno.

## Regras de upload (tema customizado)
- Extensoes aceitas: `.html`, `.htm`
- Tamanho maximo: `1MB`
- O upload cria automaticamente:
  - Nome amigavel do tema
  - Chave unica (`slug`) para selecao

## Estrutura recomendada para criar tema
O arquivo HTML customizado deve ser autocontido e robusto:
1. Definir `<!doctype html>`, `<head>`, `<body>`.
2. Usar layout responsivo (desktop + mobile).
3. Evitar dependencias externas instaveis.
4. Evitar scripts inline desnecessarios.
5. Tratar ausencia de dados dinamicos com fallback visual.

Contexto disponivel no template renderizado:
- `platform_settings`
- `request`

Exemplo minimo:

```html
<!doctype html>
<html lang="pt-BR">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width,initial-scale=1" />
    <title>{{ platform_settings.platform_name|default:"OTServ" }}</title>
    <style>
      body { margin: 0; font-family: Verdana, Arial, sans-serif; background: #0b1d2f; color: #f2e5c4; }
      .wrap { max-width: 1100px; margin: 0 auto; padding: 24px; }
    </style>
  </head>
  <body>
    <main class="wrap">
      <h1>{{ platform_settings.platform_name }}</h1>
      <p>Home customizada ativa com sucesso.</p>
    </main>
  </body>
</html>
```

## Tema Tibia nativo (base oficial no projeto)
Arquivos principais:
- Template: `templates/accounts/public/home_tibia_latest_news.html`
- CSS base: `accounts/static/tibia_theme/basic.css`
- Assets: `accounts/static/tibia_theme/images/...`

Padrao de nomes:
- Use namespace neutro e de produto (ex.: `tibia_theme`).
- Nao usar namespaces temporarios/de fornecedor em producao (ex.: `myaac_canary`).

## Fluxo para criar um novo tema interno (versionado no repo)
Use este fluxo quando o tema deve fazer parte do codigo-fonte:
1. Criar novo template em `templates/accounts/public/`.
2. Criar pasta de assets em `accounts/static/<nome_do_tema>/`.
3. Referenciar assets via `{% load static %}` e `{% static '...' %}`.
4. Garantir fallback seguro para links/imagens quebradas.
5. Adicionar/ajustar testes para `/` e selecao do tema.

## Fluxo para criar um tema por upload (sem deploy)
Use este fluxo para iteracao rapida:
1. Construir arquivo `.html` final.
2. Acessar `/accounts/settings/`.
3. Fazer upload em `Upload HTML template`.
4. Confirmar que o seletor `Home page template` foi atualizado.
5. Abrir `/` e validar resultado visual.

## Validacao recomendada
Checklist minimo apos qualquer alteracao de tema:
1. `python manage.py check`
2. `pytest -q tests/test_public_home_templates.py`
3. Validacao visual em `http://127.0.0.1:8000/`
4. Verificar carregamento de CSS/imagens sem 404

## Boas praticas de design para contexto Tibia
- Priorizar legibilidade de textos em fundos detalhados.
- Manter hierarquia visual clara (menu esquerdo, conteudo central, boxes laterais).
- Preservar identidade visual classica (ornamentos, molduras, contraste alto).
- Evitar simplificacao excessiva que descaracterize o tema.

## Troubleshooting
### Tema enviado nao aparece no seletor
- Verifique extensao e tamanho do arquivo.
- Confirme permissao `accounts.change_platformsetting`.

### Home abriu sem estilo
- Verifique carregamento dos assets estaticos.
- Em dev, confirme configuracao de static/media em `core/urls.py`.

### Tema customizado quebra renderizacao
- Corrija o HTML enviado.
- Enquanto houver erro, o sistema cai para o tema interno automaticamente.
