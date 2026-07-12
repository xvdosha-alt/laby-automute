import os
import time

from .autologin_client import AutologinBridgeError, push_login_passwords
from .chat_cursor import ChatCursorStore
from .client_session import ClientSession
from .config import Settings
from .console import Console
from .chat_filters import batch_needs_ml
from .heuristics import HeuristicChecker
from .llm_client import LLMClient
from .mod_client import (
    ModBridgeError,
    get_chat_state,
    get_client_nick,
    get_online_players,
    poll_chat,
)
from .models import (
    ChatMessage,
    ModClientRef,
    display_nickname,
    format_client_label,
    is_altered_nick_message,
    is_invalid_chat_nickname,
    is_spaced_ten_digit_message,
    message_dedup_key,
    message_text_for_nickname,
)
from .nick_registry import NickRegistry
from .mute_store import MuteStore
from .punishment import PunishmentExecutor
from .rules_config import RulesConfig
from .runtime_state import RuntimeState
from .screenshot import ScreenshotService
from .telegram import TelegramNotifier
from .uploader import ImageUploader
from .worker import HeuristicTask, MlBatchTask, ModerationWorker


class ModeratorBot:
    def __init__(
        self,
        settings: Settings,
        mute_store: MuteStore | None = None,
        runtime_state: RuntimeState | None = None,
        rules_config: RulesConfig | None = None,
    ):
        self.settings = settings
        self._runtime = runtime_state
        self._rules = rules_config or RulesConfig(settings.data_dir)
        self.console = Console(runtime_state)
        self._nick_registry = NickRegistry(
            settings.base_dir,
            settings.staff_nicks,
        )
        self.heuristics_factory = lambda: HeuristicChecker(
            settings.flood_time_limit,
            self._nick_registry.as_frozenset(),
        )
        self.llm = LLMClient(settings, self.console)
        self.screenshot = ScreenshotService(settings, self.console)
        self.uploader = ImageUploader(settings, self.console)
        self.telegram = TelegramNotifier(settings, self.console)
        self.punishment = PunishmentExecutor(
            settings,
            self.console,
            self.screenshot,
            self.uploader,
            self.telegram,
            mute_store,
            moderation_enabled=self._moderation_enabled,
        )
        self._cursor_store = ChatCursorStore(settings.data_dir)
        self._worker = ModerationWorker(
            self._handle_heuristic_task,
            self._handle_ml_batch_task,
            self._on_queue_change,
            settings.worker_count,
        )
        self._clients: list[ClientSession] = []
        if self._runtime is not None:
            self._runtime.set_moderation_change_handler(self._on_moderation_change)
        self._last_client_scan = 0.0
        self._last_debug_scan = 0.0
        self._last_online_sync = 0.0
        self._chat_message_owners: dict[str, tuple[int, float]] = {}
        self._global_ml_next_at: float = 0.0

    def _ml_leader_port(self) -> int | None:
        configured = self.settings.ml_primary_port
        if configured is not None:
            return configured
        online = [session for session in self._clients if session.online]
        if not online:
            return None
        return min(session.port for session in online)

    def _can_run_ml(self, session: ClientSession) -> bool:
        leader = self._ml_leader_port()
        return leader is not None and session.port == leader

    def run(self) -> None:
        self._clients = self._init_clients()
        if not self.settings.mod_scan_targets:
            self.console.print("[ошибка] нет портов для сканирования", self.console.red)
            return

        self._worker.start()
        self._print_summary()
        self._sync_online_players()
        self._publish_runtime()

        while True:
            self._maybe_discover_clients()
            self._maybe_sync_online_players()
            for session in list(self._clients):
                self._flush_stale_ml_batches(session)
                self._poll_client(session)
            self._publish_runtime()
            time.sleep(self.settings.sleep_seconds)

    def _publish_runtime(self) -> None:
        if self._runtime is None:
            return
        clients = []
        for session in self._clients:
            clients.append({
                "host": session.host,
                "port": session.port,
                "nick": session.moderator_nick or "",
                "online": session.online,
                "ml_batch": len(session.ml_batch),
                "chat_since": session.chat_since,
            })
        self._runtime.set_clients(clients)
        self._runtime.set_summary({
            "workers": self._worker.thread_count,
            "clients_known": len(self._clients),
            "clients_online": sum(1 for s in self._clients if s.online),
            "scan_ports": len(self.settings.mod_scan_targets),
            "scan_interval": self.settings.client_scan_interval,
            "queue_pending": self._worker.pending(),
            "moderation_enabled": self._moderation_enabled(),
        })

    def _moderation_enabled(self) -> bool:
        if self._runtime is None:
            return True
        return self._runtime.is_moderation_enabled()

    def _reset_session_buffers(self, session: ClientSession) -> None:
        session.ml_batch = []
        session.ml_batch_first_at = 0.0
        session.recent_messages = []

    def _on_moderation_change(self, enabled: bool) -> None:
        for session in self._clients:
            self._reset_session_buffers(session)
        dropped = self._worker.drain_pending()
        if enabled:
            self.console.print(
                "[модерация] включена — новые сообщения обрабатываются",
                self.console.green,
            )
        else:
            parts = ["[модерация] остановлена — логи идут, муты не выдаются"]
            if dropped:
                parts.append(f", сброшено задач: {dropped}")
            self.console.print("".join(parts), self.console.yellow)

    def _print_summary(self) -> None:
        online_count = sum(1 for session in self._clients if session.online)
        self.console.print(
            f"[клиенты] {len(self._clients)} известно, {online_count} онлайн "
            f"| скан {len(self.settings.mod_scan_targets)} портов / "
            f"{self.settings.client_scan_interval:g}с "
            f"| [воркеры] {self._worker.thread_count} потоков",
            self.console.yellow,
        )
        for session in self._clients:
            self._print_client_status(session)

    def _apply_known_nicks(self) -> None:
        nicks = self._nick_registry.as_frozenset()
        for session in self._clients:
            if session.heuristics is not None:
                session.heuristics.update_known_nicks(nicks)

    def _maybe_sync_online_players(self) -> None:
        now = time.monotonic()
        if now - self._last_online_sync < self.settings.online_players_sync_interval:
            return
        self._last_online_sync = now
        self._sync_online_players()

    def _sync_online_players(self) -> None:
        online_sessions = [s for s in self._clients if s.online]
        if not online_sessions:
            return

        merged: set[str] = set()
        source_label = ""
        timeout = max(self.settings.client_probe_timeout, 2.0)

        for session in online_sessions:
            try:
                players = get_online_players(
                    host=session.host,
                    port=session.port,
                    timeout=timeout,
                )
            except ModBridgeError:
                continue
            if players:
                merged.update(players)
                source_label = session.label

        if not merged:
            return

        added = self._nick_registry.merge_players(sorted(merged))
        self._apply_known_nicks()

        if self.settings.debug_chat and added:
            self.console.print(
                f"[ники] +{added} с таба ({source_label}), "
                f"всего {len(self._nick_registry)}",
                self.console.yellow,
            )

    def _maybe_discover_clients(self) -> None:
        now = time.monotonic()
        if now - self._last_client_scan < self.settings.client_scan_interval:
            return
        self._last_client_scan = now
        self._discover_clients()

    def _discover_clients(self) -> None:
        known = {(session.host, session.port) for session in self._clients}
        newly_found: list[tuple[str, int]] = []

        for host, port in self.settings.mod_scan_targets:
            if (host, port) in known:
                continue
            if not self._probe_addon(host, port):
                continue
            session = self._create_session(host, port)
            self._clients.append(session)
            newly_found.append((host, port))
            self.console.print(
                f"[новый клиент] {session.label}",
                self.console.green,
            )
            self._print_client_status(session)

        if self.settings.debug_chat:
            self._debug_scan(known, newly_found)

    def _debug_scan(
        self,
        known: set[tuple[str, int]],
        newly_found: list[tuple[str, int]],
    ) -> None:
        if newly_found:
            return
        now = time.monotonic()
        if now - self._last_debug_scan < 10.0:
            return
        self._last_debug_scan = now

        responding: list[int] = []
        for host, port in self.settings.mod_scan_targets:
            if self._probe_addon(host, port):
                responding.append(port)

        scan_from = self.settings.mod_scan_targets[0][1]
        scan_to = self.settings.mod_scan_targets[-1][1]
        self.console.print(
            f"[скан] найдено аддонов: {len(responding)} на портах {responding or '—'} "
            f"(диапазон {scan_from}-{scan_to}, известно клиентов: {len(known)})",
            self.console.yellow,
        )

    def _probe_addon(self, host: str, port: int) -> bool:
        try:
            get_chat_state(
                host=host,
                port=port,
                timeout=self.settings.client_probe_timeout,
            )
            return True
        except ModBridgeError:
            return False

    def _create_session(self, host: str, port: int) -> ClientSession:
        session = ClientSession(
            endpoint=ModClientRef(host=host, port=port),
            heuristics=self.heuristics_factory(),
        )
        known_nick = self._known_moderator_nick(session)
        if known_nick:
            session.moderator_nick = known_nick
            if self._nick_registry.add_staff(known_nick):
                self._apply_known_nicks()
        self._sync_cursor(session)
        if session.online:
            self._try_resolve_nick(session)
        self._push_login_passwords(session)
        return session

    def _push_login_passwords(self, session: ClientSession) -> None:
        if not self.settings.autologin_enabled:
            return
        if not self.settings.login_accounts:
            return
        try:
            response = push_login_passwords(
                self.settings.login_accounts,
                host=session.host,
                screenshot_port=session.port,
                port_offset=self.settings.autologin_port_offset,
                timeout=self.settings.client_probe_timeout,
            )
            accounts = int(response.get("accounts", 0))
            port = response.get("port", "?")
            self.console.print(
                f"[autologin] {session.label} пароли отправлены "
                f"({accounts} акк., порт {port})",
                self.console.green,
            )
        except AutologinBridgeError as e:
            self.console.print(
                f"[autologin] {session.label} недоступен: {e}",
                self.console.yellow,
            )

    def _init_clients(self) -> list[ClientSession]:
        sessions: list[ClientSession] = []
        seen: set[tuple[str, int]] = set()

        for host, port in self.settings.mod_clients:
            key = (host, port)
            if key in seen:
                continue
            seen.add(key)
            sessions.append(self._create_session(host, port))

        for host, port in self.settings.mod_scan_targets:
            key = (host, port)
            if key in seen:
                continue
            if not self._probe_addon(host, port):
                continue
            seen.add(key)
            sessions.append(self._create_session(host, port))

        return sessions

    def _print_client_status(self, session: ClientSession) -> None:
        if session.moderator_nick:
            color = self.console.green if session.online else self.console.yellow
            state = "онлайн" if session.online else "аддон отвечает, чат не опрашивается"
            self.console.print(f"  {session.label} ({state})", color)
            return

        if session.online:
            self.console.print(
                f"  {session.label} (в мире, ник определяется…)",
                self.console.yellow,
            )
            return

        hint = ""
        configured = self.settings.mod_client_nicks.get(session.port, "").strip()
        if configured:
            hint = f", в .env MOD_CLIENT_NICKS={configured}"
        elif (
            len(self.settings.mod_clients) == 1
            and self.settings.client_nick
        ):
            hint = f", в .env CLIENT_NICK={self.settings.client_nick}"
        self.console.print(
            f"  {session.label} (офлайн{hint})",
            self.console.yellow,
        )

    def _known_moderator_nick(self, session: ClientSession) -> str:
        configured = self.settings.mod_client_nicks.get(session.port, "").strip()
        if configured:
            return configured
        stored = self._cursor_store.get(session.host, session.port).mod_nick.strip()
        if stored:
            return stored
        if len(self.settings.mod_clients) == 1 and self.settings.client_nick:
            return self.settings.client_nick.strip()
        return ""

    def _set_moderator_nick(self, session: ClientSession, nick: str) -> None:
        cleaned = nick.strip()
        if not cleaned:
            return

        previous = session.moderator_nick
        if previous == cleaned:
            return

        session.moderator_nick = cleaned
        self._cursor_store.save(
            session.host,
            session.port,
            session.boot_id,
            session.chat_since,
            mod_nick=cleaned,
        )
        if self._nick_registry.add_staff(cleaned):
            self._apply_known_nicks()

        if previous != cleaned:
            self.console.print(
                f"[{session.host}:{session.port}] модератор: {cleaned}",
                self.console.green,
            )

    def _apply_poll_identity(self, session: ClientSession, response: dict) -> None:
        nick = str(response.get("nick", "")).strip()
        if nick:
            self._set_moderator_nick(session, nick)
            return

        if response.get("in_world") and not session.moderator_nick:
            self._try_resolve_nick(session)

    def _sync_cursor(self, session: ClientSession) -> None:
        stored = self._cursor_store.get(session.host, session.port)
        try:
            state = get_chat_state(host=session.host, port=session.port)
            boot = int(state.get("boot", 0))
            last = int(state.get("last", 0))
            session.boot_id = boot
            session.online = True
            self._apply_poll_identity(session, state)

            if boot != stored.boot:
                session.chat_since = last
            elif stored.since > 0:
                session.chat_since = min(stored.since, last)
            else:
                session.chat_since = last

            if stored.since > last and boot == stored.boot:
                self.console.print(
                    f"[{session.host}:{session.port}] курсор {stored.since} > буфер "
                    f"{last}, сброшен на {session.chat_since}",
                    self.console.yellow,
                )

            self._cursor_store.save(session.host, session.port, boot, session.chat_since)
            if last > session.chat_since:
                self.console.print(
                    f"[{session.host}:{session.port}] курсор {session.chat_since}, "
                    f"в буфере до {last}",
                    self.console.yellow,
                )
        except ModBridgeError as e:
            session.online = False
            session.chat_since = stored.since
            session.boot_id = stored.boot
            self.console.print(
                f"[{session.host}:{session.port}] аддон недоступен: {e}",
                self.console.yellow,
            )

    def _try_resolve_nick(self, session: ClientSession) -> None:
        if not session.online:
            return
        timeout = max(self.settings.client_probe_timeout, 2.0)
        try:
            nick = get_client_nick(
                host=session.host,
                port=session.port,
                timeout=timeout,
            )
        except ModBridgeError as e:
            if self.settings.debug_chat and not session.moderator_nick:
                now = time.monotonic()
                if now - getattr(session, "_last_nick_diag", 0.0) > 30.0:
                    session._last_nick_diag = now
                    self.console.print(
                        f"[{session.label}] nick недоступен: {e}",
                        self.console.yellow,
                    )
            return

        self._set_moderator_nick(session, nick)

    def _poll_client(self, session: ClientSession) -> None:
        was_online = session.online

        if not was_online:
            self._sync_cursor(session)

        if session.online:
            self._try_resolve_nick(session)

        if not session.online:
            return

        since = session.chat_since
        try:
            response = poll_chat(
                since=since,
                host=session.host,
                port=session.port,
            )
        except ModBridgeError as e:
            session.poll_failures += 1
            if session.poll_failures >= 3:
                session.online = False
                session.poll_failures = 0
                if self.settings.debug_chat:
                    self.console.print(
                        f"[{session.label}] опрос чата недоступен: {e}",
                        self.console.yellow,
                    )
            return

        session.poll_failures = 0
        session.online = True
        self._apply_poll_identity(session, response)
        last = int(response.get("last", session.chat_since))
        if since > last:
            session.chat_since = last
            self._cursor_store.save(
                session.host,
                session.port,
                session.boot_id,
                last,
            )
            if self.settings.debug_chat:
                self.console.print(
                    f"[{session.label}] курсор {since} > last {last}, сброшен",
                    self.console.yellow,
                )
            since = last

        boot = int(response.get("boot", session.boot_id))
        if session.boot_id and boot != session.boot_id:
            last = int(response.get("last", session.chat_since))
            session.chat_since = last
            session.ml_batch = []
            session.ml_batch_first_at = 0.0
            session.recent_messages = []
            session.heuristics = self.heuristics_factory()
            self.console.print(
                f"[{session.label}] аддон перезапущен, курсор сброшен на {last}",
                self.console.yellow,
            )
        session.boot_id = boot

        messages = response.get("messages") or []
        for item in messages:
            message = ChatMessage(
                timestamp=str(item.get("time", "")),
                nickname=str(item.get("nick", "")),
                text=str(item.get("text", "")),
                altered_nick=bool(item.get("altered", False)),
            )
            if not message.nickname or not message.text:
                continue
            self._handle_message(session, message)

        if last > session.chat_since:
            session.chat_since = last
            self._cursor_store.save(session.host, session.port, boot, last)
        elif (
            self.settings.debug_chat
            and session.moderator_nick
            and not messages
            and last == 0
            and time.monotonic() - getattr(session, "_last_chat_diag", 0.0) > 30.0
        ):
            session._last_chat_diag = time.monotonic()
            self.console.print(
                f"[{session.label}] буфер чата пуст (last=0) — "
                f"аддон не ловит сообщения",
                self.console.yellow,
            )

    def _claim_message(self, session: ClientSession, message: ChatMessage) -> bool:
        key = message_dedup_key(message)
        now = time.monotonic()
        if len(self._chat_message_owners) > 5000:
            cutoff = now - 120.0
            self._chat_message_owners = {
                item_key: value
                for item_key, value in self._chat_message_owners.items()
                if value[1] >= cutoff
            }

        owner = self._chat_message_owners.get(key)
        if owner is not None:
            _, claimed_at = owner
            if now - claimed_at < 120.0:
                return False

        self._chat_message_owners[key] = (session.port, now)
        return True

    def _log_chat_line(
        self,
        session: ClientSession,
        message: ChatMessage,
        color: str,
        *,
        label: str | None = None,
    ) -> None:
        if label is None:
            label = display_nickname(message)
        self.console.print(
            f"[{session.label}] [{message.timestamp}] {label}: {message.text}",
            color,
        )

    def _handle_message(self, session: ClientSession, message: ChatMessage) -> None:
        if session.heuristics is None:
            return

        if not self._claim_message(session, message):
            return

        client_ref = ModClientRef(
            host=session.host,
            port=session.port,
            moderator_nick=session.moderator_nick,
        )

        if is_invalid_chat_nickname(message.nickname, message.text):
            self._log_chat_line(session, message, self.console.purple, label="[url]")
            return

        is_staff = self.punishment.is_staff(message.nickname, client_ref)
        is_system = is_altered_nick_message(message)
        is_tab_player = self._nick_registry.is_tab_player(message.nickname)

        if is_system or is_staff:
            self._log_chat_line(session, message, self.console.green)
            return

        if not is_tab_player:
            self._log_chat_line(session, message, self.console.purple)
            return

        self._log_chat_line(session, message, self.console.green)

        if is_spaced_ten_digit_message(message.text):
            return

        self._nick_registry.register_from_message(message.nickname, message.text)
        self._apply_known_nicks()

        moderation_on = self._moderation_enabled()

        mute_command = None
        flood_kind = None
        highlight_messages: list[ChatMessage] = [message]
        has_violation = False

        if session.heuristics.check_caps(message.text):
            mute_command = session.heuristics.get_caps_mute(message.nickname)
            has_violation = True
        else:
            flood_result = session.heuristics.check_flood(
                session.recent_messages,
                message.nickname,
                message.text,
                message.timestamp,
            )
            if flood_result:
                mute_command = session.heuristics.get_flood_mute(message.nickname)
                flood_kind = flood_result.kind
                highlight_messages = flood_result.messages
                has_violation = True
            elif session.heuristics.has_explicit_insult(message.text):
                mute_command = session.heuristics.get_insult_mute(message.nickname)
                has_violation = True

        session.recent_messages.append(message)
        if len(session.recent_messages) > self.settings.recent_messages_limit:
            session.recent_messages.pop(0)

        session.heuristics.cleanup_expired_groups(message.timestamp)

        if mute_command:
            rule_id = RulesConfig.extract_rule_id(mute_command)
            if not moderation_on:
                self.console.print(
                    f"[{session.label}] [ПАУЗА] {mute_command} — в игру не отправлен",
                    self.console.yellow,
                )
                self.punishment.record_violation(
                    mute_command,
                    message.nickname,
                    status="paused",
                    note="модерация на паузе",
                    highlight_messages=highlight_messages,
                    source="heuristic",
                    client=client_ref,
                    message_text=message.text,
                )
            elif not self._rules.is_automute_enabled(rule_id):
                self.console.print(
                    f"[{session.label}] [МУТ ОТМЕНЁН] правило {rule_id}: автомут отключён",
                    self.console.yellow,
                )
                self.punishment.record_violation(
                    mute_command,
                    message.nickname,
                    status="skipped",
                    note=f"автомут отключён ({rule_id})",
                    highlight_messages=highlight_messages,
                    source="heuristic",
                    client=client_ref,
                    message_text=message.text,
                )
            else:
                self._worker.submit_heuristic(
                    mute_command,
                    message.nickname,
                    highlight_messages,
                    None,
                    client_ref,
                    flood_kind=flood_kind,
                )
        elif not has_violation:
            if not moderation_on:
                return
            if not self._can_run_ml(session):
                return
            if not session.ml_batch:
                session.ml_batch_first_at = time.monotonic()
            session.ml_batch.append(message)
            if len(session.ml_batch) >= self.settings.ml_batch_size:
                self._submit_ml_batch(session, client_ref)

    def _submit_ml_batch(
        self,
        session: ClientSession,
        client_ref: ModClientRef,
    ) -> None:
        if not self._moderation_enabled():
            session.ml_batch = []
            session.ml_batch_first_at = 0.0
            return
        if not session.ml_batch:
            return
        if not batch_needs_ml(session.ml_batch):
            session.ml_batch = []
            session.ml_batch_first_at = 0.0
            return
        batch_len = len(session.ml_batch)
        if batch_len < self.settings.ml_batch_min_messages:
            return
        now = time.monotonic()
        if now < self._global_ml_next_at:
            if batch_len < self.settings.ml_batch_size * 2:
                return
        if session.ml_last_submit_at > 0:
            elapsed = now - session.ml_last_submit_at
            if elapsed < self.settings.ml_batch_min_interval:
                if len(session.ml_batch) < self.settings.ml_batch_size * 2:
                    return
        photo_path = self.screenshot.capture(
            pending=True,
            host=session.host,
            port=session.port,
        )
        if photo_path:
            self._worker.submit_ml_batch(
                session.ml_batch,
                photo_path,
                client_ref,
            )
            session.ml_last_submit_at = now
            self._global_ml_next_at = now + self.settings.ml_batch_min_interval
        else:
            self.console.print(
                f"[{session.label}] [ML] Скриншот не создан, батч пропущен",
                self.console.red,
            )
        session.ml_batch = []
        session.ml_batch_first_at = 0.0

    def _flush_stale_ml_batches(self, session: ClientSession) -> None:
        if not self._moderation_enabled():
            return
        if not self._can_run_ml(session):
            session.ml_batch = []
            session.ml_batch_first_at = 0.0
            return
        batch = session.ml_batch
        if not batch:
            return
        if len(batch) >= self.settings.ml_batch_size:
            return
        if session.ml_batch_first_at <= 0:
            return
        idle = time.monotonic() - session.ml_batch_first_at
        if len(batch) < self.settings.ml_batch_min_messages:
            if idle < self.settings.ml_batch_timeout * 4:
                return
        if idle < self.settings.ml_batch_timeout:
            return
        client_ref = ModClientRef(
            host=session.host,
            port=session.port,
            moderator_nick=session.moderator_nick,
        )
        self._submit_ml_batch(session, client_ref)

    def _on_queue_change(self, pending: int) -> None:
        if pending > 0:
            self.console.print(
                f"[очередь] задач в обработке: {pending}",
                self.console.green,
            )

    @staticmethod
    def _batch_message_text(batch: list[ChatMessage]) -> str:
        if not batch:
            return ""
        return " | ".join(f"{msg.nickname}: {msg.text[:120]}" for msg in batch)

    def _handle_heuristic_task(self, task: HeuristicTask) -> None:
        if not self._moderation_enabled():
            self.punishment.record_violation(
                task.command,
                task.nickname,
                status="paused",
                note="модерация на паузе",
                highlight_messages=task.messages,
                source="heuristic",
                client=task.client,
                message_text=message_text_for_nickname(task.messages, task.nickname),
            )
            return
        self.punishment.execute(
            task.command,
            task.nickname,
            None,
            highlight_messages=task.messages,
            source="heuristic",
            client=task.client,
            message_text=message_text_for_nickname(task.messages, task.nickname),
            flood_kind=task.flood_kind,
        )

    def _handle_ml_batch_task(self, task: MlBatchTask) -> None:
        if not self._moderation_enabled():
            photo_path = task.photo_path
            if photo_path and os.path.isfile(photo_path):
                try:
                    os.remove(photo_path)
                except OSError:
                    pass
            return
        batch = task.batch
        photo_path = task.photo_path
        label = task.client.label if task.client else "?"

        try:
            result = self.llm.check_batch(batch)
            if not result:
                detail = self.llm.last_error
                msg = f"[{label}] [ML] API недоступен, батч пропущен"
                if detail:
                    msg += f" ({detail[:120]})"
                self.console.print(msg, self.console.red)
                return

            verdict_type, command = self.llm.parse_verdict(result)
            if verdict_type == "none":
                self.console.print(f"[{label}] none", self.console.red)
                batch_slice = batch[-self.settings.ml_batch_size :]
                self.punishment.record_violation(
                    "",
                    None,
                    status="none",
                    note="LLM: none",
                    photo_path=photo_path,
                    highlight_messages=batch_slice,
                    source="ml",
                    client=task.client,
                    message_text=self._batch_message_text(batch_slice),
                )
                photo_path = None
                return

            if verdict_type != "mute" or not command:
                self.console.print(
                    f"[{label}] [ОШИБКА LLM] Не удалось разобрать ответ. Мут отменён.\n{result[:500]}",
                    self.console.red,
                )
                return

            command = self.llm.normalize_mute_command(command)
            if self.settings.debug_ml and result.strip() != command:
                self.console.print(
                    f"[DEBUG ML] Команда после нормализации: {command}",
                    self.console.yellow,
                )
            parts = command.split()
            if len(parts) < 2:
                self.console.print(
                    f"[{label}] [МУТ ОТМЕНЁН] Некорректная команда от LLM: {command}",
                    self.console.red,
                )
                return

            nickname = parts[1]
            batch_slice = batch[-self.settings.ml_batch_size :]
            batch_nicks = {msg.nickname.lower() for msg in batch_slice}
            if nickname.lower() not in batch_nicks:
                self.console.print(
                    f"[{label}] [ОШИБКА LLM] Ник '{nickname}' не из батча! "
                    f"Отправляли: {', '.join(msg.nickname for msg in batch_slice)}. "
                    f"Ответ LLM: {result}. Мут отменён.",
                    self.console.red,
                )
                self.punishment.record_violation(
                    command,
                    nickname,
                    status="rejected",
                    note="ник не из батча",
                    photo_path=photo_path,
                    highlight_messages=batch_slice,
                    source="ml",
                    client=task.client,
                    message_text=message_text_for_nickname(batch_slice, nickname),
                )
                photo_path = None
                return

            reject_reason = self.llm.reject_false_mute(command, batch_slice)
            if reject_reason:
                self.console.print(
                    f"[{label}] [МУТ ОТМЕНЁН] {reject_reason}: {command}",
                    self.console.yellow,
                )
                self.punishment.record_violation(
                    command,
                    nickname,
                    status="rejected",
                    note=reject_reason,
                    photo_path=photo_path,
                    highlight_messages=batch_slice,
                    source="ml",
                    client=task.client,
                    message_text=message_text_for_nickname(batch_slice, nickname),
                )
                photo_path = None
                return

            fields = self.llm.parse_mute_command_fields(command)
            reason = fields[2] if fields else ""
            rule_id = RulesConfig.extract_rule_id(reason)
            if not self._rules.is_automute_enabled(rule_id):
                self.console.print(
                    f"[{label}] [МУТ ОТМЕНЁН] правило {rule_id}: автомут отключён",
                    self.console.yellow,
                )
                self.punishment.record_violation(
                    command,
                    nickname,
                    status="skipped",
                    note=f"автомут отключён ({rule_id})",
                    photo_path=photo_path,
                    highlight_messages=batch_slice,
                    source="ml",
                    client=task.client,
                    message_text=message_text_for_nickname(batch_slice, nickname),
                )
                photo_path = None
                return

            if self.llm.is_manual_only_reason(reason):
                self.punishment.record_suggestion(
                    command,
                    nickname,
                    photo_path,
                    highlight_messages=batch_slice,
                    source="ml",
                    client=task.client,
                    message_text=message_text_for_nickname(batch_slice, nickname),
                )
                photo_path = None
                return

            self.punishment.execute(
                command,
                nickname,
                photo_path,
                highlight_messages=batch_slice,
                source="ml",
                client=task.client,
                message_text=message_text_for_nickname(batch_slice, nickname),
            )
            photo_path = None
        finally:
            if photo_path and os.path.isfile(photo_path):
                try:
                    os.remove(photo_path)
                except OSError:
                    pass
