import asyncio
from dataclasses import dataclass
from fastapi import WebSocket, WebSocketDisconnect


@dataclass(eq=False)
class Client:
    ws: WebSocket
    key: str
    permission: str
    send_lock: asyncio.Lock

    def __hash__(self):
        return id(self.ws)

    def __eq__(self, other):
        return self.ws is other.ws

    async def send(self, packet: dict):
        try:
            async with self.send_lock:
                await self.ws.send_json(packet)
        except WebSocketDisconnect:
            pass
