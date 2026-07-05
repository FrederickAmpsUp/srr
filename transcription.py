from faster_whisper import WhisperModel
import config
import numpy as np
from scipy.signal import resample_poly
from queue import Empty, Queue
import threading

def _pcm_to_float32(pcm: bytes) -> np.ndarray:
    audio = np.frombuffer(pcm, dtype=np.int16).astype(np.float32)
    audio = audio[::2] / 32768.0

    audio = resample_poly(audio, up=1, down=3)
    return audio

def _apply_fade(audio: np.ndarray, sample_rate: int, fade_ms: int = 10) -> np.ndarray:
    """
    Apply fade-in and fade-out to stereo int16 PCM.
    audio.shape == (frames, 2)
    """
    if audio.dtype != np.int16:
        raise TypeError("audio must be int16")
    if audio.ndim != 2 or audio.shape[1] != 2:
        raise ValueError("audio must have shape (frames, 2)")

    fade_len = int(sample_rate * fade_ms / 1000)

    if fade_len <= 1 or len(audio) < fade_len * 2:
        return audio

    out = audio.copy()

    # Integer gain 0..32767, shape (fade_len, 1)
    gain = np.linspace(0, 32767, fade_len, dtype=np.int32)[:, None]

    # Fade in
    out[:fade_len] = (
        out[:fade_len].astype(np.int32) * gain
    ) // 32767

    # Fade out
    out[-fade_len:] = (
        out[-fade_len:].astype(np.int32) * gain[::-1]
    ) // 32767

    return out

# thin wrapper over WhisperModel
class Transcriber(object):
    def __init__(self):
        self.model = WhisperModel(config.whisper.model, device=config.whisper.device, compute_type=config.whisper.compute_type)
    
    def transcribe(self, audio: bytes) -> str:
        segments, _ = self.model.transcribe(_pcm_to_float32(audio), beam_size=config.whisper.beam_size)
        return "".join([s.text for s in segments]).strip()

class QueueTranscriber(object):
    def __init__(self, rx_queue: Queue, tx_queue: Queue):
        self.transcriber = Transcriber()
        self.rx_queue = rx_queue
        self.tx_queue = tx_queue

        self._stop = threading.Event()
        threading.Thread(target=self.run, daemon=True).start()

    def run(self):
        while not self._stop.is_set():
            try:
                try:
                    pcm, *rest = self.rx_queue.get(timeout=0.05)
                except Empty:
                    continue

                text = self.transcriber.transcribe(pcm)
                if text:
                    self.tx_queue.put((text, _apply_fade(np.frombuffer(pcm, dtype=np.int16).reshape(-1,2), 48000), *rest))
            except Exception as e:
                print(e)

    def cleanup(self):
        self._stop.set()
# ---- test segment ---- broken
if __name__ == "__main__":
    import time
    transcriber = Transcriber()

    TEST_AUDIO = "test_data/transcriber_test_2.wav"

    # Warmup
    print(transcriber.transcribe(TEST_AUDIO))

    times = []
    for _ in range(10):
        start = time.perf_counter()
        transcriber.transcribe(TEST_AUDIO)
        times.append(time.perf_counter() - start)

    print(f"Average: {sum(times) / len(times):.3f} s")
    print(f"Min:     {min(times):.3f} s")
