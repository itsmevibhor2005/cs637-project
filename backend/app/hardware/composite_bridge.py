import asyncio
import logging

from app.hardware.esp32 import ESP32Bridge
from app.models import Phase

log = logging.getLogger(__name__)


class CompositeBridge(ESP32Bridge):
    """
    Fan-out bridge: calls connect/set_phase/close on every child bridge
    in parallel so the TrafficController drives both ESP32 and SUMO with
    a single bridge reference.

    On set_phase() the first successful (ok=True) result is returned.
    If all bridges fail the last failure is returned.
    On connect() each bridge is attempted independently; failures are
    logged as warnings so a SUMO startup error never kills the app.
    """

    def __init__(self, *bridges):
        self._bridges = list(bridges)

    async def connect(self):
        log.info("CompositeBridge: connecting %d bridges", len(self._bridges))
        results = await asyncio.gather(
            *(b.connect() for b in self._bridges),
            return_exceptions=True,
        )
        for bridge, result in zip(self._bridges, results):
            if isinstance(result, Exception):
                log.warning(
                    "CompositeBridge: %s.connect() failed: %s",
                    type(bridge).__name__,
                    result,
                )
            else:
                log.info("CompositeBridge: %s.connect() OK", type(bridge).__name__)

    async def set_phase(self, phase, duration):
        log.info("CompositeBridge: forwarding phase=%s duration=%s to %d bridges", phase, duration, len(self._bridges))
        results = await asyncio.gather(
            *(b.set_phase(phase, duration) for b in self._bridges),
            return_exceptions=True,
        )
        ok_result = None
        last = (False, "no-bridges")
        for bridge, r in zip(self._bridges, results):
            if isinstance(r, Exception):
                log.debug(
                    "CompositeBridge: %s.set_phase(%s) raised: %s",
                    type(bridge).__name__, phase, r,
                )
                last = (False, str(r))
            else:
                last = r
                if r[0] and ok_result is None:
                    ok_result = r
        return ok_result if ok_result is not None else last

    async def close(self):
        await asyncio.gather(
            *(b.close() for b in self._bridges),
            return_exceptions=True,
        )
