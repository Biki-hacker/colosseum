import { useCallback, useEffect, useMemo, useState } from "react";
import { fetchDebate, fetchDebates } from "./api";
import type { Debate, Turn } from "./types";
import { Transcript } from "./Transcript";

const fmt = (iso: string) =>
  new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });

const fmtDate = (iso: string) =>
  new Date(iso).toLocaleDateString([], { month: "short", day: "numeric" });

export function History() {
  const [debates, setDebates] = useState<Debate[]>([]);
  const [selected, setSelected] = useState<(Debate & { turns: Turn[] }) | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [filterWinner, setFilterWinner] = useState<"all" | "optimist" | "pessimist">("all");
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    try {
      setLoading(true);
      setDebates(await fetchDebates(50));
      setError(null);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
    const t = setInterval(() => void refresh(), 20000);
    return () => clearInterval(t);
  }, [refresh]);

  const open = async (id: string) => {
    try {
      setSelected(await fetchDebate(id));
    } catch (e) {
      setError(String(e));
    }
  };

  const completed = useMemo(() => debates.filter((d) => d.status === "completed"), [debates]);
  const optWins = useMemo(() => completed.filter((d) => d.winner === "optimist").length, [completed]);
  const pesWins = useMemo(() => completed.filter((d) => d.winner === "pessimist").length, [completed]);

  const filteredDebates = useMemo(() => {
    return debates.filter((d) => {
      const matchSearch = search.trim() === "" || d.topic.toLowerCase().includes(search.toLowerCase());
      const matchFilter =
        filterWinner === "all" ||
        (filterWinner === "optimist" && d.winner === "optimist") ||
        (filterWinner === "pessimist" && d.winner === "pessimist");
      return matchSearch && matchFilter;
    });
  }, [debates, search, filterWinner]);

  return (
    <div className="history">
      {/* Stats Widget */}
      {completed.length > 0 && (
        <div className="history-stats card-glass">
          <div className="stat-card">
            <span className="stat-num">{completed.length}</span>
            <span className="stat-label">Total Debates</span>
          </div>
          <div className="stat-card opt">
            <span className="stat-num">{optWins}</span>
            <span className="stat-label">
              Optimist Wins ({completed.length ? Math.round((optWins / completed.length) * 100) : 0}%)
            </span>
          </div>
          <div className="stat-card pes">
            <span className="stat-num">{pesWins}</span>
            <span className="stat-label">
              Pessimist Wins ({completed.length ? Math.round((pesWins / completed.length) * 100) : 0}%)
            </span>
          </div>
        </div>
      )}

      <div className="history-controls">
        <div className="search-box">
          <input
            type="text"
            placeholder="Search debate topics…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <div className="filter-tabs">
          <button
            type="button"
            className={filterWinner === "all" ? "active" : ""}
            onClick={() => setFilterWinner("all")}
          >
            All ({debates.length})
          </button>
          <button
            type="button"
            className={filterWinner === "optimist" ? "active opt" : "opt"}
            onClick={() => setFilterWinner("optimist")}
          >
            ⚡ Optimist ({optWins})
          </button>
          <button
            type="button"
            className={filterWinner === "pessimist" ? "active pes" : "pes"}
            onClick={() => setFilterWinner("pessimist")}
          >
            🛡️ Pessimist ({pesWins})
          </button>
          <button type="button" className="refresh-btn" onClick={() => void refresh()}>
            {loading ? "…" : "↻ Refresh"}
          </button>
        </div>
      </div>

      {error && <div className="error-banner">⚠️ {error}</div>}

      <div className="history-grid">
        <div className="history-list">
          {filteredDebates.length === 0 && (
            <div className="empty-card card-glass">No debates found matching the criteria.</div>
          )}

          {filteredDebates.map((d) => {
            const isOpt = d.winner === "optimist";
            const isPes = d.winner === "pessimist";
            const isSelected = selected?.id === d.id;

            return (
              <div
                key={d.id}
                className={`history-row card-glass ${isSelected ? "selected" : ""} ${isOpt ? "opt-win" : isPes ? "pes-win" : ""}`}
                onClick={() => void open(d.id)}
              >
                <div className="row-left">
                  <span className={`status-badge ${d.status}`}>{d.status}</span>
                  <div className="topic-text">{d.topic}</div>
                </div>
                <div className="row-right">
                  {d.winner ? (
                    <span className={`winner-pill ${d.winner}`}>
                      {d.winner === "optimist" ? "⚡ OPTIMIST" : "🛡️ PESSIMIST"}
                    </span>
                  ) : (
                    <span className="winner-pill pending">—</span>
                  )}
                  <span className="time-text">
                    {fmtDate(d.created_at)} · {fmt(d.created_at)}
                  </span>
                </div>
              </div>
            );
          })}
        </div>

        {selected && (
          <div className="history-detail card-glass">
            <div className="detail-header">
              <button type="button" className="back-btn" onClick={() => setSelected(null)}>
                ✕ Close
              </button>
              <div className="detail-topic">
                <span className="topic-badge">Resolution Archive</span>
                <h3>{selected.topic}</h3>
              </div>
              {selected.winner && (
                <div className={`detail-winner-badge ${selected.winner}`}>
                  🏆 {selected.winner.toUpperCase()} VICTORIOUS
                </div>
              )}
            </div>

            <div className="detail-transcript-wrapper">
              <Transcript turns={selected.turns ?? []} />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}