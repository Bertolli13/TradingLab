from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "data"

ARQUIVO = DATA / "mss_fvg_reversal_only_trades.csv"


def main():
    df = pd.read_csv(ARQUIVO)

    df = df[
        df["executada"] == True
    ].copy()

    bins = [
        0,
        5,
        7.5,
        10,
        15,
        20,
        30,
        40,
        50,
    ]

    labels = [
        "<5",
        "5-7.5",
        "7.5-10",
        "10-15",
        "15-20",
        "20-30",
        "30-40",
        "40-50",
    ]

    df["faixa_risco"] = pd.cut(
        df["risco_pontos"],
        bins=bins,
        labels=labels,
        right=False,
    )

    print("=" * 80)
    print("MSS + FVG — ANÁLISE POR RISCO")
    print("=" * 80)

    resumo = (
        df
        .groupby(
            "faixa_risco",
            observed=True,
        )
        .agg(
            trades=(
                "resultado_liquido_r",
                "size",
            ),
            total_r=(
                "resultado_liquido_r",
                "sum",
            ),
            media_r=(
                "resultado_liquido_r",
                "mean",
            ),
            mediana_r=(
                "resultado_liquido_r",
                "median",
            ),
            bruto_r=(
                "resultado_bruto_r",
                "sum",
            ),
            pnl_usd=(
                "resultado_liquido_usd",
                "sum",
            ),
        )
    )

    resumo["win_rate"] = (
        df
        .assign(
            win=df["resultado_liquido_r"] > 0
        )
        .groupby(
            "faixa_risco",
            observed=True,
        )["win"]
        .mean()
    )

    print()
    print(resumo.to_string())

    print()
    print("=" * 80)
    print("LONG")
    print("=" * 80)

    print(
        df[
            df["direcao"] == "LONG"
        ]
        .groupby(
            "faixa_risco",
            observed=True,
        )["resultado_liquido_r"]
        .agg(
            ["count", "sum", "mean"]
        )
        .to_string()
    )

    print()
    print("=" * 80)
    print("SHORT")
    print("=" * 80)

    print(
        df[
            df["direcao"] == "SHORT"
        ]
        .groupby(
            "faixa_risco",
            observed=True,
        )["resultado_liquido_r"]
        .agg(
            ["count", "sum", "mean"]
        )
        .to_string()
    )

    print()
    print("=" * 80)
    print("BRUTO x LÍQUIDO")
    print("=" * 80)

    print(
        "Resultado bruto total R:",
        round(
            df["resultado_bruto_r"].sum(),
            6,
        ),
    )

    print(
        "Resultado líquido total R:",
        round(
            df["resultado_liquido_r"].sum(),
            6,
        ),
    )

    print(
        "Diferença causada pelos custos em R:",
        round(
            (
                df["resultado_bruto_r"].sum()
                - df["resultado_liquido_r"].sum()
            ),
            6,
        ),
    )


if __name__ == "__main__":
    main()
    