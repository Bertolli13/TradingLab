from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd

from config import MSSFVGBaselineConfig


ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = ROOT / "data"

ARQUIVO_BASE = DATA_DIR / "nq_unificado_validacao.parquet"
ARQUIVO_SAIDA = DATA_DIR / "mss_fvg_baseline_sinais.csv"


def carregar_dados(caminho: Path) -> pd.DataFrame:
    df = pd.read_parquet(caminho).copy()

    # Normaliza nomes
    df.columns = [str(c).lower().strip() for c in df.columns]

    candidatos_ts = [
        "timestamp",
        "datetime",
        "date",
        "time",
        "datahora",
    ]

    coluna_ts = None
    for c in candidatos_ts:
        if c in df.columns:
            coluna_ts = c
            break

    if coluna_ts is None:
        if isinstance(df.index, pd.DatetimeIndex):
            df = df.reset_index()
            coluna_ts = df.columns[0]
        else:
            raise ValueError(
                "Não encontrei coluna de timestamp na base."
            )

    df[coluna_ts] = pd.to_datetime(
        df[coluna_ts],
        utc=True,
        errors="coerce",
    )

    df = df.rename(columns={coluna_ts: "timestamp_utc"})

    obrigatorias = ["open", "high", "low", "close"]

    faltantes = [
        c
        for c in obrigatorias
        if c not in df.columns
    ]

    if faltantes:
        raise ValueError(
            f"Colunas OHLC ausentes: {faltantes}"
        )

    df = df.dropna(
        subset=[
            "timestamp_utc",
            "open",
            "high",
            "low",
            "close",
        ]
    )

    df = df.sort_values("timestamp_utc").reset_index(drop=True)

    df["timestamp_ny"] = (
        df["timestamp_utc"]
        .dt.tz_convert("America/New_York")
    )

    return df


def dentro_sessao(
    ts_ny: pd.Timestamp,
    inicio: str,
    fim: str,
) -> bool:
    hora = ts_ny.strftime("%H:%M")
    return inicio <= hora < fim

def dentro_horario_bloqueado(
    ts_ny: pd.Timestamp,
    inicio: str,
    fim: str,
) -> bool:
    hora = ts_ny.strftime("%H:%M")

    return inicio <= hora < fim

def detectar_pivos(
    df: pd.DataFrame,
    piv: int,
) -> pd.DataFrame:
    out = df.copy()

    n = len(out)

    pivot_high = np.full(n, np.nan)
    pivot_low = np.full(n, np.nan)

    confirmado_em_high = np.full(n, -1, dtype=int)
    confirmado_em_low = np.full(n, -1, dtype=int)

    highs = out["high"].to_numpy()
    lows = out["low"].to_numpy()

    # Pine:
    # ta.pivothigh(high, piv, piv)
    # ta.pivotlow(low, piv, piv)
    #
    # O pivô só é conhecido "piv" barras depois.
    for centro in range(piv, n - piv):
        janela_h = highs[
            centro - piv:
            centro + piv + 1
        ]

        janela_l = lows[
            centro - piv:
            centro + piv + 1
        ]

        if highs[centro] == np.max(janela_h):
            confirmacao = centro + piv

            pivot_high[centro] = highs[centro]
            confirmado_em_high[centro] = confirmacao

        if lows[centro] == np.min(janela_l):
            confirmacao = centro + piv

            pivot_low[centro] = lows[centro]
            confirmado_em_low[centro] = confirmacao

    out["pivot_high"] = pivot_high
    out["pivot_low"] = pivot_low

    out["pivot_high_confirmado_em"] = confirmado_em_high
    out["pivot_low_confirmado_em"] = confirmado_em_low

    return out


def gerar_sinais(
    df: pd.DataFrame,
    cfg: MSSFVGBaselineConfig,
) -> pd.DataFrame:
    df = detectar_pivos(
        df,
        cfg.pivot_bars,
    )

    sinais = []

    last_sh = np.nan
    prev_sh = np.nan

    last_sl = np.nan
    prev_sl = np.nan

    last_sh_bar = None
    last_sl_bar = None

    last_setup_time = None

    # Último FVG bullish conhecido
    b_top = np.nan
    b_bot = np.nan
    b_ob = np.nan
    b_bar = None

    # Último FVG bearish conhecido
    s_top = np.nan
    s_bot = np.nan
    s_ob = np.nan
    s_bar = None

    close_prev = None

    for i in range(len(df)):
        row = df.iloc[i]

        ts_utc = row["timestamp_utc"]
        ts_ny = row["timestamp_ny"]

        # --------------------------------------------------
        # Atualizar pivôs somente quando CONFIRMADOS
        # --------------------------------------------------

        origem_high = i - cfg.pivot_bars

        if origem_high >= 0:
            ph = df.iloc[origem_high]["pivot_high"]

            if not pd.isna(ph):
                prev_sh = last_sh
                last_sh = ph
                last_sh_bar = origem_high

        origem_low = i - cfg.pivot_bars

        if origem_low >= 0:
            pl = df.iloc[origem_low]["pivot_low"]

            if not pd.isna(pl):
                prev_sl = last_sl
                last_sl = pl
                last_sl_bar = origem_low

        # --------------------------------------------------
        # Estrutura
        # --------------------------------------------------

        down_struct = (
            not pd.isna(last_sh)
            and not pd.isna(prev_sh)
            and not pd.isna(last_sl)
            and not pd.isna(prev_sl)
            and last_sh < prev_sh
            and last_sl < prev_sl
        )

        up_struct = (
            not pd.isna(last_sh)
            and not pd.isna(prev_sh)
            and not pd.isna(last_sl)
            and not pd.isna(prev_sl)
            and last_sh > prev_sh
            and last_sl > prev_sl
        )

        # --------------------------------------------------
        # MSS
        #
        # Pine:
        # ta.crossover(close, lastSH)
        # ta.crossunder(close, lastSL)
        # --------------------------------------------------

        mss_bull = False
        mss_bear = False

        if close_prev is not None:
            if (
                down_struct
                and not pd.isna(last_sh)
                and close_prev <= last_sh
                and row["close"] > last_sh
            ):
                mss_bull = True

            if (
                up_struct
                and not pd.isna(last_sl)
                and close_prev >= last_sl
                and row["close"] < last_sl
            ):
                mss_bear = True

        # --------------------------------------------------
        # FVG
        #
        # Bull:
        # low atual > high[2]
        #
        # Bear:
        # high atual < low[2]
        # --------------------------------------------------

        bull_fvg = False
        bear_fvg = False

        if i >= 2:
            c1 = df.iloc[i - 2]

            if row["low"] > c1["high"]:
                bull_fvg = True

                b_top = row["low"]
                b_bot = c1["high"]

                # Pine:
                # bOB := low[2]
                b_ob = c1["low"]

                b_bar = i

            if row["high"] < c1["low"]:
                bear_fvg = True

                s_top = c1["low"]
                s_bot = row["high"]

                # Pine:
                # sOB := high[2]
                s_ob = c1["high"]

                s_bar = i

        # --------------------------------------------------
        # Intervalo mínimo entre setups
        # --------------------------------------------------

        gap_ok = True

        if last_setup_time is not None:
            minutos = (
                ts_utc - last_setup_time
            ).total_seconds() / 60.0

            gap_ok = (
                minutos
                >= cfg.min_minutes_between_setups
            )

        in_session = dentro_sessao(
            ts_ny,
            cfg.session_start,
            cfg.session_end,
        )
        
        blocked_time = dentro_horario_bloqueado(
            ts_ny,
            cfg.blocked_start,
            cfg.blocked_end,
        )
        # --------------------------------------------------
        # SETUPS LONG
        # --------------------------------------------------

        rev_long = (
            cfg.enable_reversal
            and mss_bull
        )

        cont_long = (
            cfg.enable_continuation
            and up_struct
            and bull_fvg
        )

        if (
            cfg.enable_long
            and (rev_long or cont_long)
            and gap_ok
            and in_session
            and not blocked_time
            and b_bar is not None
            and (i - b_bar)
            <= cfg.max_setup_age_bars
        ):
            entry = (
                b_top
                - (b_top - b_bot)
                * cfg.entry_pct_fvg
                / 100.0
            )

            stop = (
                b_ob
                - cfg.stop_buffer_points
            )

            risco = entry - stop

            if (
                row["close"] > entry
                and risco >= cfg.min_stop_points
                and risco <= cfg.max_stop_points
                and risco > cfg.tick_size
            ):
                tipo = (
                    "REVERSAO"
                    if rev_long
                    else "CONTINUACAO"
                )

                sinais.append(
                    {
                        "timestamp_utc": ts_utc,
                        "timestamp_ny": ts_ny,
                        "direcao": "LONG",
                        "tipo": tipo,
                        "entry": entry,
                        "stop": stop,
                        "risk_points": risco,
                        "fvg_top": b_top,
                        "fvg_bottom": b_bot,
                        "fvg_size": b_top - b_bot,
                        "fvg_bar": b_bar,
                        "ob_price": b_ob,
                        "mss": mss_bull,
                        "mss_price": last_sh
                        if rev_long
                        else np.nan,
                        "mss_bar": last_sh_bar
                        if rev_long
                        else np.nan,
                        "up_struct": up_struct,
                        "down_struct": down_struct,
                    }
                )

                last_setup_time = ts_utc

        # --------------------------------------------------
        # SETUPS SHORT
        # --------------------------------------------------

        rev_short = (
            cfg.enable_reversal
            and mss_bear
        )

        cont_short = (
            cfg.enable_continuation
            and down_struct
            and bear_fvg
        )

        if (
            cfg.enable_short
            and (rev_short or cont_short)
            and gap_ok
            and in_session
            and not blocked_time
            and s_bar is not None
            and (i - s_bar)
            <= cfg.max_setup_age_bars
        ):
            entry = (
                s_bot
                + (s_top - s_bot)
                * cfg.entry_pct_fvg
                / 100.0
            )

            stop = (
                s_ob
                + cfg.stop_buffer_points
            )

            risco = stop - entry

            if (
                row["close"] < entry
                and risco >= cfg.min_stop_points
                and risco <= cfg.max_stop_points
                and risco > cfg.tick_size
            ):
                tipo = (
                    "REVERSAO"
                    if rev_short
                    else "CONTINUACAO"
                )

                sinais.append(
                    {
                        "timestamp_utc": ts_utc,
                        "timestamp_ny": ts_ny,
                        "direcao": "SHORT",
                        "tipo": tipo,
                        "entry": entry,
                        "stop": stop,
                        "risk_points": risco,
                        "fvg_top": s_top,
                        "fvg_bottom": s_bot,
                        "fvg_size": s_top - s_bot,
                        "fvg_bar": s_bar,
                        "ob_price": s_ob,
                        "mss": mss_bear,
                        "mss_price": last_sl
                        if rev_short
                        else np.nan,
                        "mss_bar": last_sl_bar
                        if rev_short
                        else np.nan,
                        "up_struct": up_struct,
                        "down_struct": down_struct,
                    }
                )

                last_setup_time = ts_utc

        close_prev = row["close"]

    sinais_df = pd.DataFrame(sinais)

    return sinais_df


def main() -> None:
    cfg = MSSFVGBaselineConfig()

    print("=" * 70)
    print("MSS + FVG — GERADOR DE SINAIS BASELINE")
    print("=" * 70)

    print()
    print("Configuração:")
    for chave, valor in asdict(cfg).items():
        print(f"  {chave}: {valor}")

    print()
    print(f"Base: {ARQUIVO_BASE}")

    df = carregar_dados(
        ARQUIVO_BASE
    )

    print(
        f"Candles carregados: "
        f"{len(df):,}"
    )

    print(
        "Período:",
        df["timestamp_ny"].min(),
        "->",
        df["timestamp_ny"].max(),
    )

    sinais = gerar_sinais(
        df,
        cfg,
    )

    sinais.to_csv(
        ARQUIVO_SAIDA,
        index=False,
    )

    print()
    print("=" * 70)
    print("RESULTADO")
    print("=" * 70)

    print(
        f"Sinais encontrados: "
        f"{len(sinais):,}"
    )

    if not sinais.empty:
        print()
        print("Por direção:")
        print(
            sinais["direcao"]
            .value_counts()
            .to_string()
        )

        print()
        print("Por tipo:")
        print(
            sinais["tipo"]
            .value_counts()
            .to_string()
        )

        print()
        print("Direção x tipo:")
        print(
            pd.crosstab(
                sinais["direcao"],
                sinais["tipo"],
            ).to_string()
        )

        print()
        print(
            "Risco médio:",
            round(
                sinais[
                    "risk_points"
                ].mean(),
                2,
            ),
            "pts",
        )

        print(
            "FVG médio:",
            round(
                sinais[
                    "fvg_size"
                ].mean(),
                2,
            ),
            "pts",
        )

    print()
    print(
        f"Arquivo salvo em:\n"
        f"{ARQUIVO_SAIDA}"
    )


if __name__ == "__main__":
    main()