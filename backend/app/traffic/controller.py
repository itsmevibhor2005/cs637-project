import asyncio
import math
import time
from uuid import uuid4

from app.hardware.esp32 import ESP32Bridge
from app.models import Phase
from app.state import StateStore
from app.traffic.safety import GREEN_PHASES, YELLOW_FOR_GREEN, signals_for, validate_transition
from app.traffic.scheduler import AdaptiveScheduler


class TrafficController:
    PHASE_ORDER = (Phase.N_GREEN, Phase.E_GREEN, Phase.S_GREEN, Phase.W_GREEN)

    def __init__(
        self,
        store: StateStore,
        scheduler: AdaptiveScheduler,
        bridge: ESP32Bridge,
        yellow_seconds: int,
        all_red_seconds: int,
    ):
        self.store = store
        self.scheduler = scheduler
        self.bridge = bridge
        self.yellow_seconds = yellow_seconds
        self.all_red_seconds = all_red_seconds
        self._shutdown = False
        self._manual: asyncio.Queue[tuple[Phase, int]] = asyncio.Queue()

    async def request_manual(self, phase: Phase, duration: int) -> None:
        await self._manual.put((phase, duration))

    async def stop(self) -> None:
        self._shutdown = True

    async def run(self) -> None:
        next_green = Phase.N_GREEN
        while not self._shutdown:
            state = await self.store.snapshot()
            if not state.running:
                if state.phase != Phase.ALL_RED:
                    await self._force_all_red()
                await asyncio.sleep(0.2)
                continue

            if not self._manual.empty():
                requested, duration = await self._manual.get()
                if requested in GREEN_PHASES:
                    await self._safe_move_to(requested, duration)
                    next_green = self._next_after(requested)
                    continue

            snapshot = await self.store.snapshot()
            duration = self.scheduler.green_duration(next_green, snapshot.traffic)
            await self._set_phase(next_green, duration)
            await self._set_phase(YELLOW_FOR_GREEN[next_green], self.yellow_seconds)
            await self._set_phase(Phase.ALL_RED, self.all_red_seconds)
            next_green = self._next_after(next_green)
            after = await self.store.snapshot()
            await self.store.patch(cycle=after.cycle + 1, next_phase=next_green)

    async def _safe_move_to(self, target: Phase, duration: int) -> None:
        current = (await self.store.snapshot()).phase
        if current == target:
            await self._set_phase(target, duration, allow_same=True)
            return
        if current in GREEN_PHASES:
            await self._set_phase(YELLOW_FOR_GREEN[current], self.yellow_seconds)
        if (await self.store.snapshot()).phase != Phase.ALL_RED:
            await self._set_phase(Phase.ALL_RED, self.all_red_seconds)
        await self._set_phase(target, duration)

    async def _force_all_red(self) -> None:
        current = (await self.store.snapshot()).phase
        if current in GREEN_PHASES:
            await self._set_phase(YELLOW_FOR_GREEN[current], self.yellow_seconds)
        if (await self.store.snapshot()).phase != Phase.ALL_RED:
            await self._set_phase(Phase.ALL_RED, self.all_red_seconds)
        else:
            await self.bridge.set_phase(Phase.ALL_RED, 0)

    async def _set_phase(self, phase: Phase, duration: int, allow_same: bool = False) -> None:
        current = (await self.store.snapshot()).phase
        if current != phase and not validate_transition(current, phase):
            raise RuntimeError(f"Unsafe transition rejected: {current} -> {phase}")
        if current == phase and not allow_same and phase != Phase.ALL_RED:
            raise RuntimeError(f"Duplicate phase rejected: {phase}")

        ok, ack = await self.bridge.set_phase(phase, duration)
        state = await self.store.snapshot()
        esp = state.esp32.model_copy(update={
            "connected": ok,
            "last_ack": ack if ok else state.esp32.last_ack,
            "last_error": None if ok else ack,
        })
        changes = dict(
            phase=phase,
            signals=signals_for(phase),
            remaining=duration,
            phase_duration=duration,
            esp32=esp,
            last_transition_id=uuid4().hex[:10],
        )
        if phase in GREEN_PHASES:
            changes["next_phase"] = self._next_after(phase)
        await self.store.patch(**changes)

        deadline = time.monotonic() + duration
        last_remaining = duration
        while not self._shutdown:
            state = await self.store.snapshot()
            # A stop may shorten a green, but never the safety clearance phases.
            if not state.running and phase in GREEN_PHASES:
                break
            remaining = max(0, math.ceil(deadline - time.monotonic()))
            if remaining != last_remaining:
                await self.store.patch(remaining=remaining)
                last_remaining = remaining
            if remaining <= 0:
                break
            await asyncio.sleep(0.1)

    def _next_after(self, phase: Phase) -> Phase:
        index = self.PHASE_ORDER.index(phase)
        return self.PHASE_ORDER[(index + 1) % len(self.PHASE_ORDER)]
