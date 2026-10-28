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


def faixa_15_minutos(ts: pd.Timestamp) -> str:
    minutos = ts.hour * 60 + ts.minute

    inicio_total = 10 * 60 + 30   # 10:30
    fim_total = 12 * 60 + 30      # 12:30

    if not (inicio_total <= minutos < fim_total):
        return "FORA_ANALISE"

    inicio_bloco = (
        minutos // 15
    ) * 15

    fim_bloco = inicio_bloco + 15

    h1 = inicio_bloco // 60
    m1 = inicio_bloco % 60

    h2 = fim_bloco // 60
    m2 = fim_bloco % 60

    return (
        f"{h1:02d}:{m1:02d}-"
        f"{h2:02d}:{m2:02d}"
    )


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

    df["bloco_15m"] = df[
        "setup_timestamp_ny"
    ].apply(
        faixa_15_minutos
    )

    df = df[
        df["bloco_15m"] != "FORA_ANALISE"
    ].copy()

    df["win"] = (
        df["resultado_liquido_r"] > 0
    )

    ordem = [
        "10:30-10:45",
        "10:45-11:00",
        "11:00-11:15",
        "11:15-11:30",
        "11:30-11:45",
        "11:45-12:00",
        "12:00-12:15",
        "12:15-12:30",
    ]

    print("=" * 95)
    print("MSS + FVG — ANÁLISE 15 MINUTOS — 10:30 A 12:30 NY")
    print("=" * 95)

    linhas = []

    for bloco in ordem:
        parte = df[
            df["bloco_15m"] == bloco
        ]

        if parte.empty:
            continue

        serie = parte[
            "resultado_liquido_r"
        ]

        linhas.append(
            {
                "bloco": bloco,
                "trades": len(parte),
                "total_r": serie.sum(),
                "media_r": serie.mean(),
                "mediana_r": serie.median(),
                "win_rate": parte["win"].mean(),
                "profit_factor": profit_factor(
                    serie
                ),
            }
        )

    resumo = pd.DataFrame(
        linhas
    )

    print()
    print("RESUMO GERAL")
    print()

    print(
        resumo.to_string(
            index=False,
            float_format=lambda x: f"{x:.4f}",
        )
    )

    print()
    print("=" * 95)
    print("BLOCO x DIREÇÃO")
    print("=" * 95)

    por_direcao = (
        df
        .groupby(
            [
                "bloco_15m",
                "direcao",
            ]
        )["resultado_liquido_r"]
        .agg(
            [
                "count",
                "sum",
                "mean",
            ]
        )
    )

    print(
        por_direcao.to_string(
            float_format=lambda x: f"{x:.4f}"
        )
    )

    print()
    print("=" * 95)
    print("BLOCO x ANO")
    print("=" * 95)

    por_ano = (
        df
        .groupby(
            [
                "bloco_15m",
                "ano",
            ]
        )["resultado_liquido_r"]
        .agg(
            [
                "count",
                "sum",
                "mean",
            ]
        )
    )

    print(
        por_ano.to_string(
            float_format=lambda x: f"{x:.4f}"
        )
    )

    print()
    print("=" * 95)
    print("MATRIZ TOTAL R — BLOCO x ANO")
    print("=" * 95)

    matriz = pd.pivot_table(
        df,
        index="bloco_15m",
        columns="ano",
        values="resultado_liquido_r",
        aggfunc="sum",
        fill_value=0.0,
    )

    matriz = matriz.reindex(
        ordem
    )

    print(
        matriz.to_string(
            float_format=lambda x: f"{x:.4f}"
        )
    )

    print()
    print("=" * 95)
    print("ACUMULADO POR BLOCO")
    print("=" * 95)

    acumulado = (
        resumo[
            [
                "bloco",
                "total_r",
            ]
        ]
        .copy()
    )

    acumulado[
        "acumulado_r"
    ] = acumulado[
        "total_r"
    ].cumsum()

    print(
        acumulado.to_string(
            index=False,
            float_format=lambda x: f"{x:.4f}",
        )
    )


if __name__ == "__main__":
    main()