import json
import os
import re
import threading

RULE_DEFINITIONS: list[dict] = [
    {
        "id": "2.3",
        "title": "Взлом аккаунта",
        "source": "manual",
        "duration": "24h",
        "automute": False,
    },
    {"id": "3.2", "title": "КАПС", "source": "heuristic", "duration": "1h"},
    {"id": "3.3", "title": "Флуд", "source": "heuristic", "duration": "1h"},
    {"id": "3.4", "title": "Оскорбления", "source": "both", "duration": "3h"},
    {"id": "3.6", "title": "Оскорбление родных", "source": "ml", "duration": "7h"},
    {"id": "3.7", "title": "Провокация чат-игры", "source": "ml", "duration": "3h"},
    {"id": "3.8", "title": "Сексуальный контент", "source": "ml", "duration": "2h"},
    {"id": "3.9", "title": "Ненависть / пропаганда", "source": "ml", "duration": "9h"},
    {"id": "3.10", "title": "Угрозы наказания", "source": "ml", "duration": "5h"},
    {"id": "3.12", "title": "Вмешательство в наказания", "source": "ml", "duration": "4h (вручную)"},
]

_RULE_ID_RE = re.compile(r"^\d+\.\d+$")
_DURATION_TOKEN_RE = re.compile(r"^(\d+)\s*(h|m|d|ч|мин)$", re.IGNORECASE)
KNOWN_RULE_IDS = frozenset(rule["id"] for rule in RULE_DEFINITIONS)
ML_ALLOWED_RULE_IDS = frozenset({"3.4", "3.6", "3.7", "3.8", "3.9", "3.10"})
RULE_EXPECTED_DURATION: dict[str, str] = {}
for _rule in RULE_DEFINITIONS:
    _match = re.search(r"(\d+[hmd])", _rule["duration"], re.IGNORECASE)
    if _match:
        RULE_EXPECTED_DURATION[_rule["id"]] = _match.group(1).lower()


class RulesConfig:
    def __init__(self, data_dir: str):
        self.path = os.path.join(data_dir, "rules.json")
        self._lock = threading.Lock()
        os.makedirs(data_dir, exist_ok=True)
        self._state: dict[str, dict] = {}
        self._load()

    @staticmethod
    def _default_state() -> dict[str, dict]:
        return {
            rule["id"]: {"automute": rule.get("automute", True)}
            for rule in RULE_DEFINITIONS
        }

    def _load(self) -> None:
        with self._lock:
            if os.path.isfile(self.path):
                try:
                    with open(self.path, encoding="utf-8") as f:
                        data = json.load(f)
                    if isinstance(data, dict) and isinstance(data.get("rules"), dict):
                        self._state = data["rules"]
                    elif isinstance(data, dict):
                        self._state = data
                    else:
                        self._state = self._default_state()
                except Exception:
                    self._state = self._default_state()
            else:
                self._state = self._default_state()
                self._save_unlocked()
            for rule in RULE_DEFINITIONS:
                if rule["id"] not in self._state:
                    self._state[rule["id"]] = {
                        "automute": rule.get("automute", True)
                    }

    def _save_unlocked(self) -> None:
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump({"rules": self._state}, f, ensure_ascii=False, indent=2)

    @staticmethod
    def extract_rule_id(value: str) -> str:
        for part in reversed((value or "").strip().split()):
            if _RULE_ID_RE.match(part):
                return part
        return ""

    @staticmethod
    def normalize_duration(token: str) -> str | None:
        match = _DURATION_TOKEN_RE.match((token or "").strip())
        if not match:
            return None
        amount, unit = match.group(1), match.group(2).lower()
        if unit == "ч":
            unit = "h"
        elif unit == "мин":
            unit = "m"
        return f"{amount}{unit}"

    @staticmethod
    def duration_to_minutes(token: str) -> int | None:
        normalized = RulesConfig.normalize_duration(token)
        if not normalized:
            return None
        match = re.match(r"^(\d+)([hmd])$", normalized)
        if not match:
            return None
        amount = int(match.group(1))
        unit = match.group(2)
        if unit == "h":
            return amount * 60
        if unit == "m":
            return amount
        if unit == "d":
            return amount * 24 * 60
        return None

    @staticmethod
    def expected_duration(rule_id: str) -> str | None:
        base = RulesConfig.extract_rule_id(rule_id)
        if not base:
            return None
        return RULE_EXPECTED_DURATION.get(base)

    @staticmethod
    def duration_matches_rule(duration: str, rule_id: str) -> bool:
        expected = RulesConfig.expected_duration(rule_id)
        if not expected:
            return True
        got_minutes = RulesConfig.duration_to_minutes(duration)
        expected_minutes = RulesConfig.duration_to_minutes(expected)
        if got_minutes is None or expected_minutes is None:
            return False
        return got_minutes == expected_minutes

    @staticmethod
    def is_known_rule(rule_id: str) -> bool:
        base = RulesConfig.extract_rule_id(rule_id)
        return bool(base and base in KNOWN_RULE_IDS)

    def is_automute_enabled(self, rule_id: str) -> bool:
        base = self.extract_rule_id(rule_id)
        if not base or base not in KNOWN_RULE_IDS:
            return False
        with self._lock:
            entry = self._state.get(base, {})
            return bool(entry.get("automute", True))

    def list_rules(self) -> list[dict]:
        with self._lock:
            return [
                {
                    **rule,
                    "automute": bool(
                        self._state.get(rule["id"], {}).get("automute", True)
                    ),
                }
                for rule in RULE_DEFINITIONS
            ]

    def set_automute(self, rule_id: str, enabled: bool) -> bool:
        if rule_id not in {rule["id"] for rule in RULE_DEFINITIONS}:
            return False
        with self._lock:
            self._state[rule_id] = {"automute": enabled}
            self._save_unlocked()
        return True
