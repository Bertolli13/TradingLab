from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from config import MSSFVGBaselineConfig


ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = ROOT / "data"

ARQUIVO_DADOS = DATA_DIR / "nq_unificado_validacao.parquet"
ARQUIVO_SINAIS = DATA_DIR / "mss_fvg_baseline_sinais.csv"

ARQUIVO_TRADES = DATA_DIR / "mss_fvg_baseline_trades.csv"
ARQUIVO_RESUMO = DATA_DIR / "mss_fvg_baseline_resumo.csv"
ARQUIVO_ANOS = DATA_DIR / "mss_fvg_baseline_anos.csv"


def carregar_dados() -> pd.DataFrame:
    df = pd.read_parquet(ARQUIVO_DADOS).copy()

    df.columns = [
        str(c).lower().strip()
        for c in df.columns
    ]

    if isinstance(df.index, pd.DatetimeIndex):
        df = df.reset_index()

    candidatos = [
        "timestamp",
        "datetime",
        "date",
        "time",
        "datahora",
        "index",
    ]

    coluna_ts = None

    for coluna in candidatos:
        if coluna in df.columns:
            coluna_ts = coluna
            break

    if coluna_ts is None:
        raise ValueError(
            "Não foi possível localizar timestamp."
        )

    df[coluna_ts] = pd.to_datetime(
        df[coluna_ts],
        utc=True,
        errors="coerce",
    )

    df = df.rename(
        columns={
            coluna_ts: "timestamp_utc",
        }
    )

    df = (
        df
        .dropna(
            subset=[
                "timestamp_utc",
                "open",
                "high",
                "low",
                "close",
            ]
        )
        .sort_values("timestamp_utc")
        .reset_index(drop=True)
    )

    return df


def carregar_sinais() -> pd.DataFrame:
    df = pd.read_csv(
        ARQUIVO_SINAIS,
    )

    df["timestamp_utc"] = pd.to_datetime(
        df["timestamp_utc"],
        utc=True,
    )

    df["timestamp_ny"] = pd.to_datetime(
        df["timestamp_ny"],
        utc=True,
    ).dt.tz_convert(
        "America/New_York"
    )

    return (
        df
        .sort_values("timestamp_utc")
        .reset_index(drop=True)
    )


def calcular_custo_usd(
    contratos: int,
    cfg: MSSFVGBaselineConfig,
) -> float:

    slippage_pontos = (
        cfg.slippage_ticks_per_order
        * cfg.tick_size
    )

    slippage_usd_por_lado = (
        slippage_pontos
        * cfg.point_value_usd
        * contratos
    )

    comissao_usd_por_lado = (
        cfg.commission_per_contract_side_usd
        * contratos
    )

    # Entrada + saída.
    return 2.0 * (
        slippage_usd_por_lado
        + comissao_usd_por_lado
    )


def simular_setup(
    dados: pd.DataFrame,
    sinal: pd.Series,
    idx_sinal: int,
    cfg: MSSFVGBaselineConfig,
) -> dict:

    direcao = sinal["direcao"]

    entrada = float(
        sinal["entry"]
    )

    stop_inicial = float(
        sinal["stop"]
    )

    risco = float(
        sinal["risk_points"]
    )

    if risco <= 0:
        raise ValueError(
            "Risco inválido."
        )

    if direcao == "LONG":
        alvos = [
            entrada
            + risco * cfg.target_1_r,

            entrada
            + risco * cfg.target_2_r,

            entrada
            + risco * cfg.target_3_r,
        ]

    else:
        alvos = [
            entrada
            - risco * cfg.target_1_r,

            entrada
            - risco * cfg.target_2_r,

            entrada
            - risco * cfg.target_3_r,
        ]

    contratos = cfg.contracts

    q1 = contratos // 3
    q2 = q1
    q3 = contratos - q1 - q2

    quantidades = [
        q1,
        q2,
        q3,
    ]

    restante = contratos

    executada = False

    entrada_ts = None
    saida_ts = None

    stop_atual = stop_inicial

    t1_hit = False

    alvos_feitos = [
        False,
        False,
        False,
    ]

    # BE entra em vigor a partir da barra seguinte
    # à realização do primeiro alvo.
    ativar_be_proxima_barra = False

    pnl_bruto_usd = 0.0

    motivos_saida = []

    ultima_barra = min(
        idx_sinal
        + cfg.max_setup_age_bars,
        len(dados) - 1,
    )

    idx_fim = idx_sinal

    # Ordem nasce no fechamento da barra do setup.
    # Portanto começa a poder preencher na próxima.
    for i in range(
        idx_sinal + 1,
        len(dados),
    ):
        row = dados.iloc[i]

        idx_fim = i

        # ------------------------------------------
        # Ordem ainda pendente
        # ------------------------------------------

        if not executada:

            if i > ultima_barra:
                return {
                    "executada": False,
                    "motivo": "EXPIRADA",
                    "idx_fim": i,
                }

            if direcao == "LONG":

                tocou_entrada = (
                    row["low"] <= entrada
                )

                tocou_stop = (
                    row["low"] <= stop_inicial
                )

                if tocou_entrada:
                    executada = True
                    entrada_ts = row[
                        "timestamp_utc"
                    ]

                    # Cenário conservador:
                    # entrada e stop na mesma barra
                    # = considera stop.
                    if tocou_stop:

                        pnl_bruto_usd = (
                            -risco
                            * cfg.point_value_usd
                            * contratos
                        )

                        restante = 0
                        saida_ts = row[
                            "timestamp_utc"
                        ]

                        motivos_saida.append(
                            "STOP_MESMA_BARRA_ENTRADA"
                        )

                        break

                elif tocou_stop:

                    return {
                        "executada": False,
                        "motivo": "INVALIDADA_ANTES_ENTRADA",
                        "idx_fim": i,
                    }

            else:

                tocou_entrada = (
                    row["high"] >= entrada
                )

                tocou_stop = (
                    row["high"] >= stop_inicial
                )

                if tocou_entrada:
                    executada = True
                    entrada_ts = row[
                        "timestamp_utc"
                    ]

                    if tocou_stop:

                        pnl_bruto_usd = (
                            -risco
                            * cfg.point_value_usd
                            * contratos
                        )

                        restante = 0
                        saida_ts = row[
                            "timestamp_utc"
                        ]

                        motivos_saida.append(
                            "STOP_MESMA_BARRA_ENTRADA"
                        )

                        break

                elif tocou_stop:

                    return {
                        "executada": False,
                        "motivo": "INVALIDADA_ANTES_ENTRADA",
                        "idx_fim": i,
                    }

            if not executada:
                continue

        # ------------------------------------------
        # Já estamos posicionados
        # ------------------------------------------

        if ativar_be_proxima_barra:

            if (
                cfg
                .move_stop_to_break_even_after_target_1
            ):
                stop_atual = entrada

            ativar_be_proxima_barra = False

        if restante <= 0:
            break

        # ------------------------------------------
        # LONG
        # ------------------------------------------

        if direcao == "LONG":

            stop_hit = (
                row["low"] <= stop_atual
            )

            # Regra conservadora:
            # se stop e alvo aparecem na mesma barra,
            # stop vem primeiro.
            if stop_hit:

                pnl_bruto_usd += (
                    (stop_atual - entrada)
                    * cfg.point_value_usd
                    * restante
                )

                motivos_saida.append(
                    "STOP"
                    if stop_atual != entrada
                    else "BREAK_EVEN"
                )

                restante = 0
                saida_ts = row[
                    "timestamp_utc"
                ]

                break

            for alvo_idx in range(3):

                qtd = quantidades[
                    alvo_idx
                ]

                if qtd <= 0:
                    continue

                if restante <= 0:
                    break

                alvo = alvos[
                    alvo_idx
                ]

                # Só pode realizar alvo
                # ainda não realizado.
                if alvos_feitos[
                    alvo_idx
                ]:
                    continue

                if row["high"] >= alvo:

                    pnl_bruto_usd += (
                        (alvo - entrada)
                        * cfg.point_value_usd
                        * qtd
                    )

                    restante -= qtd

                    alvos_feitos[
                        alvo_idx
                    ] = True

                    motivos_saida.append(
                        f"TP{alvo_idx + 1}"
                    )

                    if alvo_idx == 0:

                        t1_hit = True

                        ativar_be_proxima_barra = True

        # ------------------------------------------
        # SHORT
        # ------------------------------------------

        else:

            stop_hit = (
                row["high"] >= stop_atual
            )

            if stop_hit:

                pnl_bruto_usd += (
                    (entrada - stop_atual)
                    * cfg.point_value_usd
                    * restante
                )

                motivos_saida.append(
                    "STOP"
                    if stop_atual != entrada
                    else "BREAK_EVEN"
                )

                restante = 0
                saida_ts = row[
                    "timestamp_utc"
                ]

                break

            for alvo_idx in range(3):

                qtd = quantidades[
                    alvo_idx
                ]

                if qtd <= 0:
                    continue

                if restante <= 0:
                    break

                alvo = alvos[
                    alvo_idx
                ]

                # Alvo já realizado anteriormente.
                if alvos_feitos[
                    alvo_idx
                ]:
                    continue

                if row["low"] <= alvo:

                    pnl_bruto_usd += (
                        (entrada - alvo)
                        * cfg.point_value_usd
                        * qtd
                    )

                    restante -= qtd

                    alvos_feitos[
                        alvo_idx
                    ] = True

                    motivos_saida.append(
                        f"TP{alvo_idx + 1}"
                    )

                    if alvo_idx == 0:

                        t1_hit = True

                        ativar_be_proxima_barra = True

        if restante == 0:

            saida_ts = row[
                "timestamp_utc"
            ]

            break

    if not executada:

        return {
            "executada": False,
            "motivo": "SEM_RETESTE",
            "idx_fim": idx_fim,
        }

    # Se chegou ao final dos dados ainda aberto.
    if restante > 0:

        ultimo_close = float(
            dados.iloc[idx_fim]["close"]
        )

        if direcao == "LONG":
            pnl_bruto_usd += (
                (ultimo_close - entrada)
                * cfg.point_value_usd
                * restante
            )

        else:
            pnl_bruto_usd += (
                (entrada - ultimo_close)
                * cfg.point_value_usd
                * restante
            )

        motivos_saida.append(
            "FIM_DADOS"
        )

        saida_ts = dados.iloc[
            idx_fim
        ]["timestamp_utc"]

        restante = 0

    custo_usd = calcular_custo_usd(
        contratos,
        cfg,
    )

    pnl_liquido_usd = (
        pnl_bruto_usd
        - custo_usd
    )

    risco_total_usd = (
        risco
        * cfg.point_value_usd
        * contratos
    )

    bruto_r = (
        pnl_bruto_usd
        / risco_total_usd
    )

    liquido_r = (
        pnl_liquido_usd
        / risco_total_usd
    )

    return {
        "executada": True,
        "motivo": "+".join(
            motivos_saida
        ),
        "idx_fim": idx_fim,
        "entrada_ts": entrada_ts,
        "saida_ts": saida_ts,
        "entrada": entrada,
        "stop": stop_inicial,
        "alvo_1": alvos[0],
        "alvo_2": alvos[1],
        "alvo_3": alvos[2],
        "risco_pontos": risco,
        "tp1_hit": t1_hit,
        "resultado_bruto_usd":
            pnl_bruto_usd,
        "custo_usd":
            custo_usd,
        "resultado_liquido_usd":
            pnl_liquido_usd,
        "resultado_bruto_r":
            bruto_r,
        "resultado_liquido_r":
            liquido_r,
    }


def profit_factor(
    serie: pd.Series,
) -> float:

    ganhos = serie[
        serie > 0
    ].sum()

    perdas = -serie[
        serie < 0
    ].sum()

    if perdas == 0:
        return np.inf

    return ganhos / perdas


def max_drawdown_r(
    serie: pd.Series,
) -> float:

    equity = serie.cumsum()

    pico = equity.cummax()

    dd = equity - pico

    return float(
        dd.min()
    )


def main():

    cfg = MSSFVGBaselineConfig()

    print("=" * 72)
    print(
        "MSS + FVG — BACKTEST BASELINE CAUSAL"
    )
    print("=" * 72)

    dados = carregar_dados()

    sinais = carregar_sinais()

    mapa_idx = {
        ts: i
        for i, ts
        in enumerate(
            dados["timestamp_utc"]
        )
    }

    resultados = []

    ocupado_ate = -1

    ignorados_ocupado = 0

    for _, sinal in sinais.iterrows():

        ts = sinal[
            "timestamp_utc"
        ]

        if ts not in mapa_idx:
            continue

        idx = mapa_idx[
            ts
        ]

        # Um setup/trade por vez.
        if idx <= ocupado_ate:

            ignorados_ocupado += 1
            continue

        resultado = simular_setup(
            dados=dados,
            sinal=sinal,
            idx_sinal=idx,
            cfg=cfg,
        )

        ocupado_ate = resultado[
            "idx_fim"
        ]

        registro = {
            "setup_timestamp_utc":
                ts,

            "setup_timestamp_ny":
                sinal["timestamp_ny"],

            "direcao":
                sinal["direcao"],

            "tipo":
                sinal["tipo"],

            "fvg_size":
                sinal["fvg_size"],

            "setup_risk_points":
                sinal["risk_points"],
        }

        registro.update(
            resultado
        )

        resultados.append(
            registro
        )

    df = pd.DataFrame(
        resultados
    )

    df.to_csv(
        ARQUIVO_TRADES,
        index=False,
    )

    executadas = df[
        df["executada"] == True
    ].copy()

    print()
    print(
        f"Setups candidatos: "
        f"{len(sinais):,}"
    )

    print(
        f"Setups processados: "
        f"{len(df):,}"
    )

    print(
        f"Ignorados por posição/"
        f"ordem ativa: "
        f"{ignorados_ocupado:,}"
    )

    print(
        f"Trades executados: "
        f"{len(executadas):,}"
    )

    if executadas.empty:
        print(
            "Nenhum trade executado."
        )
        return

    executadas[
        "ano"
    ] = pd.to_datetime(
        executadas[
            "setup_timestamp_utc"
        ],
        utc=True,
    ).dt.year

    serie = executadas[
        "resultado_liquido_r"
    ]

    wins = int(
        (serie > 0).sum()
    )

    losses = int(
        (serie < 0).sum()
    )

    zeros = int(
        (serie == 0).sum()
    )

    resumo = {
        "setups_candidatos":
            len(sinais),

        "setups_processados":
            len(df),

        "ignorados_ocupado":
            ignorados_ocupado,

        "trades_executados":
            len(executadas),

        "wins":
            wins,

        "losses":
            losses,

        "zeros":
            zeros,

        "win_rate":
            wins
            / len(executadas),

        "resultado_total_r":
            serie.sum(),

        "media_r":
            serie.mean(),

        "mediana_r":
            serie.median(),

        "profit_factor":
            profit_factor(
                serie
            ),

        "max_drawdown_r":
            max_drawdown_r(
                serie
            ),

        "resultado_total_usd":
            executadas[
                "resultado_liquido_usd"
            ].sum(),
    }

    pd.DataFrame(
        [resumo]
    ).to_csv(
        ARQUIVO_RESUMO,
        index=False,
    )

    anual = (
        executadas
        .groupby("ano")
        .agg(
            trades=(
                "resultado_liquido_r",
                "size",
            ),
            resultado_r=(
                "resultado_liquido_r",
                "sum",
            ),
            media_r=(
                "resultado_liquido_r",
                "mean",
            ),
            resultado_usd=(
                "resultado_liquido_usd",
                "sum",
            ),
        )
        .reset_index()
    )

    anual.to_csv(
        ARQUIVO_ANOS,
        index=False,
    )

    print()
    print("=" * 72)
    print("RESUMO")
    print("=" * 72)

    for k, v in resumo.items():

        if isinstance(
            v,
            float,
        ):
            print(
                f"{k}: "
                f"{v:.6f}"
            )
        else:
            print(
                f"{k}: {v}"
            )

    print()
    print("POR TIPO")

    print(
        executadas
        .groupby("tipo")[
            "resultado_liquido_r"
        ]
        .agg(
            [
                "count",
                "sum",
                "mean",
            ]
        )
    )

    print()
    print("POR DIREÇÃO")

    print(
        executadas
        .groupby("direcao")[
            "resultado_liquido_r"
        ]
        .agg(
            [
                "count",
                "sum",
                "mean",
            ]
        )
    )

    print()
    print("POR ANO")
    print(
        anual.to_string(
            index=False
        )
    )

    print()
    print(
        f"Trades:\n"
        f"{ARQUIVO_TRADES}"
    )

    print(
        f"\nResumo:\n"
        f"{ARQUIVO_RESUMO}"
    )

    print(
        f"\nAnos:\n"
        f"{ARQUIVO_ANOS}"
    )


if __name__ == "__main__":
    main()