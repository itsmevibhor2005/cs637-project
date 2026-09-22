from datetime import datetime, timezone
from enum import StrEnum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


class Direction(StrEnum):
    N = "N"
    S = "S"
    E = "E"
    W = "W"


class SignalColor(StrEnum):
    RED = "RED"
    YELLOW = "YELLOW"
    GREEN = "GREEN"


class Phase(StrEnum):
    N_GREEN = "N_GREEN"
    N_YELLOW = "N_YELLOW"
    E_GREEN = "E_GREEN"
    E_YELLOW = "E_YELLOW"
    S_GREEN = "S_GREEN"
    S_YELLOW = "S_YELLOW"
    W_GREEN = "W_GREEN"
    W_YELLOW = "W_YELLOW"
    ALL_RED = "ALL_RED"


class ApproachState(BaseModel):
    vehicles: int = 0
    queue: int = 0
    weighted_vehicles: float = 0.0
    demand: float = 0.0
    waiting_seconds: float = 0.0


class ESP32State(BaseModel):
    mode: Literal["mock", "serial"] = "mock"
    connected: bool = False
    last_ack: str | None = None
    last_error: str | None = None


class SystemState(BaseModel):
    type: Literal["traffic_state"] = "traffic_state"
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    running: bool = False
    ai_running: bool = False
    ai_mode: str = "mock"
    phase: Phase = Phase.ALL_RED
    next_phase: Phase = Phase.N_GREEN
    remaining: int = 0
    phase_duration: int = 0
    signals: dict[Direction, SignalColor] = Field(default_factory=dict)
    traffic: dict[Direction, ApproachState] = Field(default_factory=dict)
    esp32: ESP32State = Field(default_factory=ESP32State)
    emergency: Direction | None = None
    pedestrian_request: bool = False
    fps: float = 0.0
    cycle: int = 0
    last_transition_id: str = Field(default_factory=lambda: uuid4().hex[:10])


class ManualPhaseRequest(BaseModel):
    phase: Phase
    duration: int = Field(ge=1, le=60)


class SystemCommandResponse(BaseModel):
    ok: bool
    message: str
