import { useCallback, useEffect, useState } from "react";
import "./RulesTab.css";

const SOURCE_LABELS = {
  heuristic: "эвристика",
  ml: "ML",
  both: "эвристика + ML",
  manual: "только вручную",
};

export default function RulesTab() {
  const [rules, setRules] = useState([]);
  const [loading, setLoading] = useState(true);
  const [savingId, setSavingId] = useState(null);

  const refresh = useCallback(async () => {
    try {
      const response = await fetch("/api/rules");
      const data = await response.json();
      setRules(data.rules || []);
    } catch {
      setRules([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  async function toggleAutomute(rule) {
    const next = !rule.automute;
    setSavingId(rule.id);
    try {
      const response = await fetch(`/api/rules/${rule.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ automute: next }),
      });
      if (!response.ok) {
        throw new Error("save failed");
      }
      setRules((prev) =>
        prev.map((item) =>
          item.id === rule.id ? { ...item, automute: next } : item,
        ),
      );
    } catch {
      await refresh();
    } finally {
      setSavingId(null);
    }
  }

  if (loading) {
    return <div className="loader">Загрузка…</div>;
  }

  return (
    <div className="rules-tab panel">
      <div className="panel-title">Правила модерации</div>
      <p className="rules-hint">
        Отключите автомут для правила — бот не будет выдавать мут по этому
        пункту (эвристика и ML). Ручные наказания в игре не затрагиваются.
      </p>
      <div className="rules-list">
        {rules.map((rule) => (
          <div key={rule.id} className="rule-row">
            <div className="rule-info">
              <span className="rule-id">{rule.id}</span>
              <span className="rule-title">{rule.title}</span>
              <span className="rule-meta">
                {SOURCE_LABELS[rule.source] || rule.source} · {rule.duration}
              </span>
            </div>
            <label className="rule-toggle">
              <input
                type="checkbox"
                checked={rule.automute}
                disabled={savingId === rule.id}
                onChange={() => toggleAutomute(rule)}
              />
              <span>Автомут</span>
            </label>
          </div>
        ))}
      </div>
    </div>
  );
}
