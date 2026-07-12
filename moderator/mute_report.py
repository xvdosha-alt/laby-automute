def _format_log_line(entry: dict) -> str:
    ts = entry.get("ts") or ""
    text = entry.get("text") or ""
    if ts:
        return f"[{ts}] {text}"
    return text


def _score_log_line(text: str, nickname: str, command: str, message: str) -> int:
    lowered = text.lower()
    nick = nickname.lower()
    score = 0
    if nick and f"/tempmute {nick}" in lowered:
        score = 100
    elif nick and "/tempmute" in lowered and nick in lowered:
        score = 95
    elif command and command in text:
        score = 90
    elif command:
        parts = command.split()
        if len(parts) > 1 and parts[1].lower() in lowered and "/tempmute" in lowered:
            score = 88
    elif message and message in text:
        score = 50
    elif nick and nick in lowered:
        score = 15
    return score


def find_mute_log_lines(logs: list[dict], mute: dict, window: int = 12) -> list[str]:
    nickname = (mute.get("nickname") or "").strip()
    command = (mute.get("command") or "").strip()
    message = (mute.get("message") or "").strip()

    if not logs:
        return []

    best_idx = None
    best_score = 0
    for index, entry in enumerate(logs):
        score = _score_log_line(entry.get("text", ""), nickname, command, message)
        if score > best_score:
            best_score = score
            best_idx = index

    if best_idx is None or best_score < 15:
        return []

    start = max(0, best_idx - window)
    end = min(len(logs), best_idx + 2)
    return [_format_log_line(logs[i]) for i in range(start, end)]


def build_mute_report(mute: dict, logs: list[dict] | None = None) -> str:
    command = (mute.get("command") or "").strip()
    message = (mute.get("message") or "").strip()
    nickname = (mute.get("nickname") or "").strip()
    reason = (mute.get("reason") or "").strip()
    log_lines = find_mute_log_lines(logs or [], mute)

    parts = ["я не согласен с мутом", ""]

    if nickname or reason:
        meta = []
        if nickname:
            meta.append(nickname)
        if reason:
            meta.append(reason)
        parts.append(" · ".join(meta))
        parts.append("")

    parts.append("команда:")
    parts.append(command or "—")
    parts.append("")

    parts.append("лог:")
    if log_lines:
        parts.extend(log_lines)
    else:
        parts.append("— (лог с момента мута не найден в буфере панели)")
    parts.append("")

    if message:
        parts.append("сообщение:")
        parts.append(message)

    return "\n".join(parts).strip()
