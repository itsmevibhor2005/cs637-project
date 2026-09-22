from dataclasses import dataclass
import os


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


settings = Settings()

