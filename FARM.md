# 🌾 Contribution Farm

A fazenda do perfil transforma o calendário de contribuições do GitHub em uma plantação pixel art de **53 semanas × 7 dias**.

## Estrutura

```text
assets/
├── farm-base.png           # Arte-base da fazenda (campo central vazio)
├── crops/                  # Sprites de crescimento do trigo (1.png … 5.png)
├── farm-contributions.svg  # Arte gerada e exibida no README
└── farm-meta.json          # Estatísticas da última geração
scripts/
└── generate_farm.py        # Consulta o GitHub e preenche o campo com as sprites
.github/workflows/
└── update-farm.yml         # Atualização diária e execução manual
```

Apenas o retângulo central (o campo de plantação) é preenchido a cada
execução: uma grade de **53 × 7** células, onde cada célula recebe uma das
sprites de `crops/` conforme o número de commits do dia. Todo o resto do
cenário — casa, placa, lago, animais, celeiro — permanece como na arte-base.

## Estágios da plantação

| Commits no dia | Sprite | Aparência |
|---|---|---|
| 0 | `1.png` | Terra arada |
| 1 | `2.png` | Broto |
| 2 – 3 | `3.png` | Trigo crescendo |
| 4 – 7 | `4.png` | Trigo maduro |
| 8+ | `5.png` | Trigo dourado |

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
