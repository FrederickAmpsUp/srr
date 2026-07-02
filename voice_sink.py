from discord.ext import voice_recv
import time
import threading
import config
from queue import Queue

# accumulates audio data per-user
class UserBuffer:
    def __init__(self, uid: int, user):
        self.uid        = uid
        self.user       = user
        self.chunks:    list[bytes] = []
        self.last_spoke = time.monotonic()
        self.started = self.last_spoke

    def push(self, pcm: bytes):
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
        return data

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
            time.sleep(0.05)
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
