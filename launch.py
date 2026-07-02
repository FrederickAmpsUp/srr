from dotenv import load_dotenv
from session import SessionManager
from discord_bot import DiscordBot
from server import WebServer

import asyncio
import os
import uvicorn

from IPython import embed
import threading

def repl(**kwargs):
    embed(**kwargs)

async def main():
    load_dotenv()

    discord_bot = DiscordBot(os.environ["DISCORD_TOKEN"])

    session_manager = SessionManager(discord_bot)

    web_server = WebServer(session_manager)

    config = uvicorn.Config(
        web_server.app,
        host="0.0.0.0",
        port=8765,
        log_level="warning",
    )
    server = uvicorn.Server(config)

    # Start services
    bot_task = asyncio.create_task(discord_bot.start())
    web_task = asyncio.create_task(server.serve())

    # Wait for Discord to be ready
    await discord_bot.wait_ready()

    # run a REPL
    threading.Thread(target=repl, kwargs={ "user_ns": { "session_manager": session_manager } }, daemon=True).start()

    # Keep running until one service exits
    await asyncio.gather(bot_task, web_task)

if __name__ == "__main__":
    asyncio.run(main())
