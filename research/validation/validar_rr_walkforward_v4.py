from pathlib import Path
import pandas as pd


DATA = Path("data")

ARQUIVO_V3 = sorted(
    DATA.glob("v3_*/backtest_v3.csv"),
    reverse=True
)[0]

ARQUIVO_CANDLES = DATA / "nq_unificado_validacao.parquet"

RR_LISTA = [0.75, 1.00, 1.25]

CUSTO_USD = 4.0
VALOR_PONTO = 2.0


# =========================================================
# Dados V3
# =========================================================

v3 = pd.read_csv(ARQUIVO_V3)

v3 = v3[
    v3["cenario"].astype(str).str.lower()
    == "conservador"
].copy()

v3 = v3[
    v3["executada"].astype(str).str.lower()
    .isin(["true", "1", "sim"])
].copy()

v3["horario_entrada"] = pd.to_datetime(
    v3["horario_entrada"],
    utc=True,
    errors="coerce"
)

v3["ano"] = pd.to_datetime(
    v3["data"]
).dt.year


# =========================================================
# Candles
# =========================================================

candles = pd.read_parquet(
    ARQUIVO_CANDLES
)

candles["datetime"] = pd.to_datetime(
    candles["datetime"],
    utc=True
)

candles = (
    candles
    .sort_values("datetime")
    .set_index("datetime")
)


# =========================================================
# Simulação
# =========================================================

def simular(row, rr):

    entrada = float(row["entrada"])
    stop = float(row["stop"])
    direcao = row["direcao"]

    risco = abs(entrada - stop)

    if risco <= 0:
        return None

    if direcao == "COMPRA":
        alvo = entrada + risco * rr
    else:
        alvo = entrada - risco * rr

    inicio = row["horario_entrada"]

    if pd.isna(inicio):
        return None

    inicio_ny = inicio.tz_convert(
        "America/New_York"
    )

    data_ny = inicio_ny.date()

    fim_ny = pd.Timestamp(
        f"{data_ny} 16:40:00",
        tz="America/New_York"
    )

    fim = fim_ny.tz_convert("UTC")

    janela = candles.loc[
        (candles.index >= inicio)
        & (candles.index <= fim)
    ]

    if janela.empty:
        return None

    for ts, candle in janela.iterrows():

        high = float(candle["high"])
        low = float(candle["low"])

        if direcao == "COMPRA":

            stop_hit = low <= stop
            alvo_hit = high >= alvo

        else:

            stop_hit = high >= stop
            alvo_hit = low <= alvo

        # Hipótese conservadora
        if stop_hit and alvo_hit:
            bruto_r = -1.0
            motivo = "STOP_AMBIGUO"
            break

        if stop_hit:
            bruto_r = -1.0
            motivo = "STOP"
            break

        if alvo_hit:
            bruto_r = rr
            motivo = "ALVO"
            break

    else:

        fechamento = float(
            janela.iloc[-1]["close"]
        )

        if direcao == "COMPRA":
            bruto_r = (
                fechamento - entrada
            ) / risco
        else:
            bruto_r = (
                entrada - fechamento
            ) / risco

        motivo = "FECHAMENTO"

    risco_usd = (
        risco * VALOR_PONTO
    )

    custo_r = (
        CUSTO_USD / risco_usd
    )

    liquido_r = (
        bruto_r - custo_r
    )

    return {
        "bruto_r": bruto_r,
        "liquido_r": liquido_r,
        "motivo": motivo,
    }


# =========================================================
# Rodar todos os RR
# =========================================================

trades = []

for rr in RR_LISTA:

    for _, row in v3.iterrows():

        res = simular(
            row,
            rr
        )

        if res is None:
            continue

        trades.append({
            "data": row["data"],
            "ano": row["ano"],
            "rr": rr,
            "bruto_r": res["bruto_r"],
            "liquido_r": res["liquido_r"],
            "motivo": res["motivo"],
        })


trades = pd.DataFrame(
    trades
)


# =========================================================
# Estatísticas
# =========================================================

def calcular_resumo(df, periodo):

    resultados = []

    for rr, grupo in df.groupby("rr"):

        grupo = grupo.copy()

        grupo["equity"] = (
            grupo["liquido_r"].cumsum()
        )

        grupo["pico"] = (
            grupo["equity"].cummax()
        )

        grupo["drawdown"] = (
            grupo["equity"]
            - grupo["pico"]
        )

        ganhos = grupo.loc[
            grupo["liquido_r"] > 0,
            "liquido_r"
        ].sum()

        perdas = -grupo.loc[
            grupo["liquido_r"] < 0,
            "liquido_r"
        ].sum()

        pf = (
            ganhos / perdas
            if perdas > 0
            else float("inf")
        )

        resultados.append({
            "periodo": periodo,
            "rr": rr,
            "operacoes": len(grupo),
            "win_rate_pct":
                grupo["liquido_r"]
                .gt(0)
                .mean()
                * 100,
            "bruto_r":
                grupo["bruto_r"].sum(),
            "liquido_r":
                grupo["liquido_r"].sum(),
            "media_r":
                grupo["liquido_r"].mean(),
            "profit_factor":
                pf,
            "max_drawdown_r":
                grupo["drawdown"].min(),
        })

    return resultados


resumos = []


# Por ano
for ano in sorted(
    trades["ano"].unique()
):

    parte = trades[
        trades["ano"] == ano
    ]

    resumos.extend(
        calcular_resumo(
            parte,
            str(ano)
        )
    )


# Desenvolvimento
dev = trades[
    trades["ano"].isin([
        2024,
        2025
    ])
]

resumos.extend(
    calcular_resumo(
        dev,
        "DEV_2024_2025"
    )
)


# Fora da amostra
teste = trades[
    trades["ano"] == 2026
]

resumos.extend(
    calcular_resumo(
        teste,
        "OOS_2026"
    )
)


resumo = pd.DataFrame(
    resumos
)


# =========================================================
# Mostrar
# =========================================================

print(
    "\n========== RESULTADO POR ANO =========="
)

print(
    resumo[
        resumo["periodo"].isin(
            ["2024", "2025", "2026"]
        )
    ].to_string(
        index=False
    )
)


print(
    "\n========== WALK-FORWARD SIMPLES =========="
)

print(
    resumo[
        resumo["periodo"].isin([
            "DEV_2024_2025",
            "OOS_2026",
        ])
    ].to_string(
        index=False
    )
)


# =========================================================
# Exportar
# =========================================================

trades.to_csv(
    DATA / "trades_rr_walkforward_v4.csv",
    index=False
)

resumo.to_csv(
    DATA / "resumo_rr_walkforward_v4.csv",
    index=False
)

print("\nCSVs criados:")
print(DATA / "trades_rr_walkforward_v4.csv")
print(DATA / "resumo_rr_walkforward_v4.csv")