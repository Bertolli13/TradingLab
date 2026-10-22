from pathlib import Path

import pandas as pd


# =========================================================
# CONFIGURAÇÃO
# =========================================================

PROJETO = Path(__file__).resolve().parent
DATA = PROJETO / "data"

DATA_CORTE = pd.Timestamp("2026-10-08")

ARQUIVO_PLACAR = DATA / "forward_placar_v5.csv"
ARQUIVO_TRADES = DATA / "forward_trades_conservador_v5.csv"
ARQUIVO_EXCLUSAO = DATA / "forward_trades_exclusao_v5.csv"


# =========================================================
# LOCALIZAR ÚLTIMA EXECUÇÃO V5
# =========================================================

def encontrar_ultima_pasta_v5():
    pastas = [
        pasta
        for pasta in DATA.glob("v5_forward_*")
        if pasta.is_dir()
    ]

    if not pastas:
        raise FileNotFoundError(
            "Nenhuma pasta v5_forward_* foi encontrada."
        )

    return max(
        pastas,
        key=lambda pasta: pasta.stat().st_mtime
    )


# =========================================================
# LOCALIZAR CSV PRINCIPAL
# =========================================================

def encontrar_csv_backtest(pasta):
    candidatos = [
        pasta / "backtest_v3.csv",
        pasta / "trades_v3.csv",
        pasta / "resultados_v3.csv",
    ]

    for arquivo in candidatos:
        if arquivo.exists():
            return arquivo

    csvs = list(
        pasta.glob("*.csv")
    )

    for arquivo in csvs:
        try:
            df = pd.read_csv(
                arquivo,
                nrows=5
            )

            colunas = set(
                df.columns
            )

            obrigatorias = {
                "data",
                "cenario",
            }

            if obrigatorias.issubset(
                colunas
            ):
                return arquivo

        except Exception:
            continue

    raise FileNotFoundError(
        "Não encontrei o CSV principal "
        f"do backtest dentro de {pasta}"
    )


# =========================================================
# UTILIDADES
# =========================================================

def converter_data(df):
    copia = df.copy()

    copia["data"] = pd.to_datetime(
        copia["data"],
        errors="coerce"
    )

    copia = copia[
        copia["data"].notna()
    ].copy()

    return copia


def numero(
    serie,
    coluna,
    default=0.0
):
    if coluna not in serie.columns:
        return pd.Series(
            default,
            index=serie.index,
            dtype=float
        )

    return pd.to_numeric(
        serie[coluna],
        errors="coerce"
    ).fillna(
        default
    )


def booleano(
    df,
    coluna,
    default=False
):
    if coluna not in df.columns:
        return pd.Series(
            default,
            index=df.index
        )

    valores = (
        df[coluna]
        .astype(str)
        .str.strip()
        .str.lower()
    )

    return valores.isin(
        [
            "true",
            "1",
            "sim",
            "yes",
        ]
    )


# =========================================================
# MÉTRICAS
# =========================================================

def calcular_metricas(
    df,
    nome
):
    quantidade = len(df)

    if quantidade == 0:
        return {
            "modelo": nome,
            "operacoes": 0,
            "wins": 0,
            "losses": 0,
            "win_rate_pct": 0.0,
            "liquido_r": 0.0,
            "media_r": 0.0,
            "profit_factor": 0.0,
            "max_drawdown_r": 0.0,
            "liquido_usd": 0.0,
        }

    resultados = numero(
        df,
        "resultado_liquido_r"
    )

    wins = int(
        (resultados > 0).sum()
    )

    losses = int(
        (resultados < 0).sum()
    )

    win_rate = (
        wins
        / quantidade
        * 100
    )

    liquido_r = float(
        resultados.sum()
    )

    media_r = float(
        resultados.mean()
    )

    ganhos = float(
        resultados[
            resultados > 0
        ].sum()
    )

    perdas = abs(
        float(
            resultados[
                resultados < 0
            ].sum()
        )
    )

    if perdas > 0:
        profit_factor = (
            ganhos
            / perdas
        )

    elif ganhos > 0:
        profit_factor = float("inf")

    else:
        profit_factor = 0.0

    equity = resultados.cumsum()

    pico = equity.cummax()

    drawdown = (
        equity
        - pico
    )

    max_drawdown = abs(
        float(
            drawdown.min()
        )
    )

    if "resultado_liquido_usd" in df.columns:
        liquido_usd = float(
            numero(
                df,
                "resultado_liquido_usd"
            ).sum()
        )

    elif "liquido_usd" in df.columns:
        liquido_usd = float(
            numero(
                df,
                "liquido_usd"
            ).sum()
        )

    elif "resultado_usd" in df.columns:
        liquido_usd = float(
            numero(
                df,
                "resultado_usd"
            ).sum()
        )

    else:
        liquido_usd = 0.0

    return {
        "modelo": nome,
        "operacoes": quantidade,
        "wins": wins,
        "losses": losses,
        "win_rate_pct": win_rate,
        "liquido_r": liquido_r,
        "media_r": media_r,
        "profit_factor": profit_factor,
        "max_drawdown_r": max_drawdown,
        "liquido_usd": liquido_usd,
    }


# =========================================================
# MAIN
# =========================================================

def main():
    pasta = (
        encontrar_ultima_pasta_v5()
    )

    print()
    print(
        "Pasta V5 encontrada:"
    )
    print(
        pasta
    )

    arquivo = (
        encontrar_csv_backtest(
            pasta
        )
    )

    print()
    print(
        "CSV utilizado:"
    )
    print(
        arquivo
    )

    df = pd.read_csv(
        arquivo
    )

    print()
    print(
        f"Linhas totais: {len(df)}"
    )

    print(
        "Colunas:"
    )

    print(
        list(df.columns)
    )

    df = converter_data(
        df
    )

    # =====================================================
    # APENAS FORWARD
    # =====================================================

    forward = df[
        df["data"]
        > DATA_CORTE
    ].copy()

    print()
    print(
        "Período forward:"
    )

    print(
        f"> {DATA_CORTE.date()}"
    )

    print(
        f"Linhas forward: {len(forward)}"
    )

    if not forward.empty:
        print(
            "Primeira data:",
            forward["data"].min().date()
        )

        print(
            "Última data:",
            forward["data"].max().date()
        )

    # =====================================================
    # CONSERVADOR
    # =====================================================

    conservador = forward[
        forward["cenario"]
        .astype(str)
        .str.lower()
        .eq("conservador")
    ].copy()

    # Se existir executada, manter somente trades executados
    if "executada" in conservador.columns:
        executadas = booleano(
            conservador,
            "executada"
        )

        conservador_exec = (
            conservador[
                executadas
            ].copy()
        )

    else:
        conservador_exec = (
            conservador.copy()
        )

    # =====================================================
    # EXCLUSÃO
    # =====================================================

    exclusao = forward[
        forward["cenario"]
        .astype(str)
        .str.lower()
        .eq("exclusao")
    ].copy()

    if "executada" in exclusao.columns:
        executadas_exclusao = booleano(
            exclusao,
            "executada"
        )

        exclusao_exec = (
            exclusao[
                executadas_exclusao
            ].copy()
        )

    else:
        exclusao_exec = (
            exclusao.copy()
        )

    # =====================================================
    # AMBÍGUOS
    # =====================================================

    if "ambiguo" in conservador_exec.columns:
        ambiguos = booleano(
            conservador_exec,
            "ambiguo"
        )

        somente_ambiguos = (
            conservador_exec[
                ambiguos
            ].copy()
        )

        nao_ambiguos = (
            conservador_exec[
                ~ambiguos
            ].copy()
        )

    else:
        somente_ambiguos = (
            conservador_exec.iloc[
                0:0
            ].copy()
        )

        nao_ambiguos = (
            conservador_exec.copy()
        )

    # =====================================================
    # PLACAR
    # =====================================================

    placar = pd.DataFrame(
        [
            calcular_metricas(
                conservador_exec,
                "V5_conservador"
            ),

            calcular_metricas(
                exclusao_exec,
                "V5_exclusao"
            ),

            calcular_metricas(
                somente_ambiguos,
                "Somente_ambiguos"
            ),

            calcular_metricas(
                nao_ambiguos,
                "Nao_ambiguos"
            ),
        ]
    )

    # =====================================================
    # EXPORTAR
    # =====================================================

    placar.to_csv(
        ARQUIVO_PLACAR,
        index=False
    )

    conservador_exec.to_csv(
        ARQUIVO_TRADES,
        index=False
    )

    exclusao_exec.to_csv(
        ARQUIVO_EXCLUSAO,
        index=False
    )

    # =====================================================
    # RESULTADO
    # =====================================================

    print()
    print(
        "=" * 75
    )

    print(
        "V5 FORWARD - PLACAR OOS"
    )

    print(
        "=" * 75
    )

    if placar.empty:
        print(
            "Nenhum resultado forward."
        )

    else:
        print(
            placar.to_string(
                index=False
            )
        )

    print()
    print(
        "Arquivos gerados:"
    )

    print(
        ARQUIVO_PLACAR
    )

    print(
        ARQUIVO_TRADES
    )

    print(
        ARQUIVO_EXCLUSAO
    )


if __name__ == "__main__":
    main()