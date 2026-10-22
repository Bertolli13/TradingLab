from pathlib import Path
import pandas as pd


DATA = Path("data")

datas = [
    "2025-01-22",
    "2025-08-08",
]


# ---------------------------------------------------------
# Candles
# ---------------------------------------------------------

df = pd.read_parquet(
    DATA / "nq_unificado_validacao.parquet"
)

df["datetime"] = pd.to_datetime(
    df["datetime"],
    utc=True
)

df = df.sort_values("datetime")


# ---------------------------------------------------------
# Comparação dos motores
# ---------------------------------------------------------

cmp = pd.read_csv(
    DATA / "comparacao_v3_backtesting_194.csv"
)

cmp["entrada_time_v3"] = pd.to_datetime(
    cmp["entrada_time_v3"],
    utc=True,
    errors="coerce"
)

cmp["saida_time_v3"] = pd.to_datetime(
    cmp["saida_time_v3"],
    utc=True,
    errors="coerce"
)

cmp["entrada_time_bt"] = pd.to_datetime(
    cmp["entrada_time_bt"],
    utc=True,
    errors="coerce"
)

cmp["saida_time_bt"] = pd.to_datetime(
    cmp["saida_time_bt"],
    utc=True,
    errors="coerce"
)


for data in datas:

    trade = cmp[
        cmp["data_chave"] == data
    ].iloc[0]

    entrada = trade["entrada_time_v3"]

    inicio = entrada - pd.Timedelta(
        minutes=2
    )

    fim = entrada + pd.Timedelta(
        minutes=8
    )

    janela = df[
        (df["datetime"] >= inicio)
        & (df["datetime"] <= fim)
    ].copy()

    print("\n")
    print("=" * 75)
    print("DATA:", data)
    print("=" * 75)

    print(
        "Direção:",
        trade["direcao"]
    )

    print(
        "Entrada:",
        trade["entrada_v3"]
    )

    print(
        "Stop:",
        trade["stop_v3"]
    )

    print(
        "Alvo:",
        trade["alvo_v3"]
    )

    print("\nV3:")
    print(
        "Entrada:",
        trade["entrada_time_v3"]
    )
    print(
        "Saída:",
        trade["saida_time_v3"]
    )
    print(
        "Preço saída:",
        trade["saida_preco_v3"]
    )
    print(
        "Resultado:",
        trade["resultado_r_v3"],
        "R"
    )

    print("\nBacktesting.py:")
    print(
        "Entrada:",
        trade["entrada_time_bt"]
    )
    print(
        "Saída:",
        trade["saida_time_bt"]
    )
    print(
        "Preço saída:",
        trade["saida_preco_bt"]
    )
    print(
        "Resultado:",
        trade["resultado_r_bt"],
        "R"
    )

    print(
        "\nCandles próximos à entrada:"
    )

    print(
        janela[
            [
                "datetime",
                "open",
                "high",
                "low",
                "close",
            ]
        ].to_string(
            index=False
        )
    )