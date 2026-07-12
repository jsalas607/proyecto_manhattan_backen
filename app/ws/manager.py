import asyncio
from collections import defaultdict

from fastapi import WebSocket


class ConnectionManager:
    """Agrupa conexiones WebSocket por (restaurant_id, canal) y permite broadcast."""

    def __init__(self) -> None:
        self._rooms: dict[tuple[str, str], set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, restaurant_id: str, canal: str, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._rooms[(restaurant_id, canal)].add(ws)

    async def disconnect(self, restaurant_id: str, canal: str, ws: WebSocket) -> None:
        async with self._lock:
            self._rooms[(restaurant_id, canal)].discard(ws)

    async def broadcast(self, restaurant_id: str, canal: str, message: dict) -> None:
        async with self._lock:
            conns = list(self._rooms.get((restaurant_id, canal), set()))
        for ws in conns:
            try:
                await ws.send_json(message)
            except Exception:
                await self.disconnect(restaurant_id, canal, ws)


manager = ConnectionManager()
