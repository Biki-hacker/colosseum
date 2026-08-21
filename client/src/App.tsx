import { useEffect, useState } from "react";
import { fetchHealth } from "./api";
import { Arena } from "./Arena";
import { History } from "./History";
import type { Health } from "./types";

type Tab = "arena" | "history";

export function App() {
  const [tab, setTab] = useState<Tab>("arena");
  const [health, setHealth] = useState<Health | null>(null);

  useEffect(() => {
    const poll = () =>
      fetchHealth()
        .then(setHealth)
        .catch(() => setHealth(null));
    void poll();
    const t = setInterval(poll, 5000);
    return () => clearInterval(t);
  }, []);

  const fmtUptime = (s: number) => {
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    return h > 0 ? `${h}h ${m}m` : `${m}m`;
  };

  return (
    <div className="app">
      <header className="app-header">
        <div className="brand">
          <span className="brand-badge">⚡ VS 🛡️</span>
          <h1 className="brand-title">COLOSSEUM</h1>
          <span className="brand-tagline">AI DEBATE ARENA</span>
        </div>

        <nav className="tabs">
          <button
            type="button"
            className={tab === "arena" ? "tab-btn on" : "tab-btn"}
            onClick={() => setTab("arena")}
          >
            ⚔️ Live Arena
          </button>
          <button
            type="button"
            className={tab === "history" ? "tab-btn on" : "tab-btn"}
            onClick={() => setTab("history")}
          >
            📜 Archive
          </button>
        </nav>

        <div className="health">
          <span className={`dot ${health?.status === "ok" ? "on" : ""}`} />
          {health ? (
            <span className="health-text">
              <strong>{health.interval_s}s round</strong> · {health.storage} · up {fmtUptime(health.uptime_s)}
            </span>
          ) : (
            <span className="health-text offline">Connecting to server…</span>
          )}
        </div>
      </header>

      <main className="app-content">{tab === "arena" ? <Arena /> : <History />}</main>
    </div>
  );
}