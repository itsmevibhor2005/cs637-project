from app.models import Direction, Phase, SignalColor


PHASE_SIGNALS: dict[Phase, dict[Direction, SignalColor]] = {
    Phase.N_GREEN: {
        Direction.N: SignalColor.GREEN,
        Direction.S: SignalColor.RED,
        Direction.E: SignalColor.RED,
        Direction.W: SignalColor.RED,
    },
    Phase.N_YELLOW: {
        Direction.N: SignalColor.YELLOW,
        Direction.S: SignalColor.RED,
        Direction.E: SignalColor.RED,
        Direction.W: SignalColor.RED,
    },
    Phase.E_GREEN: {
        Direction.N: SignalColor.RED,
        Direction.S: SignalColor.RED,
        Direction.E: SignalColor.GREEN,
        Direction.W: SignalColor.RED,
    },
    Phase.E_YELLOW: {
        Direction.N: SignalColor.RED,
        Direction.S: SignalColor.RED,
        Direction.E: SignalColor.YELLOW,
        Direction.W: SignalColor.RED,
    },
    Phase.S_GREEN: {
        Direction.N: SignalColor.RED,
        Direction.S: SignalColor.GREEN,
        Direction.E: SignalColor.RED,
        Direction.W: SignalColor.RED,
    },
    Phase.S_YELLOW: {
        Direction.N: SignalColor.RED,
        Direction.S: SignalColor.YELLOW,
        Direction.E: SignalColor.RED,
        Direction.W: SignalColor.RED,
    },
    Phase.W_GREEN: {
        Direction.N: SignalColor.RED,
        Direction.S: SignalColor.RED,
        Direction.E: SignalColor.RED,
        Direction.W: SignalColor.GREEN,
    },
    Phase.W_YELLOW: {
        Direction.N: SignalColor.RED,
        Direction.S: SignalColor.RED,
        Direction.E: SignalColor.RED,
        Direction.W: SignalColor.YELLOW,
    },
    Phase.ALL_RED: {direction: SignalColor.RED for direction in Direction},
}

ALLOWED_TRANSITIONS: dict[Phase, set[Phase]] = {
    Phase.ALL_RED: {
        Phase.N_GREEN,
        Phase.E_GREEN,
        Phase.S_GREEN,
        Phase.W_GREEN,
        Phase.ALL_RED,
    },
    Phase.N_GREEN: {Phase.N_YELLOW},
    Phase.N_YELLOW: {Phase.ALL_RED},
    Phase.E_GREEN: {Phase.E_YELLOW},
    Phase.E_YELLOW: {Phase.ALL_RED},
    Phase.S_GREEN: {Phase.S_YELLOW},
    Phase.S_YELLOW: {Phase.ALL_RED},
    Phase.W_GREEN: {Phase.W_YELLOW},
    Phase.W_YELLOW: {Phase.ALL_RED},
}

GREEN_PHASES = (Phase.N_GREEN, Phase.E_GREEN, Phase.S_GREEN, Phase.W_GREEN)
YELLOW_FOR_GREEN = {
    Phase.N_GREEN: Phase.N_YELLOW,
    Phase.E_GREEN: Phase.E_YELLOW,
    Phase.S_GREEN: Phase.S_YELLOW,
    Phase.W_GREEN: Phase.W_YELLOW,
}


def validate_signals(signals: dict[Direction, SignalColor]) -> bool:
    green = {direction for direction, color in signals.items() if color == SignalColor.GREEN}
    return len(green) <= 1


def validate_transition(current: Phase, target: Phase) -> bool:
    return target in ALLOWED_TRANSITIONS[current]


def signals_for(phase: Phase) -> dict[Direction, SignalColor]:
    signals = PHASE_SIGNALS[phase].copy()
    if not validate_signals(signals):
        raise RuntimeError(f"Unsafe signal map for phase {phase}")
    return signals
