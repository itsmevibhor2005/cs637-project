from app.models import Direction, Phase, SignalColor
from app.traffic.safety import signals_for, validate_signals, validate_transition


def test_all_defined_phases_are_safe():
    assert all(validate_signals(signals_for(phase)) for phase in Phase)


def test_conflicting_greens_are_rejected():
    unsafe = {direction: SignalColor.RED for direction in Direction}
    unsafe[Direction.N] = SignalColor.GREEN
    unsafe[Direction.E] = SignalColor.GREEN
    assert not validate_signals(unsafe)


def test_green_to_conflicting_green_is_rejected():
    assert not validate_transition(Phase.NS_GREEN, Phase.EW_GREEN)
    assert validate_transition(Phase.NS_GREEN, Phase.NS_YELLOW)

