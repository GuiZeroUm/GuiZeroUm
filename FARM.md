# 🌾 Contribution Farm

A fazenda do perfil transforma o calendário de contribuições do GitHub em uma plantação pixel art de **53 semanas × 7 dias**.

## Estrutura

```text
assets/
├── farm-base.png           # Arte-base da fazenda (cenário fixo)
├── farm-contributions.svg  # Arte gerada e exibida no README
└── farm-meta.json          # Estatísticas da última geração
scripts/
└── generate_farm.py        # Consulta o GitHub e repinta apenas a plantação
.github/workflows/
└── update-farm.yml         # Atualização diária e execução manual
```

Apenas o retângulo central (o campo de plantação) é redesenhado a cada
execução. Todo o resto do cenário — casa, placa, lago, animais, celeiro —
permanece exatamente como na arte-base.

## Estágios da plantação

| Nível do GitHub | Aparência |
|---|---|
| `NONE` | Terra arada |
| `FIRST_QUARTILE` | Broto |
| `SECOND_QUARTILE` | Plantação jovem |
| `THIRD_QUARTILE` | Trigo verde |
| `FOURTH_QUARTILE` | Trigo dourado |

## Execução local

```bash
python -m pip install pillow
export GITHUB_TOKEN="seu_token"
export GITHUB_USERNAME="GuiZeroUm"
python scripts/generate_farm.py
```

Prévia sem consultar a API:

```bash
python scripts/generate_farm.py --demo
```

## Atualização automática

O workflow executa diariamente às `04:17 UTC`, pode ser iniciado manualmente e também roda quando o gerador, o workflow ou a arte-base são alterados.
