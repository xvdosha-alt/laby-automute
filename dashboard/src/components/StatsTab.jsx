import {
  Bar,
  BarChart,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import "./StatsTab.css";

const COLORS = ["#38bdf8", "#a78bfa", "#f472b6", "#4ade80", "#fbbf24", "#fb7185"];

function toChart(obj) {
  if (!obj) return [];
  return Object.entries(obj).map(([name, value]) => ({ name, value }));
}

export default function StatsTab({ stats }) {
  const reasons = toChart(stats?.by_reason);
  const days = toChart(stats?.by_day);
  const sources = toChart(stats?.by_source);
  const allNicks = stats?.all_nicks ?? [];

  return (
    <div className="stats-tab">
      <div className="grid-3">
        <div className="panel kpi">
          <div className="kpi-value">{stats?.total ?? 0}</div>
          <div className="kpi-label">Всего мутов</div>
        </div>
        <div className="panel kpi">
          <div className="kpi-value">{reasons.length}</div>
          <div className="kpi-label">Причин</div>
        </div>
        <div className="panel kpi">
          <div className="kpi-value">{allNicks.length}</div>
          <div className="kpi-label">Уникальных ников</div>
        </div>
      </div>

      <div className="grid-2 stats-charts">
        <div className="panel">
          <div className="panel-title">Причины мутов</div>
          {reasons.length ? (
            <ResponsiveContainer width="100%" height={260}>
              <PieChart>
                <Pie
                  data={reasons}
                  dataKey="value"
                  nameKey="name"
                  cx="50%"
                  cy="50%"
                  innerRadius={55}
                  outerRadius={95}
                  paddingAngle={3}
                >
                  {reasons.map((_, i) => (
                    <Cell key={i} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    background: "#0d1424",
                    border: "1px solid rgba(99,179,237,0.2)",
                    borderRadius: 8,
                  }}
                />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="empty">Пока нет данных</div>
          )}
          <div className="legend">
            {reasons.map((r, i) => (
              <span key={r.name} className="legend-item">
                <i style={{ background: COLORS[i % COLORS.length] }} />
                {r.name} ({r.value})
              </span>
            ))}
          </div>
        </div>

        <div className="panel">
          <div className="panel-title">Муты по дням</div>
          {days.length ? (
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={days}>
                <XAxis dataKey="name" tick={{ fill: "#7b8ba8", fontSize: 11 }} />
                <YAxis tick={{ fill: "#7b8ba8", fontSize: 11 }} />
                <Tooltip
                  contentStyle={{
                    background: "#0d1424",
                    border: "1px solid rgba(99,179,237,0.2)",
                    borderRadius: 8,
                  }}
                />
                <Bar dataKey="value" fill="url(#barGrad)" radius={[6, 6, 0, 0]} />
                <defs>
                  <linearGradient id="barGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#38bdf8" />
                    <stop offset="100%" stopColor="#a78bfa" />
                  </linearGradient>
                </defs>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="empty">Пока нет данных</div>
          )}
        </div>

        <div className="panel">
          <div className="panel-title">Источник</div>
          {sources.length ? (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={sources} layout="vertical">
                <XAxis type="number" tick={{ fill: "#7b8ba8", fontSize: 11 }} />
                <YAxis
                  type="category"
                  dataKey="name"
                  tick={{ fill: "#7b8ba8", fontSize: 11 }}
                  width={70}
                />
                <Tooltip
                  contentStyle={{
                    background: "#0d1424",
                    border: "1px solid rgba(99,179,237,0.2)",
                    borderRadius: 8,
                  }}
                />
                <Bar dataKey="value" fill="#a78bfa" radius={[0, 6, 6, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="empty">Пока нет данных</div>
          )}
        </div>

        <div className="panel">
          <div className="panel-title">Ники ({allNicks.length})</div>
          <ul className="nick-list nick-list-all">
            {allNicks.length ? (
              allNicks.map((nick) => (
                <li key={nick}>
                  <span className="nick-name">{nick}</span>
                </li>
              ))
            ) : (
              <div className="empty">Пока нет данных</div>
            )}
          </ul>
        </div>
      </div>
    </div>
  );
}
