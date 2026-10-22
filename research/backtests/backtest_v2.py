
from pathlib import Path
import pandas as pd

PASTA = Path("data")

ARQUIVO_CANDLES = PASTA / "nq_unificado_validacao.parquet"
ARQUIVO_SINAIS = PASTA / "orb_fvg_v2.csv"
ARQUIVO_ORB = PASTA / "orb_rompimentos.csv"
ARQUIVO_V1 = PASTA / "backtest_orb_fvg.csv"

SAIDA = PASTA / "backtest_v2.csv"

# Configurações experimentais
TICK = 0.25
VALOR_PONTO_MNQ = 2.0

# Custos em dólares por operação completa (ida e volta)
CUSTO_ROUND_TRIP_USD = 3.00

# Slippage total estimado, em ticks, por operação
SLIPPAGE_TOTAL_TICKS = 2

FIM_SESSAO = "16:40"

# 1. Carregar dados
candles = pd.read_parquet(ARQUIVO_CANDLES)
sinais = pd.read_csv(ARQUIVO_SINAIS)
orb = pd.read_csv(ARQUIVO_ORB)

candles["datetime"] = pd.to_datetime(
    candles["datetime"], utc=True
)

candles["datetime_ny"] = candles["datetime"].dt.tz_convert(
    "America/New_York"
)

candles["data"] = candles["datetime_ny"].dt.strftime("%Y-%m-%d")
candles = candles.sort_values("datetime")

sinais["data"] = sinais["data"].astype(str)
orb["data"] = orb["data"].astype(str)

sinais = sinais[
    sinais["fvg_encontrado"].astype(str).str.lower() == "true"
].copy()

# Adicionar os limites originais do ORB
sinais = sinais.merge(
    orb[["data", "range_max", "range_min"]],
    on="data",
    how="left",
    validate="one_to_one"
)

resultados = []

for _, sinal in sinais.iterrows():

    dia = candles[
        candles["data"] == sinal["data"]
    ].sort_values("datetime").reset_index(drop=True)

    horario_fvg = pd.to_datetime(
        sinal["horario_fvg"], utc=True
    )

    indices = dia.index[
        dia["datetime"] == horario_fvg
    ]

    if len(indices) == 0 or indices[0] < 2:
        continue

    i = indices[0]
    c1 = dia.iloc[i - 2]

    direcao = sinal["direcao"]

    if direcao == "COMPRA":
        entrada = float(sinal["fvg_max"])
        stop = float(c1["low"])
        risco = entrada - stop
        alvo = entrada + risco
    else:
        entrada = float(sinal["fvg_min"])
        stop = float(c1["high"])
        risco = stop - entrada
        alvo = entrada - risco

    if risco <= 0:
        continue

    # Custos expressos em R, usando um contrato MNQ
    risco_usd = risco * VALOR_PONTO_MNQ

    slippage_usd = (
        SLIPPAGE_TOTAL_TICKS
        * TICK
        * VALOR_PONTO_MNQ
    )

    custo_total_usd = (
        CUSTO_ROUND_TRIP_USD + slippage_usd
    )

    custo_r = custo_total_usd / risco_usd

    futuros = dia[
        (dia["datetime"] > horario_fvg)
        & (
            dia["datetime_ny"].dt.strftime("%H:%M")
            < FIM_SESSAO
        )
    ].sort_values("datetime")

    executada = False
    horario_entrada = None
    horario_saida = None

    resultado_bruto_r = None
    motivo_saida = "SEM_RETESTE"

    ultimo_candle = None

    for _, candle in futuros.iterrows():

        ultimo_candle = candle

        # ETAPA A: ordem ainda pendente
        if not executada:

            # Invalidação pelo fechamento dentro do ORB
            if direcao == "COMPRA":
                invalidou = (
                    candle["close"] <= sinal["range_max"]
                )
            else:
                invalidou = (
                    candle["close"] >= sinal["range_min"]
                )

            # Ordem limitada: exige penetração de 1 tick
            if direcao == "COMPRA":
                tocou_entrada = (
                    candle["low"] <= entrada - TICK
                )
            else:
                tocou_entrada = (
                    candle["high"] >= entrada + TICK
                )

            if tocou_entrada:
                executada = True
                horario_entrada = candle["datetime_ny"]

                # No candle de entrada, só reconhecemos
                # stop, nunca alvo.
                if direcao == "COMPRA":
                    atingiu_stop = candle["low"] <= stop
                else:
                    atingiu_stop = candle["high"] >= stop

                if atingiu_stop:
                    resultado_bruto_r = -1.0
                    motivo_saida = "STOP_ENTRADA"
                    horario_saida = candle["datetime_ny"]
                    break

                continue

            if invalidou:
                motivo_saida = "CANCELADA_RANGE"
                break

            continue

        # ETAPA B: posição aberta
        if direcao == "COMPRA":
            atingiu_stop = candle["low"] <= stop
            atingiu_alvo = candle["high"] >= alvo
        else:
            atingiu_stop = candle["high"] >= stop
            atingiu_alvo = candle["low"] <= alvo

        # Stop primeiro em candle ambíguo
        if atingiu_stop:
            resultado_bruto_r = -1.0
            motivo_saida = "STOP"
            horario_saida = candle["datetime_ny"]
            break

        if atingiu_alvo:
            resultado_bruto_r = 1.0
            motivo_saida = "ALVO"
            horario_saida = candle["datetime_ny"]
            break

    # Encerramento no último candle disponível
    if executada and resultado_bruto_r is None:

        if ultimo_candle is not None:

            fechamento = float(ultimo_candle["close"])

            if direcao == "COMPRA":
                resultado_bruto_r = (
                    fechamento - entrada
                ) / risco
            else:
                resultado_bruto_r = (
                    entrada - fechamento
                ) / risco

            motivo_saida = "ENCERRAMENTO"
            horario_saida = ultimo_candle["datetime_ny"]

    resultado_liquido_r = (
        resultado_bruto_r - custo_r
        if executada and resultado_bruto_r is not None
        else None
    )

    resultados.append({
        "data": sinal["data"],
        "direcao": direcao,
        "entrada": entrada,
        "stop": stop,
        "alvo": alvo,
        "risco_pontos": risco,
        "executada": executada,
        "horario_entrada": horario_entrada,
        "horario_saida": horario_saida,
        "motivo_saida": motivo_saida,
        "resultado_bruto_r": resultado_bruto_r,
        "custo_r": custo_r if executada else 0,
        "resultado_liquido_r": resultado_liquido_r
    })

resultado = pd.DataFrame(resultados)
resultado.to_csv(SAIDA, index=False)

operacoes = resultado[resultado["executada"]].copy()

print("\n========== BACKTEST V2 ==========")
print("Sinais analisados:", len(resultado))
print("Operações executadas:", len(operacoes))

print("\nMotivos:")
print(resultado["motivo_saida"].value_counts())

if not operacoes.empty:

    ganhos = (operacoes["resultado_liquido_r"] > 0).sum()

    win_rate = ganhos / len(operacoes) * 100

    print("\nWin rate líquido:", round(win_rate, 2), "%")

    print(
        "Resultado bruto:",
        round(operacoes["resultado_bruto_r"].sum(), 2),
        "R"
    )

    print(
        "Resultado líquido:",
        round(operacoes["resultado_liquido_r"].sum(), 2),
        "R"
    )

    print(
        "Média líquida:",
        round(operacoes["resultado_liquido_r"].mean(), 4),
        "R"
    )

    operacoes["ano"] = pd.to_datetime(
        operacoes["data"]
    ).dt.year

    print("\nResultado líquido por ano:")
    print(
        operacoes.groupby("ano")["resultado_liquido_r"]
        .agg(["count", "sum", "mean"])
        .to_string()
    )

# Comparação com V1
if ARQUIVO_V1.exists():

    v1 = pd.read_csv(ARQUIVO_V1)
    v1 = v1[v1["executada"] == True]

    print("\n========== COMPARAÇÃO ==========")

    print(
        "V1 - Operações:",
        len(v1),
        "| Resultado bruto:",
        round(v1["resultado_r"].sum(), 2),
        "R"
    )

    print(
        "V2 - Operações:",
        len(operacoes),
        "| Resultado bruto:",
        round(operacoes["resultado_bruto_r"].sum(), 2),
        "R"
    )

    print(
        "V2 - Resultado líquido:",
        round(operacoes["resultado_liquido_r"].sum(), 2),
        "R"
    )

print(f"\nArquivo salvo: {SAIDA}")
