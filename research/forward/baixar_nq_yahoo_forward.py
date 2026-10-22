from pathlib import Path

import pandas as pd
import yfinance as yf


# =========================================================
# CONFIGURAÇÃO
# =========================================================

DATA = Path("data")

ARQUIVO_SAIDA = (
    DATA
    / "nq_yahoo_forward.csv"
)

TICKER = "NQ=F"

DATA.mkdir(
    exist_ok=True
)


# =========================================================
# 1. BAIXAR JANELA RECENTE
# =========================================================

print(
    "\nBaixando NQ=F do Yahoo Finance..."
)

novo = yf.download(
    TICKER,
    period="8d",
    interval="1m",
    auto_adjust=False,
    prepost=True,
    progress=False,
)


if novo.empty:
    raise RuntimeError(
        "Yahoo não retornou dados."
    )


# =========================================================
# 2. REMOVER MULTIINDEX
# =========================================================

if isinstance(
    novo.columns,
    pd.MultiIndex
):
    novo.columns = (
        novo.columns
        .get_level_values(0)
    )


# =========================================================
# 3. RESETAR DATETIME
# =========================================================

novo = (
    novo.reset_index()
)


# =========================================================
# 4. PADRONIZAR NOMES
# =========================================================

novo = novo.rename(
    columns={
        "Datetime": "datetime",
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Volume": "volume",
    }
)


# =========================================================
# 5. COLUNAS NECESSÁRIAS
# =========================================================

colunas_base = [
    "datetime",
    "open",
    "high",
    "low",
    "close",
    "volume",
]

faltantes = [
    coluna
    for coluna in colunas_base
    if coluna not in novo.columns
]

if faltantes:
    raise RuntimeError(
        "Colunas ausentes no Yahoo: "
        + ", ".join(faltantes)
    )


novo = novo[
    colunas_base
].copy()


# =========================================================
# 6. CONVERTER DATETIME
# =========================================================

novo["datetime"] = pd.to_datetime(
    novo["datetime"],
    utc=True,
    errors="coerce",
)

novo = novo[
    novo["datetime"].notna()
].copy()


# =========================================================
# 7. CAMPOS AUXILIARES
# =========================================================

novo["source"] = "YAHOO_NQ=F"

ny = (
    novo["datetime"]
    .dt.tz_convert(
        "America/New_York"
    )
)

novo["trading_date"] = (
    ny.dt.date.astype(str)
)

novo["session"] = (
    "YAHOO_FORWARD"
)


# =========================================================
# 8. SOMENTE PERÍODO FORWARD
# =========================================================

corte = pd.Timestamp(
    "2026-10-08 23:59:59",
    tz="America/New_York",
).tz_convert("UTC")


novo = novo[
    novo["datetime"] > corte
].copy()


print(
    "\nCandles baixados nesta execução:",
    len(novo)
)


# =========================================================
# 9. CARREGAR HISTÓRICO JÁ SALVO
# =========================================================

if ARQUIVO_SAIDA.exists():

    print(
        "\nArquivo anterior encontrado."
    )

    antigo = pd.read_csv(
        ARQUIVO_SAIDA
    )

    if "datetime" not in antigo.columns:
        raise RuntimeError(
            "O arquivo existente não possui "
            "a coluna datetime."
        )

    antigo["datetime"] = (
        pd.to_datetime(
            antigo["datetime"],
            utc=True,
            errors="coerce",
        )
    )

    antigo = antigo[
        antigo["datetime"].notna()
    ].copy()

    antigo = antigo[
        antigo["datetime"] > corte
    ].copy()

    print(
        "Candles já existentes:",
        len(antigo)
    )

else:

    print(
        "\nNenhum arquivo anterior encontrado."
    )

    antigo = pd.DataFrame(
        columns=[
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
    )


# =========================================================
# 10. GARANTIR MESMAS COLUNAS
# =========================================================

colunas_finais = [
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


for coluna in colunas_finais:

    if coluna not in antigo.columns:
        antigo[coluna] = pd.NA

    if coluna not in novo.columns:
        novo[coluna] = pd.NA


antigo = antigo[
    colunas_finais
].copy()

novo = novo[
    colunas_finais
].copy()


# =========================================================
# 11. JUNTAR ANTIGO + NOVO
# =========================================================

df = pd.concat(
    [
        antigo,
        novo,
    ],
    ignore_index=True,
)


# =========================================================
# 12. NORMALIZAR TIPOS
# =========================================================

df["datetime"] = pd.to_datetime(
    df["datetime"],
    utc=True,
    errors="coerce",
)

df = df[
    df["datetime"].notna()
].copy()


for coluna in [
    "open",
    "high",
    "low",
    "close",
    "volume",
]:

    df[coluna] = pd.to_numeric(
        df[coluna],
        errors="coerce",
    )


# =========================================================
# 13. RECRIAR CAMPOS AUXILIARES
# =========================================================

df["source"] = (
    df["source"]
    .fillna("YAHOO_NQ=F")
)

df["session"] = (
    df["session"]
    .fillna("YAHOO_FORWARD")
)


ny = (
    df["datetime"]
    .dt.tz_convert(
        "America/New_York"
    )
)

df["trading_date"] = (
    ny.dt.date.astype(str)
)


# =========================================================
# 14. ORDENAR E REMOVER DUPLICATAS
# =========================================================

antes_dedup = len(df)

df = (
    df.sort_values(
        "datetime"
    )
    .drop_duplicates(
        subset=["datetime"],
        keep="last",
    )
    .reset_index(
        drop=True
    )
)

removidas = (
    antes_dedup
    - len(df)
)


# =========================================================
# 15. FILTRO DE SEGURANÇA DO FORWARD
# =========================================================

df = df[
    df["datetime"] > corte
].copy()

df = (
    df.sort_values(
        "datetime"
    )
    .reset_index(
        drop=True
    )
)


# =========================================================
# 16. VALIDAÇÃO OHLC
# =========================================================

invalidos = df[
    (df["high"] < df["low"])
    |
    (df["high"] < df["open"])
    |
    (df["high"] < df["close"])
    |
    (df["low"] > df["open"])
    |
    (df["low"] > df["close"])
]


if len(invalidos):
    print(
        "\nATENÇÃO:",
        len(invalidos),
        "candles OHLC inválidos.",
    )


# =========================================================
# 17. VERIFICAR TICK DE 0.25
# =========================================================

precos = df[
    [
        "open",
        "high",
        "low",
        "close",
    ]
].to_numpy().ravel()


precos_validos = (
    pd.Series(precos)
    .dropna()
    .to_numpy()
)


fora_tick = (
    abs(
        (precos_validos / 0.25)
        -
        (
            precos_validos
            / 0.25
        ).round()
    )
    > 1e-8
)


print(
    "\nPreços fora do tick de 0.25:",
    int(
        fora_tick.sum()
    )
)


# =========================================================
# 18. GAPS > 1 MINUTO
# =========================================================

delta = (
    df["datetime"]
    .diff()
)


mascara_gap = (
    delta
    > pd.Timedelta(
        minutes=1
    )
)


gaps = df[
    mascara_gap
].copy()


gaps["gap_minutos"] = (
    delta[
        mascara_gap
    ]
    .dt.total_seconds()
    / 60
)


# =========================================================
# 19. SALVAR CUMULATIVO
# =========================================================

df.to_csv(
    ARQUIVO_SAIDA,
    index=False,
)


# =========================================================
# 20. RELATÓRIO
# =========================================================

print(
    "\n========================================"
)

print(
    "YAHOO FORWARD CUMULATIVO"
)

print(
    "========================================"
)


print(
    "Candles atuais:",
    len(df)
)

print(
    "Duplicatas removidas na mesclagem:",
    removidas
)


if not df.empty:

    print(
        "Primeiro UTC:",
        df["datetime"].min()
    )

    print(
        "Último UTC:",
        df["datetime"].max()
    )

    print(
        "Primeiro NY:",
        df["datetime"]
        .min()
        .tz_convert(
            "America/New_York"
        )
    )

    print(
        "Último NY:",
        df["datetime"]
        .max()
        .tz_convert(
            "America/New_York"
        )
    )


print(
    "Duplicatas finais:",
    df["datetime"]
    .duplicated()
    .sum()
)

print(
    "Volume ausente:",
    df["volume"]
    .isna()
    .sum()
)

print(
    "Volume zero:",
    (
        df["volume"]
        == 0
    ).sum()
)

print(
    "Candles OHLC inválidos:",
    len(invalidos)
)

print(
    "Gaps > 1 minuto:",
    len(gaps)
)


print(
    "\nCandles por data NY:"
)


if not df.empty:

    print(
        df.assign(
            data_ny=(
                df["datetime"]
                .dt.tz_convert(
                    "America/New_York"
                )
                .dt.date
            )
        )
        .groupby(
            "data_ny"
        )
        .size()
        .to_string()
    )


if not gaps.empty:

    print(
        "\nPrimeiros gaps:"
    )

    print(
        gaps[
            [
                "datetime",
                "gap_minutos",
            ]
        ]
        .head(20)
        .to_string(
            index=False
        )
    )


print(
    "\nArquivo atualizado:"
)

print(
    ARQUIVO_SAIDA
)