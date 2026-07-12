import re

_TRADE_RE = re.compile(
    r"\b(?:продам|куплю|продаю|all на|all,?\s+куп|all\s+/ah)\b",
    re.IGNORECASE,
)
_BEGGING_RE = re.compile(
    r"\b(?:"
    r"дай(?:те)?|скинь(?:те)?|можешь дать|можете дать|помогите|пофармить|"
    r"кто тепнет|жду рек|заливай рек"
    r")\b",
    re.IGNORECASE,
)
_PVP_LFG_RE = re.compile(
    r"\b(?:"
    r"тп кто|кто тп|кто пвп|кто варп|кто тим|all кто|ищу тим|ищу тима|"
    r"алл ищу|all ищу|по дс|по ds|в лс"
    r")\b",
    re.IGNORECASE,
)
_GAME_TALK_RE = re.compile(
    r"(?:"
    r"\b(?:з[45]|z[45])\b|"
    r"\b(?:незерка|защита\s*[45]|полный\s+тоесть|трезуб|зелье|фулл\s+хп)\b|"
    r"какой\s+смысл"
    r")",
    re.IGNORECASE,
)
_SHORT_CHAT_RE = re.compile(
    r"^(?:[.?!\-+qwezxcbn]|qq|bb|ez|xd|ok|да|нет|стой|а|e|xD|sps|friki|\+{1,3})$",
    re.IGNORECASE,
)


def looks_like_trade_ad(text: str) -> bool:
    lowered = (text or "").lower()
    if _TRADE_RE.search(lowered):
        return True
    if "/ah" in lowered or re.search(r"\bah\b", lowered):
        return True
    if "/cr" in lowered:
        return True
    if re.search(r"\ball\b", lowered) and re.search(
        r"(?:прод|куп|ставк|unic|уnick|рюkz|рюкз|инфин|тим|team)",
        lowered,
    ):
        return True
    return False


def looks_like_begging(text: str) -> bool:
    return bool(_BEGGING_RE.search(text or ""))


def looks_like_pvp_lfg(text: str) -> bool:
    return bool(_PVP_LFG_RE.search(text or ""))


def looks_like_game_talk(text: str) -> bool:
    return bool(_GAME_TALK_RE.search(text or ""))


def should_skip_ml_message(text: str) -> bool:
    stripped = (text or "").strip()
    if not stripped:
        return True
    if len(stripped) <= 3 and not re.search(r"[а-яё]{4,}", stripped, re.IGNORECASE):
        return True
    if _SHORT_CHAT_RE.fullmatch(stripped):
        return True
    if looks_like_trade_ad(stripped):
        return True
    if looks_like_begging(stripped):
        return True
    if looks_like_pvp_lfg(stripped):
        return True
    if looks_like_game_talk(stripped):
        return True
    return False


def batch_needs_ml(messages) -> bool:
    return any(not should_skip_ml_message(msg.text) for msg in messages)
