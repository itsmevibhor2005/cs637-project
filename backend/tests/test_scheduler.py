from app.models import ApproachState, Direction, Phase
from app.traffic.scheduler import AdaptiveScheduler, SchedulerConfig


def sample_traffic():
    return {
        Direction.N: ApproachState(weighted_vehicles=10, queue=5),
        Direction.S: ApproachState(weighted_vehicles=8, queue=4),
        Direction.E: ApproachState(weighted_vehicles=2, queue=1),
        Direction.W: ApproachState(weighted_vehicles=3, queue=1),
    }


def test_heavier_corridor_gets_longer_green():
    scheduler = AdaptiveScheduler(SchedulerConfig())
    traffic = sample_traffic()
    assert scheduler.green_duration(Phase.NS_GREEN, traffic) > scheduler.green_duration(Phase.EW_GREEN, traffic)


def test_green_duration_is_bounded():
    scheduler = AdaptiveScheduler(SchedulerConfig(min_green=10, max_green=40))
    traffic = sample_traffic()
    for state in traffic.values():
        state.weighted_vehicles = 1000
        state.queue = 1000
    assert scheduler.green_duration(Phase.NS_GREEN, traffic) == 40

