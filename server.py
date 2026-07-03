from fastapi import FastAPI, WebSocket
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from session import SessionManager
from client import Client
import asyncio
import io

class CreateSessionRequest(BaseModel):
    race_name: str | None

class WebServer:
    def __init__(self, session_manager: SessionManager = SessionManager(None)):
        self.session_manager = session_manager

        self.app = FastAPI()

        self.app.get("/")(self.index)
        self.app.get("/s/{key}")(self.session)
        self.app.get("/o/{key}")(self.overlay)
        self.app.get("/theme.css")(self.theme)
        self.app.get("/audio/{key}/{message}")(self.audio)
        self.app.get("/favicon.ico")(self.favicon)
        self.app.post("/api/sessions")(self.create_session)
        self.app.websocket("/ws/{key}")(self.websocket)

    async def index(self):
        return FileResponse("web/index.html")

    async def session(self, key: str):
        return FileResponse("web/session.html")

    async def overlay(self, key: str):
        return FileResponse("web/overlay.html")

    async def theme(self):
        return FileResponse("web/theme.css")

    async def audio(self, key, message):
        data = self.session_manager.get_audio(key, message)
        if not data:
            return
        return StreamingResponse(io.BytesIO(data), media_type="audio/wav")

    async def favicon(self):
        return FileResponse("web/favicon.ico")

    async def create_session(self, req: CreateSessionRequest):
        session, key = self.session_manager.create_session()
        session.race_name = req.race_name
        return { "key": key }

    async def websocket(self, ws: WebSocket, key: str):
        await ws.accept()

        session = self.session_manager.get_session(key)
        if session is None:
            await ws.close()
            return

        perm = session.keys.get_perm(key)

        client = Client(
            ws=ws,
            key=key,
            permission=perm,
            send_lock=asyncio.Lock()
        )

        await session.add_client(client)
