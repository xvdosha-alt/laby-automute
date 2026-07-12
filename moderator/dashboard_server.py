import logging
import os
import threading
import time

from flask import Flask, jsonify, request, send_from_directory

from .autologin_client import (
    AutologinBridgeError,
    autologin_port_for_screenshot_port,
    get_autologin_status,
    push_login_passwords,
)
from .config import Settings
from .mod_client import (
    ModBridgeError,
    get_chat_state,
    get_client_nick,
    get_online_players,
    poll_chat,
    request_screenshot,
    run_autologin,
    say_as_nick,
)
from .mute_report import build_mute_report
from .mute_store import MuteStore
from .rules_config import RulesConfig
from .runtime_state import RuntimeState

log = logging.getLogger("werkzeug")
log.setLevel(logging.ERROR)


def _client_endpoint(settings: Settings) -> tuple[str, int]:
    data = request.get_json(silent=True) or {}
    host = (request.args.get("host") or data.get("host") or settings.mod_screenshot_host).strip()
    port_raw = request.args.get("port", type=int)
    if port_raw is None and data.get("port") is not None:
        port_raw = int(data["port"])
    port = int(port_raw if port_raw is not None else settings.mod_screenshot_port)
    return host, port


def _client_endpoint_from_body(settings: Settings) -> tuple[str, int]:
    data = request.get_json(silent=True) or {}
    host = (data.get("host") or settings.mod_screenshot_host).strip()
    port = int(data.get("port") or settings.mod_screenshot_port)
    return host, port


def create_app(
    store: MuteStore,
    settings: Settings,
    runtime: RuntimeState | None = None,
    rules: RulesConfig | None = None,
) -> Flask:
    dist = os.path.join(settings.base_dir, "dashboard_dist")
    app = Flask(__name__, static_folder=dist, static_url_path="")

    @app.get("/api/stats")
    def api_stats():
        return jsonify(store.stats())

    @app.get("/api/mutes")
    def api_mutes():
        return jsonify(store.list_mutes())

    @app.get("/api/mutes/<mute_id>")
    def api_mute(mute_id: str):
        item = store.get_mute(mute_id)
        if not item:
            return jsonify({"error": "not found"}), 404
        return jsonify(item)

    @app.get("/api/mutes/<mute_id>/report")
    def api_mute_report(mute_id: str):
        item = store.get_mute(mute_id)
        if not item:
            return jsonify({"error": "not found"}), 404
        logs = runtime.get_logs(since=0, limit=2000) if runtime is not None else []
        return jsonify({"text": build_mute_report(item, logs)})

    @app.get("/api/runtime")
    def api_runtime():
        if runtime is None:
            return jsonify({"clients": [], "summary": {}})
        return jsonify({
            "clients": runtime.get_clients(),
            "summary": runtime.get_summary(),
            "moderation_enabled": runtime.is_moderation_enabled(),
        })

    @app.get("/api/moderation")
    def api_moderation_get():
        if runtime is None:
            return jsonify({"enabled": False})
        return jsonify({"enabled": runtime.is_moderation_enabled()})

    @app.post("/api/moderation")
    def api_moderation_post():
        if runtime is None:
            return jsonify({"ok": False, "error": "runtime_unavailable"}), 503
        data = request.get_json(silent=True) or {}
        if "enabled" not in data:
            return jsonify({"ok": False, "error": "missing_enabled"}), 400
        enabled = runtime.set_moderation_enabled(bool(data["enabled"]))
        return jsonify({"ok": True, "enabled": enabled})

    @app.get("/api/logs")
    def api_logs():
        since = request.args.get("since", 0, type=int)
        if runtime is None:
            return jsonify({"logs": [], "last_id": since})
        logs = runtime.get_logs(since=since)
        last_id = since
        if logs:
            last_id = logs[-1]["id"]
        return jsonify({"logs": logs, "last_id": last_id})

    @app.post("/api/say")
    def api_say():
        data = request.get_json(silent=True) or {}
        nick = (data.get("nick") or settings.client_nick or "").strip()
        message = (data.get("message") or "").strip()
        host = (data.get("host") or settings.mod_screenshot_host).strip()
        port = int(data.get("port") or settings.mod_screenshot_port)
        if not nick:
            return jsonify({"ok": False, "error": "missing_nick"}), 400
        if not message:
            return jsonify({"ok": False, "error": "missing_message"}), 400
        try:
            result = say_as_nick(nick, message, host=host, port=port)
        except ModBridgeError as e:
            return jsonify({"ok": False, "error": str(e)}), 503
        return jsonify(result)

    @app.post("/api/unmute")
    def api_unmute():
        data = request.get_json(silent=True) or {}
        mute_id = (data.get("mute_id") or "").strip()
        item = store.get_mute(mute_id) if mute_id else None
        nick = (data.get("nick") or (item or {}).get("nickname") or "").strip()
        if not nick:
            return jsonify({"ok": False, "error": "missing_nick"}), 400
        mod_nick = (
            data.get("mod_nick")
            or (item or {}).get("mod_nick")
            or settings.client_nick
            or ""
        ).strip()
        if not mod_nick:
            return jsonify({"ok": False, "error": "missing_mod_nick"}), 400
        host = (data.get("host") or settings.mod_screenshot_host).strip()
        port_raw = data.get("port")
        if port_raw is None and item:
            port_raw = item.get("mod_port")
        port = int(port_raw if port_raw is not None else settings.mod_screenshot_port)
        message = f"/unmute {nick}"
        try:
            result = say_as_nick(mod_nick, message, host=host, port=port)
        except ModBridgeError as e:
            return jsonify({"ok": False, "error": str(e)}), 503
        if runtime is not None:
            runtime.add_log(f"[dashboard] {mod_nick}: {message}", "yellow")
        return jsonify({"ok": True, "command": message, **result})

    @app.get("/api/rules")
    def api_rules_get():
        if rules is None:
            return jsonify({"rules": []})
        return jsonify({"rules": rules.list_rules()})

    @app.put("/api/rules/<rule_id>")
    def api_rules_put(rule_id: str):
        if rules is None:
            return jsonify({"ok": False, "error": "rules_unavailable"}), 503
        data = request.get_json(silent=True) or {}
        if "automute" not in data:
            return jsonify({"ok": False, "error": "missing_automute"}), 400
        enabled = bool(data["automute"])
        if not rules.set_automute(rule_id, enabled):
            return jsonify({"ok": False, "error": "unknown_rule"}), 404
        if runtime is not None:
            state = "вкл" if enabled else "выкл"
            runtime.add_log(f"[dashboard] правило {rule_id}: автомут {state}", "yellow")
        return jsonify({"ok": True, "rule": rule_id, "automute": enabled})

    @app.get("/api/online")
    def api_online():
        host, port = _client_endpoint(settings)
        try:
            players = get_online_players(host=host, port=port)
        except ModBridgeError as e:
            return jsonify({"ok": False, "error": str(e)}), 503
        return jsonify({"ok": True, "count": len(players), "players": players})

    @app.get("/api/client/nick")
    def api_client_nick():
        host, port = _client_endpoint(settings)
        try:
            nick = get_client_nick(host=host, port=port)
        except ModBridgeError as e:
            return jsonify({"ok": False, "error": str(e)}), 503
        return jsonify({"ok": True, "nick": nick, "host": host, "port": port})

    @app.get("/api/chat")
    def api_chat():
        host, port = _client_endpoint(settings)
        since = request.args.get("since", 0, type=int)
        try:
            if since < 0:
                result = get_chat_state(host=host, port=port)
            else:
                result = poll_chat(since=since, host=host, port=port)
        except ModBridgeError as e:
            return jsonify({"ok": False, "error": str(e)}), 503
        return jsonify(result)

    @app.post("/api/ml")
    def api_ml():
        host, port = _client_endpoint_from_body(settings)
        try:
            result = run_autologin(host=host, port=port, timeout=120.0, print_logs=False)
        except ModBridgeError as e:
            return jsonify({"ok": False, "error": str(e)}), 503
        return jsonify({"ok": True, "host": host, "port": port, **result})

    @app.post("/api/screenshot")
    def api_screenshot():
        data = request.get_json(silent=True) or {}
        host, port = _client_endpoint_from_body(settings)
        path = (data.get("path") or "").strip()
        if not path:
            pending = os.path.join(settings.base_dir, "photos", "pending")
            os.makedirs(pending, exist_ok=True)
            path = os.path.join(pending, f"dashboard_{int(time.time())}.jpg")
        fmt = (data.get("format") or "jpg").strip().lower() or "jpg"
        try:
            result = request_screenshot(path, host=host, port=port, fmt=fmt)
        except ModBridgeError as e:
            return jsonify({"ok": False, "error": str(e)}), 503
        return jsonify({"ok": True, "host": host, "port": port, **result})

    @app.post("/api/autologin/push")
    def api_autologin_push():
        host, port = _client_endpoint_from_body(settings)
        if not settings.login_accounts:
            return jsonify({"ok": False, "error": "no_login_accounts"}), 400
        try:
            result = push_login_passwords(
                settings.login_accounts,
                host=host,
                screenshot_port=port,
                port_offset=settings.autologin_port_offset,
            )
        except AutologinBridgeError as e:
            return jsonify({"ok": False, "error": str(e)}), 503
        return jsonify({
            "ok": True,
            "host": host,
            "screenshot_port": port,
            "autologin_port": autologin_port_for_screenshot_port(
                port, settings.autologin_port_offset
            ),
            **result,
        })

    @app.get("/api/autologin/status")
    def api_autologin_status():
        host, port = _client_endpoint(settings)
        autologin_port = autologin_port_for_screenshot_port(
            port, settings.autologin_port_offset
        )
        try:
            result = get_autologin_status(host=host, port=autologin_port)
        except AutologinBridgeError as e:
            return jsonify({"ok": False, "error": str(e)}), 503
        return jsonify({
            "ok": True,
            "host": host,
            "screenshot_port": port,
            "autologin_port": autologin_port,
            **result,
        })

    @app.get("/api/photos/<mute_id>")
    def api_photo(mute_id: str):
        path = store.photo_path(mute_id)
        if not path:
            return jsonify({"error": "not found"}), 404
        directory = os.path.dirname(path)
        filename = os.path.basename(path)
        return send_from_directory(directory, filename)

    @app.get("/")
    def index():
        return send_from_directory(dist, "index.html")

    @app.errorhandler(404)
    def spa_fallback(_e):
        if os.path.isfile(os.path.join(dist, "index.html")):
            return send_from_directory(dist, "index.html")
        return jsonify({"error": "dashboard not built"}), 404

    return app


def start_dashboard(
    settings: Settings,
    store: MuteStore,
    runtime: RuntimeState | None = None,
    rules: RulesConfig | None = None,
) -> None:
    dist = os.path.join(settings.base_dir, "dashboard_dist")
    if not os.path.isdir(dist):
        return

    url = f"http://{settings.dashboard_host}:{settings.dashboard_port}"

    def run() -> None:
        app = create_app(store, settings, runtime, rules)
        if runtime is not None:
            runtime.add_log(f"[dashboard] {url}", "yellow")
        else:
            print(f"[dashboard] {url}")
        app.run(
            host=settings.dashboard_host,
            port=settings.dashboard_port,
            threaded=True,
            use_reloader=False,
        )

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
