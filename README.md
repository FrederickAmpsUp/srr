# Sim Race Radio

A Discord bot that listens to voice channels, transcribes and lists messages in a web interface, and lets you replay the audio, including a dedicated overlay page for use in OBS.

## Features

- Joins Discord voice channels and captures audio
- Displays transcribed messages in a web UI in real time
- Click a message to replay its audio and text on a separate overlay page (for OBS)
- Multiple independent sessions, each with their own access keys
- Access key permission levels:
  - **admin** - create/delete access keys, delete the session
  - **write** - replay radio messages, join voice channels
  - **read** - view data only

## Requirements

- Python 3.10+ (recommended)
- A virtual environment (venv) - required to run
- CUDA-capable GPU (for the default Whisper config; can be changed to CPU)
- A Discord bot token

## Setup

1. Clone the repository and enter the project directory.

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate   # Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Create a `.env` file in the project root:
   ```env
   DISCORD_TOKEN=<discord bot token>
   ```

5. Configure `config.toml` (defaults shown below):
   ```toml
   [whisper]
   model = "small"
   device = "cuda"
   compute_type = "float16"
   beam_size = 1

   [voice]
   silence_sec = 0.8
   utterance_sec = 15
   ```
   - `whisper.model` - Whisper model size (e.g. `tiny`, `base`, `small`, `medium`, `large`)
   - `whisper.device` - `cuda` or `cpu`
   - `whisper.compute_type` - inference precision (`float16` or `int8`)
   - `voice.silence_sec` - silence duration (seconds) that marks the end of an utterance
   - `voice.utterance_sec` - max length (seconds) of a single captured utterance

6. Run the bot:
   ```bash
   python launch.py
   ```

The web interface is served on `0.0.0.0:8765`.

## Access

- Locally: `http://localhost:8765`
- Remotely: put a reverse proxy (e.g. nginx, Caddy) in front of port 8765 with HTTPS/WSS configured, then access via your domain. Audio playback and live updates require a secure context (HTTPS/WSS) when not on localhost. Also works through Cloudflare tunnels.

## Usage

1. Start a session and generate an admin access key.
2. Use a **write** or **admin** key to join a voice channel and monitor it.
3. Messages appear in the web interface as they're transcribed.
4. Click a message to display it on the overlay.
5. Add the overlay page as a Browser Source in OBS to show replayed messages on stream.
6. Share **read**-only keys with people who just need visibility, and **write** keys with anyone who needs to trigger replays.
