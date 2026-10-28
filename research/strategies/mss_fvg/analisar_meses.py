from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = ROOT / "data"

ARQUIVO = DATA_DIR / "mss_fvg_baseline_trades.csv"


def profit_factor(serie: pd.Series) -> float:
    ganhos = serie[serie > 0].sum()
    perdas = -serie[serie < 0].sum()

    if perdas == 0:
        return float("inf")

    return ganhos / perdas


def max_drawdown(serie: pd.Series) -> float:
    equity = serie.cumsum()
    pico = equity.cummax()
    dd = equity - pico

    return float(dd.min())


def main():
    df = pd.read_csv(ARQUIVO)

    df = df[
        df["executada"] == True
    ].copy()

    df["setup_timestamp_ny"] = pd.to_datetime(
        df["setup_timestamp_ny"],
        utc=True,
    ).dt.tz_convert(
        "America/New_York"
    )

    df["ano"] = df[
        "setup_timestamp_ny"
    ].dt.year

    df["mes_num"] = df[
        "setup_timestamp_ny"
    ].dt.month

    df["ano_mes"] = df[
        "setup_timestamp_ny"
    ].dt.strftime("%Y-%m")

    df["win"] = (
        df["resultado_liquido_r"] > 0
    )

    print("=" * 100)
    print("MSS + FVG — ANÁLISE MENSAL")
    print("=" * 100)

    linhas = []

    for ano_mes, parte in df.groupby("ano_mes"):

        serie = parte[
            "resultado_liquido_r"
        ]

        linhas.append(
            {
                "mes": ano_mes,
                "trades": len(parte),
                "total_r": serie.sum(),
                "media_r": serie.mean(),
                "mediana_r": serie.median(),
                "win_rate": parte["win"].mean(),
                "profit_factor": profit_factor(
                    serie
                ),
                "max_dd_r": max_drawdown(
                    serie
                ),
            }
        )

    mensal = pd.DataFrame(
        linhas
    )

    print()
    print("RESULTADO POR MÊS")
    print()

    print(
        mensal.to_string(
            index=False,
            float_format=lambda x: f"{x:.4f}",
        )
    )

    positivos = mensal[
        mensal["total_r"] > 0
    ]

    negativos = mensal[
        mensal["total_r"] < 0
    ]

    zeros = mensal[
        mensal["total_r"] == 0
    ]

    print()
    print("=" * 100)
    print("ESTABILIDADE")
    print("=" * 100)

    print(
        f"Meses analisados: {len(mensal)}"
    )

    print(
        f"Meses positivos: {len(positivos)}"
    )

    print(
        f"Meses negativos: {len(negativos)}"
    )

    print(
        f"Meses zerados: {len(zeros)}"
    )

    if len(mensal) > 0:
        print(
            "Percentual meses positivos:",
            f"{len(positivos) / len(mensal):.2%}",
        )

    print()
    print("Média mensal R:")
    print(
        f"{mensal['total_r'].mean():.4f}"
    )

    print()
    print("Mediana mensal R:")
    print(
        f"{mensal['total_r'].median():.4f}"
    )

    print()
    print("=" * 100)
    print("MELHORES 5 MESES")
    print("=" * 100)

    print(
        mensal
        .sort_values(
            "total_r",
            ascending=False,
        )
        .head(5)
        .to_string(
            index=False,
            float_format=lambda x: f"{x:.4f}",
        )
    )

    print()
    print("=" * 100)
    print("PIORES 5 MESES")
    print("=" * 100)

    print(
        mensal
        .sort_values(
            "total_r"
        )
        .head(5)
        .to_string(
            index=False,
            float_format=lambda x: f"{x:.4f}",
        )
    )

    print()
    print("=" * 100)
    print("MÊS DO ANO — TODOS OS ANOS")
    print("=" * 100)

    por_mes_calendario = (
        df
        .groupby("mes_num")
        ["resultado_liquido_r"]
        .agg(
            [
                "count",
                "sum",
                "mean",
            ]
        )
    )

    print(
        por_mes_calendario.to_string(
            float_format=lambda x: f"{x:.4f}"
        )
    )

    print()
    print("=" * 100)
    print("MATRIZ ANO x MÊS")
    print("=" * 100)

    matriz = pd.pivot_table(
        df,
        index="mes_num",
        columns="ano",
        values="resultado_liquido_r",
        aggfunc="sum",
        fill_value=0.0,
    )

    print(
        matriz.to_string(
            float_format=lambda x: f"{x:.4f}"
        )
    )

    print()
    print("=" * 100)
    print("CONCENTRAÇÃO DO RESULTADO")
    print("=" * 100)

    total_r = mensal[
        "total_r"
    ].sum()

    top_3 = (
        mensal
        .nlargest(
            3,
            "total_r",
        )["total_r"]
        .sum()
    )

    top_5 = (
        mensal
        .nlargest(
            5,
            "total_r",
        )["total_r"]
        .sum()
    )

    print(
        f"Resultado total: {total_r:.4f} R"
    )

    print(
        f"Top 3 meses: {top_3:.4f} R"
    )

    if total_r != 0:
        print(
            "Top 3 / total:",
            f"{top_3 / total_r:.2%}",
        )

    print(
        f"Top 5 meses: {top_5:.4f} R"
    )

    if total_r != 0:
        print(
            "Top 5 / total:",
            f"{top_5 / total_r:.2%}",
        )


if __name__ == "__main__":
    main()