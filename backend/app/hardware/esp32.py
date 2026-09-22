import asyncio
from abc import ABC, abstractmethod
from uuid import uuid4

from app.models import Phase


class ESP32Bridge(ABC):
    @abstractmethod
    async def connect(self) -> None: ...

    @abstractmethod
    async def set_phase(self, phase: Phase, duration: int) -> tuple[bool, str]: ...

    @abstractmethod
    async def close(self) -> None: ...


class MockESP32Bridge(ESP32Bridge):
    async def connect(self) -> None:
        await asyncio.sleep(0.05)

    async def set_phase(self, phase: Phase, duration: int) -> tuple[bool, str]:
        await asyncio.sleep(0.03)
        return True, f"ACK,{phase.value},{duration},mock"

    async def close(self) -> None:
        return None


class SerialESP32Bridge(ESP32Bridge):
    def __init__(self, port: str, baud: int = 115200, timeout: float = 2.0):
        self.port = port
        self.baud = baud
        self.timeout = timeout
        self._serial = None
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        import serial

        self._serial = await asyncio.to_thread(
            serial.Serial, self.port, self.baud, timeout=self.timeout
        )
        await asyncio.sleep(2.0)  # ESP32 commonly resets when serial opens.
        await asyncio.to_thread(self._serial.reset_input_buffer)

    async def set_phase(self, phase: Phase, duration: int) -> tuple[bool, str]:
        if self._serial is None or not self._serial.is_open:
            return False, "serial-not-connected"

        request_id = uuid4().hex[:8]
        command = f"PHASE,{phase.value},{duration},{request_id}\n".encode()
        expected = f"ACK,{phase.value},{duration},{request_id}"

        async with self._lock:
            try:
                await asyncio.to_thread(self._serial.write, command)
                await asyncio.to_thread(self._serial.flush)
                raw = await asyncio.to_thread(self._serial.readline)
                reply = raw.decode(errors="replace").strip()
                return reply == expected, reply or "ack-timeout"
            except Exception as exc:  # Hardware faults must not crash FastAPI.
                return False, str(exc)

    async def close(self) -> None:
        if self._serial is not None and self._serial.is_open:
            await asyncio.to_thread(self._serial.close)

