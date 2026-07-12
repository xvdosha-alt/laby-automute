import re

from .models import ChatMessage

BASE_LINE_RE = re.compile(
    r"^\[(\d{2}:\d{2}:\d{2})\] \[[^\]]+\]: (?:\[System\]\s+)?\[CHAT\]\s+(?:\[ALL\]\s+)?(.+)$"
)
CHAT_CONTENT_RE = re.compile(
    r"[^\|]+\|\s+(?:«[^»]*»\s+)?(~)?([A-Za-z0-9_]+)(?:\s+[^:]+)?:\s*(.*)$"
)


class ChatParser:
    @staticmethod
    def decode_line(raw: bytes) -> str:
        for encoding in ("utf-8", "cp1251", "cp866"):
            try:
                return raw.decode(encoding)
            except UnicodeDecodeError:
                continue
        return raw.decode("utf-8", errors="replace")

    def parse(self, decoded: str) -> ChatMessage | None:
        base_match = BASE_LINE_RE.match(decoded)
        if not base_match:
            return None

        timestamp = base_match.group(1)
        content = base_match.group(2)
        chat_match = CHAT_CONTENT_RE.search(content)
        if not chat_match:
            return None

        altered = bool(chat_match.group(1))
        nickname = chat_match.group(2)
        message = chat_match.group(3)
        if "~" in nickname:
            return None

        return ChatMessage(timestamp, nickname, message, altered_nick=altered)
