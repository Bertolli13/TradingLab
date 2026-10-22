from pathlib import Path

import pandas as pd


DATA = Path("data")

HIST_FILE = DATA / "nq_unificado_validacao.parquet"
YAHOO_FILE = DATA / "nq_yahoo_forward.csv"

SAIDA = DATA / "nq_forward_v4.parquet"

TZ_NY = "America/New_York"

CORTE = pd.Timestamp(
    "2026-10-09 00:00:00",
    tz=TZ_NY
).tz_convert("UTC")


# =========================================================
# 1. HISTÓRICO ORIGINAL
# =========================================================

hist = pd.read_parquet(
    HIST_FILE
)

hist["datetime"] = pd.to_datetime(
    hist["datetime"],
    utc=True
)

print("\nHistórico original:")
print("Candles:", len(hist))
print("Início:", hist["datetime"].min())
print("Fim:", hist["datetime"].max())


# =========================================================
# 2. YAHOO
# =========================================================

yahoo = pd.read_csv(
    YAHOO_FILE
)

yahoo["datetime"] = pd.to_datetime(
    yahoo["datetime"],
    utc=True
)

print("\nYahoo:")
print("Candles:", len(yahoo))
print("Início:", yahoo["datetime"].min())
print("Fim:", yahoo["datetime"].max())


# =========================================================
# 3. SOMENTE YAHOO APÓS CORTE
# =========================================================

yahoo = yahoo[
    yahoo["datetime"] >= CORTE
].copy()


# =========================================================
# 4. COMPATIBILIDADE DE COLUNAS
# =========================================================

colunas_base = [
    "datetime",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "source",
    "trading_date",
    "session",
]


for coluna in colunas_base:

    if coluna not in hist.columns:
        hist[coluna] = None

    if coluna not in yahoo.columns:
        yahoo[coluna] = None


hist = hist[
    colunas_base
].copy()

yahoo = yahoo[
    colunas_base
].copy()


# =========================================================
# 5. GARANTIR TIPOS NUMÉRICOS
# =========================================================

for coluna in [
    "open",
    "high",
    "low",
    "close",
    "volume",
]:

    hist[coluna] = pd.to_numeric(
        hist[coluna],
        errors="coerce"
    )

    yahoo[coluna] = pd.to_numeric(
        yahoo[coluna],
        errors="coerce"
    )


# =========================================================
# 6. JUNTAR
# =========================================================

base = pd.concat(
    [
        hist,
        yahoo
    ],
    ignore_index=True
)


base = base.sort_values(
    "datetime"
)


# =========================================================
# 7. DUPLICATAS
#
# Se algum timestamp aparecer nas duas fontes,
# preservamos o histórico original.
# =========================================================

base["prioridade"] = (
    base["source"]
    .astype(str)
    .str.contains(
        "YAHOO",
        case=False,
        na=False
    )
    .astype(int)
)


base = (
    base.sort_values(
        [
            "datetime",
            "prioridade"
        ]
    )
    .drop_duplicates(
        subset=["datetime"],
        keep="first"
    )
    .drop(
        columns="prioridade"
    )
    .reset_index(drop=True)
)


# =========================================================
# 8. RECRIAR TRADING_DATE PARA YAHOO
# =========================================================

ny = (
    base["datetime"]
    .dt.tz_convert(TZ_NY)
)

mask_yahoo = (
    base["source"] == "YAHOO_NQ=F"
)

base.loc[
    mask_yahoo,
    "trading_date"
] = (
    ny[
        mask_yahoo
    ]
    .dt.date
    .astype(str)
)


# =========================================================
# 9. VALIDAÇÕES
# =========================================================

duplicatas = (
    base["datetime"]
    .duplicated()
    .sum()
)

ohlc_invalidos = base[
    (base["high"] < base["low"])
    |
    (base["high"] < base["open"])
    |
    (base["high"] < base["close"])
    |
    (base["low"] > base["open"])
    |
    (base["low"] > base["close"])
]


print()
print("=" * 70)
print("BASE FORWARD V4")
print("=" * 70)

print(
    "Candles totais:",
    len(base)
)

print(
    "Primeiro:",
    base["datetime"].min()
)

print(
    "Último:",
    base["datetime"].max()
)

print(
    "Duplicatas:",
    duplicatas
)

print(
    "OHLC inválidos:",
    len(ohlc_invalidos)
)


print()
print("Candles por fonte:")

print(
    base["source"]
    .value_counts(
        dropna=False
    )
    .to_string()
)


# =========================================================
# 10. DIAS NOVOS
# =========================================================

novos = base[
    base["datetime"] >= CORTE
].copy()

novos["data_ny"] = (
    novos["datetime"]
    .dt.tz_convert(TZ_NY)
    .dt.date
)


print()
print("Dias forward:")

print(
    novos.groupby(
        "data_ny"
    )
    .size()
    .to_string()
)


# =========================================================
# 11. SALVAR
# =========================================================

base.to_parquet(
    SAIDA,
    index=False
)


print()
print("Arquivo criado:")
print(SAIDA)