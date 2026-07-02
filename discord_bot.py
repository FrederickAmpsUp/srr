import discord
from discord.ext import voice_recv
import asyncio

class DiscordBot:
    def __init__(self, token: str):
        intents = discord.Intents.default()
        intents.guilds = True
        intents.voice_states = True

        self.client = discord.Client(intents=intents)
        self.token = token

        self.ready_event = asyncio.Event()

        @self.client.event
        async def on_ready():
            self.ready_event.set()
            print("Bot ready")

    async def start(self):
        await self.client.start(self.token)

    async def wait_ready(self):
        await self.ready_event.wait()

    async def connect_vc(self, session, channel_id: int) -> str:
        channel = await self.client.fetch_channel(channel_id)

        if not isinstance(channel, discord.VoiceChannel):
            raise TypeError("Not a voice channel")

        guild = channel.guild
        vc = guild.voice_client  # 👈 source of truth

        if vc and vc.is_connected():
            if vc.channel.id == channel.id:
                return channel.name
            await vc.move_to(channel)
        else:
            vc = await channel.connect(cls=voice_recv.VoiceRecvClient)
            vc.listen(session.voice_sink)

        session.voice_client = vc

        return channel.name
