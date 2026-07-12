import { useCallback, useEffect, useState } from "react";
import "./ApiTab.css";

const ACTIONS = [
  { id: "nick", label: "Ник клиента", method: "GET", path: "/api/client/nick" },
  { id: "online", label: "Онлайн", method: "GET", path: "/api/online" },
  { id: "chat", label: "Чат", method: "GET", path: "/api/chat?since=0" },
  { id: "ml", label: "/ml lite-дамп", method: "POST", path: "/api/ml", slow: true },
  {
    id: "screenshot",
    label: "Скриншот",
    method: "POST",
    path: "/api/screenshot",
    body: {},
  },
  {
    id: "autologin_push",
    label: "Пуш паролей",
    method: "POST",
    path: "/api/autologin/push",
    body: {},
  },
  {
    id: "autologin_status",
    label: "Статус autologin",
    method: "GET",
    path: "/api/autologin/status",
    autologin: true,
  },
];

async function callApi(method, path, host, port, body) {
  const sep = path.includes("?") ? "&" : "?";
  const query = method === "GET" ? `${sep}host=${encodeURIComponent(host)}&port=${port}` : "";
  const url = `${path}${query}`;
  const opts = { method };
  if (method !== "GET") {
    opts.headers = { "Content-Type": "application/json" };
    opts.body = JSON.stringify({ host, port, ...(body || {}) });
  }
  const res = await fetch(url, opts);
  const data = await res.json().catch(() => ({}));
  return { status: res.status, data };
}

export default function ApiTab() {
  const [clients, setClients] = useState([]);
  const [host, setHost] = useState("127.0.0.1");
  const [port, setPort] = useState("47823");
  const [sayNick, setSayNick] = useState("");
  const [sayMessage, setSayMessage] = useState("");
  const [loading, setLoading] = useState(null);
  const [response, setResponse] = useState(null);

  const loadClients = useCallback(async () => {
    try {
      const runtime = await fetch("/api/runtime").then((r) => r.json());
      const list = runtime.clients || [];
      setClients(list);
      if (list.length > 0) {
        setHost((h) => h || list[0].host);
        setPort((p) => p || String(list[0].port));
        setSayNick((n) => n || list[0].nick || "");
      }
    } catch {
      setClients([]);
    }
  }, []);

  useEffect(() => {
    loadClients();
    const id = setInterval(loadClients, 3000);
    return () => clearInterval(id);
  }, [loadClients]);

  const run = async (action, extraBody) => {
    setLoading(action.id);
    setResponse(null);
    try {
      const result = await callApi(action.method, action.path, host, Number(port), extraBody);
      setResponse(result);
    } catch (e) {
      setResponse({ status: 0, data: { ok: false, error: String(e) } });
    } finally {
      setLoading(null);
    }
  };

  const runSay = async () => {
    setLoading("say");
    setResponse(null);
    try {
      const res = await fetch("/api/say", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          host,
          port: Number(port),
          nick: sayNick,
          message: sayMessage,
        }),
      });
      const data = await res.json();
      setResponse({ status: res.status, data });
    } catch (e) {
      setResponse({ status: 0, data: { ok: false, error: String(e) } });
    } finally {
      setLoading(null);
    }
  };

  const pickClient = (c) => {
    setHost(c.host);
    setPort(String(c.port));
    if (c.nick) setSayNick(c.nick);
  };

  return (
    <div className="api-tab">
      <div className="api-grid">
        <div className="panel api-side">
          <div className="panel-title">Клиент</div>
          {clients.length > 0 && (
            <div className="api-client-pick">
              {clients.map((c) => (
                <button
                  key={`${c.host}:${c.port}`}
                  type="button"
                  className={`api-client-btn ${
                    host === c.host && String(port) === String(c.port) ? "active" : ""
                  }`}
                  onClick={() => pickClient(c)}
                >
                  <span className={`dot ${c.online ? "on" : "off"}`} />
                  {c.nick || "?"}:{c.port}
                </button>
              ))}
            </div>
          )}
          <div className="api-fields">
            <label>
              host
              <input value={host} onChange={(e) => setHost(e.target.value)} />
            </label>
            <label>
              port
              <input value={port} onChange={(e) => setPort(e.target.value)} />
            </label>
          </div>

          <div className="panel-title api-subtitle">Действия</div>
          <div className="api-actions">
            {ACTIONS.map((action) => (
              <button
                key={action.id}
                type="button"
                className="api-action-btn"
                disabled={loading !== null}
                onClick={() => run(action, action.body)}
              >
                {loading === action.id ? "…" : action.label}
              </button>
            ))}
          </div>

          <div className="panel-title api-subtitle">Say в чат</div>
          <div className="api-say">
            <input
              placeholder="ник"
              value={sayNick}
              onChange={(e) => setSayNick(e.target.value)}
            />
            <input
              placeholder="сообщение"
              value={sayMessage}
              onChange={(e) => setSayMessage(e.target.value)}
            />
            <button
              type="button"
              className="api-action-btn primary"
              disabled={loading !== null || !sayNick || !sayMessage}
              onClick={runSay}
            >
              {loading === "say" ? "…" : "Отправить"}
            </button>
          </div>
        </div>

        <div className="panel api-response">
          <div className="panel-title">Ответ</div>
          {!response ? (
            <div className="empty">Выбери клиент и нажми действие</div>
          ) : (
            <>
              <div className={`api-status ${response.status >= 200 && response.status < 300 ? "ok" : "err"}`}>
                HTTP {response.status}
              </div>
              <pre className="api-json">{JSON.stringify(response.data, null, 2)}</pre>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
