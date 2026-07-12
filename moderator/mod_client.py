import json
import re
import socket


class ModBridgeError(Exception):
    pass


def bridge_request(
    payload: dict,
    host: str = "127.0.0.1",
    port: int = 47823,
    timeout: float = 5.0,
) -> dict:
    request_line = json.dumps(payload, ensure_ascii=False) + "\n"

    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            sock.settimeout(timeout)
            sock.sendall(request_line.encode("utf-8"))

            chunks: list[bytes] = []
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                chunks.append(chunk)
                if b"\n" in chunk:
                    break

            if not chunks:
                raise ModBridgeError("empty_response")

            response_line = b"".join(chunks).split(b"\n", 1)[0].decode("utf-8")
            response = json.loads(response_line)
    except socket.timeout as e:
        raise ModBridgeError("timeout") from e
    except ConnectionRefusedError as e:
        raise ModBridgeError("mod_not_running") from e
    except OSError as e:
        raise ModBridgeError(f"connection_error: {e}") from e
    except json.JSONDecodeError as e:
        raise ModBridgeError("invalid_response") from e

    if not response.get("ok"):
        raise ModBridgeError(response.get("error", "bridge_failed"))

    return response


class ModScreenshotError(ModBridgeError):
    pass


def request_screenshot(
    path: str,
    host: str = "127.0.0.1",
    port: int = 47823,
    timeout: float = 5.0,
    fmt: str = "jpg",
) -> dict:
    return bridge_request(
        {"cmd": "screenshot", "path": path, "format": fmt},
        host=host,
        port=port,
        timeout=timeout,
    )


def get_client_nick(
    host: str = "127.0.0.1",
    port: int = 47823,
    timeout: float = 5.0,
) -> str:
    response = bridge_request({"cmd": "nick"}, host=host, port=port, timeout=timeout)
    nick = response.get("nick")
    if not nick:
        raise ModBridgeError("missing_nick")
    return nick


def resolve_client_nick(
    host: str = "127.0.0.1",
    port: int = 47823,
    timeout: float = 5.0,
    configured_nick: str = "",
) -> str:
    nick = configured_nick.strip()
    if nick:
        return nick
    return get_client_nick(host=host, port=port, timeout=timeout)


def get_chat_state(
    host: str = "127.0.0.1",
    port: int = 47823,
    timeout: float = 5.0,
) -> dict:
    return bridge_request(
        {"cmd": "chat", "since": -1},
        host=host,
        port=port,
        timeout=timeout,
    )


def poll_chat(
    since: int = 0,
    host: str = "127.0.0.1",
    port: int = 47823,
    timeout: float = 5.0,
) -> dict:
    return bridge_request(
        {"cmd": "chat", "since": since},
        host=host,
        port=port,
        timeout=timeout,
    )


def say_as_nick(
    nick: str,
    message: str,
    host: str = "127.0.0.1",
    port: int = 47823,
    timeout: float = 5.0,
) -> dict:
    return bridge_request(
        {"cmd": "say", "nick": nick, "message": message},
        host=host,
        port=port,
        timeout=timeout,
    )


def get_online_players(
    host: str = "127.0.0.1",
    port: int = 47823,
    timeout: float = 5.0,
) -> list[str]:
    response = bridge_request(
        {"cmd": "online"},
        host=host,
        port=port,
        timeout=timeout,
    )
    players = response.get("players")
    if not isinstance(players, list):
        return []
    return [str(nick) for nick in players if nick]


def run_autologin(
    host: str = "127.0.0.1",
    port: int = 47823,
    timeout: float = 120.0,
    *,
    print_logs: bool = True,
) -> dict:
    response = bridge_request(
        {"cmd": "autologin"},
        host=host,
        port=port,
        timeout=timeout,
    )
    if print_logs:
        print_autologin(response)
    return response


def print_autologin(response: dict) -> None:
    servers = _parse_anarchy_servers(response)
    if servers:
        print("[python] анархии (онлайн):")
        for row in servers:
            print(f"  #{row['number']} — {row['online']}")
    else:
        for line in response.get("logs") or []:
            if "дамп слот" in line or line.startswith("  ["):
                continue
            print(line)
    if response.get("error"):
        print(f"[python] ошибка: {response['error']}")


def _parse_anarchy_servers(response: dict) -> list[dict[str, int]]:
    anarchy = response.get("anarchy") or []
    if anarchy:
        return [
            {"number": int(row["number"]), "online": int(row["online"])}
            for row in anarchy
        ]

    heads: list[dict] = []
    for step in response.get("steps") or []:
        found = [
            item
            for item in step.get("slots") or []
            if item.get("id") == "minecraft:player_head" and not item.get("empty")
        ]
        if found:
            heads = found

    if heads:
        return [
            {
                "number": _anarchy_number_from_item(item),
                "online": int(item.get("count") or 0),
            }
            for item in heads
        ]

    rows: list[dict[str, int]] = []
    for line in response.get("logs") or []:
        if "player_head" not in line:
            continue
        match = re.match(r"^\s+\[(\d+)\].*\(minecraft:player_head\)\s+x(\d+)", line)
        if not match:
            continue
        slot = int(match.group(1))
        online = int(match.group(2))
        rows.append(
            {
                "number": slot - 17 if slot >= 18 else online,
                "online": online,
            }
        )
    return rows


def _anarchy_number_from_item(item: dict) -> int:
    name = str(item.get("name") or "")
    match = re.search(r"(?:анархи[яи]|anarchy|lite)\s*#?\s*(\d+)", name, re.I)
    if match:
        return int(match.group(1))
    match = re.search(r"#\s*(\d+)", name)
    if match:
        return int(match.group(1))
    slot = int(item.get("slot") or 0)
    if slot >= 18:
        return slot - 17
    return int(item.get("count") or slot + 1)
