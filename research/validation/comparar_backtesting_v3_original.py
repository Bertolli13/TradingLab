import glob
from pathlib import Path

import pandas as pd
from backtesting import Backtest, Strategy


DATA_DIR = Path("data")

# ---------------------------------------------------------
# 1. Localizar automaticamente o resultado V3 mais recente
# ---------------------------------------------------------

pastas_v3 = sorted(
    glob.glob(str(DATA_DIR / "v3_*")),
    reverse=True
)

if not pastas_v3:
    raise FileNotFoundError(
        "Nenhuma pasta data/v3_* encontrada."
    )

PASTA_V3 = Path(pastas_v3[0])
ARQUIVO_V3 = PASTA_V3 / "backtest_v3.csv"

print("Usando V3:")
print(ARQUIVO_V3)


# ---------------------------------------------------------
# 2. Carregar candles
# ---------------------------------------------------------

df = pd.read_parquet(
    DATA_DIR / "nq_unificado_validacao.parquet"
)

df["datetime"] = pd.to_datetime(
    df["datetime"],
    utc=True
)

df = df.sort_values("datetime")

df = df.rename(
    columns={
        "open": "Open",
        "high": "High",
        "low": "Low",
        "close": "Close",
        "volume": "Volume",
    }
)

df = df.set_index("datetime")

colunas = ["Open", "High", "Low", "Close"]

if "Volume" in df.columns:
    colunas.append("Volume")

df = df[colunas]


# ---------------------------------------------------------
# 3. Carregar sinais/níveis produzidos pela V3
# ---------------------------------------------------------

v3 = pd.read_csv(ARQUIVO_V3)

# Usamos somente um cenário porque entrada/stop/alvo são iguais.
v3 = v3[
    v3["cenario"] == "conservador"
].copy()

print("\nSinais V3:", len(v3))

for coluna in [
    "ordem_ativa_em",
    "horario_fvg",
]:
    v3[coluna] = pd.to_datetime(
        v3[coluna],
        utc=True,
        errors="coerce"
    )

v3 = v3.dropna(
    subset=[
        "ordem_ativa_em",
        "entrada",
        "stop",
        "alvo",
    ]
)

# Uma ordem/sinal por timestamp
SINAIS = {}

for _, row in v3.iterrows():

    ts = row["ordem_ativa_em"]

    SINAIS[ts] = {
        "data": row["data"],
        "direcao": row["direcao"],
        "entrada": float(row["entrada"]),
        "stop": float(row["stop"]),
        "alvo": float(row["alvo"]),
    }


# ---------------------------------------------------------
# 4. ORB para cancelamento da ordem
# ---------------------------------------------------------

orb = pd.read_csv(
    DATA_DIR / "orb_rompimentos.csv",
    dtype={"data": str}
)

ORB = {}

for _, row in orb.iterrows():

    ORB[str(row["data"])] = {
        "min": float(row["range_min"]),
        "max": float(row["range_max"]),
    }


# ---------------------------------------------------------
# 5. Estratégia Backtesting.py
# ---------------------------------------------------------

class ORBFVGComparacao(Strategy):

    def init(self):

        self.sinal_atual = None
        self.data_sinal = None

    def next(self):

        agora = self.data.index[-1]

        if agora.tzinfo is None:
            agora = agora.tz_localize("UTC")
        else:
            agora = agora.tz_convert("UTC")

        horario_ny = agora.tz_convert(
            "America/New_York"
        )

        data_ny = horario_ny.strftime(
            "%Y-%m-%d"
        )

        hora_ny = horario_ny.strftime(
            "%H:%M"
        )

        # ---------------------------------
        # Ativação de novo sinal
        # ---------------------------------

        if agora in SINAIS:

            sinal = SINAIS[agora]

            self.sinal_atual = sinal
            self.data_sinal = data_ny

            entrada = sinal["entrada"]
            stop = sinal["stop"]
            alvo = sinal["alvo"]

            if sinal["direcao"] == "COMPRA":

                self.buy(
                    size=1,
                    limit=entrada,
                    sl=stop,
                    tp=alvo,
                    tag=data_ny,
                )

            else:

                self.sell(
                    size=1,
                    limit=entrada,
                    sl=stop,
                    tp=alvo,
                    tag=data_ny,
                )

        # ---------------------------------
        # Cancelamento se voltar ao ORB
        # somente enquanto não há posição
        # ---------------------------------

        if (
            self.sinal_atual is not None
            and not self.position
            and len(self.orders) > 0
        ):

            niveis_orb = ORB.get(
                self.data_sinal
            )

            if niveis_orb:

                fechamento = self.data.Close[-1]

                if (
                    self.sinal_atual["direcao"]
                    == "COMPRA"
                ):
                    invalidou = (
                        fechamento
                        <= niveis_orb["max"]
                    )

                else:
                    invalidou = (
                        fechamento
                        >= niveis_orb["min"]
                    )

                if invalidou:

                    for ordem in list(
                        self.orders
                    ):
                        ordem.cancel()

                    self.sinal_atual = None

        # ---------------------------------
        # Fim da sessão 16:40 NY
        # ---------------------------------

        if hora_ny >= "16:40":

            # cancelar ordens pendentes
            for ordem in list(self.orders):
                ordem.cancel()

            # fechar posição aberta
            if self.position:
                self.position.close()

            self.sinal_atual = None


# ---------------------------------------------------------
# 6. Executar
# ---------------------------------------------------------

bt = Backtest(
    df,
    ORBFVGComparacao,
    cash=100_000,
    commission=0,
    exclusive_orders=True,
    trade_on_close=False,
    finalize_trades=True,
)

resultado = bt.run()


# ---------------------------------------------------------
# 7. Resultados
# ---------------------------------------------------------

print("\n========== BACKTESTING.PY ==========")

print(
    "Operações:",
    resultado["# Trades"]
)

print(
    "Win rate:",
    round(
        resultado["Win Rate [%]"],
        2
    ),
    "%"
)

print(
    "Return:",
    round(
        resultado["Return [%]"],
        4
    ),
    "%"
)

print(
    "Profit Factor:",
    resultado["Profit Factor"]
)

print(
    "Max Drawdown:",
    round(
        resultado["Max. Drawdown [%]"],
        4
    ),
    "%"
)


# ---------------------------------------------------------
# 8. Exportar operações
# ---------------------------------------------------------

trades = resultado["_trades"].copy()

saida = DATA_DIR / "backtesting_py_trades.csv"

trades.to_csv(
    saida,
    index=False
)

print("\nCSV criado:")
print(saida)

print("\nPrimeiras operações:")

print(
    trades.head(10).to_string(
        index=False
    )
)