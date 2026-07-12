from __future__ import annotations

import re
from functools import lru_cache

from .deps import OCR_AVAILABLE

_OCR_ENGINE = None


@lru_cache(maxsize=1)
def _get_engine():
    if not OCR_AVAILABLE:
        return None
    from rapidocr_onnxruntime import RapidOCR

    return RapidOCR()


def required_nick_hits(
    rule_id: str,
    *,
    flood_kind: str | None = None,
    message_count: int = 0,
) -> int:
    if (rule_id or "").strip() != "3.3":
        return 1
    if flood_kind == "repeat" and message_count >= 3:
        # Эвристика уже подтвердила 3 сообщения в буфере; на скрине часто 2.
        return 2
    return 1


def extract_text(image_path: str) -> str:
    engine = _get_engine()
    if engine is None or not image_path:
        return ""
    try:
        result, _ = engine(image_path)
    except Exception:
        return ""
    if not result:
        return ""
    lines: list[str] = []
    for item in result:
        if not item or len(item) < 2:
            continue
        text = str(item[1] or "").strip()
        if text:
            lines.append(text)
    return "\n".join(lines)


def count_nick_occurrences(text: str, nickname: str) -> int:
    nick = (nickname or "").strip()
    if not nick or not text:
        return 0

    escaped = re.escape(nick)
    chat_line = re.compile(
        rf"(?:^|\s)(~?{escaped})(?:\s*[:»])",
        re.IGNORECASE | re.MULTILINE,
    )
    chat_hits = len(chat_line.findall(text))
    word_hits = len(re.findall(rf"(?i)\b{escaped}\b", text))

    fuzzy_hits = 0
    nick_l = nick.lower()
    nick_compact = re.sub(r"[^a-z0-9_]", "", nick_l)
    for line in text.split("\n"):
        line_l = line.lower()
        line_compact = re.sub(r"[^a-z0-9_]", "", line_l)
        if nick_l in line_l or (nick_compact and nick_compact in line_compact):
            fuzzy_hits += 1

    return max(chat_hits, word_hits, fuzzy_hits)


def verify_nick_on_screenshot(
    image_path: str,
    nickname: str,
    *,
    rule_id: str = "",
    flood_kind: str | None = None,
    message_count: int = 0,
    min_hits: int | None = None,
) -> tuple[bool, int, int, str]:
    """Return (ok, hits, required, ocr_text)."""
    required = (
        min_hits
        if min_hits is not None
        else required_nick_hits(
            rule_id,
            flood_kind=flood_kind,
            message_count=message_count,
        )
    )
    target = (nickname or "").strip()
    if not target:
        return False, 0, required, ""

    text = extract_text(image_path)
    if not text:
        return False, 0, required, text

    hits = count_nick_occurrences(text, target)
    return hits >= required, hits, required, text
