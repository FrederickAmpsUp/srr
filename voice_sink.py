from discord.ext import voice_recv
import time
import threading
import config
from queue import Queue
import numpy as np

def _apply_fade(pcm: bytes, sample_rate: int, channels: int, fade_ms: int = 8) -> bytes:
    frame_size = 2 * channels
    fade_samples = int(sample_rate * fade_ms / 1000)
    fade_bytes = fade_samples * frame_size
    if len(pcm) < fade_bytes * 2:
        return pcm
    import numpy as np
    arr = np.frombuffer(pcm, dtype=np.int16).copy()
    n = fade_samples * channels
    fade_in = np.linspace(0, 1, n)
    fade_out = np.linspace(1, 0, n)
    arr[:n] = (arr[:n] * fade_in).astype(np.int16)
    arr[-n:] = (arr[-n:] * fade_out).astype(np.int16)
    return arr.tobytes()

def _despike(pcm: bytes, threshold: int = 30000, window: int = 8) -> bytes:
    arr = np.frombuffer(pcm, dtype=np.int16).copy()
    peaks = np.where(np.abs(arr) > threshold)[0]
    for p in peaks:
        lo, hi = max(0, p - window), min(len(arr), p + window)
        # replace the spike neighborhood with a linear ramp between its edges
        if lo < hi:
            arr[lo:hi] = np.linspace(arr[lo], arr[hi - 1], hi - lo).astype(np.int16)
    return arr.tobytes()

# accumulates audio data per-user
class UserBuffer:
    def __init__(self, uid: int, user):
        self.uid        = uid
        self.user       = user
        self.chunks:    list[bytes] = []
        self.last_spoke = time.monotonic()
        self.started = self.last_spoke

    def push(self, pcm: bytes):
        frame_size = 4
        if len(pcm) % frame_size != 0:
            # drop the stray trailing bytes rather than corrupt alignment
            pcm = pcm[: len(pcm) - (len(pcm) % frame_size)]
            if not pcm:
                return
        if not self.chunks:
            self.started = time.monotonic()

        self.chunks.append(pcm)
        self.last_spoke = time.monotonic()

    def should_flush(self):
        now = time.monotonic()

        silence = now - self.last_spoke >= config.voice.silence_sec
        max_duration = now - self.started >= config.voice.utterance_sec

        return self.chunks and (silence or max_duration)

    def flush(self) -> bytes:
        data = b"".join(self.chunks)
        self.chunks.clear()
        return _despike(_apply_fade(data, 48000, 2))

# recieves audio from a discord vc, accumulates per-user,
# pushes complete statements to a queue
class VoiceSink(voice_recv.AudioSink):
    def __init__(self, tx_queue: Queue):
        super().__init__()

        self.tx_queue = tx_queue

        self._buffers: dict[int, UserBuffer] = {}

        self._stop = threading.Event()

        self._lock = threading.Lock()
        threading.Thread(target=self.auto_flusher, daemon=True).start()

    def wants_opus(self) -> bool:
        return False

    def write(self, user, data):
        if user is None:
            return
        uid = user.id
        pcm = data.pcm
        if not pcm:
            return
        with self._lock:
            if uid not in self._buffers:
                self._buffers[uid] = UserBuffer(uid, user)
            self._buffers[uid].user = user
            self._buffers[uid].push(pcm)

    def cleanup(self):
        self._stop.set()

    def auto_flusher(self):
        while not self._stop.wait(0.05):
            to_queue = []
            with self._lock:
                for uid, b in list(self._buffers.items()):
                    if b.should_flush():
                        pcm = b.flush()
                        if pcm:
                            to_queue.append((pcm, b.user))
                        del self._buffers[uid]
            for x in to_queue:
                self.tx_queue.put(x)
