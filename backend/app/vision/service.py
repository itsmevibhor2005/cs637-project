import asyncio
import math
import random
import time
from typing import AsyncIterator

from app.models import ApproachState, Direction, Phase
from app.state import StateStore
from app.traffic.scheduler import AdaptiveScheduler
from app.vision.analyzer import aggregate_detections


GREEN_FOR_DIRECTION = {
    Direction.N: Phase.N_GREEN,
    Direction.E: Phase.E_GREEN,
    Direction.S: Phase.S_GREEN,
    Direction.W: Phase.W_GREEN,
}


class VisionService:
    def __init__(
        self,
        store: StateStore,
        scheduler: AdaptiveScheduler,
        mode: str,
        source: str,
        model_name: str,
        confidence: float,
    ):
        self.store = store
        self.scheduler = scheduler
        self.mode = mode
        self.source = source
        self.model_name = model_name
        self.confidence = confidence
        self._running = False
        self._jpeg: bytes | None = None
        self._jpeg_lock = asyncio.Lock()

    async def run(self) -> None:
        self._running = True
        if self.mode == "yolo":
            await self._run_yolo()
        else:
            await self._run_mock()

    async def stop(self) -> None:
        self._running = False

    async def _run_mock(self) -> None:
        tick = 0
        while self._running:
            state = await self.store.snapshot()
            traffic: dict[Direction, ApproachState] = {}
            for index, direction in enumerate(Direction):
                wave = (math.sin(tick / 8 + index * 1.7) + 1) / 2
                vehicles = max(0, round(3 + 13 * wave + random.uniform(-1.5, 1.5)))
                queue = max(0, round(vehicles * random.uniform(0.45, 0.8)))
                was_waiting = state.phase != GREEN_FOR_DIRECTION[direction]
                previous_wait = state.traffic[direction].waiting_seconds
                wait = previous_wait + 1 if was_waiting and vehicles else 0.0
                traffic[direction] = ApproachState(
                    vehicles=vehicles,
                    queue=queue,
                    weighted_vehicles=round(vehicles * random.uniform(0.9, 1.2), 1),
                    waiting_seconds=wait,
                )
            traffic = self.scheduler.enrich_demands(traffic)
            await self.store.update_traffic(traffic, fps=15.0)
            tick += 1
            await asyncio.sleep(1)

    async def _run_yolo(self) -> None:
        try:
            import cv2
            from ultralytics import YOLO
        except ImportError as exc:
            raise RuntimeError(
                "YOLO mode needs requirements-vision.txt. Use TRAFFIC_MODE=mock meanwhile."
            ) from exc

        model = await asyncio.to_thread(YOLO, self.model_name)
        source = int(self.source) if self.source.isdigit() else self.source
        capture = cv2.VideoCapture(source)
        if not capture.isOpened():
            raise RuntimeError(f"Could not open VIDEO_SOURCE={self.source}")

        previous = time.perf_counter()
        try:
            while self._running:
                ok, frame = await asyncio.to_thread(capture.read)
                if not ok:
                    if isinstance(source, str):
                        capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        continue
                    await asyncio.sleep(0.1)
                    continue

                results = await asyncio.to_thread(
                    model.predict,
                    frame,
                    conf=self.confidence,
                    verbose=False,
                    classes=[2, 3, 5, 7],  # COCO: car, motorcycle, bus, truck
                )
                result = results[0]
                detections = []
                for box in result.boxes:
                    class_id = int(box.cls[0])
                    detections.append({
                        "class": model.names[class_id],
                        "confidence": float(box.conf[0]),
                        "box": [float(v) for v in box.xyxy[0]],
                    })

                height, width = frame.shape[:2]
                measured = aggregate_detections(detections, width, height)
                old = await self.store.snapshot()
                for direction, approach in measured.items():
                    waiting = old.traffic[direction].waiting_seconds
                    green = old.phase == GREEN_FOR_DIRECTION[direction]
                    approach.waiting_seconds = 0 if green or approach.vehicles == 0 else waiting + 0.2
                measured = self.scheduler.enrich_demands(measured)

                now = time.perf_counter()
                fps = 1 / max(now - previous, 0.001)
                previous = now
                await self.store.update_traffic(measured, fps)

                annotated = result.plot()
                cv2.line(annotated, (width // 2, 0), (width // 2, height), (75, 206, 151), 1)
                cv2.line(annotated, (0, height // 2), (width, height // 2), (75, 206, 151), 1)
                encoded, jpeg = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 75])
                if encoded:
                    async with self._jpeg_lock:
                        self._jpeg = jpeg.tobytes()
                await asyncio.sleep(0)
        finally:
            capture.release()

    async def mjpeg(self) -> AsyncIterator[bytes]:
        while self._running:
            async with self._jpeg_lock:
                frame = self._jpeg
            if frame:
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
            await asyncio.sleep(0.08)
