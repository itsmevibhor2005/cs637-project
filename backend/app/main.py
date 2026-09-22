import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.api.websocket import WebSocketHub
from app.config import settings
from app.hardware.esp32 import MockESP32Bridge, SerialESP32Bridge
from app.state import StateStore
from app.traffic.controller import TrafficController
from app.traffic.scheduler import AdaptiveScheduler, SchedulerConfig
from app.vision.service import VisionService


async def broadcaster(app: FastAPI) -> None:
    while True:
        state = await app.state.store.snapshot()
        await app.state.hub.broadcast(state.model_dump(mode="json"))
        await app.state.store.record_history()
        await asyncio.sleep(0.5)


@asynccontextmanager
async def lifespan(app: FastAPI):
    store = StateStore(settings.traffic_mode, settings.serial_mode)
    scheduler = AdaptiveScheduler(SchedulerConfig(
        min_green=settings.min_green,
        max_green=settings.max_green,
        max_wait_seconds=settings.max_wait_seconds,
    ))
    bridge = (
        SerialESP32Bridge(settings.serial_port, settings.serial_baud)
        if settings.serial_mode == "serial"
        else MockESP32Bridge()
    )
    vision = VisionService(
        store,
        scheduler,
        settings.traffic_mode,
        settings.video_source,
        settings.yolo_model,
        settings.yolo_confidence,
    )
    controller = TrafficController(
        store,
        scheduler,
        bridge,
        settings.yellow_seconds,
        settings.all_red_seconds,
    )
    hub = WebSocketHub()

    app.state.store = store
    app.state.scheduler = scheduler
    app.state.bridge = bridge
    app.state.vision = vision
    app.state.controller = controller
    app.state.hub = hub

    try:
        await bridge.connect()
        current = await store.snapshot()
        await store.patch(esp32=current.esp32.model_copy(update={"connected": True}))
    except Exception as exc:
        current = await store.snapshot()
        await store.patch(esp32=current.esp32.model_copy(update={
            "connected": False,
            "last_error": str(exc),
        }))

    tasks = [
        asyncio.create_task(vision.run(), name="vision"),
        asyncio.create_task(controller.run(), name="controller"),
        asyncio.create_task(broadcaster(app), name="websocket-broadcaster"),
    ]
    yield
    await controller.stop()
    await vision.stop()
    for task in tasks:
        task.cancel()
    for task in tasks:
        with suppress(asyncio.CancelledError):
            await task
    await bridge.close()


app = FastAPI(
    title="Adaptive 4-Way Traffic Controller",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.frontend_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)


@app.get("/health")
async def health():
    return {"ok": True}


@app.websocket("/ws/live")
async def live(socket: WebSocket):
    await app.state.hub.connect(socket)
    try:
        await socket.send_json((await app.state.store.snapshot()).model_dump(mode="json"))
        while True:
            await socket.receive_text()  # Client ping or disconnect detection.
    except WebSocketDisconnect:
        await app.state.hub.disconnect(socket)
    except Exception:
        await app.state.hub.disconnect(socket)

