from app.models import Direction, Phase, SignalColor


PHASE_SIGNALS: dict[Phase, dict[Direction, SignalColor]] = {
    Phase.NS_GREEN: {
        Direction.N: SignalColor.GREEN,
        Direction.S: SignalColor.GREEN,
        Direction.E: SignalColor.RED,
        Direction.W: SignalColor.RED,
    },
    Phase.NS_YELLOW: {
        Direction.N: SignalColor.YELLOW,
        Direction.S: SignalColor.YELLOW,
        Direction.E: SignalColor.RED,
        Direction.W: SignalColor.RED,
    },
    Phase.EW_GREEN: {
        Direction.N: SignalColor.RED,
        Direction.S: SignalColor.RED,
        Direction.E: SignalColor.GREEN,
        Direction.W: SignalColor.GREEN,
    },
    Phase.EW_YELLOW: {
        Direction.N: SignalColor.RED,
        Direction.S: SignalColor.RED,
        Direction.E: SignalColor.YELLOW,
        Direction.W: SignalColor.YELLOW,
    },
    Phase.ALL_RED: {direction: SignalColor.RED for direction in Direction},
}

ALLOWED_TRANSITIONS: dict[Phase, set[Phase]] = {
    Phase.ALL_RED: {Phase.NS_GREEN, Phase.EW_GREEN, Phase.ALL_RED},
    Phase.NS_GREEN: {Phase.NS_YELLOW},
    Phase.NS_YELLOW: {Phase.ALL_RED},
    Phase.EW_GREEN: {Phase.EW_YELLOW},
    Phase.EW_YELLOW: {Phase.ALL_RED},
}


def validate_signals(signals: dict[Direction, SignalColor]) -> bool:
    green = {direction for direction, color in signals.items() if color == SignalColor.GREEN}
    return green in ({Direction.N, Direction.S}, {Direction.E, Direction.W}, set())


def validate_transition(current: Phase, target: Phase) -> bool:
    return target in ALLOWED_TRANSITIONS[current]


def signals_for(phase: Phase) -> dict[Direction, SignalColor]:
    signals = PHASE_SIGNALS[phase].copy()
    if not validate_signals(signals):
        raise RuntimeError(f"Unsafe signal map for phase {phase}")
    return signals

