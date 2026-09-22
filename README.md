# FlowSync — Adaptive 4-Way Traffic Control

A complete semester-project starter for a standard four-arm intersection. YOLO measures North/South/East/West traffic, an adaptive scheduler chooses bounded green times, a safety state machine controls legal phases, an ESP32 drives 12 LEDs, and a React dashboard receives live state through WebSockets.

> This is an educational prototype, not certified road-control equipment. Do not connect it to public-road infrastructure.

## Architecture

```text
Video / camera → YOLO → traffic demand → adaptive scheduler
                                      ↓
React dashboard ← WebSocket ← FastAPI state machine → USB serial → ESP32 → 12 LEDs
                         REST commands ↗                 ↖ ACK/status
```

The safety rule is deliberate: **AI estimates demand and green duration; it cannot invent signal combinations.** Only these phases exist:

```text
NS_GREEN → NS_YELLOW → ALL_RED → EW_GREEN → EW_YELLOW → ALL_RED → repeat
```

Green is dynamic (10–40 s by default). Yellow is fixed at 3 s and all-red at 1 s. Manual commands are also routed through safe yellow/all-red transitions.

## 1. Run the complete system in simulation mode

Requirements: Python 3.11+ and Node.js 20+.

### Backend

```bash
cd backend
python -m venv .venv
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:TRAFFIC_MODE="mock"
$env:SERIAL_MODE="mock"
uvicorn app.main:app --reload
```

macOS/Linux:

```bash
source .venv/bin/activate
pip install -r requirements.txt
TRAFFIC_MODE=mock SERIAL_MODE=mock uvicorn app.main:app --reload
```

Open API docs at `http://localhost:8000/docs`.

### React dashboard

In another terminal:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`, then click **Start system**. The dashboard will show simulated traffic, changing demand, dynamic phase durations and mock ESP32 acknowledgements.

## 2. Wire and flash the ESP32

Each LED must have an appropriate series resistor (commonly 220–330 Ω). The included firmware uses:

| Approach | Red | Yellow | Green |
|---|---:|---:|---:|
| North | GPIO 13 | GPIO 14 | GPIO 16 |
| South | GPIO 17 | GPIO 18 | GPIO 19 |
| East | GPIO 21 | GPIO 22 | GPIO 23 |
| West | GPIO 25 | GPIO 26 | GPIO 27 |

All LED cathodes go to GND through a common ground. For a larger lamp/load, use transistor or relay drivers—never power it directly from GPIO.

Open `firmware/traffic_controller/traffic_controller.ino` in Arduino IDE, select your ESP32 board and flash it. Close Arduino Serial Monitor before starting Python because only one process can own the serial port.

Run the backend with hardware:

```powershell
$env:SERIAL_MODE="serial"
$env:SERIAL_PORT="COM5"
uvicorn app.main:app --reload
```

On Linux the port may look like `/dev/ttyUSB0`; the user may need serial-device permission.

The protocol is atomic:

```text
Python → PHASE,NS_GREEN,25,a1b2c3d4
ESP32  → ACK,NS_GREEN,25,a1b2c3d4
```

The ESP32 accepts only the five predefined phases and forces all-red if the commanded duration expires without a fresh command (with a five-second transport grace period).

## 3. Enable the real YOLO model

Install the vision dependencies:

```bash
cd backend
pip install -r requirements-vision.txt
```

For a webcam:

```powershell
$env:TRAFFIC_MODE="yolo"
$env:VIDEO_SOURCE="0"
uvicorn app.main:app --reload
```

For a video, place it under `videos/` and use an absolute path or a path relative to `backend/`:

```powershell
$env:TRAFFIC_MODE="yolo"
$env:VIDEO_SOURCE="../videos/intersection.mp4"
uvicorn app.main:app --reload
```

The first run downloads `yolo11n.pt`. The COCO model detects cars, motorcycles, buses and trucks. Vehicle weights are 1.0, 0.5, 2.0 and 2.0 respectively.

The starter assigns detections to N/S/E/W by their position around the image centre and treats detections in the central 65% as a queue proxy. For your final camera angle, calibrate this logic in `backend/app/vision/analyzer.py` using four hand-drawn approach/stop-line polygons. That calibration is necessary for defensible queue measurements.

Annotated video is exposed separately at `GET /api/video.mjpg`; numerical state stays on `/ws/live` so video bytes never overload the state WebSocket.

## Adaptive timing formula

For approach `i`:

```text
demand_i = weighted_vehicle_count + 2 × queue_count + 0.05 × waiting_seconds
```

For a corridor:

```text
NS demand = North demand + South demand
EW demand = East demand + West demand
green = clamp(8 + 0.6 × corridor_demand, 10, 40)
```

If an approach waits 60 seconds, starvation protection guarantees at least half of the configured green range. A new duration is calculated immediately before a green phase and then locked until that phase completes.

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Health check |
| GET | `/api/system` | Complete current state |
| GET | `/api/traffic` | N/S/E/W measurements |
| GET | `/api/signals` | Current phase and lamps |
| GET | `/api/history?limit=120` | Recent in-memory samples |
| POST | `/api/system/start` | Start adaptive sequence |
| POST | `/api/system/stop` | Safe stop through all-red |
| POST | `/api/manual/phase` | Queue NS/EW manual phase |
| WS | `/ws/live` | Live state, approximately 2 Hz |
| GET | `/api/video.mjpg` | Annotated YOLO stream |

Manual phase body:

```json
{ "phase": "NS_GREEN", "duration": 15 }
```

## Tests

```bash
cd backend
pytest -q
```

The tests cover dynamic timing bounds, heavier-corridor priority, legal phase maps and rejection of conflicting greens.

## Recommended next upgrades

1. Calibrate four polygonal regions and stop lines for the exact intersection video.
2. Add tracking (ByteTrack) so vehicle flow and stationary queue length are distinct.
3. Persist events to SQLite/PostgreSQL instead of the current in-memory history.
4. Add authenticated operator access before allowing manual control over a network.
5. Add emergency/pedestrian phases only after explicitly defining their safe transition tables.
