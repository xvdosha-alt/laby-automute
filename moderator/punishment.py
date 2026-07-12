import os
import threading
import time
from collections.abc import Callable

from .annotator import PhotoAnnotator
from .chat_ocr import verify_nick_on_screenshot
from .config import Settings
from .console import Console
from .mod_client import ModBridgeError, get_client_nick, say_as_nick
from .models import ChatMessage, ModClientRef, format_client_label, is_muteable_nickname, resolve_moderation_client
from .mute_store import MuteStore
from .rules_config import RulesConfig
from .screenshot import ScreenshotService
from .telegram import TelegramNotifier
from .uploader import ImageUploader


class PunishmentExecutor:
    def __init__(
        self,
        settings: Settings,
        console: Console,
        screenshot: ScreenshotService,
        uploader: ImageUploader,
        telegram: TelegramNotifier,
        mute_store: MuteStore | None = None,
        moderation_enabled: Callable[[], bool] | None = None,
    ):
        self.settings = settings
        self.console = console
        self.screenshot = screenshot
        self.uploader = uploader
        self.telegram = telegram
        self.mute_store = mute_store
        self._moderation_enabled = moderation_enabled
        self.annotator = PhotoAnnotator(settings, console)
        self._nick_cache: dict[str, str] = {}
        self._send_lock = threading.Lock()
        self._mute_cooldown: dict[str, float] = {}

    @staticmethod
    def attach_screenshot_link(command: str, link: str) -> str:
        if " link" in command:
            return command.replace(" link", f" {link}", 1)
        command = command.rstrip()
        if command.endswith("-s"):
            return f"{command[:-2].rstrip()} {link} -s"
        return f"{command} {link} -s"

    def _auto_punishments_allowed(self) -> bool:
        if self._moderation_enabled is None:
            return True
        return bool(self._moderation_enabled())

    def record_violation(
        self,
        command: str,
        nickname: str | None,
        *,
        status: str,
        note: str = "",
        photo_path: str | None = None,
        highlight_messages: list[ChatMessage] | None = None,
        source: str = "auto",
        client: ModClientRef | None = None,
        message_text: str | None = None,
        link: str = "",
    ) -> bool:
        if not self.mute_store:
            if photo_path and os.path.isfile(photo_path):
                try:
                    os.remove(photo_path)
                except OSError:
                    pass
            return False

        detect_client = client
        mod_client = resolve_moderation_client(self.settings, detect_client)
        screenshot_host, screenshot_port = self._resolve_endpoint(detect_client)
        host, port = self._resolve_endpoint(mod_client)
        target = (nickname or "").strip()
        mod_nick = self._resolve_client_nick(mod_client)

        if photo_path is None:
            photo_path = self.screenshot.capture(
                host=screenshot_host,
                port=screenshot_port,
            )

        if photo_path and highlight_messages:
            self.annotator.highlight(photo_path, highlight_messages, focus_nick=nickname)

        stored_message = (message_text or "").strip()
        if not stored_message and highlight_messages and target:
            for item in reversed(highlight_messages):
                if item.nickname.lower() == target.lower():
                    stored_message = item.text
                    break

        record = self.mute_store.record_attempt(
            command=command,
            photo_path=photo_path,
            source=source,
            message=stored_message,
            status=status,
            note=note,
            mod_nick=mod_nick,
            mod_port=port,
            link=link,
        )
        return record is not None

    def execute(
        self,
        command: str,
        nickname: str | None,
        photo_path: str | None = None,
        link: str | None = None,
        highlight_messages: list[ChatMessage] | None = None,
        source: str = "auto",
        client: ModClientRef | None = None,
        message_text: str | None = None,
        flood_kind: str | None = None,
    ) -> bool:
        if not self._auto_punishments_allowed():
            self.console.print(
                f"[модерация стоп] {command} — автомут не отправлен",
                self.console.yellow,
            )
            self.record_violation(
                command,
                nickname,
                status="paused",
                note="модерация на паузе",
                photo_path=photo_path,
                highlight_messages=highlight_messages,
                source=source,
                client=client,
                message_text=message_text,
            )
            return False

        detect_client = client
        mod_client = resolve_moderation_client(self.settings, detect_client)
        screenshot_host, screenshot_port = self._resolve_endpoint(detect_client)
        host, port = self._resolve_endpoint(mod_client)
        label = format_client_label(
            mod_client,
            self.settings.mod_screenshot_host,
            self.settings.mod_screenshot_port,
        )
        target = (nickname or "").strip()
        mod_nick = self._resolve_client_nick(mod_client)
        rule_id = RulesConfig.extract_rule_id(command)

        if target and mod_nick and target.lower() == mod_nick.lower():
            self.console.print(
                f"[{label}] [САМОМУТ] {command} — детект есть, в игру не отправлен",
                self.console.yellow,
            )
            self.record_violation(
                command,
                nickname,
                status="skipped",
                note="самому себе",
                photo_path=photo_path,
                highlight_messages=highlight_messages,
                source=source,
                client=client,
                message_text=message_text,
            )
            return False

        if target and not is_muteable_nickname(target):
            self.console.print(
                f"[{label}] [ПРОПУСК] {command} — «{target}» не игровой ник",
                self.console.yellow,
            )
            self.record_violation(
                command,
                nickname,
                status="skipped",
                note="не игровой ник",
                photo_path=photo_path,
                highlight_messages=highlight_messages,
                source=source,
                client=client,
                message_text=message_text,
            )
            return False

        if target and self.is_staff(target, mod_client):
            self.console.print(
                f"[{label}] [СТАФФ] {command} — детект есть, в игру не отправлен",
                self.console.yellow,
            )
            self.record_violation(
                command,
                nickname,
                status="skipped",
                note="стафф",
                photo_path=photo_path,
                highlight_messages=highlight_messages,
                source=source,
                client=client,
                message_text=message_text,
            )
            return False

        if target and self._on_mute_cooldown(target):
            self.console.print(
                f"[{label}] [КУЛДАУН] {command} — недавно мутили {target}, пропуск",
                self.console.yellow,
            )
            self.record_violation(
                command,
                nickname,
                status="skipped",
                note="кулдаун",
                photo_path=photo_path,
                highlight_messages=highlight_messages,
                source=source,
                client=client,
                message_text=message_text,
            )
            return False

        if photo_path is None:
            photo_path = self.screenshot.capture(
                host=screenshot_host,
                port=screenshot_port,
            )

        if not photo_path:
            self.console.print(
                f"[{label}] [МУТ ОТМЕНЁН] Не удалось создать скриншот",
                self.console.red,
            )
            self.record_violation(
                command,
                nickname,
                status="rejected",
                note="нет скриншота",
                photo_path=None,
                highlight_messages=highlight_messages,
                source=source,
                client=client,
                message_text=message_text,
            )
            return False

        if highlight_messages:
            self.annotator.highlight(photo_path, highlight_messages, focus_nick=nickname)

        if self.settings.debug_upload:
            self.console.print(f"[DEBUG] Скриншот создан: {photo_path}", self.console.green)

        if target and self.settings.ocr_nick_verify:
            msg_count = len(highlight_messages or [])
            ok, hits, required, _ = verify_nick_on_screenshot(
                photo_path,
                target,
                rule_id=rule_id,
                flood_kind=flood_kind,
                message_count=msg_count,
            )
            if not ok:
                note = f"OCR: ник «{target}» {hits}/{required}"
                self.console.print(
                    f"[{label}] [МУТ ОТМЕНЁН] {note}",
                    self.console.red,
                )
                self.record_violation(
                    command,
                    nickname,
                    status="rejected",
                    note=note,
                    photo_path=photo_path,
                    highlight_messages=highlight_messages,
                    source=source,
                    client=client,
                    message_text=message_text,
                )
                return False

        if link is None:
            link = self.uploader.upload(photo_path, nickname)
        if not link:
            self.console.print(
                f"[{label}] [МУТ ОТМЕНЁН] Не удалось загрузить скриншот",
                self.console.red,
            )
            self.record_violation(
                command,
                nickname,
                status="rejected",
                note="ошибка загрузки скриншота",
                photo_path=photo_path,
                highlight_messages=highlight_messages,
                source=source,
                client=client,
                message_text=message_text,
            )
            return False

        final_command = self.attach_screenshot_link(command, link)
        if not self._send_command(final_command, mod_client):
            self.console.print(
                f"[{label}] [МУТ ОТМЕНЁН] Не удалось отправить команду через аддон",
                self.console.red,
            )
            self.record_violation(
                command,
                nickname,
                status="rejected",
                note="команда не отправлена",
                photo_path=photo_path,
                highlight_messages=highlight_messages,
                source=source,
                client=client,
                message_text=message_text,
                link=link,
            )
            return False

        self.console.print(f"[{label}] {final_command}", self.console.red)
        if target:
            self._mute_cooldown[target.lower()] = time.monotonic()
        if self.mute_store:
            stored_message = (message_text or "").strip()
            if not stored_message and highlight_messages and target:
                for item in reversed(highlight_messages):
                    if item.nickname.lower() == target.lower():
                        stored_message = item.text
                        break
            self.mute_store.record(
                final_command,
                photo_path,
                source=source,
                message=stored_message,
                mod_nick=mod_nick,
                mod_port=port,
            )
        return True

    def record_suggestion(
        self,
        command: str,
        nickname: str | None,
        photo_path: str | None = None,
        highlight_messages: list[ChatMessage] | None = None,
        source: str = "ml",
        client: ModClientRef | None = None,
        message_text: str | None = None,
    ) -> bool:
        if not self._auto_punishments_allowed():
            self.console.print(
                f"[модерация стоп] {command} — предложение не сохранено",
                self.console.yellow,
            )
            return False

        detect_client = client
        mod_client = resolve_moderation_client(self.settings, detect_client)
        screenshot_host, screenshot_port = self._resolve_endpoint(detect_client)
        label = format_client_label(
            mod_client,
            self.settings.mod_screenshot_host,
            self.settings.mod_screenshot_port,
        )
        target = (nickname or "").strip()
        mod_nick = self._resolve_client_nick(mod_client)
        host, port = self._resolve_endpoint(mod_client)
        rule_id = RulesConfig.extract_rule_id(command)

        if photo_path is None:
            photo_path = self.screenshot.capture(
                host=screenshot_host,
                port=screenshot_port,
            )

        if not photo_path:
            self.console.print(
                f"[{label}] [РУЧНОЙ] Не удалось создать скриншот для {command}",
                self.console.red,
            )
            return False

        if highlight_messages:
            self.annotator.highlight(photo_path, highlight_messages, focus_nick=nickname)

        if target and self.settings.ocr_nick_verify:
            msg_count = len(highlight_messages or [])
            ok, hits, required, _ = verify_nick_on_screenshot(
                photo_path,
                target,
                rule_id=rule_id,
                message_count=msg_count,
            )
            if not ok:
                note = f"OCR: ник «{target}» {hits}/{required}"
                self.console.print(
                    f"[{label}] [РУЧНОЙ ОТМЕНЁН] {note}",
                    self.console.red,
                )
                self.record_violation(
                    command,
                    nickname,
                    status="rejected",
                    note=note,
                    photo_path=photo_path,
                    highlight_messages=highlight_messages,
                    source=source,
                    client=client,
                    message_text=message_text,
                )
                return False

        link = self.uploader.upload(photo_path, nickname)
        if not link:
            self.console.print(
                f"[{label}] [РУЧНОЙ] Не удалось загрузить скриншот",
                self.console.red,
            )
            return False

        final_command = self.attach_screenshot_link(command, link)
        self.console.print(
            f"[{label}] [РУЧНОЙ] {final_command} — выдать вручную",
            self.console.red,
        )

        if self.mute_store:
            stored_message = (message_text or "").strip()
            if not stored_message and highlight_messages and target:
                for item in reversed(highlight_messages):
                    if item.nickname.lower() == target.lower():
                        stored_message = item.text
                        break
            self.mute_store.record(
                final_command,
                photo_path,
                source=source,
                message=stored_message,
                status="pending_manual",
                mod_nick=mod_nick,
                mod_port=port,
            )
        elif photo_path and os.path.isfile(photo_path):
            try:
                os.remove(photo_path)
            except OSError:
                pass
        return True

    def _on_mute_cooldown(self, nickname: str) -> bool:
        cooldown = self.settings.mute_cooldown_seconds
        if cooldown <= 0:
            return False
        last = self._mute_cooldown.get(nickname.lower(), 0.0)
        return time.monotonic() - last < cooldown

    def _resolve_endpoint(self, client: ModClientRef | None) -> tuple[str, int]:
        if client:
            return client.host, client.port
        return self.settings.mod_screenshot_host, self.settings.mod_screenshot_port

    def is_staff(self, nickname: str, client: ModClientRef | None = None) -> bool:
        nick = nickname.strip().lower()
        if not nick:
            return False
        if nick in self.settings.staff_nicks:
            return True
        if client and client.moderator_nick and nick == client.moderator_nick.lower():
            return True
        return False

    def _resolve_client_nick(self, client: ModClientRef | None) -> str:
        host, port = self._resolve_endpoint(client)
        cache_key = f"{host}:{port}"
        if cache_key in self._nick_cache:
            return self._nick_cache[cache_key]

        if client and client.moderator_nick:
            self._nick_cache[cache_key] = client.moderator_nick
            return client.moderator_nick

        nick = get_client_nick(host=host, port=port)
        self._nick_cache[cache_key] = nick
        return nick

    def _send_command(self, command: str, client: ModClientRef | None) -> bool:
        host, port = self._resolve_endpoint(client)
        label = format_client_label(
            client,
            self.settings.mod_screenshot_host,
            self.settings.mod_screenshot_port,
        )
        try:
            nick = self._resolve_client_nick(client)
            with self._send_lock:
                result = say_as_nick(nick, command, host=host, port=port)
            if result.get("sent"):
                return True
            self.console.print(
                f"[{label}] [МУТ] Клиент {result.get('nick')} не совпал с {nick}",
                self.console.red,
            )
            return False
        except ModBridgeError as e:
            self.console.print(f"[{label}] [МУТ] Аддон недоступен: {e}", self.console.red)
            return False
