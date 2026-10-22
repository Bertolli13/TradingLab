
import pandas as pd
from backtesting import Backtest, Strategy

# Carregar os dados históricos
df = pd.read_parquet(
    "data/nq_unificado_validacao.parquet"
)

# Converter datas para o horário de Nova York
df["datetime"] = pd.to_datetime(
    df["datetime"], utc=True
).dt.tz_convert("America/New_York")

# Selecionar um período pequeno para testar a integração
df = df[
    (df["datetime"] >= "2026-09-01")
    & (df["datetime"] < "2026-09-08")
].copy()

# Formato exigido pelo backtesting.py
df = df.rename(columns={
    "open": "Open",
    "high": "High",
    "low": "Low",
    "close": "Close",
    "volume": "Volume"
})

df = df.set_index("datetime").sort_index()

# O volume não é necessário para nosso teste
df = df[["Open", "High", "Low", "Close"]]

class TesteIntegracao(Strategy):

    def init(self):
        pass

    def next(self):
        # Nenhuma operação ainda.
        # Estamos apenas verificando a integração.
        pass

bt = Backtest(
    df,
    TesteIntegracao,
    cash=100_000,
    commission=0,
    exclusive_orders=True
)

resultado = bt.run()

print("\n===== TESTE BACKTESTING.PY =====")
print("Candles carregados:", len(df))
print("Retorno:", resultado["Return [%]"])
print("Operações:", resultado["# Trades"])
print("\nIntegração concluída!")

