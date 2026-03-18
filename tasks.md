# Task - Tradução de Vocações por Versão do Tibia

## Objetivo
Traduzir e exibir corretamente as vocações dos personagens no painel (em vez de mostrar apenas o número da vocação), com suporte por versão do Tibia.

## Base de dados (fonte)
Arquivo de referência: `C:\dev\crystalserver\data\XML\vocations.xml`

Cada `<vocation>` no XML possui pelo menos:
- `id`
- `name`
- `description`
- `baseid`
- `fromvoc`
- `clientid`

## Nova tabela proposta
Nome da tabela: `tibia_vacations`

Campos mínimos solicitados:
- `id` (PK interno)
- `tibia_version_id` (FK para `accounts_tibiaversion.code`)
- `vocation_id` (ID da vocação no jogo; ex.: 0, 1, 2...)
- `name` (nome base)
- `description` (descrição base)

Campos adicionais recomendados para tradução:
- `name_pt_br`
- `description_pt_br`

Campos adicionais úteis do XML:
- `base_id` (de `baseid`)
- `from_voc` (de `fromvoc`)
- `client_id` (de `clientid`)

Regras:
- `UNIQUE (tibia_version_id, vocation_id)`
- `ON DELETE PROTECT` para `tibia_version`
- índices em `(tibia_version_id, name)`

## Exemplo de modelo (Django)
```python
class Vocation(models.Model):
    tibia_version = models.ForeignKey(
        TibiaVersion,
        on_delete=models.PROTECT,
        related_name="vocations",
    )
    vocation_id = models.PositiveSmallIntegerField()
    name = models.CharField(max_length=120)
    description = models.CharField(max_length=255, blank=True)
    name_pt_br = models.CharField(max_length=120, blank=True)
    description_pt_br = models.CharField(max_length=255, blank=True)
    base_id = models.PositiveSmallIntegerField(default=0)
    from_voc = models.PositiveSmallIntegerField(default=0)
    client_id = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = "tibia_vacations"
        constraints = [
            models.UniqueConstraint(
                fields=["tibia_version", "vocation_id"],
                name="uniq_vocation_per_tibia_version",
            )
        ]
```

## Seed inicial (extraído do XML anexado)
> Versão alvo inicial sugerida: `15.30` (ajustar se necessário)

| vocation_id | name            | description           | base_id | from_voc | client_id |
|-------------|-----------------|-----------------------|---------|----------|-----------|
| 0           | None            | none                  | 0       | 0        | 0         |
| 1           | Sorcerer        | a sorcerer            | 1       | 1        | 3         |
| 2           | Druid           | a druid               | 2       | 2        | 4         |
| 3           | Paladin         | a paladin             | 3       | 3        | 2         |
| 4           | Knight          | a knight              | 4       | 4        | 1         |
| 5           | Master Sorcerer | a master sorcerer     | 1       | 1        | 13        |
| 6           | Elder Druid     | an elder druid        | 2       | 2        | 14        |
| 7           | Royal Paladin   | a royal paladin       | 3       | 3        | 12        |
| 8           | Elite Knight    | an elite knight       | 4       | 4        | 11        |
| 9           | Monk            | an monk               | 5       | 9        | 5         |
| 10          | Exalted Monk    | an exalted monk       | 5       | 9        | 15        |

## Traduções pt-BR sugeridas
- None -> Sem vocação
- Sorcerer -> Feiticeiro
- Druid -> Druida
- Paladin -> Paladino
- Knight -> Cavaleiro
- Master Sorcerer -> Mestre Feiticeiro
- Elder Druid -> Ancião Druida
- Royal Paladin -> Paladino Real
- Elite Knight -> Cavaleiro de Elite
- Monk -> Monge
- Exalted Monk -> Monge Exaltado

## Plano de implementação
- [ ] Criar migration da nova tabela `tibia_vacations`.
- [ ] Criar serviço de importação do XML por versão do Tibia.
- [ ] Popular dados iniciais para versão `15.30`.
- [ ] Atualizar listagem de personagens para resolver `vocation` numérica para nome traduzido.
- [ ] Garantir fallback: `name_pt_br` -> `name` -> ID numérico.
- [ ] Adicionar testes (model, importador e tela de personagens).

## Critérios de aceite
- [ ] Coluna "Vocation" na listagem de personagens não mostra mais apenas números.
- [ ] Nome da vocação muda conforme idioma selecionado (en/pt-BR).
- [ ] Vocações são carregadas por `tibia_version` do OTServer.
- [ ] Testes automatizados cobrindo mapeamento e fallback.
