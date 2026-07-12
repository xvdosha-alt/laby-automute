from dataclasses import dataclass
import re

MC_NICK_RE = re.compile(r"^[A-Za-z0-9_]{3,16}$")
# Префиксы клана/консоли, которые парсер может принять за ник (HW, ALL, …)
SYSTEM_CHAT_PREFIXES = frozenset({
    "hw", "all", "system", "console", "server", "info", "chat",
})
INVALID_CHAT_NICKS = frozenset({"http", "https", "ftp", "www"})
_SPACED_DIGITS_RE = re.compile(r"^[\d\s]+$")


def is_spaced_ten_digit_message(text: str) -> bool:
    """Сообщение из пробелов и ровно 10 цифр (например номер телефона)."""
    stripped = (text or "").strip()
    if not stripped or not _SPACED_DIGITS_RE.match(stripped):
        return False
    return sum(ch.isdigit() for ch in stripped) == 10


def is_invalid_chat_nickname(nickname: str, text: str = "") -> bool:
    nick = (nickname or "").strip().lower()
    if not nick:
        return True
    if nick in INVALID_CHAT_NICKS:
        return True
    body = (text or "").strip()
    if nick in {"http", "https"} and body.startswith("//"):
        return True
    return False


def is_muteable_nickname(nickname: str) -> bool:
    nick = nickname.strip()
    if not nick or not MC_NICK_RE.fullmatch(nick):
        return False
    low = nick.lower()
    if low in SYSTEM_CHAT_PREFIXES or low in INVALID_CHAT_NICKS:
        return False
    return True


@dataclass(frozen=True)
class ChatMessage:
    timestamp: str
    nickname: str
    text: str
    altered_nick: bool = False

    def format_batch_line(self, index: int) -> str:
        return f"[{index}] {self.nickname}: {self.text}"


def is_altered_nick_message(message: ChatMessage) -> bool:
    nick = message.nickname.strip()
    if nick.lower() in SYSTEM_CHAT_PREFIXES:
        return True
    return message.altered_nick or nick.startswith("~")


def display_nickname(message: ChatMessage) -> str:
    nick = message.nickname.strip()
    if is_altered_nick_message(message) and not nick.startswith("~"):
        return f"~{nick}"
    return nick


def message_text_for_nickname(messages: list[ChatMessage], nickname: str) -> str:
    nick = nickname.strip().lower()
    if not nick:
        return ""
    for message in reversed(messages):
        if message.nickname.lower() == nick:
            return message.text
    return ""


@dataclass(frozen=True)
class ModClientRef:
    host: str
    port: int
    moderator_nick: str = ""

    @property
    def key(self) -> str:
        return f"{self.host}:{self.port}"

    @property
    def label(self) -> str:
        nick = self.moderator_nick.strip() or "?"
        return f"{nick}@{self.port}"


def format_client_label(client: ModClientRef | None, fallback_host: str = "127.0.0.1", fallback_port: int = 47823) -> str:
    if client is None:
        return f"{fallback_host}:{fallback_port}"
    return client.label


def resolve_moderation_client(settings, fallback: ModClientRef | None = None) -> ModClientRef | None:
    nick = getattr(settings, "client_nick", "").strip()
    if not nick:
        return fallback
    return ModClientRef(
        settings.mod_screenshot_host,
        settings.mod_screenshot_port,
        nick,
    )


def message_dedup_key(message: ChatMessage) -> str:
    return f"{message.timestamp}|{message.nickname.strip().lower()}|{message.text.strip()}"
