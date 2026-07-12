import { useState } from "react";
import "./HistoryTab.css";

function formatDate(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("ru-RU");
  } catch {
    return iso;
  }
}

const STATUS_LABELS = {
  executed: "замучен",
  pending_manual: "вручную",
  paused: "пауза",
  skipped: "пропуск",
  rejected: "отклонён",
  none: "нет нарушения",
};

function statusClass(status) {
  if (status === "pending_manual") return "pending-manual";
  if (status === "paused") return "status-paused";
  if (status === "skipped") return "status-skipped";
  if (status === "rejected") return "status-rejected";
  if (status === "none") return "status-none";
  return "status-executed";
}

function statusLabel(status) {
  return STATUS_LABELS[status] || status || "—";
}

async function copyMuteReport(muteId) {
  const response = await fetch(`/api/mutes/${muteId}/report`);
  if (!response.ok) {
    throw new Error("report failed");
  }
  const data = await response.json();
  const text = data.text || "";
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }
  const area = document.createElement("textarea");
  area.value = text;
  area.style.position = "fixed";
  area.style.left = "-9999px";
  document.body.appendChild(area);
  area.select();
  document.execCommand("copy");
  document.body.removeChild(area);
}

export default function HistoryTab({ mutes }) {
  const [selected, setSelected] = useState(mutes[0]?.id ?? null);
  const [reportState, setReportState] = useState("idle");
  const [unmuteState, setUnmuteState] = useState("idle");

  const current = mutes.find((m) => m.id === selected) ?? mutes[0];
  const currentStatus = current?.status || "executed";
  const currentManual = currentStatus === "pending_manual";
  const currentExecuted = currentStatus === "executed";
  const hasPhoto = Boolean(current?.photo_file);

  async function handleReport() {
    if (!current?.id || !currentExecuted) return;
    setReportState("loading");
    try {
      await copyMuteReport(current.id);
      setReportState("copied");
      setTimeout(() => setReportState("idle"), 2000);
    } catch {
      setReportState("error");
      setTimeout(() => setReportState("idle"), 2500);
    }
  }

  async function handleUnmute() {
    if (!current?.id || !currentExecuted) return;
    setUnmuteState("loading");
    try {
      const response = await fetch("/api/unmute", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mute_id: current.id }),
      });
      const data = await response.json();
      if (!response.ok || !data.ok) {
        throw new Error(data.error || "unmute failed");
      }
      setUnmuteState("done");
      setTimeout(() => setUnmuteState("idle"), 2000);
    } catch {
      setUnmuteState("error");
      setTimeout(() => setUnmuteState("idle"), 2500);
    }
  }

  const unmuteLabel =
    unmuteState === "loading"
      ? "…"
      : unmuteState === "done"
        ? "Отправлено"
        : unmuteState === "error"
          ? "Ошибка"
          : "Unmute";

  const reportLabel =
    reportState === "loading"
      ? "…"
      : reportState === "copied"
        ? "Скопировано"
        : reportState === "error"
          ? "Ошибка"
          : "Report";

  return (
    <div className="history-tab">
      <div className="history-list panel">
        <div className="panel-title">История ({mutes.length})</div>
        <div className="mute-scroll">
          {mutes.length ? (
            mutes.map((m) => {
              const rowStatus = m.status || "executed";
              const rowClass = statusClass(rowStatus);
              const reasonText = m.reason
                ? `${m.reason} · ${statusLabel(rowStatus)}`
                : statusLabel(rowStatus);
              return (
                <button
                  key={m.id}
                  className={`mute-row ${selected === m.id ? "active" : ""} ${rowClass}`}
                  onClick={() => setSelected(m.id)}
                >
                  {m.photo_file ? (
                    <img
                      src={`/api/photos/${m.id}`}
                      alt=""
                      className="mute-thumb"
                      loading="lazy"
                    />
                  ) : (
                    <div className="mute-thumb mute-thumb-empty">—</div>
                  )}
                  <div className="mute-info">
                    <span className="mute-nick">{m.nickname || "—"}</span>
                    <span className={`mute-reason ${rowClass}`}>{reasonText}</span>
                    {m.note ? <span className="mute-note">{m.note}</span> : null}
                    {m.message ? (
                      <span className="mute-message">{m.message}</span>
                    ) : null}
                    {m.mod_nick ? (
                      <span className="mute-mod">мод: {m.mod_nick}@{m.mod_port}</span>
                    ) : null}
                    <span className="mute-time">{formatDate(m.timestamp)}</span>
                  </div>
                </button>
              );
            })
          ) : (
            <div className="empty">Записей пока нет</div>
          )}
        </div>
      </div>

      <div className="history-detail panel">
        {current ? (
          <>
            {currentManual ? (
              <div className="manual-banner">
                Нарушение есть — наказание выдать вручную в игре
              </div>
            ) : null}
            {!currentExecuted && !currentManual ? (
              <div className={`status-banner ${statusClass(currentStatus)}`}>
                Мут не выдан · {statusLabel(currentStatus)}
                {current.note ? ` — ${current.note}` : ""}
              </div>
            ) : null}
            <div className="detail-header">
              <div>
                <h2>{current.nickname || "—"}</h2>
                <p className="detail-meta">
                  {formatDate(current.timestamp)}
                  {current.duration ? ` · ${current.duration}` : ""}
                  {current.source ? ` · ${current.source}` : ""}
                  {current.mod_nick ? ` · мод ${current.mod_nick}@${current.mod_port}` : ""}
                  {` · ${statusLabel(currentStatus)}`}
                </p>
              </div>
              <div className="detail-actions">
                <div className="detail-actions-row">
                  {currentExecuted ? (
                    <>
                      <button
                        type="button"
                        className="report-btn"
                        onClick={handleReport}
                        disabled={reportState === "loading"}
                        title="Скопировать лог, команду мута и «я не согласен с мутом»"
                      >
                        {reportLabel}
                      </button>
                      <button
                        type="button"
                        className="unmute-btn"
                        onClick={handleUnmute}
                        disabled={unmuteState === "loading"}
                        title={`Отправить /unmute ${current.nickname} в игру`}
                      >
                        {unmuteLabel}
                      </button>
                    </>
                  ) : null}
                </div>
                {current.reason ? (
                  <span className={`reason-badge ${statusClass(currentStatus)}`}>
                    {current.reason}
                  </span>
                ) : null}
              </div>
            </div>
            {current.note ? (
              <div className="detail-note">
                <span className="detail-message-label">Примечание</span>
                <p>{current.note}</p>
              </div>
            ) : null}
            {current.message ? (
              <div className="detail-message">
                <span className="detail-message-label">Сообщение</span>
                <p>{current.message}</p>
              </div>
            ) : null}
            {hasPhoto ? (
              <div className="detail-photo-wrap">
                <img
                  src={`/api/photos/${current.id}`}
                  alt={`Запись ${current.nickname || current.id}`}
                  className="detail-photo"
                />
              </div>
            ) : null}
            {current.command ? (
              <div className="detail-cmd">
                <code>{current.command}</code>
              </div>
            ) : null}
            {current.link && (
              <a
                href={current.link}
                target="_blank"
                rel="noreferrer"
                className="detail-link"
              >
                Скриншот в облаке →
              </a>
            )}
          </>
        ) : (
          <div className="empty">Выберите запись из списка</div>
        )}
      </div>
    </div>
  );
}
