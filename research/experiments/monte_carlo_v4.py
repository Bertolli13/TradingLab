from pathlib import Path

import numpy as np
import pandas as pd


DATA = Path("data")

V3_DIR = DATA / "v3_20261016_230146_766337"

V3_FILE = V3_DIR / "backtest_v3.csv"
FVG_FILE = DATA / "orb_fvg_v2.csv"


# =========================================================
# CONFIGURAÇÃO
# =========================================================

N_SIMULACOES = 10000
SEED = 42

rng = np.random.default_rng(SEED)


# =========================================================
# 1. V3 CONSERVADOR
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
)


# =========================================================
# 2. FVG
# =========================================================

fvg = pd.read_csv(FVG_FILE)

fvg = fvg[
    fvg["motivo"] == "FVG_VALIDO"
].copy()

fvg["data"] = pd.to_datetime(
    fvg["data"]
)

fvg = fvg[
    [
        "data",
        "direcao",
        "tamanho_fvg",
    ]
]


# =========================================================
# 3. JUNTAR
# =========================================================

df = v3.merge(
    fvg,
    on=["data", "direcao"],
    how="left"
)


# =========================================================
# 4. FILTRO FVG 6-12
# =========================================================

df = df[
    (df["tamanho_fvg"] >= 6)
    & (df["tamanho_fvg"] < 12)
].copy()

resultados = pd.to_numeric(
    df["resultado_liquido_r"],
    errors="raise"
).to_numpy()


print(
    "\nOperações usadas:",
    len(resultados)
)

print(
    "Resultado histórico:",
    resultados.sum()
)

print(
    "Média por operação:",
    resultados.mean()
)


# =========================================================
# 5. FUNÇÃO DE MAX DRAWDOWN
# =========================================================

def max_drawdown(sequence):

    equity = np.concatenate(
        [
            np.array([0.0]),
            np.cumsum(sequence)
        ]
    )

    peak = np.maximum.accumulate(
        equity
    )

    drawdown = equity - peak

    return drawdown.min()


# =========================================================
# 6. MONTE CARLO
# =========================================================

lucros_finais = []
drawdowns = []

n = len(resultados)

for _ in range(N_SIMULACOES):

    amostra = rng.choice(
        resultados,
        size=n,
        replace=True
    )

    lucro = amostra.sum()

    dd = max_drawdown(
        amostra
    )

    lucros_finais.append(
        lucro
    )

    drawdowns.append(
        dd
    )


lucros_finais = np.array(
    lucros_finais
)

drawdowns = np.array(
    drawdowns
)


# =========================================================
# 7. PERCENTIS
# =========================================================

percentis = [
    1,
    5,
    10,
    25,
    50,
    75,
    90,
    95,
    99,
]


tabela = []

for p in percentis:

    tabela.append({
        "percentil": p,

        "resultado_final_r":
            np.percentile(
                lucros_finais,
                p
            ),

        "max_drawdown_r":
            np.percentile(
                drawdowns,
                100 - p
            ),
    })


tabela = pd.DataFrame(
    tabela
)


# =========================================================
# 8. PROBABILIDADES
# =========================================================

prob_prejuizo = (
    lucros_finais < 0
).mean() * 100

prob_lucro_5r = (
    lucros_finais >= 5
).mean() * 100

prob_lucro_10r = (
    lucros_finais >= 10
).mean() * 100

prob_dd_5r = (
    drawdowns <= -5
).mean() * 100

prob_dd_10r = (
    drawdowns <= -10
).mean() * 100

prob_dd_15r = (
    drawdowns <= -15
).mean() * 100


# =========================================================
# 9. RESULTADOS
# =========================================================

print(
    "\n========== MONTE CARLO =========="
)

print(
    tabela.to_string(
        index=False
    )
)


print(
    "\n========== PROBABILIDADES =========="
)

print(
    f"Probabilidade de resultado final negativo: "
    f"{prob_prejuizo:.2f}%"
)

print(
    f"Probabilidade de terminar >= +5R: "
    f"{prob_lucro_5r:.2f}%"
)

print(
    f"Probabilidade de terminar >= +10R: "
    f"{prob_lucro_10r:.2f}%"
)

print(
    f"Probabilidade de DD <= -5R: "
    f"{prob_dd_5r:.2f}%"
)

print(
    f"Probabilidade de DD <= -10R: "
    f"{prob_dd_10r:.2f}%"
)

print(
    f"Probabilidade de DD <= -15R: "
    f"{prob_dd_15r:.2f}%"
)


# =========================================================
# 10. RESUMO
# =========================================================

resumo = pd.DataFrame(
    [
        {
            "simulacoes":
                N_SIMULACOES,

            "trades_por_simulacao":
                n,

            "resultado_historico_r":
                resultados.sum(),

            "media_resultado_simulado_r":
                lucros_finais.mean(),

            "mediana_resultado_simulado_r":
                np.median(lucros_finais),

            "pior_1pct_resultado_r":
                np.percentile(
                    lucros_finais,
                    1
                ),

            "melhor_99pct_resultado_r":
                np.percentile(
                    lucros_finais,
                    99
                ),

            "mediana_max_drawdown_r":
                np.median(drawdowns),

            "drawdown_95pct_r":
                np.percentile(
                    drawdowns,
                    5
                ),

            "prob_resultado_negativo_pct":
                prob_prejuizo,

            "prob_dd_10r_pct":
                prob_dd_10r,
        }
    ]
)


print(
    "\n========== RESUMO =========="
)

print(
    resumo.to_string(
        index=False
    )
)


# =========================================================
# 11. EXPORTAR
# =========================================================

tabela.to_csv(
    DATA / "monte_carlo_percentis_v4.csv",
    index=False
)

resumo.to_csv(
    DATA / "monte_carlo_resumo_v4.csv",
    index=False
)

pd.DataFrame(
    {
        "resultado_final_r":
            lucros_finais,

        "max_drawdown_r":
            drawdowns,
    }
).to_csv(
    DATA / "monte_carlo_simulacoes_v4.csv",
    index=False
)


print(
    "\nCSVs criados:"
)

print(
    DATA / "monte_carlo_percentis_v4.csv"
)

print(
    DATA / "monte_carlo_resumo_v4.csv"
)

print(
    DATA / "monte_carlo_simulacoes_v4.csv"
)