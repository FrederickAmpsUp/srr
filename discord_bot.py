import discord
from discord.ext import voice_recv, tasks
import asyncio

class DiscordBot:
    def __init__(self, token: str):
        intents = discord.Intents.default()
        intents.guilds = True
        intents.voice_states = True

        self.client = discord.Client(intents=intents)
        self.client.setup_hook = self.setup_hook
        self.token = token

        self.ready_event = asyncio.Event()

        self.vcs = set()

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
        vc = guild.voice_client

        if vc and vc.is_connected():
            if vc.channel.id == channel.id:
                return channel.name
            await vc.move_to(channel)
        else:
            vc = await channel.connect(cls=voice_recv.VoiceRecvClient)
            vc.listen(session.voice_sink)

        session.voice_client = vc
        self.vcs.add(vc)
        
        return channel.name

    async def setup_hook(self) -> None:
        self.send_packet.start()

    @tasks.loop(seconds=10)
    async def send_packet(self):
        '''
        We need this to send packets occasionally in case there is a period of no voice activity.
        This will prevent our bot's listen socket from closing.
        '''
        for vc in self.vcs:
            try:
                if vc and vc.is_connected():
                    vc.send_audio_packet(b"\xf8\xff\xfe", encode=False)
            except Exception as e:
                print(e)
