from pathlib import Path
import subprocess
import sys
import pandas as pd


PROJETO = Path(__file__).resolve().parent
DATA = PROJETO / "data"

SCRIPT_BACKTEST = PROJETO / "backtest_v5_research.py"

STOPS = [
    "vela_fvg",
    "range_50",
    "range_75",
]

RRS = [
    1.00,
    1.25,
    1.50,
    2.00,
]


def executar_backtest(stop_modelo, rr_alvo):
    pasta_saida = (
        DATA
        / f"v5_grid_{stop_modelo}_rr_{str(rr_alvo).replace('.', '_')}"
    )

    if pasta_saida.exists():
        raise FileExistsError(
            f"A pasta já existe: {pasta_saida}"
        )

    comando = [
        sys.executable,
        str(SCRIPT_BACKTEST),
        "--stop-modelo",
        stop_modelo,
        "--rr-alvo",
        str(rr_alvo),
        "--output-dir",
        str(pasta_saida),
    ]

    print()
    print("=" * 80)
    print(
        f"STOP={stop_modelo} | RR={rr_alvo}"
    )
    print("=" * 80)

    subprocess.run(
        comando,
        cwd=PROJETO,
        check=True
    )

    return pasta_saida


def ler_resumo(pasta, stop_modelo, rr_alvo):
    arquivo = pasta / "comparacao_resumo.csv"

    df = pd.read_csv(arquivo)

    linha = df[
        (df["modelo"] == "V3_conservador")
        & (df["universo"] == "original")
    ]

    if len(linha) != 1:
        raise ValueError(
            "Não foi possível localizar "
            "V3_conservador/original"
        )

    linha = linha.iloc[0]

    return {
        "stop_modelo": stop_modelo,
        "rr_alvo": rr_alvo,
        "sinais": linha["sinais"],
        "operacoes": linha["operacoes"],
        "excluidos": linha["excluidos"],
        "ambiguos": linha["ambiguos"],
        "win_rate_pct": linha[
            "win_rate_liquido_pct"
        ],
        "bruto_r": linha["bruto_r"],
        "liquido_r": linha["liquido_r"],
        "media_liquida_r": linha[
            "media_liquida_r"
        ],
        "profit_factor": linha[
            "profit_factor"
        ],
        "max_drawdown_r": linha[
            "max_drawdown_r"
        ],
        "liquido_usd": linha[
            "liquido_usd"
        ],
        "pasta": str(pasta),
    }


def ler_anos(pasta, stop_modelo, rr_alvo):
    arquivo = pasta / "estatisticas_anuais.csv"

    df = pd.read_csv(arquivo)

    df = df[
        df["modelo"] == "V3_conservador"
    ].copy()

    df["stop_modelo"] = stop_modelo
    df["rr_alvo"] = rr_alvo

    colunas = [
        "stop_modelo",
        "rr_alvo",
        "ano",
        "sinais",
        "operacoes",
        "excluidos",
        "ambiguos",
        "win_rate_liquido_pct",
        "bruto_r",
        "liquido_r",
        "media_liquida_r",
        "profit_factor",
        "max_drawdown_r",
        "liquido_usd",
    ]

    return df[colunas]


def main():
    resultados = []
    resultados_anuais = []

    print()
    print("=" * 80)
    print("V5 RESEARCH - GRID STOP x RR")
    print("=" * 80)

    for stop_modelo in STOPS:
        for rr_alvo in RRS:

            pasta = executar_backtest(
                stop_modelo,
                rr_alvo
            )

            resumo = ler_resumo(
                pasta,
                stop_modelo,
                rr_alvo
            )

            resultados.append(
                resumo
            )

            anual = ler_anos(
                pasta,
                stop_modelo,
                rr_alvo
            )

            resultados_anuais.append(
                anual
            )

    resumo_df = pd.DataFrame(
        resultados
    )

    anual_df = pd.concat(
        resultados_anuais,
        ignore_index=True
    )

    resumo_df = resumo_df.sort_values(
        [
            "liquido_r",
            "profit_factor",
        ],
        ascending=[
            False,
            False,
        ]
    )

    resumo_saida = (
        DATA
        / "v5_grid_resumo.csv"
    )

    anual_saida = (
        DATA
        / "v5_grid_anos.csv"
    )

    resumo_df.to_csv(
        resumo_saida,
        index=False
    )

    anual_df.to_csv(
        anual_saida,
        index=False
    )

    print()
    print("=" * 80)
    print("RANKING V5 - V3 CONSERVADOR")
    print("=" * 80)

    print(
        resumo_df[
            [
                "stop_modelo",
                "rr_alvo",
                "operacoes",
                "win_rate_pct",
                "liquido_r",
                "media_liquida_r",
                "profit_factor",
                "max_drawdown_r",
                "ambiguos",
                "excluidos",
            ]
        ].to_string(
            index=False
        )
    )

    print()
    print("Arquivos criados:")
    print(resumo_saida)
    print(anual_saida)


if __name__ == "__main__":
    main()