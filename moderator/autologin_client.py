import json
import socket


class AutologinBridgeError(Exception):
    pass


def autologin_request(
    payload: dict,
    host: str = "127.0.0.1",
    port: int = 47923,
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
                raise AutologinBridgeError("empty_response")

            response_line = b"".join(chunks).split(b"\n", 1)[0].decode("utf-8")
            response = json.loads(response_line)
    except socket.timeout as e:
        raise AutologinBridgeError("timeout") from e
    except ConnectionRefusedError as e:
        raise AutologinBridgeError("mod_not_running") from e
    except OSError as e:
        raise AutologinBridgeError(f"connection_error: {e}") from e
    except json.JSONDecodeError as e:
        raise AutologinBridgeError("invalid_response") from e

    if not response.get("ok"):
        raise AutologinBridgeError(response.get("error", "bridge_failed"))

    return response


def autologin_port_for_screenshot_port(
    screenshot_port: int,
    offset: int = 100,
) -> int:
    return screenshot_port + offset


def set_login_passwords(
    accounts: dict[str, str],
    host: str = "127.0.0.1",
    port: int = 47923,
    timeout: float = 5.0,
) -> dict:
    payload_accounts = [
        {"nick": nick, "password": password}
        for nick, password in accounts.items()
        if nick and password
    ]
    if not payload_accounts:
        raise AutologinBridgeError("empty_accounts")

    return autologin_request(
        {"cmd": "set_passwords", "accounts": payload_accounts},
        host=host,
        port=port,
        timeout=timeout,
    )


def push_login_passwords(
    accounts: dict[str, str],
    host: str,
    screenshot_port: int,
    *,
    port_offset: int = 100,
    timeout: float = 5.0,
) -> dict:
    return set_login_passwords(
        accounts,
        host=host,
        port=autologin_port_for_screenshot_port(screenshot_port, port_offset),
        timeout=timeout,
    )


def get_autologin_status(
    host: str = "127.0.0.1",
    port: int = 47923,
    timeout: float = 5.0,
) -> dict:
    return autologin_request(
        {"cmd": "status"},
        host=host,
        port=port,
        timeout=timeout,
    )
