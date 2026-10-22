from __future__ import annotations

from dataclasses import dataclass, asdict, replace
from datetime import time
from typing import Optional

import pandas as pd


# ============================================================
# CONFIGURAÇÃO V4
# ============================================================

TICK = 0.25
PENETRACAO_TICKS = 1

VALOR_PONTO = 2.0
CONTRATOS = 1

CUSTO_ROUND_TRIP = 3.0
SLIPPAGE_TOTAL_TICKS = 2.0

RR_ALVO = 1.25

FIM_SESSAO = time(16, 40)

INVALIDAR_POSICAO = False


# ============================================================
# ESTADO DE UM CAMINHO INTRABAR
# ============================================================

@dataclass(frozen=True)
class EstadoExecucao:
    status: str = "PENDENTE"

    entrada_ts: str = ""

    saida_ts: str = ""

    preco_saida: Optional[float] = None

    motivo: str = ""


# ============================================================
# RESULTADO PAPER
# ============================================================

@dataclass
class ResultadoPaper:
    status: str = "AGUARDANDO_FVG"

    direcao: Optional[str] = None

    horario_fvg: Optional[str] = None

    entrada: Optional[float] = None
    stop: Optional[float] = None
    alvo: Optional[float] = None

    risco_pontos: Optional[float] = None

    ordem_ativa_em: Optional[str] = None

    executada: bool = False

    horario_entrada: Optional[str] = None

    horario_saida: Optional[str] = None

    preco_saida: Optional[float] = None

    motivo_saida: Optional[str] = None

    ambiguo: bool = False

    alternativas: int = 0

    resultado_bruto_r: Optional[float] = None

    custo_r: Optional[float] = None

    resultado_liquido_r: Optional[float] = None

    resultado_liquido_usd: Optional[float] = None

    ordens_reais_habilitadas: bool = False


# ============================================================
# PAPER ENGINE V4
# ============================================================

class PaperEngineV4:

    def __init__(self) -> None:

        self.resultado = ResultadoPaper()

        self.ativo = False

        self.direcao = None

        self.entry = None
        self.stop = None
        self.target = None

        self.orb_min = None
        self.orb_max = None

        self.risk = None

        self.fvg_ts_utc = None

        self.ordem_ativa_utc = None

        self.end_utc = None

        self.previous_utc = None

        self.last_bar = None

        self.active_states = {
            EstadoExecucao()
        }

        self.terminal_states = set()

        self.finalizado = False

        self.erro = None

    # ========================================================
    # ATIVAR A PARTIR DO FVG DO LIVE ENGINE
    # ========================================================

    def ativar(
        self,
        direcao: str,
        horario_fvg,
        fvg_min: float,
        fvg_max: float,
        orb_min: float,
        orb_max: float,
        candle_c1: dict,
    ) -> None:

        if self.ativo:
            return

        if direcao not in (
            "COMPRA",
            "VENDA",
        ):
            raise ValueError(
                "Direção inválida."
            )

        ts = pd.Timestamp(
            horario_fvg
        )

        if ts.tzinfo is None:
            raise ValueError(
                "FVG sem timezone."
            )

        ts_utc = ts.tz_convert(
            "UTC"
        )

        buy = (
            direcao == "COMPRA"
        )

        # ====================================================
        # MESMA ENTRADA DO V3
        # ====================================================

        entry = (
            float(fvg_max)
            if buy
            else float(fvg_min)
        )

        # ====================================================
        # MESMO STOP DO V3
        #
        # COMPRA -> low do c1
        # VENDA  -> high do c1
        # ====================================================

        stop = (
            float(
                candle_c1["low"]
            )
            if buy
            else float(
                candle_c1["high"]
            )
        )

        risk = (
            entry - stop
            if buy
            else stop - entry
        )

        if risk <= 0:
            raise ValueError(
                "RISCO_INVALIDO"
            )

        target = (
            entry + risk * RR_ALVO
            if buy
            else entry - risk * RR_ALVO
        )

        data_ny = (
            ts
            .tz_convert(
                "America/New_York"
            )
            .strftime(
                "%Y-%m-%d"
            )
        )

        end = pd.Timestamp(
            f"{data_ny} 16:40",
            tz="America/New_York"
        ).tz_convert(
            "UTC"
        )

        self.ativo = True

        self.direcao = direcao

        self.entry = entry
        self.stop = stop
        self.target = target

        self.orb_min = float(
            orb_min
        )

        self.orb_max = float(
            orb_max
        )

        self.risk = float(
            risk
        )

        self.fvg_ts_utc = ts_utc

        self.ordem_ativa_utc = (
            ts_utc
            +
            pd.Timedelta(
                minutes=1
            )
        )

        self.end_utc = end

        self.previous_utc = ts_utc

        self.last_bar = None

        self.active_states = {
            EstadoExecucao()
        }

        self.terminal_states = set()

        self.finalizado = False

        self.erro = None

        self.resultado = ResultadoPaper(
            status="ORDEM_PENDENTE",

            direcao=direcao,

            horario_fvg=ts.isoformat(),

            entrada=entry,

            stop=stop,

            alvo=target,

            risco_pontos=risk,

            ordem_ativa_em=(
                self.ordem_ativa_utc
                .isoformat()
            ),

            ordens_reais_habilitadas=False,
        )

    # ========================================================
    # PROCESSAR CANDLE
    # ========================================================

    def processar_candle(
        self,
        candle: dict
    ) -> ResultadoPaper:

        if (
            not self.ativo
            or self.finalizado
        ):
            return self.resultado

        ts = pd.Timestamp(
            candle["datetime"]
        )

        if ts.tzinfo is None:

            ts = ts.tz_localize(
                "UTC"
            )

        else:

            ts = ts.tz_convert(
                "UTC"
            )

        # ====================================================
        # ORDEM AINDA NÃO ESTÁ ATIVA
        # ====================================================

        if ts < self.ordem_ativa_utc:
            return self.resultado

        # ====================================================
        # 16:40 NÃO ENTRA NA SIMULAÇÃO
        # ====================================================

        if ts >= self.end_utc:

            self._encerrar_sessao()

            return self.resultado

        # ====================================================
        # CONTIGUIDADE
        # ====================================================

        if (
            ts - self.previous_utc
            != pd.Timedelta(
                minutes=1
            )
        ):

            self.erro = (
                "LACUNA_DADOS"
            )

            self.resultado.status = (
                "DADOS_INVALIDOS"
            )

            self.resultado.motivo_saida = (
                "DADOS_INVALIDOS"
            )

            self.finalizado = True

            return self.resultado

        bar = {
            "datetime":
                ts,

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
        }

        self.last_bar = bar

        next_active = set()

        # ====================================================
        # MESMOS DOIS CAMINHOS DO V3
        # ====================================================

        for state in self.active_states:

            for path in (
                "OHLC",
                "OLHC",
            ):

                out = self._advance(
                    state,
                    bar,
                    path
                )

                if out.status in (
                    "FECHADA",
                    "CANCELADA",
                ):

                    self.terminal_states.add(
                        out
                    )

                else:

                    next_active.add(
                        out
                    )

        self.active_states = (
            next_active
        )

        self.previous_utc = ts

        # ====================================================
        # TODOS OS RAMOS TERMINARAM
        # ====================================================

        if not self.active_states:

            self._consolidar()

            return self.resultado

        # ====================================================
        # ESTADO VISUAL
        # ====================================================

        existe_aberta = any(
            state.status == "ABERTA"
            for state
            in self.active_states
        )

        existe_pendente = any(
            state.status == "PENDENTE"
            for state
            in self.active_states
        )

        if existe_aberta:

            self.resultado.status = (
                "POSICAO_ABERTA"
            )

        elif existe_pendente:

            self.resultado.status = (
                "ORDEM_PENDENTE"
            )

        return self.resultado

    # ========================================================
    # AVANÇAR UM CAMINHO INTRABAR
    # ========================================================

    def _advance(
        self,
        state: EstadoExecucao,
        bar: dict,
        path: str,
    ) -> EstadoExecucao:

        ts = str(
            bar["datetime"]
        )

        sign = (
            1
            if self.direcao == "COMPRA"
            else -1
        )

        # ====================================================
        # PENETRAÇÃO DE 1 TICK
        # ====================================================

        trigger = (
            self.entry
            -
            sign
            *
            PENETRACAO_TICKS
            *
            TICK
        )

        # ====================================================
        # CAMINHOS POSSÍVEIS
        # ====================================================

        if path == "OHLC":

            points = [
                bar["open"],
                bar["high"],
                bar["low"],
                bar["close"],
            ]

        else:

            points = [
                bar["open"],
                bar["low"],
                bar["high"],
                bar["close"],
            ]

        s = state

        # ====================================================
        # TRATAR UM PREÇO
        # ====================================================

        def at_price(
            estado: EstadoExecucao,
            price: float
        ) -> EstadoExecucao:

            # ------------------------------------------------
            # ABRIR POSIÇÃO
            # ------------------------------------------------

            if (
                estado.status == "PENDENTE"
                and
                sign
                *
                (
                    price - trigger
                )
                <= 0
            ):

                estado = EstadoExecucao(
                    status="ABERTA",
                    entrada_ts=ts
                )

            # ------------------------------------------------
            # POSIÇÃO ABERTA
            # ------------------------------------------------

            if estado.status == "ABERTA":

                # STOP
                if (
                    sign
                    *
                    (
                        price - self.stop
                    )
                    <= 0
                ):

                    return replace(
                        estado,

                        status="FECHADA",

                        saida_ts=ts,

                        preco_saida=float(
                            price
                        ),

                        motivo="STOP"
                    )

                # ALVO
                if (
                    sign
                    *
                    (
                        price - self.target
                    )
                    >= 0
                ):

                    return replace(
                        estado,

                        status="FECHADA",

                        saida_ts=ts,

                        preco_saida=self.target,

                        motivo="ALVO"
                    )

            return estado

        # ====================================================
        # ABERTURA DO CANDLE
        # ====================================================

        s = at_price(
            s,
            points[0]
        )

        # ====================================================
        # SEGMENTOS INTRABAR
        # ====================================================

        for a, b in zip(
            points,
            points[1:]
        ):

            if s.status == "FECHADA":
                return s

            # =================================================
            # RETESTE
            # =================================================

            if s.status == "PENDENTE":

                if (
                    min(a, b)
                    <= trigger
                    <= max(a, b)
                ):

                    s = EstadoExecucao(
                        status="ABERTA",
                        entrada_ts=ts
                    )

                    a = trigger

                    s = at_price(
                        s,
                        a
                    )

                else:

                    continue

            if s.status == "FECHADA":
                return s

            # =================================================
            # STOP OU ALVO DENTRO DO SEGMENTO
            # =================================================

            hits = [
                x
                for x
                in (
                    self.stop,
                    self.target
                )
                if (
                    min(a, b)
                    <= x
                    <= max(a, b)
                )
            ]

            if hits:

                price = min(
                    hits,
                    key=lambda x:
                        abs(x - a)
                )

                s = replace(
                    s,

                    status="FECHADA",

                    saida_ts=ts,

                    preco_saida=price,

                    motivo=(
                        "STOP"
                        if price == self.stop
                        else "ALVO"
                    )
                )

        # ====================================================
        # CANCELAMENTO POR RETORNO AO RANGE
        # ====================================================

        invalid = (
            bar["close"] <= self.orb_max
            if sign == 1
            else
            bar["close"] >= self.orb_min
        )

        if (
            invalid
            and
            s.status == "PENDENTE"
        ):

            s = replace(
                s,

                status="CANCELADA",

                saida_ts=ts,

                motivo="CANCELADA_RANGE"
            )

        elif (
            invalid
            and
            s.status == "ABERTA"
            and
            INVALIDAR_POSICAO
        ):

            s = replace(
                s,

                status="FECHADA",

                saida_ts=ts,

                preco_saida=float(
                    bar["close"]
                ),

                motivo="SAIDA_RANGE"
            )

        return s

    # ========================================================
    # ENCERRAMENTO DA SESSÃO
    # ========================================================

    def _encerrar_sessao(
        self
    ) -> None:

        if self.finalizado:
            return

        # ====================================================
        # VALIDAR QUE O ÚLTIMO CANDLE FOI 16:39
        # ====================================================

        if (
            self.last_bar is None
            or
            self.last_bar["datetime"]
            +
            pd.Timedelta(
                minutes=1
            )
            != self.end_utc
        ):

            self.resultado.status = (
                "DADOS_INVALIDOS"
            )

            self.resultado.motivo_saida = (
                "SESSAO_INCOMPLETA"
            )

            self.finalizado = True

            return

        # ====================================================
        # TERMINAR RAMOS AINDA ATIVOS
        # ====================================================

        for state in self.active_states:

            if state.status == "ABERTA":

                self.terminal_states.add(
                    replace(
                        state,

                        status="FECHADA",

                        saida_ts=str(
                            self.last_bar[
                                "datetime"
                            ]
                        ),

                        preco_saida=float(
                            self.last_bar[
                                "close"
                            ]
                        ),

                        motivo="ENCERRAMENTO"
                    )
                )

            else:

                self.terminal_states.add(
                    replace(
                        state,

                        status="CANCELADA",

                        motivo="SEM_RETESTE"
                    )
                )

        self.active_states = set()

        self._consolidar()

    # ========================================================
    # RESULTADO BRUTO EM R
    # ========================================================

    def _gross(
        self,
        state: EstadoExecucao
    ) -> float:

        if state.preco_saida is None:
            return 0.0

        sign = (
            1
            if self.direcao == "COMPRA"
            else -1
        )

        return (
            sign
            *
            (
                state.preco_saida
                -
                self.entry
            )
            /
            self.risk
        )

    # ========================================================
    # CONSOLIDAR CENÁRIO CONSERVADOR
    # ========================================================

    def _consolidar(
        self
    ) -> None:

        if self.finalizado:
            return

        outcomes = sorted(
            self.terminal_states,

            key=lambda s: (
                s.saida_ts,
                s.motivo,
                s.entrada_ts
            )
        )

        if not outcomes:

            self.resultado.status = (
                "DADOS_INVALIDOS"
            )

            self.resultado.motivo_saida = (
                "SEM_RESULTADO"
            )

            self.finalizado = True

            return

        # ====================================================
        # AMBIGUIDADE
        # ====================================================

        ambiguous = (
            len(outcomes) > 1
        )

        # ====================================================
        # MESMO RANKING DO V3
        # ====================================================

        ranked = sorted(
            outcomes,

            key=lambda s: (
                self._gross(s),
                s.saida_ts,
                s.motivo
            )
        )

        # ====================================================
        # CONSERVADOR = PIOR RESULTADO
        # ====================================================

        escolhido = ranked[0]

        executed = bool(
            escolhido.entrada_ts
        )

        # ====================================================
        # CUSTO
        #
        # 3 USD round trip
        # +
        # 2 ticks de slippage financeiro
        #
        # 2 * 0.25 * 2 = 1 USD
        #
        # TOTAL = 4 USD
        # ====================================================

        custo_usd = (
            CONTRATOS
            *
            (
                CUSTO_ROUND_TRIP
                +
                SLIPPAGE_TOTAL_TICKS
                *
                TICK
                *
                VALOR_PONTO
            )
        )

        risk_usd = (
            self.risk
            *
            VALOR_PONTO
            *
            CONTRATOS
        )

        # ====================================================
        # CAMPOS GERAIS
        # ====================================================

        self.resultado.ambiguo = (
            ambiguous
        )

        self.resultado.alternativas = (
            len(outcomes)
        )

        self.resultado.executada = (
            executed
        )

        self.resultado.horario_entrada = (
            escolhido.entrada_ts
            or None
        )

        self.resultado.horario_saida = (
            escolhido.saida_ts
            or None
        )

        self.resultado.preco_saida = (
            escolhido.preco_saida
        )

        self.resultado.motivo_saida = (
            escolhido.motivo
        )

        # ====================================================
        # SEM EXECUÇÃO
        #
        # CORREÇÃO:
        # V3 oficial grava custo_r = 0 quando
        # não houve trade.
        # ====================================================

        if not executed:

            self.resultado.custo_r = 0.0

            self.resultado.resultado_bruto_r = None

            self.resultado.resultado_liquido_r = None

            self.resultado.resultado_liquido_usd = None

            self.resultado.status = (
                escolhido.motivo
                or
                "SEM_EXECUCAO"
            )

            self.finalizado = True

            return

        # ====================================================
        # OPERAÇÃO EXECUTADA
        # ====================================================

        bruto_r = self._gross(
            escolhido
        )

        custo_r = (
            custo_usd
            /
            risk_usd
        )

        liquido_r = (
            bruto_r
            -
            custo_r
        )

        liquido_usd = (
            bruto_r
            *
            risk_usd
            -
            custo_usd
        )

        self.resultado.resultado_bruto_r = (
            bruto_r
        )

        self.resultado.custo_r = (
            custo_r
        )

        self.resultado.resultado_liquido_r = (
            liquido_r
        )

        self.resultado.resultado_liquido_usd = (
            liquido_usd
        )

        self.resultado.status = (
            escolhido.motivo
        )

        self.finalizado = True

    # ========================================================
    # FINALIZAR MANUALMENTE
    # ========================================================

    def finalizar(
        self
    ) -> ResultadoPaper:

        if (
            self.ativo
            and
            not self.finalizado
        ):

            self._encerrar_sessao()

        return self.resultado

    # ========================================================
    # EXPORTAR ESTADO
    # ========================================================

    def obter_estado(
        self
    ) -> dict:

        return asdict(
            self.resultado
        )