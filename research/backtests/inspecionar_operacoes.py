
import pandas as pd
from pathlib import Path

PASTA = Path("data")

candles = pd.read_parquet(
    PASTA / "nq_unificado_validacao.parquet"
)

v2 = pd.read_csv(
    PASTA / "backtest_v2.csv"
)

auditoria = pd.read_csv(
    PASTA / "auditoria_v1_v2.csv"
)

candles["datetime"] = pd.to_datetime(
    candles["datetime"], utc=True
)

candles["datetime_ny"] = candles["datetime"].dt.tz_convert(
    "America/New_York"
)

candles["data"] = candles["datetime_ny"].dt.strftime("%Y-%m-%d")

auditoria = auditoria[
    auditoria["resultado_v1"].notna()
    & auditoria["resultado_v2"].notna()
    & (
        auditoria["resultado_v1"]
        != auditoria["resultado_v2"]
    )
]

detalhes = []

for _, caso in auditoria.iterrows():

    operacao = v2[
        (v2["data"] == caso["data"])
        & (v2["direcao"] == caso["direcao"])
    ]

    if operacao.empty:
        continue

    op = operacao.iloc[0]

    horario_entrada = pd.to_datetime(
        op["horario_entrada"], utc=True
    )

    inicio = horario_entrada - pd.Timedelta(minutes=3)
    fim = horario_entrada + pd.Timedelta(minutes=3)

    janela = candles[
        (candles["datetime"] >= inicio)
        & (candles["datetime"] <= fim)
    ].sort_values("datetime")

    entrada = float(op["entrada"])
    stop = float(op["stop"])
    alvo = float(op["alvo"])
    direcao = op["direcao"]

    print("\n" + "=" * 65)
    print("DATA:", caso["data"])
    print("DIREÇÃO:", direcao)
    print("ENTRADA:", entrada)
    print("STOP:", stop)
    print("ALVO:", alvo)
    print("HORÁRIO ENTRADA:", op["horario_entrada"])

    for _, candle in janela.iterrows():

        if direcao == "COMPRA":
            tocou_entrada = candle["low"] <= entrada - 0.25
            tocou_stop = candle["low"] <= stop
            tocou_alvo = candle["high"] >= alvo
        else:
            tocou_entrada = candle["high"] >= entrada + 0.25
            tocou_stop = candle["high"] >= stop
            tocou_alvo = candle["low"] <= alvo

        eh_entrada = candle["datetime"] == horario_entrada

        detalhes.append({
            "data": caso["data"],
            "direcao": direcao,
            "horario": candle["datetime_ny"],
            "open": candle["open"],
            "high": candle["high"],
            "low": candle["low"],
            "close": candle["close"],
            "candle_entrada": eh_entrada,
            "tocou_entrada": tocou_entrada,
            "tocou_stop": tocou_stop,
            "tocou_alvo": tocou_alvo
        })

    print(
        janela[
            ["datetime_ny", "open", "high", "low", "close"]
        ].to_string(index=False)
    )

resultado = pd.DataFrame(detalhes)

saida = PASTA / "auditoria_candles.csv"
resultado.to_csv(saida, index=False)

print("\nRelatório salvo:", saida)
