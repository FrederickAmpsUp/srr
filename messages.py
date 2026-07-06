from dataclasses import dataclass, asdict
from datetime import datetime
from rich.console import Console
from rich.table import Table

@dataclass
class Message(object):
    id: int
    name: str
    pfp: str
    content: str
    time: float  # time.time() float

class MessageManager:
    def __init__(self):
        self.messages = []
        self._console = Console(force_terminal=True)

    def add(self, message):
        self.messages.insert(0, message)

    def serialize(self):
        return [asdict(m) for m in self.messages]

    def __repr__(self) -> str:
        if not self.messages:
            return "<MessageManager: No Messages>"

        table = Table(title="Message History")
        table.add_column("ID", style="dim cyan", justify="right")
        table.add_column("Time", style="yellow")
        table.add_column("Sender", style="bold green")
        table.add_column("Content", style="white")

        for msg in self.messages:
            table.add_row(
                str(msg.id),
                msg.time,
                msg.name,
                msg.content
            )

        # 3. Capture the table formatting as a string
        with self._console.capture() as capture:
            self._console.print(table)
            
        return capture.get()
