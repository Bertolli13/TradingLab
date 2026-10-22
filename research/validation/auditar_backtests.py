
import pandas as pd

v1 = pd.read_csv("data/backtest_orb_fvg.csv")
v2 = pd.read_csv("data/backtest_v2.csv")

colunas_v1 = [
    "data",
    "direcao",
    "executada",
    "resultado_r",
    "motivo_saida"
]

colunas_v2 = [
    "data",
    "direcao",
    "executada",
    "resultado_bruto_r",
    "resultado_liquido_r",
    "motivo_saida"
]

a = v1[colunas_v1].rename(columns={
    "executada": "executada_v1",
    "resultado_r": "resultado_v1",
    "motivo_saida": "motivo_v1"
})

b = v2[colunas_v2].rename(columns={
    "executada": "executada_v2",
    "resultado_bruto_r": "resultado_v2",
    "motivo_saida": "motivo_v2"
})

comparacao = a.merge(
    b,
    on=["data", "direcao"],
    how="outer",
    validate="one_to_one"
)

comparacao["diferenca_r"] = (
    comparacao["resultado_v2"]
    - comparacao["resultado_v1"]
)

mudaram = comparacao[
    comparacao["resultado_v1"].notna()
    & comparacao["resultado_v2"].notna()
    & (comparacao["diferenca_r"].abs() > 0.000001)
].copy()

print("\n===== AUDITORIA V1 X V2 =====")
print("Total de registros:", len(comparacao))
print("Operações que mudaram:", len(mudaram))

print("\nTransições de resultado:")
print(
    mudaram.groupby(["motivo_v1", "motivo_v2"])
    .size()
    .to_string()
)

print("\nOperações alteradas:")
print(
    mudaram[
        [
            "data",
            "direcao",
            "resultado_v1",
            "resultado_v2",
            "motivo_v1",
            "motivo_v2"
        ]
    ].to_string(index=False)
)

saida = "data/auditoria_v1_v2.csv"
comparacao.to_csv(saida, index=False)

print("\nArquivo salvo:", saida)
