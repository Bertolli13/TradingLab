from pathlib import Path

import pandas as pd

from live_engine import (
    LiveEngine,
    carregar_replay,
    ARQUIVO_REPLAY,
)


# ============================================================
# CONFIGURAÇÃO
# ============================================================

PROJETO = Path(__file__).resolve().parent
DATA = PROJETO / "data"

ARQUIVO_OFICIAL = (
    DATA / "orb_fvg_forward_v4.csv"
)

SAIDA_COMPARACAO = (
    DATA / "validacao_live_fvg.csv"
)


# ============================================================
# NORMALIZAÇÕES
# ============================================================

def normalizar_bool(valor):
    if pd.isna(valor):
        return False

    if isinstance(valor, bool):
        return valor

    return (
        str(valor)
        .strip()
        .lower()
        in {
            "true",
            "1",
            "sim",
            "yes"
        }
    )


def normalizar_numero(valor):
    if pd.isna(valor):
        return None

    return float(valor)


def normalizar_horario(valor):
    if (
        valor is None
        or pd.isna(valor)
    ):
        return None

    ts = pd.Timestamp(valor)

    if ts.tzinfo is None:
        return ts.isoformat()

    return ts.isoformat()


def numeros_iguais(
    a,
    b,
    tolerancia=1e-9
):
    a = normalizar_numero(a)
    b = normalizar_numero(b)

    if a is None and b is None:
        return True

    if a is None or b is None:
        return False

    return abs(a - b) <= tolerancia


# ============================================================
# EXECUTAR UM DIA
# ============================================================

def executar_dia(
    dia: pd.DataFrame
):
    engine = LiveEngine()

    for _, linha in dia.iterrows():

        candle = {
            "datetime":
                linha["datetime"],

            "open":
                linha["open"],

            "high":
                linha["high"],

            "low":
                linha["low"],

            "close":
                linha["close"],

            "volume":
                linha.get(
                    "volume"
                )
        }

        engine.processar_candle(
            candle
        )

    return engine.obter_estado()


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "=" * 80
    )

    print(
        "VALIDAÇÃO HISTÓRICA"
    )

    print(
        "LIVE ENGINE × FVG OFICIAL"
    )

    print(
        "=" * 80
    )

    # --------------------------------------------------------
    # DADOS DE CANDLES
    # --------------------------------------------------------

    candles = carregar_replay(
        ARQUIVO_REPLAY
    )

    candles["datetime_ny"] = (
        candles["datetime"]
        .dt
        .tz_convert(
            "America/New_York"
        )
    )

    candles["data"] = (
        candles[
            "datetime_ny"
        ]
        .dt
        .strftime(
            "%Y-%m-%d"
        )
    )

    # --------------------------------------------------------
    # RESULTADO OFICIAL
    # --------------------------------------------------------

    oficial = pd.read_csv(
        ARQUIVO_OFICIAL
    )

    oficial["data"] = (
        oficial["data"]
        .astype(str)
    )

    print(
        "Candles:",
        f"{len(candles):,}"
    )

    print(
        "Sinais oficiais:",
        f"{len(oficial):,}"
    )

    print()

    resultados = []

    total = len(oficial)

    # ========================================================
    # CADA DIA COM ROMPIMENTO OFICIAL
    # ========================================================

    for numero_linha, (
        _,
        sinal
    ) in enumerate(
        oficial.iterrows(),
        start=1
    ):

        data = sinal["data"]

        dia = (
            candles[
                candles["data"]
                ==
                data
            ]
            .copy()
            .sort_values(
                "datetime"
            )
            .reset_index(
                drop=True
            )
        )

        if dia.empty:

            resultados.append({
                "data":
                    data,

                "erro":
                    "SEM_CANDLES"
            })

            print(
                f"[{numero_linha}/{total}] "
                f"{data} "
                f"SEM CANDLES"
            )

            continue

        estado = executar_dia(
            dia
        )

        # ----------------------------------------------------
        # OFICIAL
        # ----------------------------------------------------

        oficial_fvg = (
            normalizar_bool(
                sinal[
                    "fvg_encontrado"
                ]
            )
        )

        oficial_motivo = (
            str(
                sinal["motivo"]
            )
        )

        oficial_fvg_min = (
            normalizar_numero(
                sinal["fvg_min"]
            )
        )

        oficial_fvg_max = (
            normalizar_numero(
                sinal["fvg_max"]
            )
        )

        oficial_tamanho = (
            normalizar_numero(
                sinal[
                    "tamanho_fvg"
                ]
            )
        )

        oficial_horario = (
            normalizar_horario(
                sinal[
                    "horario_fvg"
                ]
            )
        )

        # ----------------------------------------------------
        # LIVE
        # ----------------------------------------------------

        live_fvg = bool(
            estado[
                "fvg_detectado"
            ]
        )

        live_motivo = (
            estado[
                "motivo_fvg"
            ]
        )

        live_fvg_min = (
            estado[
                "fvg_low"
            ]
        )

        live_fvg_max = (
            estado[
                "fvg_high"
            ]
        )

        live_tamanho = (
            estado[
                "tamanho_fvg"
            ]
        )

        live_horario = (
            normalizar_horario(
                estado[
                    "horario_fvg"
                ]
            )
        )

        # ----------------------------------------------------
        # COMPARAÇÕES
        # ----------------------------------------------------

        bate_fvg = (
            oficial_fvg
            ==
            live_fvg
        )

        bate_motivo = (
            oficial_motivo
            ==
            live_motivo
        )

        bate_min = (
            numeros_iguais(
                oficial_fvg_min,
                live_fvg_min
            )
        )

        bate_max = (
            numeros_iguais(
                oficial_fvg_max,
                live_fvg_max
            )
        )

        bate_tamanho = (
            numeros_iguais(
                oficial_tamanho,
                live_tamanho
            )
        )

        # Comparar timestamp somente
        # quando houver FVG.
        if oficial_fvg:

            bate_horario = (
                oficial_horario
                ==
                live_horario
            )

        else:

            bate_horario = (
                live_horario
                is None
            )

        tudo_bate = all([
            bate_fvg,
            bate_motivo,
            bate_min,
            bate_max,
            bate_tamanho,
            bate_horario,
        ])

        resultados.append({
            "data":
                data,

            "oficial_direcao":
                sinal["direcao"],

            "live_direcao":
                estado["direcao"],

            "oficial_fvg":
                oficial_fvg,

            "live_fvg":
                live_fvg,

            "oficial_motivo":
                oficial_motivo,

            "live_motivo":
                live_motivo,

            "oficial_horario_fvg":
                oficial_horario,

            "live_horario_fvg":
                live_horario,

            "oficial_fvg_min":
                oficial_fvg_min,

            "live_fvg_min":
                live_fvg_min,

            "oficial_fvg_max":
                oficial_fvg_max,

            "live_fvg_max":
                live_fvg_max,

            "oficial_tamanho_fvg":
                oficial_tamanho,

            "live_tamanho_fvg":
                live_tamanho,

            "bate_fvg":
                bate_fvg,

            "bate_motivo":
                bate_motivo,

            "bate_horario":
                bate_horario,

            "bate_min":
                bate_min,

            "bate_max":
                bate_max,

            "bate_tamanho":
                bate_tamanho,

            "tudo_bate":
                tudo_bate,

            "erro":
                None
        })

        status = (
            "OK"
            if tudo_bate
            else "DIVERGÊNCIA"
        )

        print(
            f"[{numero_linha}/{total}] "
            f"{data} "
            f"{status}"
        )

    # ========================================================
    # RESULTADO
    # ========================================================

    comparacao = pd.DataFrame(
        resultados
    )

    comparacao.to_csv(
        SAIDA_COMPARACAO,
        index=False
    )

    print()

    print(
        "=" * 80
    )

    print(
        "RESUMO"
    )

    print(
        "=" * 80
    )

    validos = comparacao[
        comparacao["erro"].isna()
    ]

    total_validado = (
        len(validos)
    )

    total_ok = int(
        validos[
            "tudo_bate"
        ].sum()
    )

    total_divergencias = (
        total_validado
        -
        total_ok
    )

    percentual = (
        total_ok
        /
        total_validado
        *
        100
        if total_validado
        else 0
    )

    print(
        "Sinais validados:",
        total_validado
    )

    print(
        "Equivalentes:",
        total_ok
    )

    print(
        "Divergências:",
        total_divergencias
    )

    print(
        "Equivalência:",
        f"{percentual:.4f}%"
    )

    # --------------------------------------------------------
    # MOTIVOS
    # --------------------------------------------------------

    print()

    print(
        "Motivos oficiais:"
    )

    print(
        validos[
            "oficial_motivo"
        ]
        .value_counts()
        .to_string()
    )

    print()

    print(
        "Motivos Live:"
    )

    print(
        validos[
            "live_motivo"
        ]
        .value_counts()
        .to_string()
    )

    # --------------------------------------------------------
    # DIVERGÊNCIAS
    # --------------------------------------------------------

    divergencias = validos[
        ~validos[
            "tudo_bate"
        ]
    ]

    if not divergencias.empty:

        print()

        print(
            "=" * 80
        )

        print(
            "PRIMEIRAS DIVERGÊNCIAS"
        )

        print(
            "=" * 80
        )

        colunas = [
            "data",
            "oficial_direcao",
            "live_direcao",
            "oficial_fvg",
            "live_fvg",
            "oficial_motivo",
            "live_motivo",
            "oficial_horario_fvg",
            "live_horario_fvg",
            "oficial_fvg_min",
            "live_fvg_min",
            "oficial_fvg_max",
            "live_fvg_max",
        ]

        print(
            divergencias[
                colunas
            ]
            .head(20)
            .to_string(
                index=False
            )
        )

    print()

    print(
        "Arquivo salvo:"
    )

    print(
        SAIDA_COMPARACAO
    )


if __name__ == "__main__":
    main()