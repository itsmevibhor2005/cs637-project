import asyncio

from fastapi import WebSocket


class WebSocketHub:
    def __init__(self):
        self.clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, socket: WebSocket) -> None:
        await socket.accept()
        async with self._lock:
            self.clients.add(socket)

    async def disconnect(self, socket: WebSocket) -> None:
        async with self._lock:
            self.clients.discard(socket)

    async def broadcast(self, payload: dict) -> None:
        stale: list[WebSocket] = []
        for socket in list(self.clients):
            try:
                await socket.send_json(payload)
            except Exception:
                stale.append(socket)
        if stale:
            async with self._lock:
                for socket in stale:
                    self.clients.discard(socket)

