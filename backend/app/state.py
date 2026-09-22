import asyncio
from collections import deque
from datetime import datetime, timezone
from typing import Any

from app.models import ApproachState, Direction, ESP32State, Phase, SystemState
from app.traffic.safety import signals_for


def initial_state(ai_mode: str, esp_mode: str) -> SystemState:
    return SystemState(
        ai_mode=ai_mode,
        signals=signals_for(Phase.ALL_RED),
        traffic={direction: ApproachState() for direction in Direction},
        esp32=ESP32State(mode=esp_mode),
    )


class StateStore:
    def __init__(self, ai_mode: str, esp_mode: str):
        self._state = initial_state(ai_mode, esp_mode)
        self._lock = asyncio.Lock()
        self._history: deque[dict[str, Any]] = deque(maxlen=600)

    async def snapshot(self) -> SystemState:
        async with self._lock:
            return self._state.model_copy(deep=True)

    async def patch(self, **changes: Any) -> SystemState:
        async with self._lock:
            changes["timestamp"] = datetime.now(timezone.utc).isoformat()
            self._state = self._state.model_copy(update=changes, deep=True)
            return self._state.model_copy(deep=True)

    async def update_traffic(
        self,
        traffic: dict[Direction, ApproachState],
        fps: float,
    ) -> None:
        async with self._lock:
            self._state.traffic = {k: v.model_copy(deep=True) for k, v in traffic.items()}
            self._state.fps = round(fps, 1)
            self._state.ai_running = True
            self._state.timestamp = datetime.now(timezone.utc).isoformat()

    async def record_history(self) -> None:
        state = await self.snapshot()
        self._history.append({
            "timestamp": state.timestamp,
            "phase": state.phase,
            "traffic": {
                direction: approach.model_dump(mode="json")
                for direction, approach in state.traffic.items()
            },
        })

    def history(self, limit: int = 120) -> list[dict[str, Any]]:
        return list(self._history)[-limit:]

