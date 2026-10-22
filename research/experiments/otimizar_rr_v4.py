from pathlib import Path
import pandas as pd


DATA = Path("data")

ARQUIVO_V3 = sorted(
    DATA.glob("v3_*/backtest_v3.csv"),
    reverse=True
)[0]

ARQUIVO_CANDLES = (
    DATA / "nq_unificado_validacao.parquet"
)


# ---------------------------------------------------------
# Configurações
# ---------------------------------------------------------

RR_LISTA = [
    0.75,
    1.00,
    1.25,
    1.50,
    2.00,
]

TICK = 0.25

# Custo padrão usado anteriormente na V3
CUSTO_USD = 4.0

# MNQ = US$ 2 por ponto
VALOR_PONTO = 2.0


# ---------------------------------------------------------
# Carregar V3
# ---------------------------------------------------------

v3 = pd.read_csv(ARQUIVO_V3)

v3 = v3[
    v3["cenario"].astype(str).str.lower()
    == "conservador"
].copy()

v3 = v3[
    v3["executada"].astype(str).str.lower()
    .isin(["true", "1", "sim"])
].copy()


for col in [
    "horario_entrada",
]:
    v3[col] = pd.to_datetime(
        v3[col],
        utc=True,
        errors="coerce"
    )


# ---------------------------------------------------------
# Candles
# ---------------------------------------------------------

df = pd.read_parquet(
    ARQUIVO_CANDLES
)

df["datetime"] = pd.to_datetime(
    df["datetime"],
    utc=True
)

df = (
    df.sort_values("datetime")
    .set_index("datetime")
)


# ---------------------------------------------------------
# Simulador conservador simplificado
# ---------------------------------------------------------

def simular_trade(row, rr):

    direcao = row["direcao"]

    entrada = float(row["entrada"])
    stop = float(row["stop"])

    risco = abs(
        entrada - stop
    )

    if risco <= 0:
        return None

    if direcao == "COMPRA":

        alvo = (
            entrada
            + risco * rr
        )

    else:

        alvo = (
            entrada
            - risco * rr
        )


    inicio = row["horario_entrada"]

    if pd.isna(inicio):
        return None


    # Sessão termina 16:40 NY
    inicio_ny = inicio.tz_convert(
        "America/New_York"
    )

    data_ny = inicio_ny.date()

    fim_ny = pd.Timestamp(
        f"{data_ny} 16:40:00",
        tz="America/New_York"
    )

    fim = fim_ny.tz_convert("UTC")


    janela = df.loc[
        (df.index >= inicio)
        & (df.index <= fim)
    ]

    if janela.empty:
        return None


    primeiro = True

    for ts, candle in janela.iterrows():

        high = float(
            candle["high"]
        )

        low = float(
            candle["low"]
        )


        if direcao == "COMPRA":

            bateu_stop = (
                low <= stop
            )

            bateu_alvo = (
                high >= alvo
            )


        else:

            bateu_stop = (
                high >= stop
            )

            bateu_alvo = (
                low <= alvo
            )


        # ---------------------------------------------
        # Conservador:
        # se stop e alvo ocorrem no mesmo candle,
        # conta STOP.
        # ---------------------------------------------

        if bateu_stop and bateu_alvo:

            resultado_bruto_r = -1.0
            motivo = "STOP_AMBIGUO"

            return {
                "resultado_bruto_r":
                    resultado_bruto_r,

                "motivo":
                    motivo,

                "saida":
                    ts,
            }


        if bateu_stop:

            resultado_bruto_r = -1.0

            return {
                "resultado_bruto_r":
                    resultado_bruto_r,

                "motivo":
                    "STOP",

                "saida":
                    ts,
            }


        if bateu_alvo:

            resultado_bruto_r = rr

            return {
                "resultado_bruto_r":
                    resultado_bruto_r,

                "motivo":
                    "ALVO",

                "saida":
                    ts,
            }


        primeiro = False


    # Se não bateu stop nem alvo até 16:40
    ultimo = janela.iloc[-1]

    fechamento = float(
        ultimo["close"]
    )


    if direcao == "COMPRA":

        resultado_bruto_r = (
            fechamento - entrada
        ) / risco

    else:

        resultado_bruto_r = (
            entrada - fechamento
        ) / risco


    return {
        "resultado_bruto_r":
            resultado_bruto_r,

        "motivo":
            "FECHAMENTO",

        "saida":
            janela.index[-1],
    }


# ---------------------------------------------------------
# Rodar otimização
# ---------------------------------------------------------

resumos = []

for rr in RR_LISTA:

    trades = []

    for _, row in v3.iterrows():

        res = simular_trade(
            row,
            rr
        )

        if res is None:
            continue


        risco_pontos = abs(
            float(row["entrada"])
            - float(row["stop"])
        )

        risco_usd = (
            risco_pontos
            * VALOR_PONTO
        )

        custo_r = (
            CUSTO_USD
            / risco_usd
        )

        resultado_liquido_r = (
            res["resultado_bruto_r"]
            - custo_r
        )


        trades.append({
            "data":
                row["data"],

            "rr":
                rr,

            "resultado_bruto_r":
                res[
                    "resultado_bruto_r"
                ],

            "resultado_liquido_r":
                resultado_liquido_r,

            "motivo":
                res["motivo"],

            "saida":
                res["saida"],
        })


    trades = pd.DataFrame(
        trades
    )


    if trades.empty:
        continue


    ganhos = trades[
        trades["resultado_liquido_r"]
        > 0
    ][
        "resultado_liquido_r"
    ].sum()


    perdas = -trades[
        trades["resultado_liquido_r"]
        < 0
    ][
        "resultado_liquido_r"
    ].sum()


    if perdas > 0:

        profit_factor = (
            ganhos / perdas
        )

    else:

        profit_factor = float("inf")


    resumos.append({
        "rr":
            rr,

        "operacoes":
            len(trades),

        "win_rate_pct":
            (
                trades[
                    "resultado_liquido_r"
                ]
                .gt(0)
                .mean()
                * 100
            ),

        "bruto_r":
            trades[
                "resultado_bruto_r"
            ].sum(),

        "liquido_r":
            trades[
                "resultado_liquido_r"
            ].sum(),

        "media_liquida_r":
            trades[
                "resultado_liquido_r"
            ].mean(),

        "profit_factor":
            profit_factor,
    })


# ---------------------------------------------------------
# Resultado
# ---------------------------------------------------------

resumo = pd.DataFrame(
    resumos
)

resumo = resumo.sort_values(
    "liquido_r",
    ascending=False
)


print(
    "\n========== OTIMIZAÇÃO RR V4 =========="
)

print(
    resumo.to_string(
        index=False
    )
)


# ---------------------------------------------------------
# Exportar
# ---------------------------------------------------------

saida = (
    DATA
    / "otimizacao_rr_v4.csv"
)

resumo.to_csv(
    saida,
    index=False
)

print("\nCSV criado:")
print(saida)