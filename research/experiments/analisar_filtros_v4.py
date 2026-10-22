from pathlib import Path
import pandas as pd


DATA = Path("data")

# Execução V3 de 1.25R que você acabou de gerar
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

v3["horario_entrada"] = pd.to_datetime(
    v3["horario_entrada"],
    utc=True,
    errors="coerce"
)

v3["entrada_ny"] = (
    v3["horario_entrada"]
    .dt.tz_convert("America/New_York")
)

v3["ano"] = (
    pd.to_datetime(v3["data"])
    .dt.year
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
# 4. Juntar tudo
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
# 5. Horário da entrada
# =========================================================

minutos = (
    df["entrada_ny"].dt.hour * 60
    + df["entrada_ny"].dt.minute
)

df["faixa_horario"] = pd.cut(
    minutos,
    bins=[
        9 * 60 + 45,
        10 * 60,
        10 * 60 + 30,
        11 * 60,
        16 * 60 + 41,
    ],
    labels=[
        "09:45-10:00",
        "10:00-10:30",
        "10:30-11:00",
        "apos_11:00",
    ],
    include_lowest=True,
    right=False,
)


# =========================================================
# 6. Faixas fixas de FVG
# =========================================================

df["faixa_fvg"] = pd.cut(
    df["tamanho_fvg"],
    bins=[
        0,
        4,
        8,
        12,
        20,
        float("inf"),
    ],
    labels=[
        "2-4",
        "4-8",
        "8-12",
        "12-20",
        "20+",
    ],
    right=False,
)


# =========================================================
# 7. Faixas de ORB
# =========================================================

df["faixa_orb"] = pd.cut(
    df["range_pontos"],
    bins=[
        0,
        50,
        100,
        150,
        200,
        float("inf"),
    ],
    labels=[
        "<50",
        "50-100",
        "100-150",
        "150-200",
        "200+",
    ],
    right=False,
)


# =========================================================
# 8. Faixas de risco
# =========================================================

df["faixa_risco"] = pd.cut(
    df["risco_pontos"],
    bins=[
        0,
        15,
        30,
        50,
        80,
        float("inf"),
    ],
    labels=[
        "<15",
        "15-30",
        "30-50",
        "50-80",
        "80+",
    ],
    right=False,
)


# =========================================================
# Função de resumo
# =========================================================

def resumo_por(coluna):

    linhas = []

    for valor, grupo in df.groupby(
        coluna,
        observed=True
    ):

        ganhos = grupo.loc[
            grupo["resultado_liquido_r"] > 0,
            "resultado_liquido_r"
        ].sum()

        perdas = -grupo.loc[
            grupo["resultado_liquido_r"] < 0,
            "resultado_liquido_r"
        ].sum()

        pf = (
            ganhos / perdas
            if perdas > 0
            else float("inf")
        )

        equity = (
            grupo["resultado_liquido_r"]
            .cumsum()
        )

        pico = equity.cummax()

        dd = (
            equity - pico
        ).min()

        linhas.append({
            coluna: valor,
            "operacoes": len(grupo),
            "win_rate_pct":
                grupo["resultado_liquido_r"]
                .gt(0)
                .mean()
                * 100,
            "liquido_r":
                grupo["resultado_liquido_r"]
                .sum(),
            "media_r":
                grupo["resultado_liquido_r"]
                .mean(),
            "profit_factor":
                pf,
            "max_drawdown_r":
                dd,
        })

    return pd.DataFrame(linhas)


# =========================================================
# Resultados
# =========================================================

analises = {
    "ANO": resumo_por("ano"),
    "DIRECAO": resumo_por("direcao"),
    "HORARIO": resumo_por("faixa_horario"),
    "FVG": resumo_por("faixa_fvg"),
    "ORB": resumo_por("faixa_orb"),
    "RISCO": resumo_por("faixa_risco"),
}


for nome, tabela in analises.items():

    print("\n")
    print("=" * 70)
    print(nome)
    print("=" * 70)

    print(
        tabela.to_string(
            index=False
        )
    )

    tabela.to_csv(
        DATA / f"analise_{nome.lower()}_v4.csv",
        index=False
    )


print(
    "\nAnálises exportadas para a pasta data."
)