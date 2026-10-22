from pathlib import Path
import pandas as pd


DATA = Path("data")

V3_DIR = DATA / "v3_20261016_230146_766337"

V3_FILE = V3_DIR / "backtest_v3.csv"
FVG_FILE = DATA / "orb_fvg_v2.csv"


# =========================================================
# 1. V3 conservador
# =========================================================

v3 = pd.read_csv(V3_FILE)

v3 = v3[
    v3["cenario"].astype(str).str.lower()
    == "conservador"
].copy()

v3 = v3[
    v3["executada"].astype(str).str.lower()
    .isin(["true", "1", "sim"])
].copy()

v3["data"] = pd.to_datetime(
    v3["data"]
).dt.strftime("%Y-%m-%d")

v3["ano"] = pd.to_datetime(
    v3["data"]
).dt.year


# =========================================================
# 2. FVG
# =========================================================

fvg = pd.read_csv(FVG_FILE)

fvg = fvg[
    fvg["motivo"] == "FVG_VALIDO"
].copy()

fvg["data"] = pd.to_datetime(
    fvg["data"]
).dt.strftime("%Y-%m-%d")

fvg = fvg[
    [
        "data",
        "direcao",
        "tamanho_fvg",
    ]
]


# =========================================================
# 3. Juntar
# =========================================================

df = v3.merge(
    fvg,
    on=["data", "direcao"],
    how="left"
)


# =========================================================
# 4. Faixas para teste de sensibilidade
# =========================================================

FAIXAS = [
    (4, 8),
    (5, 9),
    (6, 10),
    (7, 11),
    (8, 12),
    (9, 13),
    (10, 14),
    (11, 15),
    (12, 16),

    # faixas mais largas
    (6, 12),
    (7, 13),
    (8, 14),
    (8, 16),
]


# =========================================================
# 5. Função de resumo
# =========================================================

def resumo(grupo):

    if grupo.empty:
        return None

    r = grupo[
        "resultado_liquido_r"
    ].astype(float)

    ganhos = r[
        r > 0
    ].sum()

    perdas = -r[
        r < 0
    ].sum()

    pf = (
        ganhos / perdas
        if perdas > 0
        else float("inf")
    )

    equity = r.cumsum()

    equity = pd.concat(
        [
            pd.Series([0.0]),
            equity.reset_index(drop=True)
        ],
        ignore_index=True
    )

    pico = equity.cummax()

    dd = (
        equity - pico
    ).min()

    return {
        "operacoes": len(grupo),
        "win_rate_pct":
            r.gt(0).mean() * 100,
        "liquido_r":
            r.sum(),
        "media_r":
            r.mean(),
        "profit_factor":
            pf,
        "max_drawdown_r":
            dd,
    }


# =========================================================
# 6. Rodar
# =========================================================

linhas = []

for minimo, maximo in FAIXAS:

    mascara = (
        (df["tamanho_fvg"] >= minimo)
        & (df["tamanho_fvg"] < maximo)
    )

    amostra = df[
        mascara
    ].copy()

    total = resumo(amostra)

    if total is None:
        continue

    linha = {
        "fvg_min": minimo,
        "fvg_max": maximo,
        "periodo": "TOTAL",
        **total,
    }

    linhas.append(linha)

    for ano in [
        2024,
        2025,
        2026,
    ]:

        parte = amostra[
            amostra["ano"] == ano
        ]

        r = resumo(parte)

        if r is None:
            continue

        linhas.append({
            "fvg_min": minimo,
            "fvg_max": maximo,
            "periodo": str(ano),
            **r,
        })


resultado = pd.DataFrame(
    linhas
)


# =========================================================
# 7. Ranking total
# =========================================================

total = resultado[
    resultado["periodo"] == "TOTAL"
].copy()

total = total.sort_values(
    "liquido_r",
    ascending=False
)


print(
    "\n========== SENSIBILIDADE FVG - TOTAL =========="
)

print(
    total.to_string(
        index=False
    )
)


# =========================================================
# 8. Por ano das melhores faixas
# =========================================================

top = total.head(6)[
    [
        "fvg_min",
        "fvg_max",
    ]
]


print(
    "\n========== TOP FAIXAS POR ANO =========="
)

for _, faixa in top.iterrows():

    minimo = faixa["fvg_min"]
    maximo = faixa["fvg_max"]

    print("\n")
    print(
        f"FVG {minimo:g} até {maximo:g}"
    )

    parte = resultado[
        (resultado["fvg_min"] == minimo)
        & (resultado["fvg_max"] == maximo)
    ]

    print(
        parte.to_string(
            index=False
        )
    )


# =========================================================
# 9. Exportar
# =========================================================

saida = (
    DATA
    / "sensibilidade_fvg_v4.csv"
)

resultado.to_csv(
    saida,
    index=False
)

print("\nCSV criado:")
print(saida)