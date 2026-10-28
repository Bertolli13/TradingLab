from dataclasses import dataclass


@dataclass(frozen=True)
class MSSFVGBaselineConfig:
    """
    Configuração baseline da estratégia MSS + FVG.

    Estes valores reproduzem os parâmetros padrão
    do Pine Script original antes de qualquer otimização.
    """

    # --------------------------------------------------
    # Estrutura / MSS
    # --------------------------------------------------
    pivot_bars: int = 5
    max_setup_age_bars: int = 20

    # --------------------------------------------------
    # Entrada
    # --------------------------------------------------
    entry_pct_fvg: float = 50.0
    stop_buffer_points: float = 0.0
    min_stop_points: float = 12.5
    max_stop_points: float = 50.0

    # --------------------------------------------------    
    # Setups
    # --------------------------------------------------
    enable_long: bool = True
    enable_short: bool = True

    enable_reversal: bool = True
    enable_continuation: bool = False

    min_minutes_between_setups: int = 60

    # --------------------------------------------------
    # Sessão
    # --------------------------------------------------
    timezone: str = "America/New_York"

    session_start: str = "09:30"
    session_end: str = "16:00"

    blocked_start: str = "11:00"
    blocked_end: str = "12:00"

    # --------------------------------------------------
    # Gestão
    # --------------------------------------------------
    contracts: int = 3

    target_1_r: float = 1.0
    target_2_r: float = 2.0
    target_3_r: float = 3.0

    move_stop_to_break_even_after_target_1: bool = True

    # --------------------------------------------------
    # Instrumento / execução
    # --------------------------------------------------
    tick_size: float = 0.25

    # MNQ = US$ 2 por ponto por contrato.
    point_value_usd: float = 2.0

    # Começaremos com estes custos explicitamente
    # configuráveis. Depois validaremos o modelo.
    commission_per_contract_side_usd: float = 1.0

    slippage_ticks_per_order: int = 2