from pathlib import Path

import pandas as pd


PROJETO = Path(__file__).resolve().parent
DATA = PROJETO / "data"

DATA_TESTE = "2026-10-19"

ARQUIVOS = [
    DATA / "orb_rompimentos_forward_v4.csv",
    DATA / "orb_fvg_forward_v4.csv",
]


def localizar_coluna_data(df):
    candidatos = [
        "data",
        "date",
        "trading_date",
        "datetime",
        "timestamp",
    ]

    for coluna in candidatos:
        if coluna in df.columns:
            return coluna

    return None


def filtrar_data(df, coluna_data, data):
    serie = df[coluna_data].astype(str)

    mascara = serie.str.startswith(data)

    return df.loc[mascara].copy()


def main():
    print("=" * 80)
    print("VALIDAÇÃO LIVE ENGINE × PIPELINE OFICIAL")
    print("=" * 80)

    print()
    print("Data:", DATA_TESTE)

    for arquivo in ARQUIVOS:
        print()
        print("=" * 80)
        print("ARQUIVO:", arquivo.name)
        print("=" * 80)

        if not arquivo.exists():
            print("Arquivo não encontrado.")
            continue

        df = pd.read_csv(arquivo)

        print()
        print("Linhas totais:", len(df))

        print()
        print("Colunas:")
        for coluna in df.columns:
            print(" -", coluna)

        coluna_data = localizar_coluna_data(df)

        if coluna_data is None:
            print()
            print("Não consegui identificar a coluna de data.")
            continue

        dia = filtrar_data(
            df,
            coluna_data,
            DATA_TESTE,
        )

        print()
        print(
            f"Registros encontrados para {DATA_TESTE}:",
            len(dia),
        )

        if dia.empty:
            continue

        print()
        print("REGISTRO COMPLETO:")
        print()

        for indice, linha in dia.iterrows():
            print("-" * 80)

            for coluna in df.columns:
                print(
                    f"{coluna}: {linha[coluna]}"
                )

            print("-" * 80)


if __name__ == "__main__":
    main()