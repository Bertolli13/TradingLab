from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import time
from pathlib import Path
from typing import Optional

import pandas as pd


# ============================================================
# CONFIGURAÇÃO
# ============================================================

PROJETO = Path(__file__).resolve().parent
DATA = PROJETO / "data"

ARQUIVO_REPLAY = DATA / "nq_forward_v4.parquet"


# ============================================================
# PARÂMETROS
# ============================================================

FVG_MIN_PONTOS = 2.0
MAX_MINUTOS_FVG = 30

FIM_SESSAO = time(16, 40)

ORB_INICIO = time(9, 30)
ORB_FIM = time(9, 45)

FIM_ROMPIMENTO = time(11, 0)


# ============================================================
# ESTADO DO MOTOR
# ============================================================

@dataclass
class EstadoLive:
    modo: str = "PAPER"

    data: Optional[str] = None

    ultimo_candle_utc: Optional[str] = None
    ultimo_candle_ny: Optional[str] = None

    preco_atual: Optional[float] = None

    estado: str = "AGUARDANDO_DADOS"

    # ========================================================
    # ORB
    # ========================================================

    orb_pronta: bool = False

    orb_high: Optional[float] = None
    orb_low: Optional[float] = None
    orb_range: Optional[float] = None

    # ========================================================
    # ROMPIMENTO
    # ========================================================

    rompeu: bool = False

    direcao: Optional[str] = None

    horario_rompimento: Optional[str] = None
    preco_rompimento: Optional[float] = None

    # ========================================================
    # FVG
    # ========================================================

    fvg_detectado: bool = False

    motivo_fvg: Optional[str] = None

    horario_fvg: Optional[str] = None

    fvg_low: Optional[float] = None
    fvg_high: Optional[float] = None

    tamanho_fvg: Optional[float] = None

    # Candle C1 do padrão FVG.
    # Necessário para o stop do motor V3/V4.
    fvg_c1_open: Optional[float] = None
    fvg_c1_high: Optional[float] = None
    fvg_c1_low: Optional[float] = None
    fvg_c1_close: Optional[float] = None

    # ========================================================
    # OPERAÇÃO PAPER
    # ========================================================

    posicao: str = "FLAT"

    entrada: Optional[float] = None
    stop: Optional[float] = None
    alvo: Optional[float] = None

    # ========================================================
    # SEGURANÇA
    # ========================================================

    ordens_reais_habilitadas: bool = False


# ============================================================
# MOTOR AO VIVO
# ============================================================

class LiveEngine:

    def __init__(self) -> None:
        self.estado = EstadoLive()

        self.data_atual: Optional[str] = None

        self.candles_sessao: list[dict] = []

        self.candles_orb: list[dict] = []

        self.fvg_finalizado = False

    # ========================================================
    # RESET DA SESSÃO
    # ========================================================

    def reset_sessao(
        self,
        data_ny: str
    ) -> None:

        print(
            f"[LIVE] Nova sessão: {data_ny}"
        )

        self.data_atual = data_ny

        self.candles_sessao = []
        self.candles_orb = []

        self.fvg_finalizado = False

        self.estado = EstadoLive(
            modo="PAPER",
            data=data_ny,
            estado="AGUARDANDO_ORB",
            ordens_reais_habilitadas=False
        )

    # ========================================================
    # NORMALIZAR TIMESTAMP
    # ========================================================

    def normalizar_timestamp(
        self,
        valor
    ) -> pd.Timestamp:

        ts = pd.Timestamp(valor)

        if ts.tzinfo is None:
            ts = ts.tz_localize("UTC")

        else:
            ts = ts.tz_convert("UTC")

        return ts

    # ========================================================
    # PROCESSAR CANDLE
    # ========================================================

    def processar_candle(
        self,
        candle: dict
    ) -> EstadoLive:

        ts_utc = self.normalizar_timestamp(
            candle["datetime"]
        )

        ts_ny = ts_utc.tz_convert(
            "America/New_York"
        )

        data_ny = str(
            ts_ny.date()
        )

        hora_ny = ts_ny.time()

        # ====================================================
        # NOVA SESSÃO
        # ====================================================

        if self.data_atual != data_ny:
            self.reset_sessao(
                data_ny
            )

        registro = {
            "datetime_utc":
                ts_utc,

            "datetime_ny":
                ts_ny,

            "open":
                float(
                    candle["open"]
                ),

            "high":
                float(
                    candle["high"]
                ),

            "low":
                float(
                    candle["low"]
                ),

            "close":
                float(
                    candle["close"]
                ),

            "volume":
                (
                    float(
                        candle["volume"]
                    )
                    if pd.notna(
                        candle.get("volume")
                    )
                    else None
                )
        }

        self.candles_sessao.append(
            registro
        )

        # ====================================================
        # ATUALIZAÇÃO GERAL
        # ====================================================

        self.estado.ultimo_candle_utc = (
            ts_utc.isoformat()
        )

        self.estado.ultimo_candle_ny = (
            ts_ny.isoformat()
        )

        self.estado.preco_atual = (
            registro["close"]
        )

        # ====================================================
        # ANTES DA ABERTURA
        # ====================================================

        if hora_ny < ORB_INICIO:

            self.estado.estado = (
                "AGUARDANDO_ABERTURA"
            )

            return self.estado

        # ====================================================
        # FORMAÇÃO DA ORB
        # ====================================================

        if (
            ORB_INICIO
            <= hora_ny
            < ORB_FIM
        ):

            self.candles_orb.append(
                registro
            )

            self.estado.estado = (
                "FORMANDO_ORB"
            )

            self._atualizar_orb_parcial()

            return self.estado

        # ====================================================
        # FINALIZAR ORB
        # ====================================================

        if (
            hora_ny >= ORB_FIM
            and
            not self.estado.orb_pronta
        ):

            self._finalizar_orb()

        if not self.estado.orb_pronta:

            self.estado.estado = (
                "ORB_INCOMPLETA"
            )

            return self.estado

        # ====================================================
        # PROCURAR ROMPIMENTO
        # ====================================================

        if not self.estado.rompeu:

            if hora_ny > FIM_ROMPIMENTO:

                self.estado.estado = (
                    "SEM_ROMPIMENTO"
                )

                return self.estado

            self._detectar_rompimento(
                registro
            )

        # ====================================================
        # APÓS ROMPIMENTO
        # ====================================================

        if self.estado.rompeu:

            if not self.fvg_finalizado:

                self._avaliar_fvg()

        return self.estado

    # ========================================================
    # ORB PARCIAL
    # ========================================================

    def _atualizar_orb_parcial(
        self
    ) -> None:

        if not self.candles_orb:
            return

        highs = [
            candle["high"]
            for candle
            in self.candles_orb
        ]

        lows = [
            candle["low"]
            for candle
            in self.candles_orb
        ]

        self.estado.orb_high = max(
            highs
        )

        self.estado.orb_low = min(
            lows
        )

        self.estado.orb_range = (
            self.estado.orb_high
            -
            self.estado.orb_low
        )

    # ========================================================
    # FINALIZAR ORB
    # ========================================================

    def _finalizar_orb(
        self
    ) -> None:

        if not self.candles_orb:

            self.estado.estado = (
                "ORB_INCOMPLETA"
            )

            return

        self._atualizar_orb_parcial()

        self.estado.orb_pronta = True

        self.estado.estado = (
            "AGUARDANDO_ROMPIMENTO"
        )

    # ========================================================
    # DETECTAR ROMPIMENTO
    # ========================================================

    def _detectar_rompimento(
        self,
        candle: dict
    ) -> None:

        if (
            self.estado.orb_high is None
            or
            self.estado.orb_low is None
        ):
            return

        close = candle["close"]

        # ====================================================
        # COMPRA
        # ====================================================

        if close > self.estado.orb_high:

            self.estado.rompeu = True

            self.estado.direcao = (
                "COMPRA"
            )

            self.estado.preco_rompimento = (
                close
            )

            self.estado.horario_rompimento = (
                candle[
                    "datetime_ny"
                ].isoformat()
            )

            self.estado.estado = (
                "ROMPIMENTO_CONFIRMADO"
            )

            # O FVG pode ser confirmado
            # no próprio candle do rompimento.
            self._avaliar_fvg()

            return

        # ====================================================
        # VENDA
        # ====================================================

        if close < self.estado.orb_low:

            self.estado.rompeu = True

            self.estado.direcao = (
                "VENDA"
            )

            self.estado.preco_rompimento = (
                close
            )

            self.estado.horario_rompimento = (
                candle[
                    "datetime_ny"
                ].isoformat()
            )

            self.estado.estado = (
                "ROMPIMENTO_CONFIRMADO"
            )

            self._avaliar_fvg()

    # ========================================================
    # AVALIAR FVG
    # ========================================================

    def _avaliar_fvg(
        self
    ) -> None:

        if not self.estado.rompeu:
            return

        if self.fvg_finalizado:
            return

        if not self.estado.horario_rompimento:
            return

        horario_rompimento_ny = (
            pd.Timestamp(
                self.estado.horario_rompimento
            )
        )

        horario_rompimento_utc = (
            horario_rompimento_ny
            .tz_convert("UTC")
        )

        inicio = (
            horario_rompimento_utc
            -
            pd.Timedelta(
                minutes=2
            )
        )

        limite = (
            horario_rompimento_utc
            +
            pd.Timedelta(
                minutes=MAX_MINUTOS_FVG
            )
        )

        # ====================================================
        # JANELA DISPONÍVEL ATÉ O CANDLE ATUAL
        # ====================================================

        janela = [
            candle
            for candle
            in self.candles_sessao
            if (
                candle["datetime_utc"]
                >= inicio
                and
                candle["datetime_utc"]
                <= limite
                and
                candle[
                    "datetime_ny"
                ].time()
                < FIM_SESSAO
            )
        ]

        janela = sorted(
            janela,
            key=lambda x:
                x["datetime_utc"]
        )

        # ====================================================
        # MESMA LÓGICA DO detectar_fvg_v2.py
        # ====================================================

        for i in range(
            2,
            len(janela)
        ):

            c1 = janela[i - 2]
            c2 = janela[i - 1]
            c3 = janela[i]

            # =================================================
            # EXIGIR CANDLES CONSECUTIVOS
            # =================================================

            if (
                c2["datetime_utc"]
                -
                c1["datetime_utc"]
                !=
                pd.Timedelta(
                    minutes=1
                )
                or
                c3["datetime_utc"]
                -
                c2["datetime_utc"]
                !=
                pd.Timedelta(
                    minutes=1
                )
            ):
                continue

            # =================================================
            # SÓ CONFIRMA APÓS O ROMPIMENTO
            # =================================================

            if (
                c3["datetime_utc"]
                <
                horario_rompimento_utc
            ):
                continue

            direcao = (
                self.estado.direcao
            )

            range_max = (
                self.estado.orb_high
            )

            range_min = (
                self.estado.orb_low
            )

            # =================================================
            # COMPRA
            # =================================================

            if direcao == "COMPRA":

                # Retorno ao interior da ORB
                if (
                    c3["close"]
                    <=
                    range_max
                ):

                    self.estado.estado = (
                        "RETORNO_RANGE"
                    )

                    self.estado.motivo_fvg = (
                        "RETORNO_RANGE"
                    )

                    self.estado.fvg_detectado = (
                        False
                    )

                    self.fvg_finalizado = True

                    return

                gap_min = (
                    c1["high"]
                )

                gap_max = (
                    c3["low"]
                )

                valido = (
                    gap_max > gap_min
                    and
                    gap_min >= range_max
                )

            # =================================================
            # VENDA
            # =================================================

            else:

                # Retorno ao interior da ORB
                if (
                    c3["close"]
                    >=
                    range_min
                ):

                    self.estado.estado = (
                        "RETORNO_RANGE"
                    )

                    self.estado.motivo_fvg = (
                        "RETORNO_RANGE"
                    )

                    self.estado.fvg_detectado = (
                        False
                    )

                    self.fvg_finalizado = True

                    return

                gap_min = (
                    c3["high"]
                )

                gap_max = (
                    c1["low"]
                )

                valido = (
                    gap_max > gap_min
                    and
                    gap_max <= range_min
                )

            tamanho = (
                gap_max
                -
                gap_min
            )

            # =================================================
            # FVG VÁLIDO
            # =================================================

            if (
                valido
                and
                tamanho >= FVG_MIN_PONTOS
            ):

                self.estado.fvg_detectado = (
                    True
                )

                self.estado.motivo_fvg = (
                    "FVG_VALIDO"
                )

                self.estado.horario_fvg = (
                    c3[
                        "datetime_ny"
                    ].isoformat()
                )

                self.estado.fvg_low = (
                    float(
                        gap_min
                    )
                )

                self.estado.fvg_high = (
                    float(
                        gap_max
                    )
                )

                self.estado.tamanho_fvg = (
                    float(
                        tamanho
                    )
                )

                # =============================================
                # GUARDAR C1
                #
                # O motor V3 usa:
                #
                # COMPRA -> stop = low do c1
                # VENDA  -> stop = high do c1
                # =============================================

                self.estado.fvg_c1_open = (
                    float(
                        c1["open"]
                    )
                )

                self.estado.fvg_c1_high = (
                    float(
                        c1["high"]
                    )
                )

                self.estado.fvg_c1_low = (
                    float(
                        c1["low"]
                    )
                )

                self.estado.fvg_c1_close = (
                    float(
                        c1["close"]
                    )
                )

                self.estado.estado = (
                    "FVG_VALIDO"
                )

                self.fvg_finalizado = True

                return

        # ====================================================
        # JANELA DE 30 MINUTOS TERMINOU
        # ====================================================

        if not self.candles_sessao:
            return

        candle_atual = (
            self.candles_sessao[-1]
        )

        if (
            candle_atual[
                "datetime_utc"
            ]
            >= limite
        ):

            self.estado.estado = (
                "SEM_FVG"
            )

            self.estado.motivo_fvg = (
                "SEM_FVG"
            )

            self.estado.fvg_detectado = (
                False
            )

            self.fvg_finalizado = True

            return

        # ====================================================
        # AINDA PROCURANDO
        # ====================================================

        self.estado.estado = (
            "PROCURANDO_FVG"
        )

    # ========================================================
    # EXPORTAR ESTADO
    # ========================================================

    def obter_estado(
        self
    ) -> dict:

        return asdict(
            self.estado
        )


# ============================================================
# CARREGAR REPLAY
# ============================================================

def carregar_replay(
    caminho: Path
) -> pd.DataFrame:

    if not caminho.exists():

        raise FileNotFoundError(
            f"Arquivo não encontrado: "
            f"{caminho}"
        )

    df = pd.read_parquet(
        caminho
    )

    # ========================================================
    # IDENTIFICAR DATETIME
    # ========================================================

    candidatos = [
        "datetime",
        "timestamp",
        "Date",
        "date"
    ]

    coluna_data = None

    for coluna in candidatos:

        if coluna in df.columns:

            coluna_data = coluna

            break

    if coluna_data is None:

        if isinstance(
            df.index,
            pd.DatetimeIndex
        ):

            nome_indice = (
                df.index.name
                or
                "index"
            )

            df = (
                df
                .reset_index()
                .rename(
                    columns={
                        nome_indice:
                            "datetime"
                    }
                )
            )

            coluna_data = (
                "datetime"
            )

        else:

            raise ValueError(
                "Não foi encontrada "
                "coluna datetime."
            )

    if coluna_data != "datetime":

        df = df.rename(
            columns={
                coluna_data:
                    "datetime"
            }
        )

    # ========================================================
    # NORMALIZAR OHLC
    # ========================================================

    mapa = {}

    for coluna in df.columns:

        nome = (
            coluna
            .lower()
        )

        if nome == "open":
            mapa[coluna] = "open"

        elif nome == "high":
            mapa[coluna] = "high"

        elif nome == "low":
            mapa[coluna] = "low"

        elif nome == "close":
            mapa[coluna] = "close"

        elif nome == "volume":
            mapa[coluna] = "volume"

    df = df.rename(
        columns=mapa
    )

    obrigatorias = [
        "datetime",
        "open",
        "high",
        "low",
        "close"
    ]

    faltando = [
        coluna
        for coluna
        in obrigatorias
        if coluna not in df.columns
    ]

    if faltando:

        raise ValueError(
            "Colunas ausentes: "
            +
            ", ".join(
                faltando
            )
        )

    df["datetime"] = pd.to_datetime(
        df["datetime"],
        utc=True
    )

    df = (
        df
        .sort_values(
            "datetime"
        )
        .drop_duplicates(
            subset=[
                "datetime"
            ],
            keep="last"
        )
        .reset_index(
            drop=True
        )
    )

    return df


# ============================================================
# TESTE LOCAL
# ============================================================

def main() -> None:

    print(
        "=" * 70
    )

    print(
        "TRADINGLAB - LIVE ENGINE"
    )

    print(
        "MODO: PAPER / REPLAY"
    )

    print(
        "ORDENS REAIS: DESABILITADAS"
    )

    print(
        "=" * 70
    )

    df = carregar_replay(
        ARQUIVO_REPLAY
    )

    print(
        f"Candles carregados: "
        f"{len(df):,}"
    )

    # ========================================================
    # ÚLTIMO DIA
    # ========================================================

    ny = (
        df["datetime"]
        .dt
        .tz_convert(
            "America/New_York"
        )
    )

    ultima_data = (
        ny.dt.date.max()
    )

    mascara = (
        ny.dt.date
        ==
        ultima_data
    )

    dia = (
        df.loc[
            mascara
        ]
        .copy()
        .reset_index(
            drop=True
        )
    )

    print(
        f"Replay da sessão: "
        f"{ultima_data}"
    )

    print(
        f"Candles do dia: "
        f"{len(dia)}"
    )

    engine = LiveEngine()

    ultimo_estado = None

    # ========================================================
    # REPLAY CANDLE A CANDLE
    # ========================================================

    for _, linha in dia.iterrows():

        candle = {
            "datetime":
                linha[
                    "datetime"
                ],

            "open":
                linha[
                    "open"
                ],

            "high":
                linha[
                    "high"
                ],

            "low":
                linha[
                    "low"
                ],

            "close":
                linha[
                    "close"
                ],

            "volume":
                linha.get(
                    "volume"
                )
        }

        estado = (
            engine
            .processar_candle(
                candle
            )
        )

        # ====================================================
        # MOSTRAR SOMENTE MUDANÇA DE ESTADO
        # ====================================================

        if (
            estado.estado
            !=
            ultimo_estado
        ):

            print()

            print(
                estado.ultimo_candle_ny
            )

            print(
                "Estado:",
                estado.estado
            )

            print(
                "ORB:",
                estado.orb_low,
                "→",
                estado.orb_high
            )

            print(
                "Direção:",
                estado.direcao
            )

            print(
                "FVG:",
                estado.fvg_low,
                "→",
                estado.fvg_high
            )

            print(
                "Tamanho FVG:",
                estado.tamanho_fvg
            )

            print(
                "Motivo FVG:",
                estado.motivo_fvg
            )

            if estado.fvg_detectado:

                print(
                    "C1 OHLC:",
                    estado.fvg_c1_open,
                    estado.fvg_c1_high,
                    estado.fvg_c1_low,
                    estado.fvg_c1_close
                )

            ultimo_estado = (
                estado.estado
            )

    # ========================================================
    # RESULTADO FINAL
    # ========================================================

    print()

    print(
        "=" * 70
    )

    print(
        "ESTADO FINAL"
    )

    print(
        "=" * 70
    )

    for chave, valor in (
        engine
        .obter_estado()
        .items()
    ):

        print(
            f"{chave}: {valor}"
        )


if __name__ == "__main__":
    main()