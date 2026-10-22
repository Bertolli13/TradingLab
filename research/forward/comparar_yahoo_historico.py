from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf


DATA = Path("data")

HIST_FILE = DATA / "nq_unificado_validacao.parquet"

TZ_NY = "America/New_York"

INICIO = "2026-10-05"
FIM = "2026-10-09"  # end exclusivo no Yahoo


# =========================================================
# 1. BAIXAR YAHOO PARA SOBREPOSIÇÃO
# =========================================================

print("\nBaixando Yahoo para comparação...")

yahoo = yf.download(
    "NQ=F",
    start=INICIO,
    end=FIM,
    interval="1m",
    auto_adjust=False,
    prepost=True,
    progress=False
)

if yahoo.empty:
    raise RuntimeError("Yahoo não retornou dados.")


if isinstance(yahoo.columns, pd.MultiIndex):
    yahoo.columns = yahoo.columns.get_level_values(0)

yahoo = yahoo.reset_index()

yahoo = yahoo.rename(
    columns={
        "Datetime": "datetime",
        "Open": "open_yahoo",
        "High": "high_yahoo",
        "Low": "low_yahoo",
        "Close": "close_yahoo",
        "Volume": "volume_yahoo",
    }
)

yahoo["datetime"] = pd.to_datetime(
    yahoo["datetime"],
    utc=True
)

yahoo = yahoo[
    [
        "datetime",
        "open_yahoo",
        "high_yahoo",
        "low_yahoo",
        "close_yahoo",
        "volume_yahoo",
    ]
].copy()


# =========================================================
# 2. CARREGAR HISTÓRICO ORIGINAL
# =========================================================

hist = pd.read_parquet(
    HIST_FILE
)

hist["datetime"] = pd.to_datetime(
    hist["datetime"],
    utc=True
)

hist = hist.rename(
    columns={
        "open": "open_hist",
        "high": "high_hist",
        "low": "low_hist",
        "close": "close_hist",
        "volume": "volume_hist",
    }
)

hist = hist[
    [
        "datetime",
        "open_hist",
        "high_hist",
        "low_hist",
        "close_hist",
        "volume_hist",
    ]
].copy()


# =========================================================
# 3. FILTRAR MESMO PERÍODO
# =========================================================

inicio_utc = pd.Timestamp(
    f"{INICIO} 00:00",
    tz=TZ_NY
).tz_convert("UTC")

fim_utc = pd.Timestamp(
    "2026-10-08 23:59:59",
    tz=TZ_NY
).tz_convert("UTC")


hist = hist[
    (hist["datetime"] >= inicio_utc)
    & (hist["datetime"] <= fim_utc)
].copy()


# =========================================================
# 4. SOMENTE JANELA OPERACIONAL
# =========================================================

def filtrar_janela(df):

    ny = (
        df["datetime"]
        .dt.tz_convert(TZ_NY)
    )

    hora = ny.dt.strftime("%H:%M")

    return df[
        (hora >= "09:30")
        & (hora < "16:40")
    ].copy()


yahoo = filtrar_janela(yahoo)
hist = filtrar_janela(hist)


# =========================================================
# 5. MERGE MINUTO A MINUTO
# =========================================================

comp = hist.merge(
    yahoo,
    on="datetime",
    how="inner"
)


print("\nCandles históricos na janela:", len(hist))
print("Candles Yahoo na janela:", len(yahoo))
print("Candles coincidentes:", len(comp))


# =========================================================
# 6. DIFERENÇAS
# =========================================================

for campo in ["open", "high", "low", "close"]:

    comp[f"diff_{campo}"] = (
        comp[f"{campo}_yahoo"]
        - comp[f"{campo}_hist"]
    )


# diferença absoluta
for campo in ["open", "high", "low", "close"]:

    comp[f"abs_diff_{campo}"] = (
        comp[f"diff_{campo}"].abs()
    )


# =========================================================
# 7. RESUMO
# =========================================================

print()
print("=" * 75)
print("COMPARAÇÃO YAHOO x HISTÓRICO")
print("=" * 75)


for campo in ["open", "high", "low", "close"]:

    diff = comp[
        f"diff_{campo}"
    ]

    abs_diff = comp[
        f"abs_diff_{campo}"
    ]

    print()
    print(campo.upper())

    print(
        "Diferença média:",
        round(diff.mean(), 6)
    )

    print(
        "Diferença mediana:",
        round(diff.median(), 6)
    )

    print(
        "Erro absoluto médio:",
        round(abs_diff.mean(), 6)
    )

    print(
        "Erro absoluto máximo:",
        round(abs_diff.max(), 6)
    )

    print(
        "% exatamente iguais:",
        round(
            (abs_diff < 1e-9).mean() * 100,
            2
        )
    )


# =========================================================
# 8. OFFSET DE PREÇO
# =========================================================

offset_close = (
    comp["close_yahoo"]
    - comp["close_hist"]
)

print()
print("=" * 75)
print("OFFSET CLOSE")
print("=" * 75)

print(
    "Média:",
    round(offset_close.mean(), 6)
)

print(
    "Mediana:",
    round(offset_close.median(), 6)
)

print(
    "Desvio padrão:",
    round(offset_close.std(), 6)
)

print(
    "Mínimo:",
    round(offset_close.min(), 6)
)

print(
    "Máximo:",
    round(offset_close.max(), 6)
)


# =========================================================
# 9. DIFERENÇA ENTRE RETORNOS DE 1 MINUTO
# =========================================================

comp = comp.sort_values(
    "datetime"
).reset_index(drop=True)

comp["ret_hist"] = (
    comp["close_hist"]
    .diff()
)

comp["ret_yahoo"] = (
    comp["close_yahoo"]
    .diff()
)

comp["diff_retorno"] = (
    comp["ret_yahoo"]
    - comp["ret_hist"]
)


print()
print("=" * 75)
print("MOVIMENTO MINUTO A MINUTO")
print("=" * 75)

print(
    "Correlação retornos:",
    round(
        comp[
            ["ret_hist", "ret_yahoo"]
        ]
        .corr()
        .iloc[0, 1],
        6
    )
)

print(
    "Erro absoluto médio retorno:",
    round(
        comp["diff_retorno"]
        .abs()
        .mean(),
        6
    )
)


# =========================================================
# 10. POR DIA
# =========================================================

comp["data_ny"] = (
    comp["datetime"]
    .dt.tz_convert(TZ_NY)
    .dt.date
)

diario = (
    comp.groupby("data_ny")
    .agg(
        candles=("datetime", "size"),
        offset_close_medio=(
            "diff_close",
            "mean"
        ),
        erro_close_medio=(
            "abs_diff_close",
            "mean"
        ),
        erro_close_max=(
            "abs_diff_close",
            "max"
        ),
    )
    .reset_index()
)


print()
print("=" * 75)
print("POR DIA")
print("=" * 75)

print(
    diario.to_string(
        index=False
    )
)


# =========================================================
# 11. EXPORTAR
# =========================================================

comp.to_csv(
    DATA / "comparacao_yahoo_historico.csv",
    index=False
)

diario.to_csv(
    DATA / "comparacao_yahoo_historico_diario.csv",
    index=False
)


print()
print("CSVs criados:")
print(DATA / "comparacao_yahoo_historico.csv")
print(DATA / "comparacao_yahoo_historico_diario.csv")