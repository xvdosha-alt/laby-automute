import json
import os
import threading
from dataclasses import dataclass


@dataclass
class ChatCursor:
    boot: int = 0
    since: int = 0
    mod_nick: str = ""


class ChatCursorStore:
    def __init__(self, data_dir: str):
        self.path = os.path.join(data_dir, "chat_cursors.json")
        self._lock = threading.Lock()
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        if not os.path.isfile(self.path):
            self._write({})

    def get(self, host: str, port: int) -> ChatCursor:
        key = self._key(host, port)
        with self._lock:
            raw = self._read().get(key, {})
        return ChatCursor(
            boot=int(raw.get("boot", 0)),
            since=int(raw.get("since", 0)),
            mod_nick=str(raw.get("mod_nick", "")).strip(),
        )

    def save(
        self,
        host: str,
        port: int,
        boot: int,
        since: int,
        mod_nick: str | None = None,
    ) -> None:
        key = self._key(host, port)
        with self._lock:
            data = self._read()
            entry = dict(data.get(key, {}))
            entry["boot"] = boot
            entry["since"] = since
            if mod_nick:
                entry["mod_nick"] = mod_nick.strip()
            data[key] = entry
            self._write(data)

    @staticmethod
    def _key(host: str, port: int) -> str:
        return f"{host}:{port}"

    def _read(self) -> dict:
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _write(self, data: dict) -> None:
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
