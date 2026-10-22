
from pathlib import Path
import pandas as pd

PASTA = Path("data")

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
    dia = candles[candles["data"] == sinal["data"]].copy()

    if dia.empty:
        continue

    horario = pd.to_datetime(
        sinal["horario_rompimento"], utc=True
    )

    # Analisa somente a sessão posterior ao rompimento
    posteriores = dia[
        (dia["datetime"] > horario)
        & (dia["datetime_ny"].dt.strftime("%H:%M") < "16:40")
    ].copy()

    posteriores = posteriores.sort_values("datetime")
    posteriores = posteriores.reset_index(drop=True)

    fvg_encontrado = None

    for i in range(2, len(posteriores)):
        c1 = posteriores.iloc[i - 2]
        c2 = posteriores.iloc[i - 1]
        c3 = posteriores.iloc[i]

        # Evita FVG artificial atravessando lacunas
        if (
            c2["datetime"] - c1["datetime"]
            != pd.Timedelta(minutes=1)
            or c3["datetime"] - c2["datetime"]
            != pd.Timedelta(minutes=1)
        ):
            continue

        if sinal["rompimento"] == "COMPRA":
            if c3["low"] > c1["high"]:
                fvg_encontrado = {
                    "fvg_min": c1["high"],
                    "fvg_max": c3["low"],
                    "horario_fvg": c3["datetime_ny"]
                }
                break

        elif sinal["rompimento"] == "VENDA":
            if c3["high"] < c1["low"]:
                fvg_encontrado = {
                    "fvg_min": c3["high"],
                    "fvg_max": c1["low"],
                    "horario_fvg": c3["datetime_ny"]
                }
                break

    resultados.append({
        "data": sinal["data"],
        "direcao": sinal["rompimento"],
        "horario_rompimento": sinal["horario_rompimento"],
        "fvg_encontrado": fvg_encontrado is not None,
        "horario_fvg": (
            fvg_encontrado["horario_fvg"]
            if fvg_encontrado else pd.NaT
        ),
        "fvg_min": (
            fvg_encontrado["fvg_min"]
            if fvg_encontrado else None
        ),
        "fvg_max": (
            fvg_encontrado["fvg_max"]
            if fvg_encontrado else None
        )
    })

resultado = pd.DataFrame(resultados)

saida = PASTA / "orb_fvg.csv"
resultado.to_csv(saida, index=False)

print("\n===== RESULTADOS ORB + FVG =====")
print("Rompimentos analisados:", len(resultado))

if not resultado.empty:
    print("FVGs encontrados:", resultado["fvg_encontrado"].sum())
    print("Sem FVG:", (~resultado["fvg_encontrado"]).sum())

    print("\nPrimeiros resultados:")
    print(resultado.head(10).to_string(index=False))

print(f"\nArquivo salvo: {saida}")
