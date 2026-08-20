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
        <h1>COLOSSEUM</h1>
        <nav className="tabs">
          <button className={tab === "arena" ? "on" : ""} onClick={() => setTab("arena")}>
            Arena
          </button>
          <button className={tab === "history" ? "on" : ""} onClick={() => setTab("history")}>
            History
          </button>
        </nav>
        <div className="health">
          <span className={`dot ${health?.status === "ok" ? "on" : ""}`} />
          {health
            ? `every ${health.interval_s}s · ${health.llm}/${health.storage} · up ${fmtUptime(health.uptime_s)}`
            : "server offline"}
        </div>
      </header>
      {tab === "arena" ? <Arena /> : <History />}
    </div>
  );
}