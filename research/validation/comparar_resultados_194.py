import glob
from pathlib import Path

import pandas as pd


DATA = Path("data")


# ---------------------------------------------------------
# 1. Localizar V3 mais recente
# ---------------------------------------------------------

pastas_v3 = sorted(
    glob.glob(str(DATA / "v3_*")),
    reverse=True
)

if not pastas_v3:
    raise FileNotFoundError(
        "Nenhuma pasta data/v3_* encontrada."
    )

pasta_v3 = Path(pastas_v3[0])

arquivo_v3 = pasta_v3 / "backtest_v3.csv"
arquivo_bt = DATA / "backtesting_py_trades.csv"


# ---------------------------------------------------------
# 2. Carregar arquivos
# ---------------------------------------------------------

v3 = pd.read_csv(arquivo_v3)
bt = pd.read_csv(arquivo_bt)


# ---------------------------------------------------------
# 3. Selecionar V3 conservador executado
# ---------------------------------------------------------

v3 = v3[
    v3["cenario"].astype(str).str.lower()
    == "conservador"
].copy()

v3 = v3[
    v3["executada"].astype(str).str.lower()
    .isin(["true", "1", "sim"])
].copy()


# ---------------------------------------------------------
# 4. Converter datas/horários
# ---------------------------------------------------------

for col in [
    "horario_entrada",
    "horario_saida",
]:
    v3[col] = pd.to_datetime(
        v3[col],
        utc=True,
        errors="coerce"
    )

bt["EntryTime"] = pd.to_datetime(
    bt["EntryTime"],
    utc=True,
    errors="coerce"
)

bt["ExitTime"] = pd.to_datetime(
    bt["ExitTime"],
    utc=True,
    errors="coerce"
)


# ---------------------------------------------------------
# 5. Criar chave pela data da operação
# ---------------------------------------------------------

v3["data_chave"] = pd.to_datetime(
    v3["data"]
).dt.strftime("%Y-%m-%d")

bt["data_chave"] = pd.to_datetime(
    bt["Tag"]
).dt.strftime("%Y-%m-%d")


# ---------------------------------------------------------
# 6. Renomear colunas
# ---------------------------------------------------------

v3_cmp = v3[
    [
        "data_chave",
        "direcao",
        "entrada",
        "stop",
        "alvo",
        "horario_entrada",
        "horario_saida",
        "preco_saida",
        "motivo_saida",
        "resultado_bruto_r",
        "resultado_liquido_r",
        "ambiguo",
    ]
].copy()

v3_cmp = v3_cmp.rename(
    columns={
        "entrada": "entrada_v3",
        "stop": "stop_v3",
        "alvo": "alvo_v3",
        "horario_entrada": "entrada_time_v3",
        "horario_saida": "saida_time_v3",
        "preco_saida": "saida_preco_v3",
        "motivo_saida": "motivo_v3",
        "resultado_bruto_r": "resultado_r_v3",
        "resultado_liquido_r": "resultado_liquido_r_v3",
        "ambiguo": "ambiguo_v3",
    }
)


bt_cmp = bt[
    [
        "data_chave",
        "Size",
        "EntryPrice",
        "ExitPrice",
        "SL",
        "TP",
        "PnL",
        "EntryTime",
        "ExitTime",
    ]
].copy()

bt_cmp["direcao_bt"] = bt_cmp["Size"].apply(
    lambda x: "COMPRA" if x > 0 else "VENDA"
)

bt_cmp = bt_cmp.rename(
    columns={
        "EntryPrice": "entrada_bt",
        "ExitPrice": "saida_preco_bt",
        "SL": "stop_bt",
        "TP": "alvo_bt",
        "PnL": "pnl_pontos_bt",
        "EntryTime": "entrada_time_bt",
        "ExitTime": "saida_time_bt",
    }
)


# ---------------------------------------------------------
# 7. Juntar os motores
# ---------------------------------------------------------

cmp = v3_cmp.merge(
    bt_cmp,
    on="data_chave",
    how="outer",
    indicator=True
)


# ---------------------------------------------------------
# 8. Resultado em R no backtesting.py
# ---------------------------------------------------------

cmp["risco_bt"] = (
    cmp["entrada_bt"]
    - cmp["stop_bt"]
).abs()

cmp["resultado_r_bt"] = (
    cmp["pnl_pontos_bt"]
    / cmp["risco_bt"]
)


# ---------------------------------------------------------
# 9. Comparações
# ---------------------------------------------------------

TOL_PRECO = 1e-9
TOL_R = 1e-6


cmp["mesma_direcao"] = (
    cmp["direcao"]
    == cmp["direcao_bt"]
)

cmp["mesma_entrada"] = (
    (cmp["entrada_v3"] - cmp["entrada_bt"]).abs()
    <= TOL_PRECO
)

cmp["mesmo_stop"] = (
    (cmp["stop_v3"] - cmp["stop_bt"]).abs()
    <= TOL_PRECO
)

cmp["mesmo_alvo"] = (
    (cmp["alvo_v3"] - cmp["alvo_bt"]).abs()
    <= TOL_PRECO
)

cmp["mesmo_horario_entrada"] = (
    cmp["entrada_time_v3"]
    == cmp["entrada_time_bt"]
)

cmp["mesmo_horario_saida"] = (
    cmp["saida_time_v3"]
    == cmp["saida_time_bt"]
)

cmp["mesmo_preco_saida"] = (
    (
        cmp["saida_preco_v3"]
        - cmp["saida_preco_bt"]
    ).abs()
    <= TOL_PRECO
)

cmp["mesmo_resultado_r"] = (
    (
        cmp["resultado_r_v3"]
        - cmp["resultado_r_bt"]
    ).abs()
    <= TOL_R
)


# ---------------------------------------------------------
# 10. Classificação geral
# ---------------------------------------------------------

cmp["entrada_niveis_iguais"] = (
    cmp[
        [
            "mesma_direcao",
            "mesma_entrada",
            "mesmo_stop",
            "mesmo_alvo",
        ]
    ].all(axis=1)
)

cmp["saida_igual"] = (
    cmp[
        [
            "mesmo_horario_saida",
            "mesmo_preco_saida",
            "mesmo_resultado_r",
        ]
    ].all(axis=1)
)

cmp["operacao_totalmente_igual"] = (
    cmp[
        [
            "entrada_niveis_iguais",
            "mesmo_horario_entrada",
            "saida_igual",
        ]
    ].all(axis=1)
)


# ---------------------------------------------------------
# 11. Resumo
# ---------------------------------------------------------

print("\n========== COMPARAÇÃO V3 x BACKTESTING.PY ==========")

print("Operações comparadas:", len(cmp))

print(
    "Direção igual:",
    int(cmp["mesma_direcao"].sum())
)

print(
    "Entrada igual:",
    int(cmp["mesma_entrada"].sum())
)

print(
    "Stop igual:",
    int(cmp["mesmo_stop"].sum())
)

print(
    "Alvo igual:",
    int(cmp["mesmo_alvo"].sum())
)

print(
    "Horário de entrada igual:",
    int(cmp["mesmo_horario_entrada"].sum())
)

print(
    "Preço de saída igual:",
    int(cmp["mesmo_preco_saida"].sum())
)

print(
    "Horário de saída igual:",
    int(cmp["mesmo_horario_saida"].sum())
)

print(
    "Resultado em R igual:",
    int(cmp["mesmo_resultado_r"].sum())
)

print(
    "Operações totalmente iguais:",
    int(cmp["operacao_totalmente_igual"].sum())
)


# ---------------------------------------------------------
# 12. Divergentes
# ---------------------------------------------------------

divergentes = cmp[
    ~cmp["operacao_totalmente_igual"]
].copy()

print(
    "\nOperações divergentes:",
    len(divergentes)
)


# ---------------------------------------------------------
# 13. Resumo das divergências
# ---------------------------------------------------------

print("\nDivergências por tipo:")

for coluna in [
    "mesma_direcao",
    "mesma_entrada",
    "mesmo_stop",
    "mesmo_alvo",
    "mesmo_horario_entrada",
    "mesmo_horario_saida",
    "mesmo_preco_saida",
    "mesmo_resultado_r",
]:

    qtd = int(
        (~cmp[coluna]).sum()
    )

    print(
        f"{coluna}: {qtd}"
    )


# ---------------------------------------------------------
# 14. Mostrar divergentes
# ---------------------------------------------------------

colunas_saida = [
    "data_chave",
    "direcao",
    "entrada_v3",
    "entrada_bt",
    "stop_v3",
    "stop_bt",
    "alvo_v3",
    "alvo_bt",
    "entrada_time_v3",
    "entrada_time_bt",
    "saida_time_v3",
    "saida_time_bt",
    "saida_preco_v3",
    "saida_preco_bt",
    "resultado_r_v3",
    "resultado_r_bt",
    "motivo_v3",
    "ambiguo_v3",
]

print(
    "\n========== PRIMEIRAS DIVERGÊNCIAS =========="
)

print(
    divergentes[
        colunas_saida
    ].head(30).to_string(
        index=False
    )
)


# ---------------------------------------------------------
# 15. Exportações
# ---------------------------------------------------------

arquivo_completo = (
    DATA
    / "comparacao_v3_backtesting_194.csv"
)

arquivo_divergencias = (
    DATA
    / "divergencias_v3_backtesting.csv"
)

cmp.to_csv(
    arquivo_completo,
    index=False
)

divergentes[
    colunas_saida
].to_csv(
    arquivo_divergencias,
    index=False
)


print("\nArquivos criados:")

print(arquivo_completo)
print(arquivo_divergencias)