import json
import os
import sys
from dataclasses import dataclass, field


def load_env(path=None):
    if path is None:
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    if not os.path.isfile(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if not key:
                continue
            if key not in os.environ:
                os.environ[key] = os.path.expandvars(value)


def _env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def _env_int(name, default):
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return default
    return int(value)


def _env_float(name, default):
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return default
    return float(value)


def _env_int_optional(name):
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return None
    return int(value)


DEFAULT_LLM_MODEL = "gpt-5.5"
DEFAULT_LLM_FALLBACK = "claude-sonnet-4-6"


def _parse_llm_models() -> list[str]:
    raw = os.environ.get("LLM_MODELS", "").strip()
    if raw:
        models = [part.strip() for part in raw.split(",") if part.strip()]
        if models:
            return models

    primary = (
        os.environ.get("LLM_MODEL")
        or os.environ.get("OPENROUTER_MODEL")
        or DEFAULT_LLM_MODEL
    ).strip()
    fallback = os.environ.get("LLM_MODEL_FALLBACK", DEFAULT_LLM_FALLBACK).strip()

    models: list[str] = []
    if primary:
        models.append(primary)
    if fallback and fallback not in models:
        models.append(fallback)
    return models or [DEFAULT_LLM_MODEL]


def _parse_nick_list(raw: str) -> frozenset[str]:
    nicks: set[str] = set()
    for part in raw.replace("\n", ",").split(","):
        nick = part.strip()
        if nick:
            nicks.add(nick.lower())
    return frozenset(nicks)


def _parse_login_accounts(raw: str) -> dict[str, str]:
    accounts: dict[str, str] = {}
    for part in raw.replace("\n", ",").split(","):
        item = part.strip()
        if not item or item.startswith("#"):
            continue
        if ":" not in item:
            continue
        nick, password = item.split(":", 1)
        nick = nick.strip()
        password = password.strip()
        if nick and password:
            accounts[nick] = password
    return accounts


def _moderator_dir() -> str:
    return os.path.dirname(os.path.abspath(__file__))


def _minecraft_dir() -> str:
    custom = os.environ.get("MINECRAFT_DIR", "").strip()
    if custom:
        return os.path.expandvars(os.path.expanduser(custom))

    log_path = os.environ.get("LOG_PATH", "").strip()
    if log_path:
        logs_dir = os.path.dirname(os.path.abspath(log_path))
        if os.path.basename(logs_dir).lower() == "logs":
            return os.path.dirname(logs_dir)

    appdata = os.environ.get("APPDATA")
    if appdata:
        return os.path.join(appdata, ".minecraft")
    return os.path.join(os.path.expanduser("~"), ".minecraft")


def _minecraft_autologin_dir() -> str:
    return os.path.join(_minecraft_dir(), "config", "autologin")


def _legacy_accounts_json_path() -> str | None:
    appdata = os.environ.get("APPDATA")
    if not appdata:
        return None
    return os.path.join(appdata, ".minecraft", "config", "autologin", "accounts.json")


def _accounts_json_path() -> str:
    return os.path.join(_minecraft_autologin_dir(), "accounts.json")


def _parse_login_accounts_line(line: str) -> tuple[str, str] | None:
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    if ":" in line:
        nick, password = line.split(":", 1)
    else:
        parts = line.split(None, 1)
        if len(parts) != 2:
            return None
        nick, password = parts
    nick = nick.strip()
    password = password.strip()
    if nick and password:
        return nick, password
    return None


def _load_accounts_json(path: str) -> dict[str, str]:
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    accounts: dict[str, str] = {}
    for nick, password in data.items():
        if isinstance(nick, str) and isinstance(password, str):
            nick = nick.strip()
            password = password.strip()
            if nick and password:
                accounts[nick] = password
    return accounts


def _save_accounts_json(path: str, accounts: dict[str, str]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(accounts, f, ensure_ascii=False, indent=2)
        f.write("\n")


def _load_login_accounts() -> dict[str, str]:
    accounts = _load_accounts_json(_accounts_json_path())
    imported = False

    legacy_path = _legacy_accounts_json_path()
    if legacy_path:
        for nick, password in _load_accounts_json(legacy_path).items():
            if nick not in accounts:
                accounts[nick] = password
                imported = True

    accounts.update(_parse_login_accounts(os.environ.get("LOGIN_ACCOUNTS", "")))
    txt_path = os.path.join(_moderator_dir(), "login_accounts.txt")
    if os.path.isfile(txt_path):
        with open(txt_path, encoding="utf-8") as f:
            for line in f:
                parsed = _parse_login_accounts_line(line)
                if not parsed:
                    continue
                nick, password = parsed
                if accounts.get(nick) != password:
                    accounts[nick] = password
                    imported = True

    if imported or not os.path.isfile(_accounts_json_path()):
        _save_accounts_json(_accounts_json_path(), accounts)

    return accounts


def _load_staff_nicks() -> frozenset[str]:
    nicks = set(_parse_nick_list(os.environ.get("STAFF_NICKS", "")))
    path = os.path.join(_moderator_dir(), "staff_nicks.txt")
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                nick = line.strip()
                if nick and not nick.startswith("#"):
                    nicks.add(nick.lower())
    return frozenset(nicks)


def _parse_mod_client_nicks() -> dict[int, str]:
    raw = os.environ.get("MOD_CLIENT_NICKS", "").strip()
    if not raw:
        return {}

    mapping: dict[int, str] = {}
    for part in raw.replace("\n", ",").split(","):
        item = part.strip()
        if not item or "=" not in item:
            continue
        port_str, nick = item.rsplit("=", 1)
        port = int(port_str.strip())
        nick = nick.strip()
        if port > 0 and nick:
            mapping[port] = nick
    return mapping


def _parse_mod_clients(default_host: str, default_port: int) -> list[tuple[str, int]]:
    raw = os.environ.get("MOD_CLIENTS", "").strip()
    if not raw:
        return [(default_host, default_port)]

    clients: list[tuple[str, int]] = []
    for part in raw.replace("\n", ",").split(","):
        item = part.strip()
        if not item:
            continue
        if ":" in item:
            host, port_str = item.rsplit(":", 1)
            clients.append((host.strip() or default_host, int(port_str.strip())))
        else:
            clients.append((default_host, int(item)))
    return clients or [(default_host, default_port)]


def _parse_port_scan(
    host: str,
    mod_clients: list[tuple[str, int]],
    default_port: int,
    raw: str,
) -> list[tuple[str, int]]:
    targets: set[tuple[str, int]] = set(mod_clients)
    scan = raw.strip()
    if not scan:
        for port in range(default_port, default_port + 10):
            targets.add((host, port))
        return sorted(targets)

    for part in scan.replace("\n", ",").split(","):
        item = part.strip()
        if not item:
            continue
        if ":" in item:
            item_host, ports = item.rsplit(":", 1)
            item_host = item_host.strip() or host
        else:
            item_host = host
            ports = item
        if "-" in ports:
            start_str, end_str = ports.split("-", 1)
            start = int(start_str.strip())
            end = int(end_str.strip())
            for port in range(start, end + 1):
                targets.add((item_host, port))
        else:
            targets.add((item_host, int(ports.strip())))
    return sorted(targets)


def _default_data_dir() -> str:
    env = os.environ.get("DATA_DIR", "").strip()
    if env:
        return os.path.expanduser(os.path.expandvars(env))
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        return os.path.join(base, "mc-moderator")
    if sys.platform == "darwin":
        return os.path.join(
            os.path.expanduser("~/Library/Application Support"),
            "mc-moderator",
        )
    return os.path.join(os.path.expanduser("~/.local/share"), "mc-moderator")


@dataclass
class Settings:
    base_dir: str
    data_dir: str
    log_path: str
    sleep_seconds: float
    recent_messages_limit: int
    flood_time_limit: int
    llm_model: str
    llm_api_url: str
    llm_models: list[str] = field(default_factory=list)
    llm_api_keys: list[str] = field(default_factory=list)
    skr_app_id: str = ""
    skr_uids_url: str = "https://skr.sh/api/app/v1/uids.php"
    skr_upload_url: str = "https://skrinshoter.ru/post_file2.php"
    skr_short_base: str = "https://skr.sh"
    ml_batch_size: int = 3
    ml_batch_timeout: float = 3.0
    ml_batch_min_interval: float = 5.0
    ml_batch_min_messages: int = 2
    ml_primary_port: int | None = None
    ml_quota_cooldown: float = 600.0
    online_players_sync_interval: float = 30.0
    ml_api_timeout: int = 30
    ml_max_tokens: int = 50
    ml_temperature: float = 0.1
    debug_chat: bool = False
    debug_ml: bool = False
    debug_upload: bool = False
    mod_screenshot_host: str = "127.0.0.1"
    mod_screenshot_port: int = 47823
    mod_clients: list[tuple[str, int]] = field(default_factory=list)
    mod_client_nicks: dict[int, str] = field(default_factory=dict)
    mod_scan_targets: list[tuple[str, int]] = field(default_factory=list)
    client_scan_interval: float = 1.0
    client_probe_timeout: float = 0.4
    client_nick: str = ""
    staff_nicks: frozenset[str] = field(default_factory=frozenset)
    mute_cooldown_seconds: int = 120
    ocr_nick_verify: bool = True
    screenshot_auto_open: bool = False
    telegram_enabled: bool = False
    dashboard_host: str = "127.0.0.1"
    dashboard_port: int = 9999
    worker_count: int = 3
    login_accounts: dict[str, str] = field(default_factory=dict)
    autologin_port_offset: int = 100
    autologin_enabled: bool = True

    @classmethod
    def load(cls, env_path=None):
        load_env(env_path)
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        data_dir = _default_data_dir()
        keys = []
        for i in range(1, 6):
            names = ["LLM_API_KEY", "OPENROUTER_API_KEY"] if i == 1 else [
                f"LLM_API_KEY_{i}",
                f"OPENROUTER_API_KEY_{i}",
            ]
            for name in names:
                value = os.environ.get(name, "").strip()
                if value:
                    keys.append(value)
                    break
        llm_models = _parse_llm_models()
        return cls(
            base_dir=base_dir,
            data_dir=data_dir,
            log_path=os.path.expandvars(os.environ.get(
                "LOG_PATH",
                r"C:\Users\User\AppData\Roaming\.minecraft\logs\latest.log",
            )),
            sleep_seconds=_env_float("SLEEP_SECONDS", 0.3),
            recent_messages_limit=_env_int("RECENT_MESSAGES_LIMIT", 19),
            flood_time_limit=_env_int("FLOOD_TIME_LIMIT", 60),
            llm_model=llm_models[0],
            llm_models=llm_models,
            llm_api_url=os.environ.get("LLM_API_URL") or os.environ.get(
                "OPENROUTER_API_URL",
                "https://clodex.xyz/v1/chat/completions",
            ),
            llm_api_keys=keys,
            skr_app_id=os.environ.get("SKR_APP_ID", "").strip(),
            skr_uids_url=os.environ.get(
                "SKR_UIDS_URL", "https://skr.sh/api/app/v1/uids.php"
            ),
            skr_upload_url=os.environ.get(
                "SKR_UPLOAD_URL", "https://skrinshoter.ru/post_file2.php"
            ),
            skr_short_base=os.environ.get("SKR_SHORT_BASE", "https://skr.sh"),
            ml_batch_size=_env_int("ML_BATCH_SIZE", 3),
            ml_batch_timeout=_env_float("ML_BATCH_TIMEOUT", 3.0),
            ml_batch_min_interval=_env_float("ML_BATCH_MIN_INTERVAL", 5.0),
            ml_batch_min_messages=_env_int("ML_BATCH_MIN_MESSAGES", 2),
            ml_primary_port=_env_int_optional("ML_PRIMARY_PORT"),
            ml_quota_cooldown=_env_float("ML_QUOTA_COOLDOWN", 600.0),
            online_players_sync_interval=_env_float("ONLINE_PLAYERS_SYNC_INTERVAL", 30.0),
            ml_api_timeout=_env_int("ML_API_TIMEOUT", 90),
            ml_max_tokens=_env_int("ML_MAX_TOKENS", 50),
            ml_temperature=_env_float("ML_TEMPERATURE", 0.1),
            debug_chat=_env_bool("DEBUG_CHAT"),
            debug_ml=_env_bool("DEBUG_ML"),
            debug_upload=_env_bool("DEBUG_UPLOAD"),
            mod_screenshot_host=os.environ.get("MOD_SCREENSHOT_HOST", "127.0.0.1"),
            mod_screenshot_port=_env_int("MOD_SCREENSHOT_PORT", 47823),
            mod_clients=_parse_mod_clients(
                os.environ.get("MOD_SCREENSHOT_HOST", "127.0.0.1"),
                _env_int("MOD_SCREENSHOT_PORT", 47823),
            ),
            mod_client_nicks=_parse_mod_client_nicks(),
            mod_scan_targets=_parse_port_scan(
                os.environ.get("MOD_SCREENSHOT_HOST", "127.0.0.1"),
                _parse_mod_clients(
                    os.environ.get("MOD_SCREENSHOT_HOST", "127.0.0.1"),
                    _env_int("MOD_SCREENSHOT_PORT", 47823),
                ),
                _env_int("MOD_SCREENSHOT_PORT", 47823),
                os.environ.get("MOD_PORT_SCAN", ""),
            ),
            client_scan_interval=_env_float("CLIENT_SCAN_INTERVAL", 1.0),
            client_probe_timeout=_env_float("CLIENT_PROBE_TIMEOUT", 0.4),
            client_nick=os.environ.get("CLIENT_NICK", "").strip(),
            staff_nicks=_load_staff_nicks(),
            mute_cooldown_seconds=_env_int("MUTE_COOLDOWN_SECONDS", 120),
            ocr_nick_verify=_env_bool("OCR_NICK_VERIFY", True),
            screenshot_auto_open=_env_bool("SCREENSHOT_AUTO_OPEN"),
            telegram_enabled=_env_bool("TELEGRAM_ENABLED"),
            dashboard_host=os.environ.get("DASHBOARD_HOST", "127.0.0.1"),
            dashboard_port=_env_int("DASHBOARD_PORT", 9999),
            worker_count=_env_int("WORKER_COUNT", 3),
            login_accounts=_load_login_accounts(),
            autologin_port_offset=_env_int("AUTOLOGIN_PORT_OFFSET", 100),
            autologin_enabled=_env_bool("AUTOLOGIN_ENABLED", True),
        )
