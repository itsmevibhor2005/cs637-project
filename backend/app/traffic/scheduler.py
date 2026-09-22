from dataclasses import dataclass

from app.models import ApproachState, Direction, Phase


@dataclass(frozen=True)
class SchedulerConfig:
    min_green: int = 10
    max_green: int = 40
    base_green: float = 8.0
    demand_factor: float = 0.6
    queue_weight: float = 2.0
    wait_weight: float = 0.05
    max_wait_seconds: int = 60


class AdaptiveScheduler:
    def __init__(self, config: SchedulerConfig):
        self.config = config

    def approach_demand(self, state: ApproachState) -> float:
        return round(
            state.weighted_vehicles
            + self.config.queue_weight * state.queue
            + self.config.wait_weight * state.waiting_seconds,
            2,
        )

    def enrich_demands(
        self, traffic: dict[Direction, ApproachState]
    ) -> dict[Direction, ApproachState]:
        return {
            direction: state.model_copy(update={"demand": self.approach_demand(state)})
            for direction, state in traffic.items()
        }

    def phase_score(self, phase: Phase, traffic: dict[Direction, ApproachState]) -> float:
        directions = (
            (Direction.N, Direction.S)
            if phase == Phase.NS_GREEN
            else (Direction.E, Direction.W)
        )
        return sum(self.approach_demand(traffic[d]) for d in directions)

    def green_duration(self, phase: Phase, traffic: dict[Direction, ApproachState]) -> int:
        directions = (
            (Direction.N, Direction.S)
            if phase == Phase.NS_GREEN
            else (Direction.E, Direction.W)
        )
        score = self.phase_score(phase, traffic)
        duration = round(self.config.base_green + self.config.demand_factor * score)

        # A phase that has waited too long receives at least half of the available range.
        if any(traffic[d].waiting_seconds >= self.config.max_wait_seconds for d in directions):
            duration = max(duration, (self.config.min_green + self.config.max_green) // 2)

        return max(self.config.min_green, min(self.config.max_green, duration))

