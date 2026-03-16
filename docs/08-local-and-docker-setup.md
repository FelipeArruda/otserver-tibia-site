# 08 - Execução Local e Docker

## Execução local
- Python 3.13
- PostgreSQL ou MariaDB
- Redis opcional

### Passos rápidos
1. Instale dependências:
   - `pip install -r requirements.txt -r requirements-dev.txt`
2. Rode migrações:
   - `python manage.py migrate`
3. Compile mensagens de tradução:
   - `python scripts/compile_messages.py`
4. Suba o servidor:
   - `python manage.py runserver`

## Internacionalização (i18n)
A troca de idioma via seletor (`/i18n/setlang/`) depende de arquivos compilados `.mo`.

- Fonte de tradução: `locale/<idioma>/LC_MESSAGES/django.po`
- Arquivo usado em runtime: `locale/<idioma>/LC_MESSAGES/django.mo`

Sempre que alterar textos com `{% trans %}` ou editar `django.po`, rode:
- `python scripts/compile_messages.py`

### Padrão pt-BR para traduções
- Arquivos de tradução devem ser gravados em UTF-8.
- Traduções em português do Brasil devem manter acentuação correta (ex.: `instruções`, `redefinição`, `você`, `página`).
- Evite remover acentos por compatibilidade; o projeto usa UTF-8 ponta a ponta.

Sem esse passo, o cookie de idioma será salvo, mas a interface continuará no idioma anterior.

## Execução Docker
Serviços sugeridos:
- web
- db
- redis
