from pathlib import Path

import numpy as np
import pandas as pd

from live_engine import (
    LiveEngine,
    carregar_replay,
    ARQUIVO_REPLAY,
)

from paper_engine_v4 import (
    PaperEngineV4,
)


# ============================================================
# CONFIGURAÇÃO
# ============================================================

PROJETO = Path(__file__).resolve().parent
DATA = PROJETO / "data"

ARQUIVO_SINAIS = (
    DATA / "orb_fvg_forward_v4.csv"
)

# Último diretório v4_forward gerado pelo pipeline
PREFIXO_V4 = "v4_forward_"

SAIDA = (
    DATA / "validacao_paper_v4.csv"
)


# ============================================================
# UTILIDADES
# ============================================================

def ultimo_diretorio_v4() -> Path:

    candidatos = [
        pasta
        for pasta in DATA.iterdir()
        if (
            pasta.is_dir()
            and
            pasta.name.startswith(
                PREFIXO_V4
            )
        )
    ]

    if not candidatos:

        raise FileNotFoundError(
            "Nenhum diretório v4_forward encontrado."
        )

    return max(
        candidatos,
        key=lambda p:
            p.stat().st_mtime
    )


def numero(valor):

    if valor is None:
        return None

    if pd.isna(valor):
        return None

    return float(valor)


def texto(valor):

    if valor is None:
        return None

    if pd.isna(valor):
        return None

    valor = str(valor).strip()

    if valor == "":
        return None

    return valor


def booleano(valor):

    if isinstance(valor, bool):
        return valor

    if pd.isna(valor):
        return False

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


def iguais_numero(
    a,
    b,
    tolerancia=1e-8
):

    a = numero(a)
    b = numero(b)

    if a is None and b is None:
        return True

    if a is None or b is None:
        return False

    return bool(
        np.isclose(
            a,
            b,
            rtol=0,
            atol=tolerancia
        )
    )


def normalizar_timestamp(
    valor
):

    if valor is None:
        return None

    if pd.isna(valor):
        return None

    valor = str(valor).strip()

    if not valor:
        return None

    ts = pd.Timestamp(valor)

    if ts.tzinfo is None:

        # Saídas do V3 normalmente já estão em UTC,
        # mas deixamos explícito.
        ts = ts.tz_localize(
            "UTC"
        )

    else:

        ts = ts.tz_convert(
            "UTC"
        )

    return ts.isoformat()


# ============================================================
# CARREGAR BACKTEST OFICIAL
# ============================================================

def carregar_oficial():

    pasta = ultimo_diretorio_v4()

    arquivo = (
        pasta / "backtest_v3.csv"
    )

    if not arquivo.exists():

        raise FileNotFoundError(
            f"Arquivo não encontrado: {arquivo}"
        )

    df = pd.read_csv(
        arquivo,
        dtype={
            "data": str
        }
    )

    df = df[
        df["cenario"]
        ==
        "conservador"
    ].copy()

    return pasta, df


# ============================================================
# EXECUTAR PAPER EM UM DIA
# ============================================================

def executar_dia(
    dia: pd.DataFrame
):

    live = LiveEngine()

    paper = PaperEngineV4()

    paper_ativado = False

    tamanho_fvg = None

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

        estado_live = (
            live.processar_candle(
                candle
            )
        )

        # ====================================================
        # ATIVAR PAPER NO PRIMEIRO FVG VÁLIDO
        # ====================================================

        if (
            estado_live.fvg_detectado
            and
            not paper_ativado
        ):

            tamanho_fvg = (
                estado_live.tamanho_fvg
            )

            c1 = {
                "open":
                    estado_live.fvg_c1_open,

                "high":
                    estado_live.fvg_c1_high,

                "low":
                    estado_live.fvg_c1_low,

                "close":
                    estado_live.fvg_c1_close,
            }

            paper.ativar(
                direcao=
                    estado_live.direcao,

                horario_fvg=
                    estado_live.horario_fvg,

                fvg_min=
                    estado_live.fvg_low,

                fvg_max=
                    estado_live.fvg_high,

                orb_min=
                    estado_live.orb_low,

                orb_max=
                    estado_live.orb_high,

                candle_c1=
                    c1,
            )

            paper_ativado = True

            # =================================================
            # IMPORTANTE
            #
            # Não processar novamente este candle no paper.
            # No V3, a ordem fica ativa em FVG + 1 minuto.
            # =================================================

            continue

        # ====================================================
        # APÓS ATIVAÇÃO
        # ====================================================

        if paper_ativado:

            paper.processar_candle(
                candle
            )

    # ========================================================
    # FINALIZAÇÃO
    # ========================================================

    if paper_ativado:

        paper.finalizar()

        resultado = (
            paper.obter_estado()
        )

    else:

        resultado = {
            "status":
                "SEM_FVG",

            "direcao":
                live.estado.direcao,

            "horario_fvg":
                None,

            "entrada":
                None,

            "stop":
                None,

            "alvo":
                None,

            "risco_pontos":
                None,

            "ordem_ativa_em":
                None,

            "executada":
                False,

            "horario_entrada":
                None,

            "horario_saida":
                None,

            "preco_saida":
                None,

            "motivo_saida":
                None,

            "ambiguo":
                False,

            "alternativas":
                0,

            "resultado_bruto_r":
                None,

            "custo_r":
                None,

            "resultado_liquido_r":
                None,

            "resultado_liquido_usd":
                None,
        }

    resultado[
        "tamanho_fvg"
    ] = tamanho_fvg

    return resultado


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "=" * 90
    )

    print(
        "VALIDAÇÃO PAPER V4 × BACKTEST V3 OFICIAL"
    )

    print(
        "=" * 90
    )

    candles = carregar_replay(
        ARQUIVO_REPLAY
    )

    candles[
        "datetime_ny"
    ] = (
        candles[
            "datetime"
        ]
        .dt
        .tz_convert(
            "America/New_York"
        )
    )

    candles[
        "data"
    ] = (
        candles[
            "datetime_ny"
        ]
        .dt
        .strftime(
            "%Y-%m-%d"
        )
    )

    sinais = pd.read_csv(
        ARQUIVO_SINAIS,
        dtype={
            "data": str
        }
    )

    sinais[
        "fvg_bool"
    ] = (
        sinais[
            "fvg_encontrado"
        ]
        .astype(str)
        .str
        .lower()
        .eq("true")
    )

    sinais = sinais[
        sinais[
            "fvg_bool"
        ]
    ].copy()

    pasta_oficial, oficial = (
        carregar_oficial()
    )

    print()
    print(
        "Diretório oficial:"
    )

    print(
        pasta_oficial
    )

    print()
    print(
        "FVGs válidos:",
        len(sinais)
    )

    print(
        "Linhas V3 conservador:",
        len(oficial)
    )

    print()

    resultados = []

    total = len(sinais)

    # ========================================================
    # CADA FVG VÁLIDO
    # ========================================================

    for posicao, (
        _,
        sinal
    ) in enumerate(
        sinais.iterrows(),
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

        oficial_dia = (
            oficial[
                oficial["data"]
                ==
                data
            ]
        )

        if dia.empty:

            resultados.append({
                "data":
                    data,

                "tudo_bate":
                    False,

                "erro":
                    "SEM_CANDLES"
            })

            print(
                f"[{posicao}/{total}] "
                f"{data} SEM_CANDLES"
            )

            continue

        if len(oficial_dia) != 1:

            resultados.append({
                "data":
                    data,

                "tudo_bate":
                    False,

                "erro":
                    "OFICIAL_NAO_UNICO"
            })

            print(
                f"[{posicao}/{total}] "
                f"{data} OFICIAL_NAO_UNICO"
            )

            continue

        paper = executar_dia(
            dia
        )

        ref = (
            oficial_dia.iloc[0]
        )

        # ====================================================
        # COMPARAÇÕES
        # ====================================================

        checks = {}

        checks[
            "bate_direcao"
        ] = (
            texto(
                paper["direcao"]
            )
            ==
            texto(
                ref["direcao"]
            )
        )

        checks[
            "bate_entrada"
        ] = iguais_numero(
            paper["entrada"],
            ref["entrada"]
        )

        checks[
            "bate_stop"
        ] = iguais_numero(
            paper["stop"],
            ref["stop"]
        )

        checks[
            "bate_alvo"
        ] = iguais_numero(
            paper["alvo"],
            ref["alvo"]
        )

        checks[
            "bate_risco"
        ] = iguais_numero(
            paper[
                "risco_pontos"
            ],
            ref[
                "risco_pontos"
            ]
        )

        checks[
            "bate_executada"
        ] = (
            bool(
                paper[
                    "executada"
                ]
            )
            ==
            booleano(
                ref[
                    "executada"
                ]
            )
        )

        checks[
            "bate_ambiguo"
        ] = (
            bool(
                paper[
                    "ambiguo"
                ]
            )
            ==
            booleano(
                ref[
                    "ambiguo"
                ]
            )
        )

        checks[
            "bate_motivo"
        ] = (
            texto(
                paper[
                    "motivo_saida"
                ]
            )
            ==
            texto(
                ref[
                    "motivo_saida"
                ]
            )
        )

        checks[
            "bate_horario_entrada"
        ] = (
            normalizar_timestamp(
                paper[
                    "horario_entrada"
                ]
            )
            ==
            normalizar_timestamp(
                ref[
                    "horario_entrada"
                ]
            )
        )

        checks[
            "bate_horario_saida"
        ] = (
            normalizar_timestamp(
                paper[
                    "horario_saida"
                ]
            )
            ==
            normalizar_timestamp(
                ref[
                    "horario_saida"
                ]
            )
        )

        checks[
            "bate_preco_saida"
        ] = iguais_numero(
            paper[
                "preco_saida"
            ],
            ref[
                "preco_saida"
            ]
        )

        checks[
            "bate_bruto_r"
        ] = iguais_numero(
            paper[
                "resultado_bruto_r"
            ],
            ref[
                "resultado_bruto_r"
            ]
        )

        checks[
            "bate_custo_r"
        ] = iguais_numero(
            paper[
                "custo_r"
            ],
            ref[
                "custo_r"
            ]
        )

        checks[
            "bate_liquido_r"
        ] = iguais_numero(
            paper[
                "resultado_liquido_r"
            ],
            ref[
                "resultado_liquido_r"
            ]
        )

        checks[
            "bate_liquido_usd"
        ] = iguais_numero(
            paper[
                "resultado_liquido_usd"
            ],
            ref[
                "resultado_liquido_usd"
            ]
        )

        tudo_bate = all(
            checks.values()
        )

        linha = {
            "data":
                data,

            "paper_tamanho_fvg":
                paper[
                    "tamanho_fvg"
                ],

            "paper_direcao":
                paper[
                    "direcao"
                ],

            "oficial_direcao":
                ref[
                    "direcao"
                ],

            "paper_entrada":
                paper[
                    "entrada"
                ],

            "oficial_entrada":
                ref[
                    "entrada"
                ],

            "paper_stop":
                paper[
                    "stop"
                ],

            "oficial_stop":
                ref[
                    "stop"
                ],

            "paper_alvo":
                paper[
                    "alvo"
                ],

            "oficial_alvo":
                ref[
                    "alvo"
                ],

            "paper_executada":
                paper[
                    "executada"
                ],

            "oficial_executada":
                booleano(
                    ref[
                        "executada"
                    ]
                ),

            "paper_ambiguo":
                paper[
                    "ambiguo"
                ],

            "oficial_ambiguo":
                booleano(
                    ref[
                        "ambiguo"
                    ]
                ),

            "paper_motivo":
                paper[
                    "motivo_saida"
                ],

            "oficial_motivo":
                ref[
                    "motivo_saida"
                ],

            "paper_horario_entrada":
                paper[
                    "horario_entrada"
                ],

            "oficial_horario_entrada":
                ref[
                    "horario_entrada"
                ],

            "paper_horario_saida":
                paper[
                    "horario_saida"
                ],

            "oficial_horario_saida":
                ref[
                    "horario_saida"
                ],

            "paper_preco_saida":
                paper[
                    "preco_saida"
                ],

            "oficial_preco_saida":
                ref[
                    "preco_saida"
                ],

            "paper_bruto_r":
                paper[
                    "resultado_bruto_r"
                ],

            "oficial_bruto_r":
                ref[
                    "resultado_bruto_r"
                ],

            "paper_liquido_r":
                paper[
                    "resultado_liquido_r"
                ],

            "oficial_liquido_r":
                ref[
                    "resultado_liquido_r"
                ],

            "paper_liquido_usd":
                paper[
                    "resultado_liquido_usd"
                ],

            "oficial_liquido_usd":
                ref[
                    "resultado_liquido_usd"
                ],

            **checks,

            "tudo_bate":
                tudo_bate,

            "erro":
                None,
        }

        resultados.append(
            linha
        )

        status = (
            "OK"
            if tudo_bate
            else "DIVERGÊNCIA"
        )

        print(
            f"[{posicao}/{total}] "
            f"{data} "
            f"{status}"
        )

    # ========================================================
    # DATAFRAME
    # ========================================================

    comparacao = pd.DataFrame(
        resultados
    )

    comparacao.to_csv(
        SAIDA,
        index=False
    )

    validos = comparacao[
        comparacao[
            "erro"
        ].isna()
    ]

    ok = int(
        validos[
            "tudo_bate"
        ].sum()
    )

    total_validos = len(
        validos
    )

    divergencias = (
        total_validos
        -
        ok
    )

    percentual = (
        ok
        /
        total_validos
        *
        100
        if total_validos
        else 0
    )

    # ========================================================
    # RESUMO
    # ========================================================

    print()

    print(
        "=" * 90
    )

    print(
        "RESUMO"
    )

    print(
        "=" * 90
    )

    print(
        "Sinais comparados:",
        total_validos
    )

    print(
        "Equivalentes:",
        ok
    )

    print(
        "Divergências:",
        divergencias
    )

    print(
        "Equivalência:",
        f"{percentual:.4f}%"
    )

    # ========================================================
    # DIVERGÊNCIAS
    # ========================================================

    falhas = validos[
        ~validos[
            "tudo_bate"
        ]
    ]

    if not falhas.empty:

        print()

        print(
            "=" * 90
        )

        print(
            "PRIMEIRAS DIVERGÊNCIAS"
        )

        print(
            "=" * 90
        )

        colunas = [
            "data",

            "paper_direcao",
            "oficial_direcao",

            "paper_entrada",
            "oficial_entrada",

            "paper_stop",
            "oficial_stop",

            "paper_alvo",
            "oficial_alvo",

            "paper_executada",
            "oficial_executada",

            "paper_ambiguo",
            "oficial_ambiguo",

            "paper_motivo",
            "oficial_motivo",

            "paper_horario_entrada",
            "oficial_horario_entrada",

            "paper_horario_saida",
            "oficial_horario_saida",

            "paper_bruto_r",
            "oficial_bruto_r",

            "paper_liquido_r",
            "oficial_liquido_r",
        ]

        print(
            falhas[
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
        SAIDA
    )


if __name__ == "__main__":
    main()