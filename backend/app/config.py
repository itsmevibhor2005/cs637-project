from dataclasses import dataclass
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    def load_dotenv(*_args, **_kwargs):
        return False

# Resolve the sumo/ directory relative to this file's location so the
# default cfg path works whether uvicorn is started from backend/ or root.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_SUMO_CFG = str(_PROJECT_ROOT / "sumo" / "cross.sumocfg")

# Load configuration from the project root or backend directory before reading
# environment variables. This keeps the app working when uvicorn is launched
# from either the repository root or from backend/.
for _env_file in (
    _PROJECT_ROOT / ".env",
    _BACKEND_ROOT / ".env",
    Path.cwd() / ".env",
):
    if _env_file.exists():
        load_dotenv(_env_file, override=False)


def _int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


def _float(name: str, default: float) -> float:
    return float(os.getenv(name, str(default)))


@dataclass(frozen=True)
class Settings:
    traffic_mode: str = os.getenv("TRAFFIC_MODE", "mock").lower()
    video_source: str = os.getenv("VIDEO_SOURCE", "0")
    yolo_model: str = os.getenv("YOLO_MODEL", "yolo11n.pt")
    yolo_confidence: float = _float("YOLO_CONFIDENCE", 0.35)
    serial_mode: str = os.getenv("SERIAL_MODE", "mock").lower()
    serial_port: str = os.getenv("SERIAL_PORT", "COM5")
    serial_baud: int = _int("SERIAL_BAUD", 115200)
    min_green: int = _int("MIN_GREEN", 10)
    max_green: int = _int("MAX_GREEN", 40)
    yellow_seconds: int = _int("YELLOW_SECONDS", 3)
    all_red_seconds: int = _int("ALL_RED_SECONDS", 1)
    max_wait_seconds: int = _int("MAX_WAIT_SECONDS", 60)
    frontend_origins: tuple[str, ...] = tuple(
        origin.strip()
        for origin in os.getenv("FRONTEND_ORIGINS", "http://localhost:5173").split(",")
        if origin.strip()
    )
    # ── SUMO / TraCI integration (disabled by default) ───────────────────
    # Set SUMO_ENABLED=true to start SUMO alongside the adaptive controller.
    sumo_enabled: bool = os.getenv("SUMO_ENABLED", "false").lower() == "true"
    # Path to cross.sumocfg; defaults to <project_root>/sumo/cross.sumocfg.
    sumo_cfg: str = os.getenv("SUMO_CFG", _DEFAULT_SUMO_CFG)
    # Set SUMO_GUI=true to open the sumo-gui window (useful during development).
    sumo_gui: bool = os.getenv("SUMO_GUI", "false").lower() == "true"
    # Seconds of real time between consecutive traci.simulationStep() calls.
    sumo_step_length: float = _float("SUMO_STEP_LENGTH", 1.0)


settings = Settings()

