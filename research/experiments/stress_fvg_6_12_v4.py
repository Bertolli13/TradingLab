from pathlib import Path

import pandas as pd


DATA = Path("data")

V3_DIR = DATA / "v3_20261016_230146_766337"

V3_FILE = V3_DIR / "backtest_v3.csv"
FVG_FILE = DATA / "orb_fvg_v2.csv"


# =========================================================
# 1. Carregar V3 conservador
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

v3["ano"] = v3["data"].dt.year
v3["mes"] = v3["data"].dt.to_period("M").astype(str)


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
# 3. Juntar
# =========================================================

df = v3.merge(
    fvg,
    on=["data", "direcao"],
    how="left"
)


# =========================================================
# 4. Filtro principal
# =========================================================

df = df[
    (df["tamanho_fvg"] >= 6)
    & (df["tamanho_fvg"] < 12)
].copy()

print(
    "\nOperações FVG 6-12:",
    len(df)
)


# =========================================================
# 5. Resultado bruto original
# =========================================================

df["resultado_bruto_r"] = pd.to_numeric(
    df["resultado_bruto_r"]
)

df["risco_usd"] = pd.to_numeric(
    df["risco_usd"]
)


# =========================================================
# 6. Teste de custos
# =========================================================

# custo total por operação em USD
CUSTOS = [
    4.0,   # atual
    5.0,
    6.0,
    8.0,
    10.0,
]

stress = []

for custo_usd in CUSTOS:

    teste = df.copy()

    teste["custo_r_stress"] = (
        custo_usd
        / teste["risco_usd"]
    )

    teste["liquido_r_stress"] = (
        teste["resultado_bruto_r"]
        - teste["custo_r_stress"]
    )

    ganhos = teste.loc[
        teste["liquido_r_stress"] > 0,
        "liquido_r_stress"
    ].sum()

    perdas = -teste.loc[
        teste["liquido_r_stress"] < 0,
        "liquido_r_stress"
    ].sum()

    pf = (
        ganhos / perdas
        if perdas > 0
        else float("inf")
    )

    equity = (
        teste["liquido_r_stress"]
        .cumsum()
    )

    equity_zero = pd.concat(
        [
            pd.Series([0.0]),
            equity.reset_index(drop=True),
        ],
        ignore_index=True
    )

    pico = equity_zero.cummax()

    drawdown = (
        equity_zero - pico
    ).min()

    stress.append({
        "custo_usd": custo_usd,
        "operacoes": len(teste),
        "win_rate_pct":
            teste["liquido_r_stress"]
            .gt(0)
            .mean()
            * 100,
        "liquido_r":
            teste["liquido_r_stress"]
            .sum(),
        "media_r":
            teste["liquido_r_stress"]
            .mean(),
        "profit_factor":
            pf,
        "max_drawdown_r":
            drawdown,
    })


stress = pd.DataFrame(stress)


# =========================================================
# 7. Resultado mensal usando custo atual
# =========================================================

mensal = (
    df.groupby("mes")
    .agg(
        operacoes=(
            "resultado_liquido_r",
            "size"
        ),
        liquido_r=(
            "resultado_liquido_r",
            "sum"
        ),
        media_r=(
            "resultado_liquido_r",
            "mean"
        ),
    )
    .reset_index()
)


mensal["positivo"] = (
    mensal["liquido_r"] > 0
)


# =========================================================
# 8. Resumo mensal
# =========================================================

meses_total = len(mensal)

meses_positivos = int(
    mensal["positivo"].sum()
)

meses_negativos = (
    meses_total - meses_positivos
)


print(
    "\n========== STRESS DE CUSTOS =========="
)

print(
    stress.to_string(
        index=False
    )
)


print(
    "\n========== RESULTADO MENSAL =========="
)

print(
    mensal.to_string(
        index=False
    )
)


print(
    "\n========== RESUMO MENSAL =========="
)

print(
    "Meses com operações:",
    meses_total
)

print(
    "Meses positivos:",
    meses_positivos
)

print(
    "Meses negativos:",
    meses_negativos
)

print(
    "% meses positivos:",
    round(
        meses_positivos
        / meses_total
        * 100,
        2
    )
    if meses_total
    else 0
)


# =========================================================
# 9. Melhores e piores meses
# =========================================================

print(
    "\n5 melhores meses:"
)

print(
    mensal
    .sort_values(
        "liquido_r",
        ascending=False
    )
    .head(5)
    .to_string(index=False)
)


print(
    "\n5 piores meses:"
)

print(
    mensal
    .sort_values(
        "liquido_r"
    )
    .head(5)
    .to_string(index=False)
)


# =========================================================
# 10. Exportar
# =========================================================

stress.to_csv(
    DATA / "stress_custos_fvg_6_12_v4.csv",
    index=False
)

mensal.to_csv(
    DATA / "mensal_fvg_6_12_v4.csv",
    index=False
)

print(
    "\nCSVs criados:"
)

print(
    DATA / "stress_custos_fvg_6_12_v4.csv"
)

print(
    DATA / "mensal_fvg_6_12_v4.csv"
)