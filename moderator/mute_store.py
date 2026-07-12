import json
import os
import shutil
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from threading import Lock

from .config import Settings


def _migrate_legacy_data(legacy_dir: str, target_dir: str) -> None:
    if legacy_dir == target_dir or not os.path.isdir(legacy_dir):
        return
    legacy_index = os.path.join(legacy_dir, "mutes.json")
    target_index = os.path.join(target_dir, "mutes.json")
    if os.path.isfile(target_index) or not os.path.isfile(legacy_index):
        return
    os.makedirs(target_dir, exist_ok=True)
    try:
        shutil.copy2(legacy_index, target_index)
        legacy_photos = os.path.join(legacy_dir, "mutes")
        target_photos = os.path.join(target_dir, "mutes")
        if os.path.isdir(legacy_photos):
            os.makedirs(target_photos, exist_ok=True)
            for name in os.listdir(legacy_photos):
                src = os.path.join(legacy_photos, name)
                dst = os.path.join(target_photos, name)
                if os.path.isfile(src) and not os.path.isfile(dst):
                    shutil.copy2(src, dst)
        legacy_cursors = os.path.join(legacy_dir, "chat_cursors.json")
        target_cursors = os.path.join(target_dir, "chat_cursors.json")
        if os.path.isfile(legacy_cursors) and not os.path.isfile(target_cursors):
            shutil.copy2(legacy_cursors, target_cursors)
        legacy_rules = os.path.join(legacy_dir, "rules.json")
        target_rules = os.path.join(target_dir, "rules.json")
        if os.path.isfile(legacy_rules) and not os.path.isfile(target_rules):
            shutil.copy2(legacy_rules, target_rules)
    except OSError:
        pass


@dataclass
class MuteRecord:
    id: str
    timestamp: str
    nickname: str
    duration: str
    reason: str
    command: str
    photo_file: str
    link: str
    source: str
    message: str = ""
    status: str = "executed"
    note: str = ""
    mod_nick: str = ""
    mod_port: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


class MuteStore:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.data_dir = settings.data_dir
        legacy_dir = os.path.join(settings.base_dir, "data")
        _migrate_legacy_data(legacy_dir, self.data_dir)
        self.photos_dir = os.path.join(self.data_dir, "mutes")
        self.index_path = os.path.join(self.data_dir, "mutes.json")
        self._lock = Lock()
        os.makedirs(self.photos_dir, exist_ok=True)
        if not os.path.isfile(self.index_path):
            self._write([])

    def _read(self) -> list[dict]:
        try:
            with open(self.index_path, encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def _write(self, items: list[dict]) -> None:
        with open(self.index_path, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)

    @staticmethod
    def parse_command(command: str) -> tuple[str, str, str, str]:
        parts = command.split()
        nickname = parts[1] if len(parts) > 1 else ""
        duration = parts[2] if len(parts) > 2 else ""
        reason = parts[3] if len(parts) > 3 else ""
        link = ""
        for part in parts:
            if part.startswith("http"):
                link = part
                break
        return nickname, duration, reason, link

    def record(
        self,
        command: str,
        photo_path: str,
        source: str = "auto",
        message: str = "",
        status: str = "executed",
        note: str = "",
        mod_nick: str = "",
        mod_port: int = 0,
        link: str = "",
    ) -> MuteRecord | None:
        parsed_nick, duration, reason, parsed_link = self.parse_command(command)
        return self.record_attempt(
            command=command,
            nickname=parsed_nick,
            duration=duration,
            reason=reason,
            photo_path=photo_path,
            link=link or parsed_link,
            source=source,
            message=message,
            status=status,
            note=note,
            mod_nick=mod_nick,
            mod_port=mod_port,
        )

    def record_attempt(
        self,
        *,
        command: str = "",
        nickname: str = "",
        duration: str = "",
        reason: str = "",
        photo_path: str | None = None,
        link: str = "",
        source: str = "auto",
        message: str = "",
        status: str = "skipped",
        note: str = "",
        mod_nick: str = "",
        mod_port: int = 0,
    ) -> MuteRecord | None:
        mute_id = uuid.uuid4().hex[:12]
        archive_name = ""

        if command and (not nickname or not duration or not reason):
            parsed_nick, parsed_duration, parsed_reason, parsed_link = self.parse_command(
                command
            )
            nickname = nickname or parsed_nick
            duration = duration or parsed_duration
            reason = reason or parsed_reason
            link = link or parsed_link

        if photo_path and os.path.isfile(photo_path):
            ext = os.path.splitext(photo_path)[1].lower() or ".jpg"
            archive_name = f"{mute_id}{ext}"
            archive_path = os.path.join(self.photos_dir, archive_name)
        else:
            archive_path = ""

        record = MuteRecord(
            id=mute_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            nickname=(nickname or "").strip(),
            duration=(duration or "").strip(),
            reason=(reason or "").strip(),
            command=(command or "").strip(),
            photo_file=archive_name,
            link=(link or "").strip(),
            source=source,
            message=(message or "").strip(),
            status=status,
            note=(note or "").strip(),
            mod_nick=(mod_nick or "").strip(),
            mod_port=int(mod_port or 0),
        )

        with self._lock:
            try:
                if archive_path:
                    shutil.move(photo_path, archive_path)
                items = self._read()
                items.insert(0, record.to_dict())
                self._write(items)
                return record
            except Exception:
                return None

    def list_mutes(self) -> list[dict]:
        with self._lock:
            return self._read()

    def get_mute(self, mute_id: str) -> dict | None:
        for item in self.list_mutes():
            if item.get("id") == mute_id:
                return item
        return None

    def photo_path(self, mute_id: str) -> str | None:
        item = self.get_mute(mute_id)
        if not item:
            return None
        path = os.path.join(self.photos_dir, item.get("photo_file", ""))
        return path if os.path.isfile(path) else None

    def stats(self) -> dict:
        items = self.list_mutes()
        by_reason: dict[str, int] = {}
        by_day: dict[str, int] = {}
        by_source: dict[str, int] = {}
        by_nick: dict[str, int] = {}
        all_nicks_set: set[str] = set()

        for item in items:
            reason = item.get("reason") or "unknown"
            by_reason[reason] = by_reason.get(reason, 0) + 1
            nick = (item.get("nickname") or "").strip()
            if nick:
                by_nick[nick] = by_nick.get(nick, 0) + 1
                all_nicks_set.add(nick)
            source = item.get("source") or "auto"
            by_source[source] = by_source.get(source, 0) + 1
            day = (item.get("timestamp") or "")[:10]
            if day:
                by_day[day] = by_day.get(day, 0) + 1

        return {
            "total": len(items),
            "by_reason": by_reason,
            "by_day": dict(sorted(by_day.items())),
            "by_source": by_source,
            "all_nicks": sorted(all_nicks_set, key=str.lower),
        }
