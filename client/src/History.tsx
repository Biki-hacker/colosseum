import { useCallback, useEffect, useMemo, useState } from "react";
import { fetchDebate, fetchDebates } from "./api";
import type { Debate, Turn } from "./types";
import { Transcript } from "./Transcript";

const fmtTime = (iso: string) =>
  new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });

const fmtDate = (iso: string) =>
  new Date(iso).toLocaleDateString([], { month: "short", day: "numeric", year: "numeric" });

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
      const raw = await fetchDebates(50);
      setDebates(raw.filter((d) => d.status === "completed"));
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
  const optPct = completed.length ? Math.round((optWins / completed.length) * 100) : 50;
  const pesPct = completed.length ? 100 - optPct : 50;

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
    <div className="archive-suite">
      {/* Analytics Telemetry Hero */}
      {completed.length > 0 && (
        <div className="analytics-hero-card">
          <div className="analytics-header">
            <span className="analytics-title">HISTORICAL COMBAT TELEMETRY</span>
            <span className="analytics-sample-size">{completed.length} CONCLUDED DISPUTES</span>
          </div>

          {/* Dual Combatant Win Rate Bar */}
          <div className="analytics-distribution-bar">
            <div className="dist-opt" style={{ width: `${optPct}%` }}>
              <span className="dist-label">THE OPTIMIST {optPct}%</span>
            </div>
            <div className="dist-pes" style={{ width: `${pesPct}%` }}>
              <span className="dist-label">THE PESSIMIST {pesPct}%</span>
            </div>
          </div>

          <div className="analytics-stat-grid">
            <div className="analytics-stat-item opt-stat">
              <span className="stat-symbol">☀️</span>
              <div className="stat-data">
                <strong className="stat-val">{optWins}</strong>
                <span className="stat-sub">OPTIMIST VICTORIES</span>
              </div>
            </div>

            <div className="analytics-stat-item center-stat">
              <span className="stat-symbol">🏛️</span>
              <div className="stat-data">
                <strong className="stat-val">{completed.length}</strong>
                <span className="stat-sub">TOTAL RESOLUTIONS</span>
              </div>
            </div>

            <div className="analytics-stat-item pes-stat">
              <span className="stat-symbol">🌙</span>
              <div className="stat-data">
                <strong className="stat-val">{pesWins}</strong>
                <span className="stat-sub">PESSIMIST VICTORIES</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Control & Filter Suite */}
      <div className="archive-control-bar">
        <div className="archive-search-wrapper">
          <span className="search-icon">🔍</span>
          <input
            type="text"
            className="archive-search-input"
            placeholder="Filter resolutions by topic keyword…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          {search && (
            <button type="button" className="search-clear-btn" onClick={() => setSearch("")}>
              ✕
            </button>
          )}
        </div>

        <div className="archive-filter-pills">
          <button
            type="button"
            className={`filter-pill ${filterWinner === "all" ? "active" : ""}`}
            onClick={() => setFilterWinner("all")}
          >
            ALL DISPUTES ({debates.length})
          </button>
          <button
            type="button"
            className={`filter-pill opt-pill ${filterWinner === "optimist" ? "active" : ""}`}
            onClick={() => setFilterWinner("optimist")}
          >
            ☀️ OPTIMIST ({optWins})
          </button>
          <button
            type="button"
            className={`filter-pill pes-pill ${filterWinner === "pessimist" ? "active" : ""}`}
            onClick={() => setFilterWinner("pessimist")}
          >
            🌙 PESSIMIST ({pesWins})
          </button>
          <button
            type="button"
            className="refresh-pill-btn"
            onClick={() => void refresh()}
            title="Refresh database records"
          >
            {loading ? "SYNCING..." : "↻ REFRESH"}
          </button>
        </div>
      </div>

      {error && (
        <div className="archive-alert-error">
          <span>⚠️ Query Error: {error}</span>
        </div>
      )}

      {/* Archive Grid & Modal Detail Layout */}
      <div className="archive-layout-grid">
        <div className="archive-feed-list">
          {filteredDebates.length === 0 && (
            <div className="archive-empty-card">
              <span className="empty-icon">📜</span>
              <h4>No archived disputes match your search criteria</h4>
              <p>Try refining your search terms or clearing active filters.</p>
            </div>
          )}

          {filteredDebates.map((d, index) => {
            const isOpt = d.winner === "optimist";
            const isPes = d.winner === "pessimist";
            const isSelected = selected?.id === d.id;

            return (
              <div
                key={d.id}
                className={`archive-entry-card ${isSelected ? "is-selected" : ""} ${isOpt ? "opt-border" : isPes ? "pes-border" : ""}`}
                onClick={() => void open(d.id)}
              >
                <div className="card-top-row">
                  <div className="card-index-group">
                    <span className="card-roman-index">DISPUTE #{filteredDebates.length - index}</span>
                    <span className="card-status-badge">CONCLUDED</span>
                  </div>
                  <span className="card-timestamp">{fmtDate(d.created_at)} · {fmtTime(d.created_at)}</span>
                </div>

                <h3 className="card-topic-title">{d.topic}</h3>

                <div className="card-bottom-row">
                  <div className="card-winner-seal">
                    <span className="seal-prefix">VICTOR:</span>
                    {d.winner ? (
                      <span className={`seal-name ${d.winner}`}>
                        {d.winner === "optimist" ? "☀️ THE OPTIMIST" : "🌙 THE PESSIMIST"}
                      </span>
                    ) : (
                      <span className="seal-name pending">UNDECIDED</span>
                    )}
                  </div>

                  <span className="card-view-link">INSPECT LOG →</span>
                </div>
              </div>
            );
          })}
        </div>

        {/* Modal / Slide-In Detail Transcript */}
        {selected && (
          <div className="archive-detail-overlay">
            <div className="archive-detail-panel">
              <div className="detail-panel-header">
                <div className="detail-meta-group">
                  <span className="detail-tag">VERDICT DOSSIER · ID {selected.id.slice(0, 8)}</span>
                  <h3 className="detail-resolution-title">{selected.topic}</h3>
                </div>

                <div className="detail-actions">
                  {selected.winner && (
                    <span className={`detail-verdict-seal ${selected.winner}`}>
                      🏆 {selected.winner === "optimist" ? "THE OPTIMIST VICTORIOUS" : "THE PESSIMIST VICTORIOUS"}
                    </span>
                  )}
                  <button type="button" className="close-detail-btn" onClick={() => setSelected(null)}>
                    ✕ CLOSE
                  </button>
                </div>
              </div>

              <div className="detail-panel-scroll">
                <Transcript turns={selected.turns ?? []} />
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
