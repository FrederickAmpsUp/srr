import tomllib
import os
from dataclasses import dataclass

with open(os.getenv("SRR_CONFIG_FILE", "config.toml"), "rb") as f:
    config = tomllib.load(f)

@dataclass
class WhisperConfig:
    model: str
    device: str
    compute_type: str
    beam_size: int

@dataclass
class VoiceConfig:
    silence_sec: float

whisper = WhisperConfig(**config["whisper"])
voice = VoiceConfig(**config["voice"])
