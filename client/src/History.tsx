import { useCallback, useEffect, useMemo, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { fetchDebate, fetchDebates } from "./api";
import { playClick } from "./sound";
import { Transcript } from "./Transcript";
import type { Debate, Turn } from "./types";

const fmtTime = (iso: string) =>
  new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

const fmtDate = (iso: string) =>
  new Date(iso).toLocaleDateString([], { month: "short", day: "numeric" });

export function History() {
  const [debates, setDebates] = useState<Debate[]>([]);
  const [selected, setSelected] = useState<(Debate & { turns: Turn[] }) | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [filterWinner, setFilterWinner] = useState<"all" | "optimist" | "pessimist">("all");
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);

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
    const t = setInterval(() => void refresh(), 15000);
    return () => clearInterval(t);
  }, [refresh]);

  const open = async (id: string) => {
    playClick();
    try {
      setSelected(await fetchDebate(id));
    } catch (e) {
      setError(String(e));
    }
  };

  const closeModal = () => {
    playClick();
    setSelected(null);
  };

  const copyMarkdown = () => {
    if (!selected) return;
    playClick();

    const md = `# COLOSSEUM DEBATE
**Topic:** ${selected.topic}
**Victor:** ${selected.winner ? selected.winner.toUpperCase() : "UNDECIDED"}
**Date:** ${fmtDate(selected.created_at)} ${fmtTime(selected.created_at)}

${(selected.turns || [])
  .map((t) => `**${t.speaker.toUpperCase()} (Turn ${t.position + 1}):**\n${t.text}\n`)
  .join("\n")}
`;

    void navigator.clipboard.writeText(md);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
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
    <div className="history-stage">
      {/* 1. Minimal Analytics */}
      {completed.length > 0 && (
        <div className="analytics-card">
          <div className="analytics-header">
            <h3 className="analytics-title">WIN RATE DISTRIBUTION</h3>
            <span className="analytics-sub">{completed.length} DEBATES</span>
          </div>

          <div className="win-bar">
            <div className="win-opt" style={{ width: `${optPct}%` }}>
              <span>OPTIMIST {optPct}%</span>
            </div>
            <div className="win-pes" style={{ width: `${pesPct}%` }}>
              <span>PESSIMIST {pesPct}%</span>
            </div>
          </div>

          <div className="stats-row">
            <div className="stat-box">
              <span className="stat-num">{optWins}</span>
              <span className="stat-label">OPTIMIST WINS</span>
            </div>
            <div className="stat-box">
              <span className="stat-num">{completed.length}</span>
              <span className="stat-label">TOTAL DEBATES</span>
            </div>
            <div className="stat-box">
              <span className="stat-num">{pesWins}</span>
              <span className="stat-label">PESSIMIST WINS</span>
            </div>
          </div>
        </div>
      )}

      {/* 2. Search & Filter Bar */}
      <div className="filter-bar">
        <input
          type="text"
          className="search-input"
          placeholder="Filter by topic keyword..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />

        <div className="filter-group">
          <button
            type="button"
            className={`filter-btn ${filterWinner === "all" ? "active" : ""}`}
            onClick={() => setFilterWinner("all")}
          >
            ALL ({debates.length})
          </button>
          <button
            type="button"
            className={`filter-btn ${filterWinner === "optimist" ? "active" : ""}`}
            onClick={() => setFilterWinner("optimist")}
          >
            OPTIMIST ({optWins})
          </button>
          <button
            type="button"
            className={`filter-btn ${filterWinner === "pessimist" ? "active" : ""}`}
            onClick={() => setFilterWinner("pessimist")}
          >
            PESSIMIST ({pesWins})
          </button>
          <button
            type="button"
            className="filter-btn"
            onClick={() => void refresh()}
          >
            {loading ? "SYNCING..." : "REFRESH"}
          </button>
        </div>
      </div>

      {error && <div className="error-box">{error}</div>}

      {/* 3. List of Past Debates */}
      <div className="debate-list">
        {filteredDebates.length === 0 && (
          <div className="empty-box">No archived debates found.</div>
        )}

        {filteredDebates.map((d) => (
          <div key={d.id} className="debate-card" onClick={() => void open(d.id)}>
            <div className="card-header">
              <span className="card-date">{fmtDate(d.created_at)} {fmtTime(d.created_at)}</span>
              <span className="card-winner">{d.winner ? d.winner.toUpperCase() : "UNDECIDED"}</span>
            </div>
            <h4 className="card-topic">{d.topic}</h4>
          </div>
        ))}
      </div>

      {/* 4. Modal View */}
      <AnimatePresence>
        {selected && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="modal-overlay"
            onClick={closeModal}
          >
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 10 }}
              className="modal-card"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="modal-header">
                <div>
                  <h3 className="modal-title">{selected.topic}</h3>
                  <span className="modal-meta">
                    WINNER: {selected.winner ? selected.winner.toUpperCase() : "UNDECIDED"} · {fmtDate(selected.created_at)}
                  </span>
                </div>

                <div className="modal-actions">
                  <button type="button" className="action-btn-sm" onClick={copyMarkdown}>
                    {copied ? "COPIED!" : "COPY MARKDOWN"}
                  </button>
                  <button type="button" className="action-btn-sm" onClick={closeModal}>
                    CLOSE
                  </button>
                </div>
              </div>

              <div className="modal-body">
                <Transcript turns={selected.turns ?? []} isLive={false} />
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}