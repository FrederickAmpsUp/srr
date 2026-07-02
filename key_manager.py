class KeyManager:
    def __init__(self):
        self.keys: dict[str, str] = {}
        self.labels: dict[str, str] = {}

        self.rank = {
            "read": 0,
            "write": 1,
            "admin": 2
        }

    def add(self, key: str, perm: str, label: str = ""):
        self.keys[key] = perm
        if label:
            self.labels[key] = label

    def delete(self, key: str):
        self.keys.pop(key, None)
        self.labels.pop(key, None)

    def get_perm(self, key: str) -> str:
        return self.keys.get(key, "read")

    def can_see(self, viewer_perm: str, target_perm: str) -> bool:
        return self.rank[viewer_perm] >= self.rank[target_perm]
