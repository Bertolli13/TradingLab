from pathlib import Path

import pandas as pd


ARQUIVO = Path("data/nq_yahoo_forward.csv")

TZ_NY = "America/New_York"

INICIO = "09:30"
FIM = "16:40"


# =========================================================
# 1. CARREGAR
# =========================================================

df = pd.read_csv(
    ARQUIVO,
    parse_dates=["datetime"]
)

df["datetime"] = pd.to_datetime(
    df["datetime"],
    utc=True
)

df["datetime_ny"] = (
    df["datetime"]
    .dt.tz_convert(TZ_NY)
)

df["data_ny"] = (
    df["datetime_ny"]
    .dt.date
)


# =========================================================
# 2. SOMENTE DIAS ÚTEIS
# =========================================================

df = df[
    df["datetime_ny"].dt.weekday < 5
].copy()


# =========================================================
# 3. JANELA DA ESTRATÉGIA
#
# 09:30 até 16:39.
# O V3 encerra antes das 16:40.
# =========================================================

hora = df["datetime_ny"].dt.strftime(
    "%H:%M"
)

janela = df[
    (hora >= "09:30")
    & (hora < "16:40")
].copy()


# =========================================================
# 4. VALIDAR DIA A DIA
# =========================================================

resultados = []

for data, grupo in janela.groupby("data_ny"):

    grupo = grupo.sort_values(
        "datetime_ny"
    ).copy()

    inicio = pd.Timestamp(
        f"{data} 09:30",
        tz=TZ_NY
    )

    fim = pd.Timestamp(
        f"{data} 16:39",
        tz=TZ_NY
    )

    esperados = pd.date_range(
        inicio,
        fim,
        freq="1min"
    )

    existentes = pd.DatetimeIndex(
        grupo["datetime_ny"]
    )

    faltantes = esperados.difference(
        existentes
    )

    duplicatas = grupo[
        "datetime_ny"
    ].duplicated().sum()

    resultados.append({
        "data": str(data),
        "candles": len(grupo),
        "esperados": len(esperados),
        "faltantes": len(faltantes),
        "duplicatas": duplicatas,
        "primeiro":
            grupo["datetime_ny"].min()
            if not grupo.empty
            else None,
        "ultimo":
            grupo["datetime_ny"].max()
            if not grupo.empty
            else None,
        "minutos_faltantes":
            ",".join(
                x.strftime("%H:%M")
                for x in faltantes[:30]
            )
    })


resultado = pd.DataFrame(
    resultados
)


# =========================================================
# 5. RESULTADO
# =========================================================

print()
print("=" * 75)
print("VALIDAÇÃO YAHOO - JANELA V4")
print("=" * 75)

print(
    resultado.to_string(
        index=False
    )
)


# =========================================================
# 6. RESUMO
# =========================================================

dias_com_falhas = resultado[
    resultado["faltantes"] > 0
]

print()
print("=" * 75)
print("RESUMO")
print("=" * 75)

print(
    "Dias analisados:",
    len(resultado)
)

print(
    "Dias completos:",
    (resultado["faltantes"] == 0).sum()
)

print(
    "Dias com minutos faltantes:",
    len(dias_com_falhas)
)

print(
    "Total de minutos faltantes:",
    resultado["faltantes"].sum()
)


# =========================================================
# 7. ORB + BREAKOUT
#
# Verificação ainda mais importante:
# 09:30 até 11:00
# =========================================================

hora_total = df[
    "datetime_ny"
].dt.strftime("%H:%M")

manha = df[
    (hora_total >= "09:30")
    & (hora_total <= "11:00")
].copy()


print()
print("=" * 75)
print("JANELA CRÍTICA 09:30-11:00")
print("=" * 75)


for data, grupo in manha.groupby("data_ny"):

    inicio = pd.Timestamp(
        f"{data} 09:30",
        tz=TZ_NY
    )

    fim = pd.Timestamp(
        f"{data} 11:00",
        tz=TZ_NY
    )

    esperado = pd.date_range(
        inicio,
        fim,
        freq="1min"
    )

    existente = pd.DatetimeIndex(
        grupo["datetime_ny"]
    )

    faltantes = esperado.difference(
        existente
    )

    status = (
        "OK"
        if len(faltantes) == 0
        else "FALHA"
    )

    print(
        f"{data} | "
        f"{status} | "
        f"candles={len(grupo)} | "
        f"faltantes={len(faltantes)}"
    )

    if len(faltantes):
        print(
            "  faltando:",
            ", ".join(
                x.strftime("%H:%M")
                for x in faltantes
            )
        )


# =========================================================
# 8. EXPORTAR
# =========================================================

saida = Path(
    "data/validacao_yahoo_janela_v4.csv"
)

resultado.to_csv(
    saida,
    index=False
)

print()
print("CSV criado:")
print(saida)