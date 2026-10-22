from pathlib import Path

import numpy as np
import pandas as pd


DATA = Path("data")

DATA_CORTE = pd.Timestamp("2026-10-08")

FVG_MIN = 6.0
FVG_MAX = 12.0


def max_drawdown(resultados):
    resultados = np.asarray(resultados, dtype=float)

    equity = np.concatenate([
        np.array([0.0]),
        np.cumsum(resultados)
    ])

    pico = np.maximum.accumulate(equity)

    drawdown = equity - pico

    return drawdown.min()


def localizar_execucao_mais_recente():
    pastas = sorted(
        DATA.glob("v4_forward_*"),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )

    if not pastas:
        raise FileNotFoundError(
            "Nenhuma pasta v4_forward_* encontrada em data."
        )

    for pasta in pastas:
        arquivo = pasta / "backtest_v3.csv"

        if arquivo.exists():
            return pasta

    raise FileNotFoundError(
        "Nenhuma execução v4_forward contém backtest_v3.csv."
    )


def resumo(grupo):
    if grupo.empty:
        return {
            "operacoes": 0,
            "wins": 0,
            "losses": 0,
            "win_rate_pct": 0.0,
            "bruto_r": 0.0,
            "liquido_r": 0.0,
            "media_liquida_r": 0.0,
            "profit_factor": np.nan,
            "max_drawdown_r": 0.0,
            "liquido_usd": 0.0,
        }

    r_liquido = pd.to_numeric(
        grupo["resultado_liquido_r"],
        errors="coerce"
    )

    r_bruto = pd.to_numeric(
        grupo["resultado_bruto_r"],
        errors="coerce"
    )

    usd = pd.to_numeric(
        grupo["resultado_liquido_usd"],
        errors="coerce"
    )

    ganhos = r_liquido[
        r_liquido > 0
    ].sum()

    perdas = -r_liquido[
        r_liquido < 0
    ].sum()

    pf = (
        ganhos / perdas
        if perdas > 0
        else np.inf
    )

    return {
        "operacoes": len(grupo),

        "wins":
            int((r_liquido > 0).sum()),

        "losses":
            int((r_liquido < 0).sum()),

        "win_rate_pct":
            (r_liquido > 0).mean() * 100,

        "bruto_r":
            r_bruto.sum(),

        "liquido_r":
            r_liquido.sum(),

        "media_liquida_r":
            r_liquido.mean(),

        "profit_factor":
            pf,

        "max_drawdown_r":
            max_drawdown(
                r_liquido.fillna(0).to_numpy()
            ),

        "liquido_usd":
            usd.sum(),
    }


def main():
    pasta = localizar_execucao_mais_recente()

    arquivo = pasta / "backtest_v3.csv"

    print()
    print("=" * 75)
    print("FORWARD TEST V4 - PLACAR OFICIAL")
    print("=" * 75)

    print(
        "Execução usada:",
        pasta
    )

    df = pd.read_csv(
        arquivo,
        dtype={
            "data": str
        }
    )

    df["data_dt"] = pd.to_datetime(
        df["data"],
        errors="raise"
    )

    df["executada_bool"] = (
        df["executada"]
        .astype(str)
        .str.lower()
        .isin([
            "true",
            "1",
            "sim"
        ])
    )

    df["ambiguo_bool"] = (
        df["ambiguo"]
        .astype(str)
        .str.lower()
        .isin([
            "true",
            "1",
            "sim"
        ])
    )

    # =====================================================
    # 1. SOMENTE FORWARD / OOS
    # =====================================================

    oos = df[
        df["data_dt"] > DATA_CORTE
    ].copy()

    print()
    print("Data de corte:", DATA_CORTE.date())

    if oos.empty:
        print()
        print(
            "Ainda não existem registros OOS."
        )
        return


    # =====================================================
    # 2. CENÁRIO CONSERVADOR
    # =====================================================

    conservador = oos[
        (
            oos["cenario"]
            .astype(str)
            .str.lower()
            == "conservador"
        )
        &
        (
            oos["executada_bool"]
        )
    ].copy()


    # =====================================================
    # 3. CENÁRIO EXCLUSÃO
    # =====================================================

    exclusao = oos[
        (
            oos["cenario"]
            .astype(str)
            .str.lower()
            == "exclusao"
        )
        &
        (
            oos["executada_bool"]
        )
        &
        (
            oos["incluida"]
            .astype(str)
            .str.lower()
            .isin([
                "true",
                "1",
                "sim"
            ])
        )
    ].copy()


    # =====================================================
    # 4. AMBÍGUOS
    # =====================================================

    ambiguos = conservador[
        conservador["ambiguo_bool"]
    ].copy()

    nao_ambiguos = conservador[
        ~conservador["ambiguo_bool"]
    ].copy()


    # =====================================================
    # 5. RESUMOS
    # =====================================================

    r_cons = resumo(
        conservador
    )

    r_exc = resumo(
        exclusao
    )

    r_amb = resumo(
        ambiguos
    )

    r_nao_amb = resumo(
        nao_ambiguos
    )


    # =====================================================
    # 6. PLACAR
    # =====================================================

    placar = pd.DataFrame([
        {
            "modelo": "V3_conservador",
            **r_cons
        },
        {
            "modelo": "V3_exclusao",
            **r_exc
        },
        {
            "modelo": "Somente_ambiguos",
            **r_amb
        },
        {
            "modelo": "Somente_nao_ambiguos",
            **r_nao_amb
        },
    ])

    print()
    print("=" * 75)
    print("PLACAR OOS")
    print("=" * 75)

    print(
        placar.to_string(
            index=False
        )
    )


    # =====================================================
    # 7. TRADES CONSERVADOR
    # =====================================================

    colunas = [
        "data",
        "direcao",
        "entrada",
        "stop",
        "alvo",
        "risco_pontos",
        "horario_entrada",
        "horario_saida",
        "motivo_saida",
        "ambiguo",
        "resultado_bruto_r",
        "custo_r",
        "resultado_liquido_r",
        "resultado_liquido_usd",
    ]

    colunas = [
        c
        for c in colunas
        if c in conservador.columns
    ]

    print()
    print("=" * 75)
    print("TRADES OOS - CONSERVADOR")
    print("=" * 75)

    if conservador.empty:
        print(
            "Nenhuma operação OOS executada."
        )
    else:
        print(
            conservador[
                colunas
            ].sort_values(
                "data"
            ).to_string(
                index=False
            )
        )


    # =====================================================
    # 8. ACUMULADO
    # =====================================================

    if not conservador.empty:
        curva = conservador.sort_values(
            "data"
        ).copy()

        curva[
            "resultado_acumulado_r"
        ] = pd.to_numeric(
            curva["resultado_liquido_r"],
            errors="coerce"
        ).cumsum()

        curva[
            "resultado_acumulado_usd"
        ] = pd.to_numeric(
            curva["resultado_liquido_usd"],
            errors="coerce"
        ).cumsum()

        print()
        print("=" * 75)
        print("EVOLUÇÃO OOS")
        print("=" * 75)

        print(
            curva[
                [
                    "data",
                    "direcao",
                    "ambiguo",
                    "resultado_liquido_r",
                    "resultado_acumulado_r",
                    "resultado_liquido_usd",
                    "resultado_acumulado_usd",
                ]
            ].to_string(
                index=False
            )
        )


    # =====================================================
    # 9. EXPORTAR
    # =====================================================

    placar.to_csv(
        DATA / "forward_placar_v4.csv",
        index=False
    )

    conservador.to_csv(
        DATA / "forward_trades_conservador_v4.csv",
        index=False
    )

    exclusao.to_csv(
        DATA / "forward_trades_exclusao_v4.csv",
        index=False
    )

    print()
    print("Arquivos criados:")

    print(
        DATA / "forward_placar_v4.csv"
    )

    print(
        DATA / "forward_trades_conservador_v4.csv"
    )

    print(
        DATA / "forward_trades_exclusao_v4.csv"
    )


if __name__ == "__main__":
    main()