
from pathlib import Path
import requests
import pandas as pd

BASE_URL = (
    "https://raw.githubusercontent.com/"
    "kfccolonel1/BARS/main/NQ/1min/"
)

ARQUIVOS = [
    "NQ_1min_2024-06-21_2024-12-31_stitched.csv",
    "NQ_1min_2025-01-01_2025-12-31_stitched.csv",
    "NQ_1min_2026-01-01_2026-10-08_stitched.csv",
]

PASTA = Path("data")
PASTA.mkdir(exist_ok=True)


def baixar_arquivo(nome):
    destino = PASTA / nome

    if destino.exists() and destino.stat().st_size > 0:
        print(f"\nArquivo existente: {nome}")
    else:
        print(f"\nBaixando: {nome}")

        url = BASE_URL + nome
        temporario = destino.with_suffix(".part")

        try:
            with requests.get(
                url, stream=True, timeout=(15, 120)
            ) as resposta:
                resposta.raise_for_status()

                with open(temporario, "wb") as arquivo:
                    for bloco in resposta.iter_content(
                        chunk_size=1024 * 1024
                    ):
                        if bloco:
                            arquivo.write(bloco)

            temporario.replace(destino)

        except Exception:
            temporario.unlink(missing_ok=True)
            raise

    tamanho = destino.stat().st_size / (1024 * 1024)
    print(f"Tamanho: {tamanho:.2f} MB")

    df = pd.read_csv(destino)

    print("Linhas:", len(df))
    print("Colunas:", df.columns.tolist())
    print("Primeiras linhas:")
    print(df.head(3).to_string(index=False))

    print("Valores ausentes:")
    print(df.isna().sum().to_string())

    return df


def main():
    for nome in ARQUIVOS:
        try:
            baixar_arquivo(nome)
        except Exception as erro:
            print(f"Erro em {nome}: {erro}")

    print("\nInspeção inicial concluída.")


if __name__ == "__main__":
    main()
