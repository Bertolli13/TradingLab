from pathlib import Path

import pandas as pd


DATA = Path("data")

arquivo = (
    DATA
    / "comparacao_v3_backtesting_194.csv"
)

df = pd.read_csv(arquivo)


# ---------------------------------------------------------
# 1. Apenas trades cujo resultado em R diverge
# ---------------------------------------------------------

div = df[
    df["mesmo_resultado_r"] == False
].copy()


print(
    "\n========== RESULTADOS DIVERGENTES =========="
)

print("Quantidade:", len(div))


# ---------------------------------------------------------
# 2. Diferença em R
# ---------------------------------------------------------

div["diferenca_r"] = (
    div["resultado_r_bt"]
    - div["resultado_r_v3"]
)


colunas = [
    "data_chave",
    "direcao",
    "entrada_v3",
    "entrada_bt",
    "stop_v3",
    "alvo_v3",
    "saida_preco_v3",
    "saida_preco_bt",
    "resultado_r_v3",
    "resultado_r_bt",
    "diferenca_r",
    "entrada_time_v3",
    "entrada_time_bt",
    "saida_time_v3",
    "saida_time_bt",
    "motivo_v3",
    "ambiguo_v3",
]


print(
    div[colunas].to_string(
        index=False
    )
)


# ---------------------------------------------------------
# 3. Impacto agregado
# ---------------------------------------------------------

print(
    "\n========== IMPACTO =========="
)

print(
    "Resultado V3 nesses trades:",
    round(
        div["resultado_r_v3"].sum(),
        6
    ),
    "R"
)

print(
    "Resultado backtesting.py nesses trades:",
    round(
        div["resultado_r_bt"].sum(),
        6
    ),
    "R"
)

print(
    "Diferença:",
    round(
        div["diferenca_r"].sum(),
        6
    ),
    "R"
)


# ---------------------------------------------------------
# 4. Resultado bruto completo do BT em R
# ---------------------------------------------------------

resultado_bt_total = (
    df["resultado_r_bt"].sum()
)

resultado_v3_total = (
    df["resultado_r_v3"].sum()
)

print(
    "\n========== RESULTADO BRUTO TOTAL =========="
)

print(
    "V3:",
    round(resultado_v3_total, 6),
    "R"
)

print(
    "Backtesting.py:",
    round(resultado_bt_total, 6),
    "R"
)

print(
    "Diferença total:",
    round(
        resultado_bt_total
        - resultado_v3_total,
        6
    ),
    "R"
)


# ---------------------------------------------------------
# 5. Exportar
# ---------------------------------------------------------

saida = (
    DATA
    / "auditoria_9_resultados.csv"
)

div[colunas].to_csv(
    saida,
    index=False
)

print("\nCSV criado:")
print(saida)