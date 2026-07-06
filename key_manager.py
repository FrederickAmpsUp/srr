from rich.console import Console
from rich.table import Table

class KeyManager:
    def __init__(self):
        self.keys: dict[str, str] = {}
        self.labels: dict[str, str] = {}

        self.rank = {
            "read": 0,
            "write": 1,
            "admin": 2
        }
        # Force terminal capabilities for internal string capturing
        self._console = Console(force_terminal=True)

    def add(self, key: str, perm: str, label: str = ""):
        self.keys[key] = perm
        if label:
            self.labels[key] = label

    def delete_key(self, key: str):
        self.keys.pop(key, None)
        self.labels.pop(key, None)

    def get_perm(self, key: str) -> str:
        return self.keys.get(key, "read")

    def can_see(self, viewer_perm: str, target_perm: str) -> bool:
        return self.rank[viewer_perm] >= self.rank[target_perm]

    # --- REPL utils ---
    def get(self, i) -> str | None:
        try:
            return list(self.keys.keys())[i]
        except IndexError:
            return None

    def delete(self, i) -> bool:
        key = self.get(i)
        if not key:
            return False
        self.delete_key(key)
        return True

    def __repr__(self) -> str:
        if not self.keys:
            return "<KeyManager: Empty>"

        table = Table(title="Key Manager Registry")
        table.add_column("Index")
        table.add_column("Key (Masked)", no_wrap=True)
        table.add_column("Permission", style="bold magenta")
        table.add_column("Label", style="italic green")

        perm_colors = {
            "admin": "[red]admin[/red]",
            "write": "[yellow]write[/yellow]",
            "read": "[green]read[/green]"
        }

        i = 0
        for key, perm in self.keys.items():
            masked_key = f"{key[:8]}..." if len(key) > 8 else key
            
            perm_display = perm_colors.get(perm, perm)
            
            label_display = self.labels.get(key, "-")

            table.add_row(str(i), masked_key, perm_display, label_display)
            i += 1

        with self._console.capture() as capture:
            self._console.print(table)
            
        return capture.get()
