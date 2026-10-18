import json
import os
import secrets


class Config:
    def __init__(self, data=None):
        data = data or {}
        self.host = data.get("host", "0.0.0.0")
        self.port = data.get("port", 8080)
        self.secret = data.get("secret", secrets.token_hex(16))
        self.lang = data.get("lang", "hi")
        self.voice_enabled = data.get("voice_enabled", True)
        self.announce_structure = data.get("announce_structure", True)
        self.relay_url = data.get("relay_url", "")
        self.relay_key = data.get("relay_key", "")
        self.path = None

    @classmethod
    def load(cls, path: str) -> "Config":
        cfg = cls()
        cfg.path = path
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    cfg = cls(json.load(f))
                cfg.path = path
        except Exception:
            pass
        if not cfg.secret:
            cfg.secret = secrets.token_hex(16)
        cfg.save()
        return cfg

    def save(self):
        if not self.path:
            return
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.__dict__, f, indent=2)
        except Exception:
            pass
