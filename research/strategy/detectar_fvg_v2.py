
from pathlib import Path
import pandas as pd

PASTA = Path("data")

# Parâmetros experimentais
FVG_MIN_PONTOS = 2.0
MAX_MINUTOS_FVG = 30
FIM_SESSAO = "16:40"

candles = pd.read_parquet(
    PASTA / "nq_unificado_validacao.parquet"
)

orb = pd.read_csv(
    PASTA / "orb_rompimentos.csv"
)

candles["datetime"] = pd.to_datetime(
    candles["datetime"], utc=True
)

candles["datetime_ny"] = candles["datetime"].dt.tz_convert(
    "America/New_York"
)

candles = candles.sort_values("datetime").copy()
candles["data"] = candles["datetime_ny"].dt.strftime("%Y-%m-%d")

orb["data"] = orb["data"].astype(str)
orb = orb[orb["rompimento"].isin(["COMPRA", "VENDA"])]

resultados = []

for _, sinal in orb.iterrows():

    dia = candles[
        candles["data"] == sinal["data"]
    ].copy()

    horario = pd.to_datetime(
        sinal["horario_rompimento"], utc=True
    )

    direcao = sinal["rompimento"]
    range_max = sinal["range_max"]
    range_min = sinal["range_min"]

    # Inclui candles anteriores ao rompimento para
    # permitir padrões cujo FVG começa no rompimento.
    inicio = horario - pd.Timedelta(minutes=2)
    limite = horario + pd.Timedelta(
        minutes=MAX_MINUTOS_FVG
    )

    janela = dia[
        (dia["datetime"] >= inicio)
        & (dia["datetime"] <= limite)
        & (
            dia["datetime_ny"].dt.strftime("%H:%M")
            < FIM_SESSAO
        )
    ].sort_values("datetime").reset_index(drop=True)

    fvg = None
    motivo = "SEM_FVG"

    for i in range(2, len(janela)):

        c1 = janela.iloc[i - 2]
        c2 = janela.iloc[i - 1]
        c3 = janela.iloc[i]

        if (
            c2["datetime"] - c1["datetime"]
            != pd.Timedelta(minutes=1)
            or c3["datetime"] - c2["datetime"]
            != pd.Timedelta(minutes=1)
        ):
            continue

        # O padrão só pode ser confirmado após
        # o fechamento do candle de rompimento.
        if c3["datetime"] < horario:
            continue

        # Invalidação se o fechamento retornar
        # ao interior do range.
        if direcao == "COMPRA":
            if c3["close"] <= range_max:
                motivo = "RETORNO_RANGE"
                break

            gap_min = c1["high"]
            gap_max = c3["low"]

            valido = (
                gap_max > gap_min
                and gap_min >= range_max
            )

        else:
            if c3["close"] >= range_min:
                motivo = "RETORNO_RANGE"
                break

            gap_min = c3["high"]
            gap_max = c1["low"]

            valido = (
                gap_max > gap_min
                and gap_max <= range_min
            )

        tamanho = gap_max - gap_min

        if valido and tamanho >= FVG_MIN_PONTOS:
            fvg = {
                "horario": c3["datetime_ny"],
                "min": gap_min,
                "max": gap_max,
                "tamanho": tamanho
            }
            motivo = "FVG_VALIDO"
            break

    resultados.append({
        "data": sinal["data"],
        "direcao": direcao,
        "horario_rompimento": sinal["horario_rompimento"],
        "fvg_encontrado": fvg is not None,
        "motivo": motivo,
        "horario_fvg": fvg["horario"] if fvg else pd.NaT,
        "fvg_min": fvg["min"] if fvg else None,
        "fvg_max": fvg["max"] if fvg else None,
        "tamanho_fvg": (
            fvg["tamanho"] if fvg else None
        )
    })

resultado = pd.DataFrame(resultados)

saida = PASTA / "orb_fvg_v2.csv"
resultado.to_csv(saida, index=False)

print("\n===== ORB + FVG V2 =====")
print("Rompimentos:", len(resultado))
print("FVGs válidos:", resultado["fvg_encontrado"].sum())

print("\nMotivos:")
print(resultado["motivo"].value_counts())

print("\nPrimeiros resultados:")
print(resultado.head(10).to_string(index=False))

print(f"\nArquivo salvo: {saida}")
