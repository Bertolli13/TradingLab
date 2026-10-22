"""Testes de comportamento sem dados externos: python -m unittest -v."""
import unittest
from types import SimpleNamespace

import pandas as pd

from backtest_v3 import Config, State, advance, build, gross, simulate, stats


class ExecutionTests(unittest.TestCase):
    def bar(self, o, h, l, c, minute=1):
        return SimpleNamespace(open=o, high=h, low=l, close=c,
                               datetime=pd.Timestamp(f"2025-01-02 15:{minute:02}:00Z"))

    def move(self, bar, path="OHLC", state=State(), cfg=Config(), direction="COMPRA"):
        return advance(state, bar, direction, 100, 95 if direction == "COMPRA" else 105,
                       105 if direction == "COMPRA" else 95, 90, 110, cfg, path)

    def test_target_before_entry_is_not_a_win(self):
        bar = self.bar(103, 106, 99, 101)
        self.assertEqual(self.move(bar, "OHLC").status, "ABERTA")
        self.assertEqual(self.move(bar, "OLHC").motivo, "ALVO")

    def test_entry_stop_is_causal(self):
        bar = self.bar(103, 104, 94, 101)
        for path in ("OHLC", "OLHC"):
            self.assertEqual(self.move(bar, path).preco_saida, 95)

    def test_both_levels_with_open_position(self):
        bar = self.bar(100, 106, 94, 100)
        opened = State("ABERTA", "anterior")
        self.assertEqual(self.move(bar, "OHLC", opened).motivo, "ALVO")
        self.assertEqual(self.move(bar, "OLHC", opened).motivo, "STOP")

    def test_pending_cancel_at_close_after_intrabar_fill(self):
        filled = self.move(self.bar(103, 104, 99, 99))
        self.assertEqual(filled.status, "ABERTA")
        no_fill = self.move(self.bar(103, 104, 100, 101))
        self.assertEqual(no_fill.motivo, "CANCELADA_RANGE")

    def test_penetration_and_touch(self):
        bar = self.bar(103, 104, 100, 102)
        self.assertEqual(self.move(bar).status, "CANCELADA")
        self.assertEqual(self.move(bar, cfg=Config(penetracao_ticks=0)).status, "ABERTA")

    def test_gap_stop_adverse(self):
        s = self.move(self.bar(92, 96, 91, 94), state=State("ABERTA", "anterior"))
        self.assertEqual(s.preco_saida, 92)
        self.assertEqual(gross(s, "COMPRA", 100, 5), -1.6)

    def test_short_mirror(self):
        bar = self.bar(97, 101, 94, 99)
        self.assertEqual(self.move(bar, "OLHC", direction="VENDA").status, "ABERTA")
        self.assertEqual(self.move(bar, "OHLC", direction="VENDA").motivo, "ALVO")

    def test_optional_position_invalidation(self):
        s = self.move(self.bar(103, 104, 99, 99), cfg=Config(invalidar_posicao=True))
        self.assertEqual(s.motivo, "SAIDA_RANGE")
        self.assertEqual(s.preco_saida, 99)

    def test_branches_are_kept_to_session_end(self):
        start = pd.Timestamp("2025-01-02 15:00Z")
        bars = pd.DataFrame([vars(self.bar(103, 106, 99, 101)),
                             vars(self.bar(101, 102, 94, 96, 2))])
        out, error = simulate(bars, "COMPRA", 100, 95, 105, 90, 90,
                              Config(), start, start + pd.Timedelta(minutes=3))
        self.assertFalse(error)
        self.assertEqual({s.motivo for s in out}, {"ALVO", "STOP"})

    def test_missing_minute_excludes(self):
        start = pd.Timestamp("2025-01-02 15:00Z")
        bars = pd.DataFrame([vars(self.bar(103, 104, 101, 102, 2))])
        out, error = simulate(bars, "COMPRA", 100, 95, 105, 90, 90,
                              Config(), start, start + pd.Timedelta(minutes=3))
        self.assertEqual(error, "LACUNA_DADOS")

    def test_drawdown_includes_initial_loss(self):
        f = pd.DataFrame(dict(data=["2025-01-02"], horario_entrada=["x"],
                              executada=[True], incluida=[True], ambiguo=[False],
                              resultado_liquido_r=[-1.1], resultado_bruto_r=[-1],
                              resultado_liquido_usd=[-11]))
        self.assertAlmostEqual(stats(f)["max_drawdown_r"], 1.1)

    def test_config_rejects_invalid_values(self):
        for cfg in [Config(tick=0), Config(custo_round_trip=-1), Config(valor_ponto=float("nan"))]:
            with self.assertRaises(ValueError):
                cfg.validate()

    def test_scenarios_exclusion_and_costs(self):
        # FVG confirmado no terceiro candle; alvo pode preceder a entrada no quarto.
        rows = [(94, 98, 93, 97), (98, 101, 97, 100), (101, 103, 100, 102),
                (103, 106, 99, 101), (101, 102, 92, 94)]
        start = pd.Timestamp("2025-01-02 15:00Z")
        candles = pd.DataFrame(rows, columns=["open", "high", "low", "close"])
        candles["datetime"] = pd.date_range(start, periods=5, freq="min")
        candles["data"] = "2025-01-02"
        signal = pd.DataFrame([dict(data="2025-01-02", direcao="COMPRA", rompimento="COMPRA",
                                    horario_fvg=str(start + pd.Timedelta(minutes=2)),
                                    fvg_min=98, fvg_max=100, range_min=80, range_max=90)])
        # Risco 7; alvo 107. Alterar candle para alcançar o alvo do padrão.
        candles.loc[3, "high"] = 108
        a, _ = build(candles, signal, Config())
        b, _ = build(candles, signal, Config(contratos=3))
        opt = a[a.cenario.eq("otimista")].iloc[0]
        con = a[a.cenario.eq("conservador")].iloc[0]
        excluded = a[a.cenario.eq("exclusao")].iloc[0]
        self.assertEqual(opt.resultado_bruto_r, 1)
        self.assertEqual(con.resultado_bruto_r, -1)
        self.assertAlmostEqual(opt.custo_total_usd, 4)
        self.assertAlmostEqual(opt.resultado_liquido_r, 1 - 4 / 14)
        self.assertFalse(excluded.incluida)
        self.assertFalse(excluded.executada)
        self.assertTrue(pd.isna(excluded.resultado_bruto_r))
        self.assertAlmostEqual(b.iloc[0].resultado_liquido_r, opt.resultado_liquido_r)
        self.assertAlmostEqual(b.iloc[0].resultado_liquido_usd, 3 * opt.resultado_liquido_usd)

    def test_no_entry_in_confirmation_candle(self):
        start = pd.Timestamp("2025-01-02 15:00Z")
        bars = pd.DataFrame([vars(self.bar(103, 104, 101, 102))])
        out, error = simulate(bars, "COMPRA", 100, 95, 105, 90, 90,
                              Config(), start, start + pd.Timedelta(minutes=2))
        self.assertFalse(error)
        self.assertEqual(out[0].motivo, "SEM_RETESTE")
        self.assertFalse(out[0].entrada_ts)


if __name__ == "__main__":
    unittest.main()
