
import pandas as pd

candles = pd.read_parquet(
    "data/nq_unificado_validacao.parquet"
)

sinais = pd.read_csv(
    "data/orb_fvg_v2.csv"
)

print("\n===== VALIDAÇÃO DOS SINAIS =====")
print("Total de candles:", len(candles))
print("Total de sinais:", len(sinais))

print("\nColunas dos sinais:")
print(sinais.columns.tolist())

print("\nDistribuição dos motivos:")
print(sinais["motivo"].value_counts(dropna=False))

validos = sinais[
    sinais["motivo"] == "FVG_VALIDO"
].copy()

print("\nSinais válidos:", len(validos))

print("\nPrimeiros cinco sinais válidos:")
print(
    validos[
        [
            "data",
            "direcao",
            "horario_rompimento",
            "horario_fvg",
            "fvg_min",
            "fvg_max"
        ]
    ].head().to_string(index=False)
)
