import glob
from pathlib import Path

import pandas as pd


DATA = Path("data")


# ---------------------------------------------------------
# Último resultado V3
# ---------------------------------------------------------

pastas = sorted(
    glob.glob(str(DATA / "v3_*")),
    reverse=True
)

if not pastas:
    raise FileNotFoundError("Nenhuma pasta V3 encontrada.")

pasta_v3 = Path(pastas[0])

arquivo_v3 = pasta_v3 / "backtest_v3.csv"
arquivo_bt = DATA / "backtesting_py_trades.csv"


# ---------------------------------------------------------
# Carregar
# ---------------------------------------------------------

v3 = pd.read_csv(arquivo_v3)
bt = pd.read_csv(arquivo_bt)


print("\n===== COLUNAS V3 =====")
print(v3.columns.tolist())

print("\n===== COLUNAS BACKTESTING.PY =====")
print(bt.columns.tolist())


# ---------------------------------------------------------
# Selecionar cenário conservador
# ---------------------------------------------------------

if "cenario" in v3.columns:
    v3 = v3[
        v3["cenario"].astype(str).str.lower()
        == "conservador"
    ].copy()


# ---------------------------------------------------------
# Manter somente operações executadas na V3
# ---------------------------------------------------------

# Detectar automaticamente coluna de execução
possiveis_execucao = [
    "executada",
    "executado",
    "operacao_executada",
]

col_exec = next(
    (
        c for c in possiveis_execucao
        if c in v3.columns
    ),
    None
)

if col_exec:
    v3 = v3[
        v3[col_exec].astype(str).str.lower().isin(
            ["true", "1", "sim"]
        )
    ].copy()


# Caso exista resultado/motivo, excluir explicitamente SEM_RETESTE
if "motivo" in v3.columns:

    v3 = v3[
        ~v3["motivo"]
        .astype(str)
        .str.upper()
        .isin([
            "SEM_RETESTE",
            "NAO_EXECUTADA",
            "NÃO_EXECUTADA",
        ])
    ]


# ---------------------------------------------------------
# Criar chave por data
# ---------------------------------------------------------

v3["data_chave"] = pd.to_datetime(
    v3["data"]
).dt.strftime("%Y-%m-%d")


bt["data_chave"] = pd.to_datetime(
    bt["Tag"]
).dt.strftime("%Y-%m-%d")


datas_v3 = set(v3["data_chave"])
datas_bt = set(bt["data_chave"])


# ---------------------------------------------------------
# Diferenças
# ---------------------------------------------------------

somente_v3 = sorted(
    datas_v3 - datas_bt
)

somente_bt = sorted(
    datas_bt - datas_v3
)

comuns = sorted(
    datas_v3 & datas_bt
)


print("\n========== COMPARAÇÃO ==========")

print("V3:", len(datas_v3))
print("Backtesting.py:", len(datas_bt))
print("Datas comuns:", len(comuns))

print("\nSomente na V3:")
for d in somente_v3:
    print(" ", d)

print("\nSomente no backtesting.py:")
for d in somente_bt:
    print(" ", d)


# ---------------------------------------------------------
# Exportar
# ---------------------------------------------------------

pd.DataFrame({
    "data": somente_v3
}).to_csv(
    DATA / "trades_somente_v3.csv",
    index=False
)

pd.DataFrame({
    "data": somente_bt
}).to_csv(
    DATA / "trades_somente_backtesting.csv",
    index=False
)


print("\nArquivos criados:")
print(DATA / "trades_somente_v3.csv")
print(DATA / "trades_somente_backtesting.csv")