import { useCallback, useEffect, useState } from "react";
import ApiTab from "./components/ApiTab";
import HistoryTab from "./components/HistoryTab";
import MonitorTab from "./components/MonitorTab";
import RulesTab from "./components/RulesTab";
import StatsTab from "./components/StatsTab";
import "./App.css";

const TABS = [
  { id: "api", label: "API" },
  { id: "stats", label: "Статистика" },
  { id: "history", label: "История мутов" },
  { id: "rules", label: "Правила" },
  { id: "monitor", label: "Клиенты" },
];

export default function App() {
  const [tab, setTab] = useState("stats");
  const [stats, setStats] = useState(null);
  const [mutes, setMutes] = useState([]);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const [s, m] = await Promise.all([
        fetch("/api/stats").then((r) => r.json()),
        fetch("/api/mutes").then((r) => r.json()),
      ]);
      setStats(s);
      setMutes(m);
    } catch {
      setStats({ total: 0, by_reason: {}, by_day: {}, by_source: {}, all_nicks: [] });
      setMutes([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 5000);
    return () => clearInterval(id);
  }, [refresh]);

  return (
    <div className="app">
      <div className="bg-glow" />
      <header className="header">
        <div className="logo">
          <span className="logo-cube" />
          <div>
            <h1>Laby AutoMute</h1>
            <p>Локальная панель модерации</p>
          </div>
        </div>
        <nav className="tabs">
          {TABS.map((t) => (
            <button
              key={t.id}
              className={`tab ${tab === t.id ? "active" : ""}`}
              onClick={() => setTab(t.id)}
            >
              {t.label}
            </button>
          ))}
        </nav>
        <div className="header-stat">
          <span className="stat-num">{stats?.total ?? "—"}</span>
          <span className="stat-label">мутов</span>
        </div>
      </header>

      <main className="main">
        {loading && tab !== "monitor" ? (
          <div className="loader">Загрузка…</div>
        ) : tab === "api" ? (
          <ApiTab />
        ) : tab === "stats" ? (
          <StatsTab stats={stats} />
        ) : tab === "history" ? (
          <HistoryTab mutes={mutes} />
        ) : tab === "rules" ? (
          <RulesTab />
        ) : tab === "monitor" ? (
          <MonitorTab />
        ) : null}
      </main>
    </div>
  );
}
