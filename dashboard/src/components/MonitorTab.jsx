import { useCallback, useEffect, useRef, useState } from "react";
import "./MonitorTab.css";

const LEVEL_CLASS = {
  green: "log-green",
  yellow: "log-yellow",
  red: "log-red",
  purple: "log-purple",
  default: "log-default",
};

function readModerationEnabled(runtime) {
  if (typeof runtime?.moderation_enabled === "boolean") {
    return runtime.moderation_enabled;
  }
  if (typeof runtime?.summary?.moderation_enabled === "boolean") {
    return runtime.summary.moderation_enabled;
  }
  return null;
}

export default function MonitorTab() {
  const [clients, setClients] = useState([]);
  const [summary, setSummary] = useState(null);
  const [logs, setLogs] = useState([]);
  const [autoScroll, setAutoScroll] = useState(true);
  const [moderationEnabled, setModerationEnabled] = useState(false);
  const [moderationBusy, setModerationBusy] = useState(false);
  const [moderationError, setModerationError] = useState("");
  const lastLogIdRef = useRef(0);
  const logEndRef = useRef(null);
  const ignoreSyncUntilRef = useRef(0);

  const refresh = useCallback(async () => {
    try {
      const since = lastLogIdRef.current;
      const [runtime, logChunk] = await Promise.all([
        fetch("/api/runtime").then((r) => r.json()),
        fetch(`/api/logs?since=${since}`).then((r) => r.json()),
      ]);
      setClients(runtime.clients || []);
      setSummary(runtime.summary || {});
      const remoteEnabled = readModerationEnabled(runtime);
      if (
        remoteEnabled !== null &&
        Date.now() >= ignoreSyncUntilRef.current
      ) {
        setModerationEnabled(remoteEnabled);
      }
      if (logChunk.logs?.length) {
        lastLogIdRef.current = logChunk.last_id || since;
        setLogs((prev) => {
          const merged = [...prev, ...logChunk.logs];
          return merged.slice(-2000);
        });
      }
    } catch {
      /* ignore */
    }
  }, []);

  const toggleModeration = async () => {
    if (moderationBusy) return;
    const next = !moderationEnabled;
    setModerationBusy(true);
    setModerationError("");
    setModerationEnabled(next);
    ignoreSyncUntilRef.current = Date.now() + 3000;
    try {
      const res = await fetch("/api/moderation", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled: next }),
      });
      let data = {};
      try {
        data = await res.json();
      } catch {
        data = {};
      }
      if (!res.ok || !data.ok) {
        setModerationEnabled(!next);
        setModerationError(
          data.error || `Ошибка ${res.status}: не удалось переключить модерацию`,
        );
        return;
      }
      setModerationEnabled(Boolean(data.enabled));
      ignoreSyncUntilRef.current = Date.now() + 1500;
      refresh();
    } catch {
      setModerationEnabled(!next);
      setModerationError("Нет связи с ботом");
    } finally {
      setModerationBusy(false);
    }
  };

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 1000);
    return () => clearInterval(id);
  }, [refresh]);

  useEffect(() => {
    if (autoScroll && logEndRef.current) {
      logEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [logs, autoScroll]);

  const online = summary?.clients_online ?? 0;
  const total = summary?.clients_known ?? clients.length;

  return (
    <div className="monitor-tab">
      <div className="panel moderation-bar">
        <div className="moderation-status">
          <span
            className={`moderation-dot ${moderationEnabled ? "on" : "off"}`}
          />
          <div>
            <div className="moderation-title">
              {moderationEnabled ? "Модерация активна" : "Модерация остановлена"}
            </div>
            <div className="moderation-hint">
              {moderationEnabled
                ? "Сообщения проверяются, муты выдаются"
                : "Логи идут в панель, автомуты отключены"}
            </div>
            {moderationError ? (
              <div className="moderation-error">{moderationError}</div>
            ) : null}
          </div>
        </div>
        <button
          type="button"
          className={`moderation-btn ${moderationEnabled ? "stop" : "start"}`}
          onClick={toggleModeration}
          disabled={moderationBusy}
        >
          {moderationBusy
            ? "…"
            : moderationEnabled
              ? "Стоп модерации"
              : "Старт модерации"}
        </button>
      </div>

      <div className="grid-3 monitor-kpis">
        <div className="panel kpi">
          <div className="kpi-value">
            {online}/{total}
          </div>
          <div className="kpi-label">Клиентов онлайн</div>
        </div>
        <div className="panel kpi">
          <div className="kpi-value">{summary?.workers ?? "—"}</div>
          <div className="kpi-label">Воркеров</div>
        </div>
        <div className="panel kpi">
          <div className="kpi-value">{summary?.queue_pending ?? 0}</div>
          <div className="kpi-label">В очереди</div>
        </div>
      </div>

      <div className="monitor-grid">
        <div className="panel monitor-clients">
          <div className="panel-title">
            Клиенты · скан {summary?.scan_ports ?? "—"} портов /{" "}
            {summary?.scan_interval ?? 1}с
          </div>
          {clients.length === 0 ? (
            <div className="empty">Нет клиентов</div>
          ) : (
            <ul className="client-list">
              {clients.map((c) => (
                <li
                  key={`${c.host}:${c.port}`}
                  className={`client-card ${c.online ? "online" : "offline"}`}
                >
                  <div className="client-top">
                    <span className={`client-dot ${c.online ? "on" : "off"}`} />
                    <span className="client-nick">{c.nick || "?"}</span>
                    <span className="client-port">:{c.port}</span>
                  </div>
                  <div className="client-meta">
                    <span>{c.online ? "онлайн" : "офлайн"}</span>
                    <span>батч {c.ml_batch ?? 0}/3</span>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="panel monitor-logs">
          <div className="logs-header">
            <div className="panel-title">Логи</div>
            <label className="autoscroll">
              <input
                type="checkbox"
                checked={autoScroll}
                onChange={(e) => setAutoScroll(e.target.checked)}
              />
              автопрокрутка
            </label>
          </div>
          <div className="log-view">
            {logs.length === 0 ? (
              <div className="empty">Ожидание логов…</div>
            ) : (
              logs.map((entry) => (
                <div
                  key={entry.id}
                  className={`log-line ${LEVEL_CLASS[entry.level] || LEVEL_CLASS.default}`}
                >
                  <span className="log-ts">{entry.ts}</span>
                  <span className="log-text">{entry.text}</span>
                </div>
              ))
            )}
            <div ref={logEndRef} />
          </div>
        </div>
      </div>
    </div>
  );
}
