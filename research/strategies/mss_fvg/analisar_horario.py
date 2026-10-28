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


def classificar_horario(ts: pd.Timestamp) -> str:
    minutos = ts.hour * 60 + ts.minute

    faixas = [
        (570, 630, "09:30-10:30"),
        (630, 690, "10:30-11:30"),
        (690, 750, "11:30-12:30"),
        (750, 810, "12:30-13:30"),
        (810, 870, "13:30-14:30"),
        (870, 930, "14:30-15:30"),
        (930, 960, "15:30-16:00"),
    ]

    for inicio, fim, nome in faixas:
        if inicio <= minutos < fim:
            return nome

    return "FORA_SESSAO"


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

    df["faixa_horario"] = df[
        "setup_timestamp_ny"
    ].apply(
        classificar_horario
    )

    df["win"] = (
        df["resultado_liquido_r"] > 0
    )

    print("=" * 90)
    print("MSS + FVG — ANÁLISE POR HORÁRIO")
    print("=" * 90)

    linhas = []

    ordem = [
        "09:30-10:30",
        "10:30-11:30",
        "11:30-12:30",
        "12:30-13:30",
        "13:30-14:30",
        "14:30-15:30",
        "15:30-16:00",
    ]

    for faixa in ordem:
        parte = df[
            df["faixa_horario"] == faixa
        ]

        if parte.empty:
            continue

        serie = parte[
            "resultado_liquido_r"
        ]

        linhas.append(
            {
                "horario": faixa,
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
    print("RESUMO GERAL POR HORÁRIO")
    print()

    print(
        resumo.to_string(
            index=False,
            float_format=lambda x: f"{x:.4f}",
        )
    )

    print()
    print("=" * 90)
    print("HORÁRIO x DIREÇÃO")
    print("=" * 90)

    direcao = (
        df
        .groupby(
            [
                "faixa_horario",
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
        direcao.to_string(
            float_format=lambda x: f"{x:.4f}"
        )
    )

    print()
    print("=" * 90)
    print("HORÁRIO x ANO")
    print("=" * 90)

    anual = (
        df
        .groupby(
            [
                "faixa_horario",
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
        anual.to_string(
            float_format=lambda x: f"{x:.4f}"
        )
    )

    print()
    print("=" * 90)
    print("MATRIZ — RESULTADO R POR HORÁRIO E ANO")
    print("=" * 90)

    matriz = pd.pivot_table(
        df,
        index="faixa_horario",
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


if __name__ == "__main__":
    main()