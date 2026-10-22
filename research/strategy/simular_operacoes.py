
from pathlib import Path
import pandas as pd

PASTA = Path("data")
TICK = 0.25
FIM_SESSAO = "16:40"

candles = pd.read_parquet(
    PASTA / "nq_unificado_validacao.parquet"
)

sinais = pd.read_csv(
    PASTA / "orb_fvg_v2.csv"
)

candles["datetime"] = pd.to_datetime(
    candles["datetime"], utc=True
)

candles["datetime_ny"] = candles["datetime"].dt.tz_convert(
    "America/New_York"
)

candles["data"] = candles["datetime_ny"].dt.strftime("%Y-%m-%d")

candles = candles.sort_values("datetime")

sinais = sinais[sinais["fvg_encontrado"] == True].copy()

resultados = []

for _, sinal in sinais.iterrows():

    dia = candles[
        candles["data"] == str(sinal["data"])
    ].sort_values("datetime").reset_index(drop=True)

    horario_fvg = pd.to_datetime(
        sinal["horario_fvg"], utc=True
    )

    direcao = sinal["direcao"]

    # Recupera os três candles que formaram o FVG
    indice = dia.index[dia["datetime"] == horario_fvg]

    if len(indice) == 0 or indice[0] < 2:
        continue

    i = indice[0]
    c1 = dia.iloc[i - 2]

    if direcao == "COMPRA":
        entrada = sinal["fvg_max"]
        stop = c1["low"]
        risco = entrada - stop
        alvo = entrada + risco
    else:
        entrada = sinal["fvg_min"]
        stop = c1["high"]
        risco = stop - entrada
        alvo = entrada - risco

    if risco <= 0:
        continue

    # Apenas candles posteriores à confirmação do FVG
    futuros = dia[
        (dia["datetime"] > horario_fvg)
        & (
            dia["datetime_ny"].dt.strftime("%H:%M")
            < FIM_SESSAO
        )
    ]

    executada = False
    horario_entrada = None
    resultado_r = None
    motivo_saida = "SEM_RETESTE"

    for _, candle in futuros.iterrows():

        if not executada:
            if direcao == "COMPRA":
                executada = candle["low"] <= entrada - TICK
            else:
                executada = candle["high"] >= entrada + TICK

            if not executada:
                continue

            horario_entrada = candle["datetime_ny"]

        # Verifica stop e alvo
        if direcao == "COMPRA":
            atingiu_stop = candle["low"] <= stop
            atingiu_alvo = candle["high"] >= alvo
        else:
            atingiu_stop = candle["high"] >= stop
            atingiu_alvo = candle["low"] <= alvo

        if atingiu_stop:
            resultado_r = -1.0
            motivo_saida = "STOP"
            break

        if atingiu_alvo:
            resultado_r = 1.0
            motivo_saida = "ALVO"
            break

    if executada and resultado_r is None:
        ultimo = futuros.iloc[-1] if not futuros.empty else None

        if ultimo is not None:
            fechamento = ultimo["close"]

            if direcao == "COMPRA":
                resultado_r = (fechamento - entrada) / risco
            else:
                resultado_r = (entrada - fechamento) / risco

            motivo_saida = "ENCERRAMENTO"

    resultados.append({
        "data": sinal["data"],
        "direcao": direcao,
        "entrada": entrada,
        "stop": stop,
        "alvo": alvo,
        "risco_pontos": risco,
        "executada": executada,
        "horario_entrada": horario_entrada,
        "resultado_r": resultado_r,
        "motivo_saida": motivo_saida
    })

resultado = pd.DataFrame(resultados)

saida = PASTA / "backtest_orb_fvg.csv"
resultado.to_csv(saida, index=False)

operacoes = resultado[resultado["executada"]].copy()

print("\n===== BACKTEST ORB + FVG =====")
print("Sinais analisados:", len(resultado))
print("Operações executadas:", len(operacoes))

if not operacoes.empty:
    print("Win rate:", round(
        (operacoes["resultado_r"] > 0).mean() * 100, 2
    ), "%")

    print("Resultado total (R):", round(
        operacoes["resultado_r"].sum(), 2
    ))

    print("Resultado médio (R):", round(
        operacoes["resultado_r"].mean(), 3
    ))

    print("\nMotivos de saída:")
    print(operacoes["motivo_saida"].value_counts())

print(f"\nArquivo salvo: {saida}")
