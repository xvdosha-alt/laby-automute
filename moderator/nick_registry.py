import os
import re

_MC_NICK_RE = re.compile(r"^[A-Za-z0-9_]{3,16}$")


class NickRegistry:
    def __init__(self, base_dir: str, extra: frozenset[str] | None = None):
        self._path = os.path.join(base_dir, "player_nicks.txt")
        self._tab_players: set[str] = set()
        self._heuristic_nicks: set[str] = set()
        self._staff = {n.lower() for n in (extra or ()) if n.strip()}
        self._load_file()

    def _load_file(self) -> None:
        if not os.path.isfile(self._path):
            return
        with open(self._path, encoding="utf-8") as f:
            for line in f:
                nick = line.strip()
                if nick and not nick.startswith("#"):
                    self._tab_players.add(nick.lower())

    def _append_file(self, nick_lower: str) -> None:
        try:
            with open(self._path, "a", encoding="utf-8") as f:
                f.write(f"{nick_lower}\n")
        except OSError:
            pass

    def _add_tab_player(self, nick: str) -> None:
        cleaned = nick.strip()
        if not cleaned:
            return
        key = cleaned.lower()
        if key in self._tab_players:
            return
        self._tab_players.add(key)
        self._append_file(key)

    def register_from_message(self, nickname: str, text: str) -> None:
        for token in text.split():
            cleaned = token.strip(".,!?;:")
            if cleaned and _MC_NICK_RE.match(cleaned):
                key = cleaned.lower()
                if key not in self._heuristic_nicks:
                    self._heuristic_nicks.add(key)

    def add_staff(self, nick: str) -> bool:
        cleaned = nick.strip()
        if not cleaned:
            return False
        key = cleaned.lower()
        if key in self._staff:
            return False
        self._staff.add(key)
        return True

    def merge_players(self, players: list[str]) -> int:
        before = len(self._tab_players)
        for nick in players:
            self._add_tab_player(nick)
        return len(self._tab_players) - before

    def is_tab_player(self, nick: str) -> bool:
        return nick.strip().lower() in self._tab_players

    def as_frozenset(self) -> frozenset[str]:
        return frozenset(self._tab_players | self._heuristic_nicks | self._staff)

    def __len__(self) -> int:
        return len(self._tab_players)
