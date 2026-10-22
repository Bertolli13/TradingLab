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

# Vamos testar mais de um tamanho de bloco
BLOCOS = [2, 3, 5, 8]

rng = np.random.default_rng(SEED)


# =========================================================
# 1. CARREGAR V3 CONSERVADOR
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

v3 = v3.sort_values(
    "data"
).reset_index(drop=True)


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
# 4. FILTRO CONGELADO
#    RR = 1.25 já está dentro dessa execução V3
#    FVG >= 6 e < 12
# =========================================================

df = df[
    (df["tamanho_fvg"] >= 6)
    & (df["tamanho_fvg"] < 12)
].copy()

df = df.sort_values(
    "data"
).reset_index(drop=True)

resultados = pd.to_numeric(
    df["resultado_liquido_r"],
    errors="raise"
).to_numpy()


print("\n========== AMOSTRA ==========")
print("Operações:", len(resultados))
print("Resultado histórico:", resultados.sum())
print("Média por operação:", resultados.mean())


# =========================================================
# 5. DRAWDOWN
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
# 6. BLOCK BOOTSTRAP
# =========================================================

def gerar_block_bootstrap(
    dados,
    tamanho_bloco,
    rng
):

    n = len(dados)

    simulacao = []

    while len(simulacao) < n:

        inicio_maximo = (
            n - tamanho_bloco
        )

        inicio = rng.integers(
            0,
            inicio_maximo + 1
        )

        bloco = dados[
            inicio:
            inicio + tamanho_bloco
        ]

        simulacao.extend(
            bloco.tolist()
        )

    return np.array(
        simulacao[:n]
    )


# =========================================================
# 7. RODAR TODOS OS TAMANHOS DE BLOCO
# =========================================================

resumos = []

todas_simulacoes = []

for tamanho_bloco in BLOCOS:

    finais = []
    drawdowns = []

    for i in range(N_SIMULACOES):

        amostra = gerar_block_bootstrap(
            resultados,
            tamanho_bloco,
            rng
        )

        resultado_final = amostra.sum()

        dd = max_drawdown(
            amostra
        )

        finais.append(
            resultado_final
        )

        drawdowns.append(
            dd
        )

        todas_simulacoes.append({
            "bloco":
                tamanho_bloco,

            "simulacao":
                i + 1,

            "resultado_final_r":
                resultado_final,

            "max_drawdown_r":
                dd,
        })


    finais = np.array(
        finais
    )

    drawdowns = np.array(
        drawdowns
    )


    # =====================================================
    # PROBABILIDADES
    # =====================================================

    prob_negativo = (
        finais < 0
    ).mean() * 100

    prob_5r = (
        finais >= 5
    ).mean() * 100

    prob_10r = (
        finais >= 10
    ).mean() * 100

    prob_dd_5 = (
        drawdowns <= -5
    ).mean() * 100

    prob_dd_10 = (
        drawdowns <= -10
    ).mean() * 100

    prob_dd_15 = (
        drawdowns <= -15
    ).mean() * 100


    resumos.append({
        "bloco":
            tamanho_bloco,

        "simulacoes":
            N_SIMULACOES,

        "trades":
            len(resultados),

        "media_resultado_r":
            finais.mean(),

        "mediana_resultado_r":
            np.median(finais),

        "resultado_p01_r":
            np.percentile(
                finais,
                1
            ),

        "resultado_p05_r":
            np.percentile(
                finais,
                5
            ),

        "resultado_p10_r":
            np.percentile(
                finais,
                10
            ),

        "resultado_p50_r":
            np.percentile(
                finais,
                50
            ),

        "resultado_p90_r":
            np.percentile(
                finais,
                90
            ),

        "resultado_p95_r":
            np.percentile(
                finais,
                95
            ),

        "resultado_p99_r":
            np.percentile(
                finais,
                99
            ),

        "dd_mediano_r":
            np.median(
                drawdowns
            ),

        # 5º percentil dos DDs = cauda ruim aproximada de 95%
        "dd_95pct_r":
            np.percentile(
                drawdowns,
                5
            ),

        "prob_resultado_negativo_pct":
            prob_negativo,

        "prob_resultado_ge_5r_pct":
            prob_5r,

        "prob_resultado_ge_10r_pct":
            prob_10r,

        "prob_dd_le_5r_pct":
            prob_dd_5,

        "prob_dd_le_10r_pct":
            prob_dd_10,

        "prob_dd_le_15r_pct":
            prob_dd_15,
    })


# =========================================================
# 8. RESULTADOS
# =========================================================

resumo = pd.DataFrame(
    resumos
)


print(
    "\n========== BLOCK BOOTSTRAP =========="
)

print(
    resumo.to_string(
        index=False
    )
)


# =========================================================
# 9. INTERPRETAÇÃO RESUMIDA
# =========================================================

print(
    "\n========== RESUMO DE RISCO =========="
)

for _, linha in resumo.iterrows():

    print(
        f"\nBloco {int(linha['bloco'])}:"
    )

    print(
        f"Prob. resultado negativo: "
        f"{linha['prob_resultado_negativo_pct']:.2f}%"
    )

    print(
        f"Resultado P05: "
        f"{linha['resultado_p05_r']:.2f}R"
    )

    print(
        f"DD mediano: "
        f"{linha['dd_mediano_r']:.2f}R"
    )

    print(
        f"DD cauda 95%: "
        f"{linha['dd_95pct_r']:.2f}R"
    )

    print(
        f"Prob. DD <= -10R: "
        f"{linha['prob_dd_le_10r_pct']:.2f}%"
    )


# =========================================================
# 10. EXPORTAR
# =========================================================

resumo.to_csv(
    DATA / "block_bootstrap_resumo_v4.csv",
    index=False
)

pd.DataFrame(
    todas_simulacoes
).to_csv(
    DATA / "block_bootstrap_simulacoes_v4.csv",
    index=False
)


print(
    "\nCSVs criados:"
)

print(
    DATA / "block_bootstrap_resumo_v4.csv"
)

print(
    DATA / "block_bootstrap_simulacoes_v4.csv"
)