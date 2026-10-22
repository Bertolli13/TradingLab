
from pathlib import Path
import pandas as pd

PASTA = Path("data")
ARQUIVOS = sorted(PASTA.glob("NQ_1min_*_stitched.csv"))

if not ARQUIVOS:
    raise FileNotFoundError(
        "Nenhum arquivo NQ stitched encontrado na pasta data."
    )

bases = []

for arquivo in ARQUIVOS:
    print(f"\nLendo: {arquivo.name}")

    df = pd.read_csv(arquivo)

    # Normaliza timestamps com diferentes offsets
    df["datetime"] = pd.to_datetime(
        df["datetime"], utc=True, errors="coerce"
    )

    for coluna in ["open", "high", "low", "close"]:
        df[coluna] = pd.to_numeric(
            df[coluna], errors="coerce"
        )

    df["arquivo_origem"] = arquivo.name
    bases.append(df)

dados = pd.concat(bases, ignore_index=True)
dados = dados.sort_values("datetime").reset_index(drop=True)

print("\n========== VALIDAÇÃO ==========")
print("Total de candles:", len(dados))
print("Datas inválidas:", dados["datetime"].isna().sum())

duplicados = dados["datetime"].duplicated().sum()
print("Horários duplicados:", duplicados)

ohlc = ["open", "high", "low", "close"]
print("Preços ausentes:", dados[ohlc].isna().sum().sum())

validos = dados.dropna(subset=["datetime"] + ohlc).copy()

maximo = validos[["open", "close", "low"]].max(axis=1)
minimo = validos[["open", "close", "high"]].min(axis=1)

inconsistentes = (
    (validos["high"] < maximo)
    | (validos["low"] > minimo)
)

print("Candles OHLC inconsistentes:", inconsistentes.sum())

# Verifica diferenças entre timestamps consecutivos
horarios = validos["datetime"].drop_duplicates().sort_values()
intervalos = horarios.diff()

lacunas = intervalos[intervalos > pd.Timedelta(minutes=1)]

print("Intervalos maiores que 1 minuto:", len(lacunas))
print("Maior intervalo:", intervalos.max())

print("\nDistribuição por origem:")
print(dados["source"].value_counts(dropna=False))

print("\nDistribuição por sessão:")
print(dados["session"].value_counts(dropna=False))

# Conversão para horário de Nova York
validos["datetime_ny"] = validos["datetime"].dt.tz_convert(
    "America/New_York"
)

print("\nPrimeiro candle:", validos["datetime_ny"].min())
print("Último candle:", validos["datetime_ny"].max())

# Salva sem descartar duplicações ou erros silenciosamente
saida = PASTA / "nq_unificado_validacao.parquet"
validos.to_parquet(saida, index=False)

print(f"\nBase de inspeção salva em: {saida}")
print("Validação concluída.")
