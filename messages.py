from dataclasses import dataclass, asdict

@dataclass
class Message(object):
    id: int
    name: str
    pfp: str
    content: str
    time: str

class MessageManager:
    def __init__(self):
        self.messages = []

    def add(self, message):
        self.messages.insert(0, message)

    def serialize(self):
        return [asdict(m) for m in self.messages]
