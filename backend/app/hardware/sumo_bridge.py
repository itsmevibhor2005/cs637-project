import asyncio
import logging
import os
import queue
import sys
import threading
import time
from pathlib import Path

from app.hardware.esp32 import ESP32Bridge
from app.models import Phase

log = logging.getLogger(__name__)

_TL_ID = "0"

_GREEN_EDGES = {
    Phase.N_GREEN: {"4i"},
    Phase.S_GREEN: {"3i"},
    Phase.E_GREEN: {"2i"},
    Phase.W_GREEN: {"1i"},
}

_YELLOW_FOR_GREEN = {
    Phase.N_YELLOW: Phase.N_GREEN,
    Phase.S_YELLOW: Phase.S_GREEN,
    Phase.E_YELLOW: Phase.E_GREEN,
    Phase.W_YELLOW: Phase.W_GREEN,
}


def _ensure_traci_importable():
    sumo_home = os.environ.get("SUMO_HOME", "")
    if sumo_home:
        tools_dir = str(Path(sumo_home) / "tools")
        if tools_dir not in sys.path:
            sys.path.insert(0, tools_dir)
            log.debug("Added SUMO_HOME/tools to sys.path: %s", tools_dir)
    try:
        import traci  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "traci could not be imported. "
            "Set the SUMO_HOME environment variable to your SUMO 1.27.1 "
            "installation directory (e.g. C:\\Program Files (x86)\\Eclipse\\Sumo)."
        ) from exc


def _find_sumo_binary(name):
    sumo_home = os.environ.get("SUMO_HOME", "")
    if sumo_home:
        for candidate in (
            Path(sumo_home) / "bin" / name,
            Path(sumo_home) / "bin" / (name + ".exe"),
        ):
            if candidate.exists():
                return str(candidate)
    return name


class SumoBridge(ESP32Bridge):
    """
    Drives SUMO traffic-light junction '0' via TraCI.

    Implements ESP32Bridge so TrafficController needs zero changes.
    Runs SUMO in a daemon thread and advances simulation at step_length
    seconds per step. set_phase() is non-blocking: it enqueues the
    new RYGS state string and returns immediately.

    Parameters
    ----------
    cfg_path    : Path to cross.sumocfg.
    gui         : If True, launch sumo-gui instead of headless sumo.
    step_length : Real-time seconds per simulationStep() call (default 1.0).
    """

    def __init__(self, cfg_path, gui=False, step_length=1.0):
        self._cfg_path = str(Path(cfg_path).resolve())
        self._gui = gui
        self._step_length = step_length
        self._cmd_queue = queue.Queue()
        self._thread = None
        self._running = False
        self._ready = threading.Event()
        self._startup_error = None
        self._state_strings = {}

    async def connect(self):
        """Start SUMO and block until the simulation is ready."""
        log.info("[SUMO] Starting SUMO bridge: cfg=%s gui=%s step_length=%s", self._cfg_path, self._gui, self._step_length)
        _ensure_traci_importable()
        self._running = True
        self._ready.clear()
        self._startup_error = None
        self._thread = threading.Thread(
            target=self._sumo_thread,
            name="sumo-traci",
            daemon=True,
        )
        self._thread.start()
        await asyncio.to_thread(self._ready.wait)
        if self._startup_error is not None:
            log.error("[SUMO] Startup failed: %s", self._startup_error)
            raise self._startup_error
        log.info("[SUMO] Connected to TraCI and ready")

    async def set_phase(self, phase, duration):
        """
        Enqueue a RYGS state change and return immediately.

        The controller already sleeps for *duration* seconds after this
        call, so SUMO stepping happens in parallel with that sleep.
        """
        state_str = self._state_strings.get(phase)
        if state_str is None:
            msg = f"sumo-unknown-phase:{phase}"
            log.warning("[SUMO] Unknown phase %s; no state string available", phase)
            return False, msg
        self._cmd_queue.put(state_str)
        log.info("[SUMO] Received phase=%s duration=%s; queued state=%s", phase, duration, state_str)
        return True, f"ACK,{phase},{duration},sumo"

    async def close(self):
        """Signal the stepper thread to stop and wait for it to exit."""
        self._running = False
        self._cmd_queue.put(None)  # stop sentinel
        if self._thread is not None and self._thread.is_alive():
            await asyncio.to_thread(self._thread.join, 5.0)
        log.info("SumoBridge closed")

    def _sumo_thread(self):
        """
        Background thread that owns all TraCI socket I/O.

        Lifecycle:
          1. Start SUMO via traci.start().
          2. Build per-direction RYGS state strings.
          3. Signal asyncio side that startup is complete.
          4. Loop: drain queue -> apply latest TL state -> step simulation.
        """
        import traci  # noqa: PLC0415

        binary = _find_sumo_binary("sumo-gui" if self._gui else "sumo")
        cmd = [
            binary,
            "-c", self._cfg_path,
            "--start",
            "--quit-on-end",
        ]
        try:
            log.info("SumoBridge starting: %s", " ".join(cmd))
            traci.start(cmd, label="cs637")
        except Exception as exc:
            log.error("SumoBridge: traci.start() failed: %s", exc)
            self._startup_error = exc
            self._ready.set()
            return

        try:
            self._build_state_strings(traci)
        except Exception as exc:
            log.error("SumoBridge: _build_state_strings() failed: %s", exc)
            self._startup_error = exc
            self._ready.set()
            try:
                traci.close()
            except Exception:
                pass
            return

        try:
            traci.trafficlight.setRedYellowGreenState(
                _TL_ID, self._state_strings[Phase.ALL_RED]
            )
        except Exception as exc:
            log.warning("SumoBridge: could not set initial ALL_RED: %s", exc)

        self._ready.set()  # Unblock asyncio connect()

        while self._running:
            # Drain command queue; keep only the *latest* state string.
            latest_state = None
            try:
                while True:
                    item = self._cmd_queue.get_nowait()
                    if item is None:          # stop sentinel
                        self._running = False
                        break
                    latest_state = item
            except queue.Empty:
                pass

            if not self._running:
                break

            if latest_state is not None:
                try:
                    traci.trafficlight.setRedYellowGreenState(_TL_ID, latest_state)
                    log.info("[SUMO] Applied phase state=%s to TL %s", latest_state, _TL_ID)
                except Exception:
                    log.exception("[SUMO] setRedYellowGreenState failed for TL=%s state=%s", _TL_ID, latest_state)

            try:
                traci.simulationStep()
                log.debug("[SUMO] Simulation step: time=%s", traci.simulation.getTime())
            except Exception:
                log.exception("[SUMO] simulationStep() ended unexpectedly")
                break  # Simulation over or GUI closed

            time.sleep(self._step_length)

        try:
            traci.close()
        except Exception:
            pass
        log.info("SumoBridge: SUMO thread exited")

    def _build_state_strings(self, traci):
        """
        Build a RYGS state string for every Phase by inspecting the
        controlled links of junction '0'.

        traci.trafficlight.getControlledLinks(tl_id) returns a list of lists.
        Index i in the outer list corresponds to character i in the RYGS
        state string.  Each inner list holds (from_lane, to_lane, via_lane)
        tuples.  We strip the lane index suffix from from_lane to get the
        edge name (e.g. "4i_0" -> "4i").

        Edge -> Direction mapping (from cross.nod.xml):
          node 1  x=-500  West    incoming edge "1i"
          node 2  x=+500  East    incoming edge "2i"
          node 3  y=-500  South   incoming edge "3i"
          node 4  y=+500  North   incoming edge "4i"
        """
        links = traci.trafficlight.getControlledLinks(_TL_ID)
        n = len(links)
        log.info(
            "SumoBridge: junction %r has %d controlled signal indices",
            _TL_ID, n,
        )

        index_edge = {}
        for idx, link_group in enumerate(links):
            if link_group:
                from_lane = link_group[0][0]          # e.g. "4i_0"
                edge = from_lane.rsplit("_", 1)[0]    # e.g. "4i"
                index_edge[idx] = edge
                log.debug("  signal[%2d] <- %s (edge %s)", idx, from_lane, edge)

        for phase, edges in _GREEN_EDGES.items():
            chars = [
                "G" if index_edge.get(i, "") in edges else "r"
                for i in range(n)
            ]
            self._state_strings[phase] = "".join(chars)

        for yellow_phase, green_phase in _YELLOW_FOR_GREEN.items():
            self._state_strings[yellow_phase] = (
                self._state_strings[green_phase].replace("G", "y")
            )

        self._state_strings[Phase.ALL_RED] = "r" * n

        log.info(
            "SumoBridge: state strings built for %d phases over %d signal indices",
            len(self._state_strings), n,
        )
