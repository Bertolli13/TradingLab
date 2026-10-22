from pathlib import Path

import pandas as pd


DATA = Path("data")

V3_DIR = DATA / "v3_20261016_230146_766337"

V3_FILE = V3_DIR / "backtest_v3.csv"
FVG_FILE = DATA / "orb_fvg_v2.csv"
ORB_FILE = DATA / "orb_rompimentos.csv"


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
# 3. ORB
# =========================================================

orb = pd.read_csv(ORB_FILE)

orb["data"] = pd.to_datetime(
    orb["data"]
).dt.strftime("%Y-%m-%d")

orb = orb[
    [
        "data",
        "range_pontos",
    ]
]


# =========================================================
# 4. Juntar
# =========================================================

df = v3.merge(
    fvg,
    on=["data", "direcao"],
    how="left"
)

df = df.merge(
    orb,
    on="data",
    how="left"
)


# =========================================================
# 5. Definir filtros
# =========================================================

filtros = {
    "BASE": (
        pd.Series(True, index=df.index)
    ),

    "FVG_8_12": (
        (df["tamanho_fvg"] >= 8)
        & (df["tamanho_fvg"] < 12)
    ),

    "RISCO_GE_30": (
        df["risco_pontos"] >= 30
    ),

    "FVG_8_12_RISCO_GE_30": (
        (df["tamanho_fvg"] >= 8)
        & (df["tamanho_fvg"] < 12)
        & (df["risco_pontos"] >= 30)
    ),
}


# =========================================================
# 6. Estatísticas
# =========================================================

def resumo(grupo):

    if grupo.empty:
        return {
            "operacoes": 0,
            "win_rate_pct": None,
            "liquido_r": 0,
            "media_r": None,
            "profit_factor": None,
            "max_drawdown_r": None,
        }

    resultados = grupo[
        "resultado_liquido_r"
    ].astype(float)

    ganhos = resultados[
        resultados > 0
    ].sum()

    perdas = -resultados[
        resultados < 0
    ].sum()

    pf = (
        ganhos / perdas
        if perdas > 0
        else float("inf")
    )

    equity = resultados.cumsum()

    # inclui capital inicial em zero
    equity_com_zero = pd.concat(
        [
            pd.Series([0.0]),
            equity.reset_index(drop=True),
        ],
        ignore_index=True,
    )

    pico = equity_com_zero.cummax()

    drawdown = (
        equity_com_zero - pico
    )

    return {
        "operacoes":
            len(grupo),

        "win_rate_pct":
            resultados.gt(0).mean() * 100,

        "liquido_r":
            resultados.sum(),

        "media_r":
            resultados.mean(),

        "profit_factor":
            pf,

        "max_drawdown_r":
            drawdown.min(),
    }


# =========================================================
# 7. Rodar geral e por ano
# =========================================================

linhas = []

for nome, mascara in filtros.items():

    amostra = df[
        mascara
    ].copy()

    # Geral
    r = resumo(amostra)

    linhas.append({
        "filtro": nome,
        "periodo": "TOTAL",
        **r,
    })

    # Cada ano
    for ano in [2024, 2025, 2026]:

        parte = amostra[
            amostra["ano"] == ano
        ]

        r = resumo(parte)

        linhas.append({
            "filtro": nome,
            "periodo": str(ano),
            **r,
        })


resultado = pd.DataFrame(
    linhas
)


# =========================================================
# 8. Mostrar
# =========================================================

print(
    "\n========== VALIDAÇÃO DOS FILTROS =========="
)

for filtro in filtros:

    print("\n")
    print("=" * 65)
    print(filtro)
    print("=" * 65)

    print(
        resultado[
            resultado["filtro"] == filtro
        ].to_string(
            index=False
        )
    )


# =========================================================
# 9. Exportar
# =========================================================

saida = (
    DATA
    / "validacao_filtros_por_ano_v4.csv"
)

resultado.to_csv(
    saida,
    index=False
)

print("\nCSV criado:")
print(saida)