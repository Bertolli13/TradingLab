import glob
from pathlib import Path

import pandas as pd


DATA = Path("data")


# ---------------------------------------------------------
# Localizar V3 mais recente
# ---------------------------------------------------------

pastas = sorted(
    glob.glob(str(DATA / "v3_*")),
    reverse=True
)

if not pastas:
    raise FileNotFoundError(
        "Nenhuma pasta data/v3_* encontrada."
    )

pasta_v3 = Path(pastas[0])

arquivo_v3 = pasta_v3 / "backtest_v3.csv"
arquivo_ausentes = DATA / "trades_somente_v3.csv"


# ---------------------------------------------------------
# Carregar V3
# ---------------------------------------------------------

v3 = pd.read_csv(arquivo_v3)

v3 = v3[
    v3["cenario"].astype(str).str.lower()
    == "conservador"
].copy()

v3 = v3[
    v3["executada"].astype(str).str.lower()
    .isin(["true", "1", "sim"])
].copy()


# ---------------------------------------------------------
# Datas
# ---------------------------------------------------------

ausentes = pd.read_csv(arquivo_ausentes)

datas_ausentes = set(
    pd.to_datetime(
        ausentes["data"]
    ).dt.strftime("%Y-%m-%d")
)


v3["data_chave"] = pd.to_datetime(
    v3["data"]
).dt.strftime("%Y-%m-%d")


audit = v3[
    v3["data_chave"].isin(datas_ausentes)
].copy()


# ---------------------------------------------------------
# Converter horários
# ---------------------------------------------------------

for col in [
    "horario_fvg",
    "ordem_ativa_em",
    "horario_entrada",
    "horario_saida",
]:

    audit[col] = pd.to_datetime(
        audit[col],
        utc=True,
        errors="coerce"
    )


# ---------------------------------------------------------
# Verificar se entrou no primeiro candle possível
# ---------------------------------------------------------

audit["entrada_no_primeiro_candle"] = (
    audit["horario_entrada"]
    == audit["ordem_ativa_em"]
)


# ---------------------------------------------------------
# Carregar candles
# ---------------------------------------------------------

candles = pd.read_parquet(
    DATA / "nq_unificado_validacao.parquet"
)

candles["datetime"] = pd.to_datetime(
    candles["datetime"],
    utc=True
)

candles = candles.sort_values(
    "datetime"
).set_index("datetime")


# ---------------------------------------------------------
# Auditoria candle por candle
# ---------------------------------------------------------

resultados = []

for _, trade in audit.iterrows():

    ativo = trade["ordem_ativa_em"]

    # candle em que V3 considera ordem ativa
    if ativo not in candles.index:
        continue

    candle_ativo = candles.loc[ativo]

    # candle seguinte
    pos = candles.index.get_loc(ativo)

    if isinstance(pos, slice):
        pos = pos.start

    proximo = None

    if pos + 1 < len(candles):
        proximo = candles.iloc[pos + 1]

    entrada = float(trade["entrada"])

    direcao = trade["direcao"]

    # V3 exige 1 tick de penetração
    tick = 0.25

    if direcao == "COMPRA":

        tocou_ativo = (
            float(candle_ativo["low"])
            <= entrada - tick
        )

        tocou_proximo = (
            proximo is not None
            and float(proximo["low"])
            <= entrada - tick
        )

    else:

        tocou_ativo = (
            float(candle_ativo["high"])
            >= entrada + tick
        )

        tocou_proximo = (
            proximo is not None
            and float(proximo["high"])
            >= entrada + tick
        )

    resultados.append({
        "data": trade["data_chave"],
        "direcao": direcao,

        "ordem_ativa_em": ativo,
        "horario_entrada_v3": trade["horario_entrada"],

        "entrada": entrada,

        "open_ativo": float(candle_ativo["open"]),
        "high_ativo": float(candle_ativo["high"]),
        "low_ativo": float(candle_ativo["low"]),
        "close_ativo": float(candle_ativo["close"]),

        "entrada_no_primeiro_candle":
            trade["entrada_no_primeiro_candle"],

        "penetracao_1tick_candle_ativo":
            tocou_ativo,

        "penetracao_1tick_candle_seguinte":
            tocou_proximo,
    })


resultado = pd.DataFrame(resultados)


# ---------------------------------------------------------
# Mostrar
# ---------------------------------------------------------

print(
    "\n========== AUDITORIA 14 AUSENTES =========="
)

print(
    resultado.to_string(index=False)
)


print(
    "\nEntradas exatamente no primeiro candle ativo:"
)

print(
    resultado[
        "entrada_no_primeiro_candle"
    ].shape[0],
    "/",
    len(resultado)
)


print(
    "\nPenetração no primeiro candle:"
)

print(
    resultado[
        "penetracao_1tick_candle_ativo"
    ].sum(),
    "/",
    len(resultado)
)


print(
    "\nPenetração também no candle seguinte:"
)

print(
    resultado[
        "penetracao_1tick_candle_seguinte"
    ].sum(),
    "/",
    len(resultado)
)


# ---------------------------------------------------------
# Exportar
# ---------------------------------------------------------

saida = DATA / "auditoria_14_ausentes.csv"

resultado.to_csv(
    saida,
    index=False
)

print("\nCSV criado:")
print(saida)