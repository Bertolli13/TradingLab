
import pandas as pd

ARQUIVO = "data/backtest_orb_fvg.csv"

df = pd.read_csv(ARQUIVO)

df = df[df["executada"] == True].copy()
df["data"] = pd.to_datetime(df["data"])
df["ano"] = df["data"].dt.year

df = df.sort_values("data")

df["capital_r"] = df["resultado_r"].cumsum()
df["pico_r"] = df["capital_r"].cummax().clip(lower=0)
df["drawdown_r"] = df["capital_r"] - df["pico_r"]

resumo = df.groupby("ano").agg(
    operacoes=("resultado_r", "count"),
    ganhos=("resultado_r", lambda x: (x > 0).sum()),
    perdas=("resultado_r", lambda x: (x < 0).sum()),
    resultado_total_r=("resultado_r", "sum"),
    resultado_medio_r=("resultado_r", "mean")
)

resumo["win_rate_%"] = (
    resumo["ganhos"] / resumo["operacoes"] * 100
).round(2)

print("\n===== RESULTADO POR ANO =====")
print(resumo.to_string())

print("\n===== MÉTRICAS GERAIS =====")
print("Total de operações:", len(df))
print("Resultado acumulado:", round(df["resultado_r"].sum(), 2), "R")
print("Drawdown máximo:", round(df["drawdown_r"].min(), 2), "R")

print("\n===== POR DIREÇÃO =====")
print(
    df.groupby("direcao")["resultado_r"]
    .agg(["count", "sum", "mean"])
    .to_string()
)

print("\n===== DISTRIBUIÇÃO DO RISCO =====")
print(df["risco_pontos"].describe().to_string())
