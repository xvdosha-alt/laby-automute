import re
from dataclasses import dataclass

from .chat_filters import looks_like_trade_ad
from .models import ChatMessage

@dataclass(frozen=True)
class FloodCheckResult:
    kind: str  # "instant" | "repeat"
    messages: list[ChatMessage]

_MC_NICK_RE = re.compile(r"^[A-Za-z0-9_]{3,16}$")
_VOWELS = frozenset("aeiouyаеёиоуыэюя")
_CYRILLIC_RE = re.compile(r"[а-яё]", re.IGNORECASE)
_LATIN_RE = re.compile(r"[a-z]", re.IGNORECASE)
_TOKEN_RE = re.compile(r"[a-zа-яё0-9]+", re.IGNORECASE)
_FLOOD_SHORT_PREFIX_MAX = 4
_INSULT_STEMS = (
    "ебанат", "еблан", "ебаньк", "ебанут", "ебан", "ёбан", "ебуч",
    "дебил", "даун", "дегенерат", "мудак", "мудил", "чмо", "мраз",
    "пидор", "пидр", "пидорас", "пидрил", "шлюх", "шалав", "бляд",
    "хуесос", "хуесосин",
    "хуйл", "гандон", "петух", "урод", "твар", "ублюд", "выбляд",
    "долбо", "конч", "нищ", "шавк", "шмар", "падл", "лох", "лошар",
    "тупорыл", "членос", "соси", "сосал", "фрик", "хамл", "додик",
    "гнида", "паскуд", "сволоч", "подонок", "олух", "балбес", "кретин",
    "выродок", "жиробас", "импотент", "чурбан", "говноед", "пизд",
)
_INSULT_EXACT = frozenset({
    "лох", "лошара", "идиот", "тупой", "тупица", "дурак", "баран",
    "овца", "осёл", "осел", "козёл", "козел", "ишак", "сыкун", "сыкло",
    "немощь", "стерва", "гнида", "даун", "чмо", "мразь",
    "дегенерат", "дебил", "мудак", "урод", "тварь", "петух", "гей",
})
_INSULT_MILD_RE = re.compile(
    r"(?:"
    r"\bя\s+в\s+ахуе\b|"
    r"\bебать\s+(?:коин|кайф|не\s+встать)\b|"
    r"^(?:че|чё)\s+нахуй[?!.]*$|"
    r"\bнахуй\s+ты\s+(?:приход|лива|лез|нуж)\w*\b|"
    r"^(?:otebiz|отъебись|отвали|завали|завались)$|"
    r"\b(?:или|и)\s+сука\s+\w+|"
    r"\bу\s+меня\s+сука\s+\w+|"
    r"\bсука\s+(?:продать|теперь|наконец|просто|уже|блин|блять|давай)\b"
    r")",
    re.IGNORECASE,
)
_INSULT_PHRASE_RE = re.compile(
    r"\b(?:"
    r"иди\s+нахуй|пош[её]л\s+нахуй|съеби\s+нахуй|нахуй\s+иди|"
    r"иди\s+нахер|завали\s+ебало|ебало\s+офф|нахуй\s+отсюда|"
    r"ты\s+ебан\w*|ты\s+ёбан\w*|"
    r"ты\s+сука\b|сука\s+ты\b|"
    r"заебал\w*"
    r")\b",
    re.IGNORECASE,
)
_SELF_INSULT_RE = re.compile(
    r"(?:"
    r"^бля+\s+я\s+"
    r"|\bя\s+(?:"
    r"еблан\w*|лошар\w*|дебил\w*|даун\w*|идиот\w*|"
    r"туп\w+|дурак\w*|мудак\w*|чмо|кретин\w*|"
    r"долбо\w*|имбецил\w*|лох\w*|"
    r"уёб\w*|уеб\w*|кринж\w*|"
    r"мраз\w*|урод\w*"
    r")\b"
    r")",
    re.IGNORECASE,
)
_RU_WORD_SUFFIXES = (
    "ирование", "ировать", "ировал", "ировала", "ирован", "ирована",
    "ительство", "тельство", "ичество", "ничество", "ействие",
    "ование", "ирование", "ировка", "ировки", "ствуйте", "ствие",
    "ение", "ения", "овать", "овала", "овал", "лены", "лена", "лен",
    "ный", "ная", "ное", "ные", "ость", "ства", "ский", "ская",
    "ция", "ции", "атор", "аторы", "ировка",
)
_EN_WORD_SUFFIXES = (
    "arianism", "establishment", "standing", "ations", "ation", "tion", "sion",
    "ment", "ness", "ings", "ing", "able", "ible", "ious", "eous", "ical",
    "ally", "ingly", "ture", "ucture", "ography", "alism", "ism", "ling",
    "ship", "hood", "ward", "wise", "less", "ful", "ive",
)
_TRIVIAL_AFTER_NICK = frozenset({
    "цена", "лс", "qq", "q", "tp", "all", "алл", "да", "нет", "ok", "ок",
    "pls", "пж", "плиз", "warp", "варп", "ah", "ах", "ez", "spec",
})


class HeuristicChecker:
    def __init__(self, flood_time_limit: int, known_nicks: frozenset[str] | None = None):
        self.flood_time_limit = flood_time_limit
        self._muted_flood_groups: dict[str, int] = {}
        self._known_nicks = {n.lower() for n in (known_nicks or ())}

    def update_known_nicks(self, nicks: frozenset[str]) -> None:
        self._known_nicks = {n.lower() for n in nicks}

    @staticmethod
    def parse_time_to_seconds(time_str: str) -> int:
        try:
            hours, minutes, seconds = (int(part) for part in time_str.split(":"))
            return hours * 3600 + minutes * 60 + seconds
        except Exception:
            return 0

    @staticmethod
    def time_diff_seconds(time_a: str, time_b: str) -> int:
        a = HeuristicChecker.parse_time_to_seconds(time_a)
        b = HeuristicChecker.parse_time_to_seconds(time_b)
        diff = abs(a - b)
        if diff > 12 * 3600:
            diff = 86400 - diff
        return diff

    def check_caps(self, message: str) -> bool:
        if not message or not message.strip():
            return False

        stripped = message.strip()
        tokens = stripped.split()
        if self._is_nick_mention_only(tokens):
            return False

        if self._is_nick_then_lowercase_message(tokens):
            return False

        if self._is_lowercase_with_nick_mention(tokens):
            return False

        letters = [c for c in message if c.isalpha()]
        if not letters:
            return False

        uppercase_ratio = sum(1 for c in letters if c.isupper()) / len(letters)
        if uppercase_ratio <= 0.5:
            return False

        return any(len(word) > 10 for word in tokens) or len(tokens) >= 2

    def _is_nick_mention_only(self, tokens: list[str]) -> bool:
        if not tokens:
            return True
        cleaned = [t.strip(".,!?;:") for t in tokens if t.strip(".,!?;:")]
        if not cleaned:
            return True
        for token in cleaned:
            low = token.lower()
            if low in self._known_nicks:
                continue
            if _MC_NICK_RE.match(token):
                continue
            if low in _TRIVIAL_AFTER_NICK:
                continue
            return False
        return True

    def _is_nick_then_lowercase_message(self, tokens: list[str]) -> bool:
        if len(tokens) < 2:
            return False
        first = tokens[0].strip(".,!?;:")
        first_low = first.lower()
        if first_low not in self._known_nicks and not _MC_NICK_RE.match(first):
            return False
        rest_letters = [c for c in " ".join(tokens[1:]) if c.isalpha()]
        if not rest_letters:
            return True
        upper_ratio = sum(1 for c in rest_letters if c.isupper()) / len(rest_letters)
        return upper_ratio <= 0.3

    def _is_lowercase_with_nick_mention(self, tokens: list[str]) -> bool:
        """Обычный текст + ник в капсе (напр. «ты слабый INNMORTALITY») — не 3.2."""
        if len(tokens) < 2:
            return False
        nick_tokens: list[str] = []
        other_tokens: list[str] = []
        for token in tokens:
            cleaned = token.strip(".,!?;:")
            if not cleaned:
                continue
            low = cleaned.lower()
            if low in self._known_nicks or _MC_NICK_RE.match(cleaned):
                nick_tokens.append(cleaned)
            else:
                other_tokens.append(cleaned)
        if not nick_tokens or not other_tokens:
            return False
        other_letters = [c for c in " ".join(other_tokens) if c.isalpha()]
        if not other_letters:
            return True
        upper_ratio = sum(1 for c in other_letters if c.isupper()) / len(other_letters)
        return upper_ratio <= 0.3

    @staticmethod
    def _check_repeat_chars(message: str) -> bool:
        if not message:
            return False
        return bool(re.compile(r"(.)\1{9,}").search(message))

    @staticmethod
    def _check_repeat_laugh(message: str) -> bool:
        if not message:
            return False
        lowered = message.lower()
        latin = re.compile(r"(ah|ax|ha|xa){10,}").search(lowered)
        if latin and len(latin.group()) >= 20:
            return True
        cyrillic = re.compile(r"(ха|ах){10,}").search(lowered)
        return bool(cyrillic and len(cyrillic.group()) >= 24)

    @staticmethod
    def _normalize_flood_text(text: str) -> str:
        lowered = text.lower().strip()
        lowered = lowered.replace("х", "x").replace("×", "x")
        return " ".join(lowered.split())

    @staticmethod
    def _normalize_ad_spam_text(text: str) -> str:
        lowered = text.lower().strip()
        if "/ah" not in lowered and "уник" not in lowered:
            return ""
        normalized = re.sub(r"\d+", "", lowered)
        normalized = re.sub(r"минут\w*", "мин", normalized)
        return " ".join(normalized.split())

    @staticmethod
    def _flood_texts_match(current: str, other: str) -> bool:
        current_norm = HeuristicChecker._normalize_flood_text(current)
        other_norm = HeuristicChecker._normalize_flood_text(other)
        if not current_norm or not other_norm:
            return False
        if current_norm == other_norm:
            return True
        current_ad = HeuristicChecker._normalize_ad_spam_text(current)
        other_ad = HeuristicChecker._normalize_ad_spam_text(other)
        if current_ad and current_ad == other_ad:
            return True
        if " " in current_norm or " " in other_norm:
            return False
        shorter, longer = (
            (current_norm, other_norm)
            if len(current_norm) <= len(other_norm)
            else (other_norm, current_norm)
        )
        if len(shorter) <= _FLOOD_SHORT_PREFIX_MAX and longer.startswith(shorter + " "):
            return True
        return False

    @staticmethod
    def _max_consonant_run(letters: list[str]) -> int:
        run = 0
        best = 0
        for char in letters:
            if char in _VOWELS:
                run = 0
            else:
                run += 1
                best = max(best, run)
        return best

    @staticmethod
    def _has_russian_word_shape(token: str) -> bool:
        low = token.lower()
        return any(
            low.endswith(suffix) and len(low) > len(suffix) + 2
            for suffix in _RU_WORD_SUFFIXES
        )

    @staticmethod
    def _has_english_word_shape(token: str) -> bool:
        low = token.lower()
        letters = [c for c in low if c.isalpha()]
        if not letters or not all(c.isascii() for c in letters):
            return False
        return any(
            low.endswith(suffix) and len(low) > len(suffix) + 3
            for suffix in _EN_WORD_SUFFIXES
        )

    @staticmethod
    def _looks_like_mc_nick_exempt(token: str, known_nicks: frozenset[str] | None = None) -> bool:
        low = token.lower()
        if known_nicks and low in known_nicks:
            return True
        if not re.fullmatch(r"[a-z0-9_]{3,16}", low):
            return False
        if len(low) < 12:
            return True
        if any(c.isdigit() for c in low) or "_" in low:
            return True
        if token != low and not token.isupper():
            return True
        letters = [c for c in low if c.isalpha()]
        if letters:
            vowel_ratio = sum(1 for c in letters if c in _VOWELS) / len(letters)
            if vowel_ratio >= 0.28:
                return True
        return False

    @staticmethod
    def _is_keyboard_row_walk(token: str) -> bool:
        letters = [c for c in token.lower() if c.isalpha()]
        if len(letters) < 8:
            return False
        low = "".join(letters)
        rows = (
            "qwertyuiop",
            "asdfghjkl",
            "zxcvbnm",
            "йцукенгшщзхъ",
            "фывапролджэ",
            "ячсмитьбю",
        )
        for row in rows:
            if all(char in row for char in low):
                doubled = row + row[::-1]
                if low in row or low in doubled:
                    return True
            for index in range(len(row) - 7):
                chunk = row[index : index + 8]
                if chunk in low or chunk[::-1] in low:
                    if len(letters) <= 12:
                        return True
        return False

    @staticmethod
    def _is_keyboard_mash(token: str) -> bool:
        if HeuristicChecker._is_keyboard_row_walk(token):
            return True
        letters = [c for c in token.lower() if c.isalpha()]
        if len(letters) < 12:
            return False
        vowel_ratio = sum(1 for c in letters if c in _VOWELS) / len(letters)
        low = "".join(letters)
        rows = (
            "qwertyuiop",
            "asdfghjkl",
            "zxcvbnm",
            "йцукенгшщзхъ",
            "фывапролджэ",
            "ячсмитьбю",
        )
        for row in rows:
            for index in range(len(row) - 7):
                chunk = row[index : index + 8]
                if chunk in low or chunk[::-1] in low:
                    return True
        latin_only = all(c.isascii() for c in letters)
        if latin_only and vowel_ratio <= 0.20:
            return True
        cyrillic_only = all(_CYRILLIC_RE.match(c) for c in letters)
        if cyrillic_only and vowel_ratio <= 0.25 and len(letters) >= 14:
            return True
        return False

    @staticmethod
    def _is_mixed_nick_token(token: str) -> bool:
        if not (_CYRILLIC_RE.search(token) and _LATIN_RE.search(token)):
            return False
        latin_parts = re.findall(r"[a-z][a-z0-9_]{2,15}", token, re.IGNORECASE)
        return bool(latin_parts) and all(
            re.fullmatch(r"[a-z0-9_]{3,16}", part, re.IGNORECASE) for part in latin_parts
        )

    @staticmethod
    def _is_gibberish_token(token: str, known_nicks: frozenset[str] | None = None) -> bool:
        if known_nicks and token.lower() in known_nicks:
            return False
        if HeuristicChecker._is_mixed_nick_token(token):
            return False
        if HeuristicChecker._is_keyboard_row_walk(token):
            return True
        letters = [c for c in token.lower() if c.isalpha()]
        if len(letters) < 12:
            return False
        if HeuristicChecker._is_keyboard_mash(token):
            return True
        if HeuristicChecker._looks_like_mc_nick_exempt(token, known_nicks):
            return False
        if HeuristicChecker._has_russian_word_shape(token):
            return False
        if HeuristicChecker._has_english_word_shape(token):
            return False

        vowel_count = sum(1 for c in letters if c in _VOWELS)
        vowel_ratio = vowel_count / len(letters)
        unique_ratio = len(set(letters)) / len(letters)
        consonant_run = HeuristicChecker._max_consonant_run(letters)
        cyrillic_only = all(_CYRILLIC_RE.match(c) for c in letters)

        if cyrillic_only and len(letters) >= 14 and consonant_run <= 2:
            if vowel_ratio <= 0.55 and unique_ratio <= 0.55:
                return True

        if cyrillic_only and consonant_run < 5 and vowel_ratio >= 0.28:
            return False
        latin_only = all(c.isascii() for c in letters)
        if latin_only and consonant_run <= 3 and vowel_ratio >= 0.30:
            return False
        if vowel_ratio > 0.42:
            return False
        if unique_ratio < 0.35:
            return False
        if consonant_run < 3 and vowel_ratio >= 0.30:
            return False
        return True

    @staticmethod
    def has_gibberish_spam(
        message: str,
        known_nicks: frozenset[str] | None = None,
    ) -> bool:
        if not message:
            return False
        nick_set = {n.lower() for n in known_nicks} if known_nicks else None
        for token in _TOKEN_RE.findall(message):
            if HeuristicChecker._is_gibberish_token(token, nick_set):
                return True
        return False

    def _check_gibberish_spam(self, message: str) -> bool:
        return HeuristicChecker.has_gibberish_spam(message, self._known_nicks)

    def check_flood(
        self,
        recent_messages: list[ChatMessage],
        nickname: str,
        message: str,
        current_time_str: str,
    ) -> FloodCheckResult | None:
        current = ChatMessage(current_time_str, nickname, message)
        if (
            self._check_repeat_chars(message)
            or self._check_repeat_laugh(message)
            or self._check_gibberish_spam(message)
        ):
            return FloodCheckResult("instant", [current])

        if len(recent_messages) < 2:
            return None

        current_time_seconds = self.parse_time_to_seconds(current_time_str)
        same_nick_messages = [
            msg
            for msg in recent_messages
            if msg.nickname == nickname
        ]
        if len(same_nick_messages) < 2:
            return None

        if not message.strip():
            return None

        matches: list[ChatMessage] = []
        for other in same_nick_messages:
            if not self._flood_texts_match(message, other.text):
                continue
            time_diff = self.time_diff_seconds(current_time_str, other.timestamp)
            if time_diff <= self.flood_time_limit:
                matches.append(other)

        if len(matches) < 2:
            return None

        group_key = (
            f"{nickname}_{min(self.parse_time_to_seconds(msg.timestamp) for msg in matches)}"
        )
        if group_key in self._muted_flood_groups:
            return None

        self._muted_flood_groups[group_key] = current_time_seconds
        related = sorted(
            matches + [current],
            key=lambda msg: self.parse_time_to_seconds(msg.timestamp),
        )
        return FloodCheckResult("repeat", related)

    def cleanup_expired_groups(self, current_time_str: str) -> None:
        current_time_seconds = self.parse_time_to_seconds(current_time_str)
        expired = [
            key
            for key, value in self._muted_flood_groups.items()
            if self._seconds_diff_raw(current_time_seconds, value) > self.flood_time_limit * 2
        ]
        for key in expired:
            del self._muted_flood_groups[key]

    @staticmethod
    def _seconds_diff_raw(a: int, b: int) -> int:
        diff = abs(a - b)
        if diff > 12 * 3600:
            diff = 86400 - diff
        return diff

    def get_caps_mute(self, nickname: str) -> str:
        return f"/tempmute {nickname} 1h 3.2 link -s"

    def get_flood_mute(self, nickname: str) -> str:
        return f"/tempmute {nickname} 1h 3.3 link -s"

    def get_insult_mute(self, nickname: str) -> str:
        return f"/tempmute {nickname} 3h 3.4 link -s"

    @staticmethod
    def is_self_directed_insult(message: str) -> bool:
        if not message or not message.strip():
            return False
        return bool(_SELF_INSULT_RE.search(message.lower().strip()))

    @staticmethod
    def has_explicit_insult(message: str) -> bool:
        if not message or not message.strip():
            return False
        lowered = message.lower().strip()
        if HeuristicChecker.is_self_directed_insult(message):
            return False
        if _INSULT_MILD_RE.search(lowered):
            return False
        if _INSULT_PHRASE_RE.search(lowered):
            return True
        if re.search(r"(?:^|\s|[,.!?])заebал\w*", lowered):
            return True
        for token in _TOKEN_RE.findall(message):
            low = token.lower()
            if low in _INSULT_EXACT:
                return True
            for stem in _INSULT_STEMS:
                if len(stem) >= 5 and low.startswith(stem):
                    return True
                if len(stem) < 5 and low == stem:
                    return True
        return False
