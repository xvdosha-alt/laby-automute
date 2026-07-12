import threading
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Callable


@dataclass
class LogEntry:
    id: int
    ts: str
    text: str
    level: str


class RuntimeState:
    MAX_LOGS = 2000

    def __init__(self):
        self._lock = threading.Lock()
        self._logs: list[LogEntry] = []
        self._log_seq = 0
        self._clients: list[dict] = []
        self._summary: dict = {}
        self._moderation_enabled = False
        self._on_moderation_change: Callable[[bool], None] | None = None

    def set_moderation_change_handler(
        self, handler: Callable[[bool], None] | None
    ) -> None:
        self._on_moderation_change = handler

    def is_moderation_enabled(self) -> bool:
        with self._lock:
            return self._moderation_enabled

    def set_moderation_enabled(self, enabled: bool) -> bool:
        notify = False
        with self._lock:
            enabled = bool(enabled)
            if self._moderation_enabled == enabled:
                return self._moderation_enabled
            self._moderation_enabled = enabled
            notify = True
        if notify and self._on_moderation_change is not None:
            self._on_moderation_change(enabled)
        if notify:
            state = "включена" if enabled else "остановлена"
            self.add_log(f"[dashboard] модерация {state}", "yellow")
        return enabled

    def add_log(self, text: str, level: str = "default") -> None:
        with self._lock:
            self._log_seq += 1
            entry = LogEntry(
                id=self._log_seq,
                ts=datetime.now().strftime("%H:%M:%S"),
                text=text,
                level=level,
            )
            self._logs.append(entry)
            if len(self._logs) > self.MAX_LOGS:
                self._logs = self._logs[-self.MAX_LOGS :]

    def get_logs(self, since: int = 0, limit: int = 500) -> list[dict]:
        with self._lock:
            items = [e for e in self._logs if e.id > since]
            return [asdict(e) for e in items[-limit:]]

    def set_clients(self, clients: list[dict]) -> None:
        with self._lock:
            self._clients = list(clients)

    def set_summary(self, summary: dict) -> None:
        with self._lock:
            self._summary = dict(summary)

    def get_clients(self) -> list[dict]:
        with self._lock:
            return list(self._clients)

    def get_summary(self) -> dict:
        with self._lock:
            return dict(self._summary)
