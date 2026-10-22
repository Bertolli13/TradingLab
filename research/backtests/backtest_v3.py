"""ORB+FVG: cenários condicionais OHLC; não reconstitui execuções reais.

Executar na pasta TradingLab: python backtest_v3.py --data-dir data
Requer pandas e pyarrow. Veja LEIA_ME_V3.md para hipóteses e limitações.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, replace
from datetime import datetime
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

TZ = "America/New_York"
SCENARIOS = ("otimista", "conservador", "exclusao")


@dataclass(frozen=True)
class Config:
    tick: float = 0.25
    penetracao_ticks: int = 1
    valor_ponto: float = 2.0  # MNQ, apesar de os preços históricos serem NQ
    contratos: int = 1
    custo_round_trip: float = 3.0  # USD por contrato
    slippage_total_ticks: float = 2.0  # débito financeiro total, não move níveis
    fim_sessao: str = "16:40"
    invalidar_posicao: bool = False

    def validate(self):
        for key in ("tick", "valor_ponto"):
            if not np.isfinite(getattr(self, key)) or getattr(self, key) <= 0:
                raise ValueError(f"{key} deve ser positivo e finito")
        if self.contratos < 1 or self.penetracao_ticks < 0:
            raise ValueError("Contratos >= 1 e penetração >= 0")
        for key in ("custo_round_trip", "slippage_total_ticks"):
            if not np.isfinite(getattr(self, key)) or getattr(self, key) < 0:
                raise ValueError(f"{key} deve ser não negativo e finito")
        datetime.strptime(self.fim_sessao, "%H:%M")


@dataclass(frozen=True)
class State:
    status: str = "PENDENTE"
    entrada_ts: str = ""
    saida_ts: str = ""
    preco_saida: float | None = None
    motivo: str = ""


def advance(state, bar, direction, entry, stop, target, orb_min, orb_max, cfg, path):
    """Percorre segmentos contínuos. Gap entre candles é tratado na abertura."""
    ts = str(bar.datetime)
    sign = 1 if direction == "COMPRA" else -1
    trigger = entry - sign * cfg.penetracao_ticks * cfg.tick
    points = ([bar.open, bar.high, bar.low, bar.close] if path == "OHLC"
              else [bar.open, bar.low, bar.high, bar.close])
    s = state

    def at_price(s, price):
        if s.status == "PENDENTE" and sign * (price - trigger) <= 0:
            s = State("ABERTA", ts)
        if s.status == "ABERTA":
            if sign * (price - stop) <= 0:
                # Stop mercado: gap desfavorável sai na abertura/preço atual.
                return replace(s, status="FECHADA", saida_ts=ts,
                               preco_saida=float(price), motivo="STOP")
            if sign * (price - target) >= 0:
                return replace(s, status="FECHADA", saida_ts=ts,
                               preco_saida=target, motivo="ALVO")
        return s

    s = at_price(s, points[0])
    for a, b in zip(points, points[1:]):
        if s.status == "FECHADA":
            return s
        if s.status == "PENDENTE":
            if min(a, b) <= trigger <= max(a, b):
                s = State("ABERTA", ts)
                a = trigger
                s = at_price(s, a)
            else:
                continue
        if s.status == "FECHADA":
            return s
        hits = [x for x in (stop, target) if min(a, b) <= x <= max(a, b)]
        if hits:
            price = min(hits, key=lambda x: abs(x - a))
            s = replace(s, status="FECHADA", saida_ts=ts, preco_saida=price,
                        motivo="STOP" if price == stop else "ALVO")
    invalid = bar.close <= orb_max if sign == 1 else bar.close >= orb_min
    if invalid and s.status == "PENDENTE":
        s = replace(s, status="CANCELADA", saida_ts=ts, motivo="CANCELADA_RANGE")
    elif invalid and s.status == "ABERTA" and cfg.invalidar_posicao:
        s = replace(s, status="FECHADA", saida_ts=ts,
                    preco_saida=float(bar.close), motivo="SAIDA_RANGE")
    return s


def gross(s, direction, entry, risk):
    if s.preco_saida is None:
        return 0.0
    return (1 if direction == "COMPRA" else -1) * (s.preco_saida - entry) / risk


def simulate(bars, direction, entry, stop, target, orb_min, orb_max, cfg, fvg_ts, end):
    """Mantém ramos ativos e todos os resultados terminais, sem escolha gulosa."""
    active = {State()}
    terminal = set()
    previous = fvg_ts
    last = None
    for bar in bars.itertuples(index=False):
        if not active:
            break
        if bar.datetime - previous != pd.Timedelta(minutes=1):
            return [], "LACUNA_DADOS"
        next_active = set()
        for s in active:
            for path in ("OHLC", "OLHC"):
                out = advance(s, bar, direction, entry, stop, target,
                              orb_min, orb_max, cfg, path)
                if out.status in ("FECHADA", "CANCELADA"):
                    terminal.add(out)
                else:
                    next_active.add(out)
        active = next_active
        previous, last = bar.datetime, bar
    if active:
        if last is None or last.datetime + pd.Timedelta(minutes=1) != end:
            return [], "SESSAO_INCOMPLETA"
        for s in active:
            if s.status == "ABERTA":
                terminal.add(replace(s, status="FECHADA", saida_ts=str(last.datetime),
                                     preco_saida=float(last.close), motivo="ENCERRAMENTO"))
            else:
                terminal.add(replace(s, status="CANCELADA", motivo="SEM_RETESTE"))
    return sorted(terminal, key=lambda s: (s.saida_ts, s.motivo, s.entrada_ts)), ""


def require(df, cols, name):
    missing = set(cols) - set(df.columns)
    if missing:
        raise ValueError(f"{name}: colunas ausentes: {sorted(missing)}")


def load(data):
    candles = pd.read_parquet(data / "nq_unificado_validacao.parquet")
    require(candles, ["datetime", "open", "high", "low", "close"], "candles")
    candles = candles[["datetime", "open", "high", "low", "close"]].copy()
    candles["datetime"] = pd.to_datetime(candles.datetime, utc=True, errors="raise")
    if candles.datetime.isna().any() or candles.datetime.duplicated().any():
        raise ValueError("Candles com timestamp ausente/duplicado; corrija a fonte explicitamente")
    if not candles.datetime.dt.second.eq(0).all() or not candles.datetime.dt.microsecond.eq(0).all():
        raise ValueError("Esperados timestamps no início de cada minuto")
    for c in ["open", "high", "low", "close"]:
        candles[c] = pd.to_numeric(candles[c], errors="raise")
    if not np.isfinite(candles[["open", "high", "low", "close"]]).all().all():
        raise ValueError("OHLC contém valores não finitos")
    if ((candles.high < candles[["open", "close", "low"]].max(axis=1)) |
            (candles.low > candles[["open", "close", "high"]].min(axis=1))).any():
        raise ValueError("OHLC inconsistente")
    candles = candles.sort_values("datetime")
    candles["data"] = candles.datetime.dt.tz_convert(TZ).dt.strftime("%Y-%m-%d")
    signals = pd.read_csv(data / "orb_fvg_v2.csv", dtype={"data": str})
    orb = pd.read_csv(data / "orb_rompimentos.csv", dtype={"data": str})
    require(signals, ["data", "direcao", "fvg_encontrado", "horario_fvg", "fvg_min", "fvg_max"], "sinais")
    require(orb, ["data", "range_min", "range_max", "rompimento"], "ORB")
    flags = signals.fvg_encontrado.astype(str).str.lower()
    if not flags.isin(["true", "false"]).all():
        raise ValueError("fvg_encontrado deve conter True/False")
    signals = signals[flags.eq("true")].copy()
    if signals.empty:
        raise ValueError("Nenhum FVG válido na fonte")
    if signals.data.duplicated().any() or orb.data.duplicated().any():
        raise ValueError("Esperado um sinal e um ORB por data")
    signals = signals.merge(orb[["data", "range_min", "range_max", "rompimento"]],
                            on="data", how="left", validate="one_to_one")
    return candles, signals


def build(candles, signals, cfg):
    days = {day: frame.reset_index(drop=True) for day, frame in candles.groupby("data")}
    results, alternatives = [], []
    for signal in signals.itertuples(index=False):
        base = {"data": signal.data, "direcao": signal.direcao,
                "horario_fvg": signal.horario_fvg}
        error = ""
        try:
            if signal.direcao not in ("COMPRA", "VENDA") or signal.rompimento != signal.direcao:
                raise ValueError("DIRECAO_ORB_INVALIDA")
            vals = [float(x) for x in (signal.fvg_min, signal.fvg_max, signal.range_min, signal.range_max)]
            if not np.isfinite(vals).all() or vals[0] >= vals[1] or vals[2] >= vals[3]:
                raise ValueError("NIVEIS_INVALIDOS")
            ts = pd.Timestamp(signal.horario_fvg)
            if ts.tzinfo is None:
                raise ValueError("FVG_SEM_FUSO")
            ts = ts.tz_convert("UTC")
            if ts.tz_convert(TZ).strftime("%Y-%m-%d") != signal.data:
                raise ValueError("DATA_FVG_DIVERGENTE")
            day = days.get(signal.data)
            if day is None:
                raise ValueError("DIA_AUSENTE")
            indexes = day.index[day.datetime.eq(ts)]
            if len(indexes) != 1 or indexes[0] < 2:
                raise ValueError("FVG_NAO_LOCALIZADO")
            i = indexes[0]
            pattern = day.iloc[i-2:i+1]
            if not pattern.datetime.diff().dropna().eq(pd.Timedelta(minutes=1)).all():
                raise ValueError("FVG_NAO_CONTIGUO")
            c1, c3 = pattern.iloc[0], pattern.iloc[-1]
            buy = signal.direcao == "COMPRA"
            expected = (c1.high, c3.low) if buy else (c3.high, c1.low)
            if not np.allclose(vals[:2], expected, rtol=0, atol=1e-8):
                raise ValueError("FVG_DIVERGE_CANDLES")
            if (buy and (vals[0] < vals[3] or c3.close <= vals[3])) or (not buy and (vals[1] > vals[2] or c3.close >= vals[2])):
                raise ValueError("FVG_INVALIDO_ORB")
            entry = vals[1] if buy else vals[0]
            stop = float(c1.low if buy else c1.high)
            risk = (entry - stop) if buy else (stop - entry)
            if risk <= 0:
                raise ValueError("RISCO_INVALIDO")
            target = entry + (risk if buy else -risk)
            end = pd.Timestamp(f"{signal.data} {cfg.fim_sessao}", tz=TZ).tz_convert("UTC")
            if ts + pd.Timedelta(minutes=1) >= end:
                raise ValueError("FVG_FORA_SESSAO")
            bars = day[(day.datetime > ts) & (day.datetime < end)]
            base.update(entrada=entry, stop=stop, alvo=target, risco_pontos=risk,
                        ordem_ativa_em=str(ts + pd.Timedelta(minutes=1)))
            outcomes, error = simulate(bars, signal.direcao, entry, stop, target,
                                       vals[2], vals[3], cfg, ts, end)
        except (ValueError, TypeError) as exc:
            outcomes, error = [], str(exc)
        if error:
            for scenario in SCENARIOS:
                results.append(dict(base, cenario=scenario, executada=False, incluida=False,
                                    ambiguo=False, motivo_saida="DADOS_INVALIDOS", erro=error,
                                    resultado_bruto_r=None, resultado_liquido_r=None))
            continue
        # Divergência de preço, motivo ou minuto de saída também conta como ambiguidade.
        ambiguous = len(outcomes) > 1
        cost_usd = cfg.contratos * (cfg.custo_round_trip + cfg.slippage_total_ticks * cfg.tick * cfg.valor_ponto)
        risk_usd = risk * cfg.valor_ponto * cfg.contratos
        ranked = sorted(outcomes, key=lambda s: (gross(s, signal.direcao, entry, risk), s.saida_ts, s.motivo))
        for j, s in enumerate(outcomes):
            alternatives.append(dict(base, alternativa=j + 1, **asdict(s),
                                      resultado_bruto_r=gross(s, signal.direcao, entry, risk) if s.entrada_ts else None))
        for scenario in SCENARIOS:
            excluded = scenario == "exclusao" and ambiguous
            s = ranked[-1] if scenario == "otimista" else ranked[0]
            executed = bool(s.entrada_ts)
            pnl = gross(s, signal.direcao, entry, risk) if executed else None
            results.append(dict(base, cenario=scenario, ambiguo=ambiguous,
                                alternativas=len(outcomes), incluida=not excluded,
                                executada=executed if not excluded else False,
                                execucao_possivel=executed, horario_entrada=s.entrada_ts if not excluded else "",
                                horario_saida=s.saida_ts if not excluded else "",
                                preco_saida=s.preco_saida if not excluded else None,
                                motivo_saida="EXCLUIDA_AMBIGUIDADE" if excluded else s.motivo,
                                erro="", risco_usd=risk_usd,
                                custo_total_usd=cost_usd if executed and not excluded else 0,
                                custo_r=cost_usd / risk_usd if executed and not excluded else 0,
                                resultado_bruto_r=pnl if not excluded else None,
                                resultado_liquido_r=pnl - cost_usd / risk_usd if executed and not excluded else None,
                                resultado_liquido_usd=pnl * risk_usd - cost_usd if executed and not excluded else None))
    frame = pd.DataFrame(results)
    # Mesmo uma amostra inteiramente inválida precisa exportar o esquema completo.
    for column in ("horario_entrada", "horario_saida", "resultado_liquido_usd",
                   "preco_saida", "custo_r", "custo_total_usd", "risco_usd"):
        if column not in frame:
            frame[column] = None
    alternatives_frame = pd.DataFrame(alternatives)
    if alternatives_frame.empty:
        alternatives_frame = pd.DataFrame(columns=["data", "direcao", "alternativa", "status",
                                                    "entrada_ts", "saida_ts", "preco_saida",
                                                    "motivo", "resultado_bruto_r"])
    return frame, alternatives_frame


def stats(frame):
    trades = frame[frame.executada & frame.incluida].sort_values(["data", "horario_entrada"])
    r = trades.resultado_liquido_r.astype(float)
    equity = np.r_[0., r.cumsum().to_numpy()]
    gains, losses = r[r > 0].sum(), -r[r < 0].sum()
    return dict(sinais=len(frame), operacoes=len(trades), excluidos=int((~frame.incluida).sum()),
                ambiguos=int(frame.ambiguo.sum()),
                win_rate_liquido_pct=float((r > 0).mean() * 100) if len(r) else None,
                bruto_r=float(trades.resultado_bruto_r.sum()), liquido_r=float(r.sum()),
                media_liquida_r=float(r.mean()) if len(r) else None,
                profit_factor=float(gains / losses) if losses else None,
                max_drawdown_r=float((np.maximum.accumulate(equity) - equity).max()),
                liquido_usd=float(trades.resultado_liquido_usd.sum()))


def historical(data, name, cfg):
    file = data / name
    if not file.exists():
        return None
    df = pd.read_csv(file, dtype={"data": str})
    require(df, ["data", "direcao", "executada", "risco_pontos", "motivo_saida"], name)
    if df.duplicated(["data", "direcao"]).any():
        raise ValueError(f"{name}: chaves duplicadas")
    flags = df.executada.astype(str).str.lower()
    if not flags.isin(["true", "false"]).all():
        raise ValueError(f"{name}: executada inválida")
    df["executada"] = flags.eq("true")
    col = "resultado_r" if name == "backtest_orb_fvg.csv" else "resultado_bruto_r"
    require(df, [col], name)
    df["resultado_bruto_r"] = pd.to_numeric(df[col], errors="raise")
    if ((df.loc[df.executada, "risco_pontos"] <= 0).any() or
            not np.isfinite(df.loc[df.executada, ["risco_pontos", "resultado_bruto_r"]]).all().all()):
        raise ValueError(f"{name}: risco/resultado inválido")
    if "resultado_liquido_r" in df:
        df["liquido_r_original"] = df.resultado_liquido_r
    debit = (cfg.custo_round_trip + cfg.slippage_total_ticks * cfg.tick * cfg.valor_ponto) / (df.risco_pontos * cfg.valor_ponto)
    df["resultado_liquido_r"] = (df.resultado_bruto_r - debit).where(df.executada)
    df["resultado_liquido_usd"] = df.resultado_liquido_r * df.risco_pontos * cfg.valor_ponto * cfg.contratos
    df["incluida"], df["ambiguo"] = True, False
    if "horario_entrada" not in df:
        df["horario_entrada"] = ""
    return df


def export(v3, alternatives, data, output, cfg):
    v3.to_csv(output / "backtest_v3.csv", index=False)
    alternatives.to_csv(output / "alternativas_intrabar.csv", index=False)
    reports, yearly, comparisons = [], [], []
    models = {f"V3_{s}": v3[v3.cenario.eq(s)] for s in SCENARIOS}
    for label, file in [("V1", "backtest_orb_fvg.csv"), ("V2", "backtest_v2.csv")]:
        old = historical(data, file, cfg)
        if old is not None:
            models[label] = old
            columns = ["data", "direcao", "executada", "motivo_saida", "resultado_bruto_r", "resultado_liquido_r"]
            if "liquido_r_original" in old:
                columns.append("liquido_r_original")
            audit = v3.merge(old[columns], on=["data", "direcao"], how="outer",
                             suffixes=("_v3", f"_{label.lower()}"), indicator=True,
                             validate="many_to_one")
            audit["referencia"] = label
            comparisons.append(audit)
    common = set.intersection(*[set(zip(f.data, f.direcao)) for f in models.values()])
    for label, frame in models.items():
        reports.append(dict(modelo=label, universo="original", **stats(frame)))
        matched = frame.loc[np.array([key in common for key in zip(frame.data, frame.direcao)], dtype=bool)]
        reports.append(dict(modelo=label, universo="chaves_comuns", **stats(matched)))
        for year, group in frame.groupby(frame.data.str[:4]):
            yearly.append(dict(modelo=label, ano=year, **stats(group)))
    pd.DataFrame(reports).to_csv(output / "comparacao_resumo.csv", index=False)
    pd.DataFrame(yearly).to_csv(output / "estatisticas_anuais.csv", index=False)
    if comparisons:
        pd.concat(comparisons, ignore_index=True).to_csv(output / "comparacao_operacoes.csv", index=False)
    v3.groupby(["cenario", "motivo_saida"], dropna=False).size().rename("quantidade").to_csv(output / "motivos.csv")
    v3[v3.ambiguo].to_csv(output / "auditoria_ambiguidades.csv", index=False)
    v3[v3.motivo_saida.eq("DADOS_INVALIDOS")].to_csv(output / "erros_dados.csv", index=False)
    return pd.DataFrame(reports)


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path(__file__).resolve().parent / "data")
    parser.add_argument("--output-dir", type=Path, help="Pasta nova; nunca sobrescreve uma execução")
    parser.add_argument("--tick", type=float, default=.25)
    parser.add_argument("--penetracao-ticks", type=int, default=1)
    parser.add_argument("--valor-ponto", type=float, default=2.)
    parser.add_argument("--contratos", type=int, default=1)
    parser.add_argument("--custo-round-trip", type=float, default=3.)
    parser.add_argument("--slippage-total-ticks", type=float, default=2.)
    parser.add_argument("--fim-sessao", default="16:40")
    parser.add_argument("--invalidar-posicao", action="store_true")
    args = parser.parse_args()
    cfg = Config(**{k: getattr(args, k) for k in Config.__dataclass_fields__})
    cfg.validate()
    data = args.data_dir.resolve()
    output = args.output_dir or data / ("v3_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
    candles, signals = load(data)
    v3, alternatives = build(candles, signals, cfg)
    # Pasta exclusiva evita sobrescrever fontes ou resultados anteriores.
    output.mkdir(parents=True, exist_ok=False)
    summary = export(v3, alternatives, data, output, cfg)
    inputs = [data / n for n in ["nq_unificado_validacao.parquet", "orb_fvg_v2.csv", "orb_rompimentos.csv", "backtest_orb_fvg.csv", "backtest_v2.csv"] if (data / n).exists()]
    manifest = dict(config=asdict(cfg), fontes={p.name: sha256(p) for p in inputs},
                    script_sha256=sha256(Path(__file__)),
                    candles=len(candles), sinais=len(signals),
                    aviso="Hipóteses OHLC/OLHC condicionais, não fills reais nem limites universais.",
                    comparacao="V1/V2 preservados; líquido recalculado com custos desta execução.")
    (output / "configuracao.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(summary.to_string(index=False))
    print(f"\nCSVs: {output.resolve()}")
    print("Cenários não determinam fills reais. Leia LEIA_ME_V3.md.")


if __name__ == "__main__":
    main()
