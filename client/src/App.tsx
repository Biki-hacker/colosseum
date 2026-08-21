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
    <div className="app-container">
      {/* Background ambient lighting */}
      <div className="ambient-glow opt-glow" />
      <div className="ambient-glow pes-glow" />

      <header className="site-header">
        <div className="brand-group">
          <div className="brand-crest">
            <span className="crest-symbol">🏛️</span>
          </div>
          <div className="brand-text">
            <h1 className="brand-title">COLOSSEUM</h1>
            <span className="brand-sub">AUTONOMOUS ADVERSARIAL ARENA</span>
          </div>
        </div>

        <nav className="nav-segment">
          <button
            type="button"
            className={`nav-item ${tab === "arena" ? "active" : ""}`}
            onClick={() => setTab("arena")}
          >
            <span className="nav-icon">⚔️</span>
            <span className="nav-label">LIVE ARENA</span>
          </button>
          <button
            type="button"
            className={`nav-item ${tab === "history" ? "active" : ""}`}
            onClick={() => setTab("history")}
          >
            <span className="nav-icon">📜</span>
            <span className="nav-label">VERDICT ARCHIVE</span>
          </button>
        </nav>

        <div className="telemetry-chip">
          <span className={`status-diamond ${health?.status === "ok" ? "online" : "offline"}`} />
          {health ? (
            <div className="telemetry-info">
              <span className="telemetry-primary">{health.interval_s}s CADENCE · {health.storage.toUpperCase()}</span>
              <span className="telemetry-secondary">UPTIME {fmtUptime(health.uptime_s)}</span>
            </div>
          ) : (
            <div className="telemetry-info">
              <span className="telemetry-primary">CONNECTING...</span>
            </div>
          )}
        </div>
      </header>

      <main className="main-viewport">{tab === "arena" ? <Arena /> : <History />}</main>
    </div>
  );
}
