from dataclasses import dataclass, field

from .heuristics import HeuristicChecker
from .models import ChatMessage, ModClientRef


@dataclass
class ClientSession:
    endpoint: ModClientRef
    chat_since: int = 0
    boot_id: int = 0
    online: bool = False
    ml_batch: list[ChatMessage] = field(default_factory=list)
    ml_batch_first_at: float = 0.0
    ml_last_submit_at: float = 0.0
    recent_messages: list[ChatMessage] = field(default_factory=list)
    heuristics: HeuristicChecker | None = None
    poll_failures: int = 0

    @property
    def host(self) -> str:
        return self.endpoint.host

    @property
    def port(self) -> int:
        return self.endpoint.port

    @property
    def moderator_nick(self) -> str:
        return self.endpoint.moderator_nick

    @moderator_nick.setter
    def moderator_nick(self, value: str) -> None:
        self.endpoint = ModClientRef(self.host, self.port, value)

    @property
    def label(self) -> str:
        nick = self.moderator_nick or "?"
        return f"{nick}@{self.port}"
