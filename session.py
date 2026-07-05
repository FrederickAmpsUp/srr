import asyncio
from key_manager import KeyManager
from messages import Message, MessageManager
from client import Client
import secrets
from queue import Queue
from discord.ext import voice_recv
from discord import Member
from voice_sink import VoiceSink
from transcription import QueueTranscriber
from dataclasses import asdict
import io
import soundfile as sf
import time

class Session:
    def __init__(self, manager: SessionManager):
        self.keys = KeyManager()
        self.messages = MessageManager()
        self.message_audio = dict() # id -> PCM bytes
        self.manager = manager

        self.clients: set[Client] = set()
        self.loop = None  # injected later

        self.voice_queue = Queue()
        self.text_queue = Queue()
        self.voice_client: voice_recv.VoiceRecvClient = None
        self.voice_sink = VoiceSink(self.voice_queue)
        self.transcriber = QueueTranscriber(self.voice_queue, self.text_queue)

        self.vc_channel = ""

        self.running = True

        self.created_at = time.time()

        self.race_name: str | None = ""

        self.message_task = asyncio.create_task(self._message_queue_loop())
    # ---- lifecycle ----

    def attach_loop(self, loop):
        self.loop = loop

    async def add_client(self, client: Client):
        self.clients.add(client)

        try:
            await client.send(self._init_packet(client.key))

            while True:
                try:
                    msg = await client.ws.receive_json()
                except:
                    break

                await self.handle_packet(client, msg)
        finally:
            self.clients.discard(client)

    # ---- packets ----

    def _init_packet(self, key: str):
        perm = self.keys.get_perm(key)

        return {
            "type": "init",
            "keys": self._filtered_keys(perm),
            "vc_channel": self.vc_channel,
            "messages": self.messages.serialize(),
            "permission": perm,
            "meta": {
                "created_at": self.created_at * 1000,
                "race_name": self.race_name
            }
        }

    def _filtered_keys(self, viewer_perm: str):
        result = []

        for key, perm in self.keys.keys.items():
            if not self.keys.can_see(viewer_perm, perm):
                value = ""
            else:
                value = key

            result.append({
                "value": value,
                "label": self.keys.labels.get(key, "Unlabeled"),
                "perms": list(self.keys.rank.keys())[:self.keys.rank[perm]+1]
            })

        return result

    # ---- logic ----

    async def delete_key(self, key: str):
        self.keys.delete(key)
        self.manager.keys.pop(key, None)
        await self.broadcast_keys()
        for client in filter(lambda c: c.key == key, self.clients):
            await client.ws.close()

    async def create_key(self, label: str, perms: list[str]):
        perm = max(perms, key=lambda p: self.keys.rank[p])
        key = self.manager.generate_key() # ensure global uniqueness
        self.keys.add(key, perm, label)
        self.manager.keys[key] = self
        await self.broadcast_keys()

    async def display_message(self, id: int):
        for c in self.clients:
            await c.send({ # figure out how to send audio later
                "type": "display_message",
                "id": id
            })

    async def connect_vc(self, id: str):
        try:
            self.vc_channel = await self.manager.discord_bot.connect_vc(self, id)
        except TypeError as e:
            print(e)
            return

        await self.broadcast_vc_channel(self.vc_channel)

    async def handle_packet(self, client: Client, msg: dict):
        t = msg.get("type")

        if t == "delete_key":
            if client.permission == "admin":
                await self.delete_key(msg["key"])
        if t == "create_key":
            if client.permission == "admin":
                await self.create_key(msg["label"], msg["perms"])
        if t == "display_message":
            if self.keys.rank[client.permission] >= self.keys.rank["write"]:
                await self.display_message(msg["id"])
        if t == "connect_vc":
            if self.keys.rank[client.permission] >= self.keys.rank["write"]:
                await self.connect_vc(msg["id"])
        if t == "delete_session":
            await self.manager.delete_session(msg["key"])

    # ---- broadcasting ----

    def _spawn(self, coro):
        self.loop.create_task(coro)

    async def send(self, client: Client, packet: dict):
        await client.send(packet)

    async def broadcast(self, packet: dict):
        await asyncio.gather(*(c.send(packet) for c in self.clients))

    async def broadcast_keys(self):
        for c in self.clients:
            await c.send({
                "type": "bulk",
                "keys": self._filtered_keys(c.permission)
            })

    async def broadcast_vc_channel(self, channel: str):
        for c in self.clients:
            await c.send({
                "type": "bulk",
                "vc_channel": channel
            })

    async def _message_queue_loop(self):
        while self.running:
            try:
                msg = await asyncio.to_thread(self.text_queue.get, timeout=0.5)
            except Exception:
                continue

            text: str
            pcm: bytes
            user: Member

            text, pcm, user = msg
           
            uname = user.display_name or user.name

            # forward to message manager / state
            message = Message(
                id=len(self.messages.messages),
                name=uname,
                pfp=user.display_avatar.url,
                content=text,
                time="0:00:00"
            )

            self.messages.add(message)

            buf = io.BytesIO()
            sf.write(buf, pcm, 48000, format="WAV", subtype="PCM_16")
            buf.seek(0)
            self.message_audio[message.id] = buf.read()

            # broadcast update
            await self.broadcast({
                "type": "new_message",
                "message": asdict(message)
            })

    async def cleanup(self):
        self.running = False

        if self.voice_client:
            await self.voice_client.disconnect(force=True)

        self.voice_sink.cleanup()
        self.transcriber.cleanup()

        await asyncio.gather(
            *(client.ws.close() for client in list(self.clients)),
            self.message_task,
            return_exceptions=True,
        )

class SessionManager:
    def __init__(self, discord_bot):
        self.sessions = {}
        self.keys = {}  # session_key -> session
        self.discord_bot = discord_bot
        
    def create_session(self) -> tuple[Session, str]:
        session = Session(self)

        key = self.generate_key()
        session.keys.add(key, "admin", "Admin")

        self.sessions[id(session)] = session
        self.keys[key] = session

        session.attach_loop(asyncio.get_running_loop())

        return session, key

    async def delete_session(self, key):
        session = self.get_session(key)
        if not session:
            return

        if session.keys.get_perm(key) != "admin":
            return

        for key, _ in session.keys.keys.items():
            self.keys.pop(key, None)
        
        await session.cleanup()
        del self.sessions[id(session)]

    def get_session(self, key: str) -> Session | None:
        return self.keys.get(key, None)

    def get_audio(self, key: str, message: int):
        session = self.get_session(key)
        if not session: return None
        return session.message_audio.get(int(message), None)

    def generate_key(self):
        while True:
            k = secrets.token_urlsafe(12)[:16]
            if k not in self.keys:
                return k
