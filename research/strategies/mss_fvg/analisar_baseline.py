from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = ROOT / "data"

ARQUIVO = DATA_DIR / "mss_fvg_baseline_trades.csv"


def main():
    df = pd.read_csv(ARQUIVO)

    executadas = df[
        df["executada"] == True
    ].copy()

    print("=" * 72)
    print("AUDITORIA — MSS + FVG BASELINE")
    print("=" * 72)

    print()
    print("TRADES EXECUTADOS")
    print(len(executadas))

    print()
    print("=" * 72)
    print("DIREÇÃO")
    print("=" * 72)

    resumo_direcao = (
        executadas
        .groupby("direcao")
        .agg(
            trades=("resultado_liquido_r", "size"),
            total_r=("resultado_liquido_r", "sum"),
            media_r=("resultado_liquido_r", "mean"),
            mediana_r=("resultado_liquido_r", "median"),
            risco_medio=("risco_pontos", "mean"),
            fvg_medio=("fvg_size", "mean"),
            pnl_usd=("resultado_liquido_usd", "sum"),
        )
    )

    print(resumo_direcao)

    print()
    print("=" * 72)
    print("TIPO x DIREÇÃO")
    print("=" * 72)

    print(
        executadas
        .groupby(
            ["tipo", "direcao"]
        )["resultado_liquido_r"]
        .agg(
            ["count", "sum", "mean", "median"]
        )
    )

    print()
    print("=" * 72)
    print("MOTIVOS DE SAÍDA")
    print("=" * 72)

    motivos = (
        executadas
        .groupby(
            ["direcao", "motivo"]
        )
        .size()
        .sort_values(
            ascending=False
        )
    )

    print(motivos.to_string())

    print()
    print("=" * 72)
    print("TP1")
    print("=" * 72)

    print(
        pd.crosstab(
            executadas["direcao"],
            executadas["tp1_hit"],
            margins=True,
        )
    )

    print()
    print("=" * 72)
    print("RESULTADO POSITIVO / NEGATIVO")
    print("=" * 72)

    executadas["classe"] = "ZERO"

    executadas.loc[
        executadas["resultado_liquido_r"] > 0,
        "classe",
    ] = "WIN"

    executadas.loc[
        executadas["resultado_liquido_r"] < 0,
        "classe",
    ] = "LOSS"

    print(
        pd.crosstab(
            executadas["direcao"],
            executadas["classe"],
            margins=True,
        )
    )

    print()
    print("=" * 72)
    print("10 PIORES SHORTS")
    print("=" * 72)

    colunas = [
        "setup_timestamp_ny",
        "tipo",
        "entrada",
        "stop",
        "risco_pontos",
        "fvg_size",
        "motivo",
        "resultado_bruto_r",
        "custo_usd",
        "resultado_liquido_r",
    ]

    piores_short = (
        executadas[
            executadas["direcao"] == "SHORT"
        ]
        .sort_values(
            "resultado_liquido_r"
        )
        .head(10)
    )

    print(
        piores_short[
            colunas
        ].to_string(
            index=False
        )
    )

    print()
    print("=" * 72)
    print("10 PIORES LONGS")
    print("=" * 72)

    piores_long = (
        executadas[
            executadas["direcao"] == "LONG"
        ]
        .sort_values(
            "resultado_liquido_r"
        )
        .head(10)
    )

    print(
        piores_long[
            colunas
        ].to_string(
            index=False
        )
    )


if __name__ == "__main__":
    main()