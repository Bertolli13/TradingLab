
from pathlib import Path
import pandas as pd

ARQUIVO = Path("data/nq_forward_v4.parquet")

INICIO_RANGE = "09:30"
FIM_RANGE = "09:45"
FIM_BUSCA = "11:00"

df = pd.read_parquet(ARQUIVO)

df["datetime_ny"] = pd.to_datetime(
    df["datetime"], utc=True
).dt.tz_convert("America/New_York")

df = df.sort_values("datetime_ny").copy()
df["data_ny"] = df["datetime_ny"].dt.date
df["hora"] = df["datetime_ny"].dt.strftime("%H:%M")

resultados = []

for data, dia in df.groupby("data_ny"):
    range_candles = dia[
        (dia["hora"] >= INICIO_RANGE)
        & (dia["hora"] < FIM_RANGE)
    ]

    # Exige os 15 candles do range
    if len(range_candles) != 15:
        continue

    # Confere continuidade minuto a minuto
    intervalo = range_candles["datetime_ny"].diff().dropna()

    if not intervalo.eq(pd.Timedelta(minutes=1)).all():
        continue

    maxima = range_candles["high"].max()
    minima = range_candles["low"].min()

    posteriores = dia[
        (dia["hora"] >= FIM_RANGE)
        & (dia["hora"] < FIM_BUSCA)
    ]

    rompimento = None

    for _, candle in posteriores.iterrows():
        if candle["close"] > maxima:
            rompimento = {
                "direcao": "COMPRA",
                "horario": candle["datetime_ny"],
                "preco": candle["close"]
            }
            break

        if candle["close"] < minima:
            rompimento = {
                "direcao": "VENDA",
                "horario": candle["datetime_ny"],
                "preco": candle["close"]
            }
            break

    resultados.append({
        "data": data,
        "range_max": maxima,
        "range_min": minima,
        "range_pontos": maxima - minima,
        "rompimento": (
            rompimento["direcao"]
            if rompimento else "SEM ROMPIMENTO"
        ),
        "horario_rompimento": (
            rompimento["horario"]
            if rompimento else pd.NaT
        ),
        "preco_rompimento": (
            rompimento["preco"]
            if rompimento else None
        )
    })

resultado = pd.DataFrame(resultados)

saida = Path("data/orb_rompimentos_forward_v4.csv")
resultado.to_csv(saida, index=False)

print("\n===== RESULTADOS ORB =====")
print("Dias analisados:", len(resultado))

if not resultado.empty:
    print("\nDireção dos rompimentos:")
    print(resultado["rompimento"].value_counts())

    print("\nPrimeiros resultados:")
    print(resultado.head(10).to_string(index=False))

print(f"\nArquivo salvo: {saida}")
