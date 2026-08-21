import { useCallback, useEffect, useMemo, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { fetchDebate, fetchDebates } from "./api";
import { playClick } from "./sound";
import { Transcript } from "./Transcript";
import { HistorySkeleton, ModalTranscriptSkeleton } from "./Skeleton";
import type { Debate, Turn } from "./types";

const PAGE_SIZE = 6;

const fmtTime = (iso: string) =>
  new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

const fmtDate = (iso: string) =>
  new Date(iso).toLocaleDateString([], { month: "short", day: "numeric" });

export function History() {
  const [debates, setDebates] = useState<Debate[]>([]);
  const [selected, setSelected] = useState<(Debate & { turns: Turn[] }) | null>(null);
  const [loadingDebateId, setLoadingDebateId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [filterWinner, setFilterWinner] = useState<"all" | "optimist" | "pessimist">("all");
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState(false);
  const [page, setPage] = useState(1);

  const refresh = useCallback(async (silent = false) => {
    try {
      if (!silent) setLoading(true);
      const raw = await fetchDebates(100);
      setDebates(raw.filter((d) => d.status === "completed"));
      setError(null);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh(false);
    const t = setInterval(() => void refresh(true), 15000);
    return () => clearInterval(t);
  }, [refresh]);

  // Lock body scroll and prevent Lenis hijacking while modal is open
  useEffect(() => {
    if (selected || loadingDebateId) {
      document.body.classList.add("modal-open");
    } else {
      document.body.classList.remove("modal-open");
    }
    return () => {
      document.body.classList.remove("modal-open");
    };
  }, [selected, loadingDebateId]);

  // Handle escape key to close modal
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        playClick();
        setSelected(null);
        setLoadingDebateId(null);
      }
    };
    if (selected || loadingDebateId) {
      window.addEventListener("keydown", handleKeyDown);
    }
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [selected, loadingDebateId]);

  const open = async (id: string) => {
    playClick();
    setLoadingDebateId(id);
    try {
      const debate = await fetchDebate(id);
      setSelected(debate);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoadingDebateId(null);
    }
  };

  const closeModal = () => {
    playClick();
    setSelected(null);
    setLoadingDebateId(null);
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

  // Reset page when search filter changes
  useEffect(() => {
    setPage(1);
  }, [search, filterWinner]);

  const totalPages = Math.max(1, Math.ceil(filteredDebates.length / PAGE_SIZE));
  const currentPage = Math.min(page, totalPages);
  const paginatedDebates = useMemo(() => {
    const start = (currentPage - 1) * PAGE_SIZE;
    return filteredDebates.slice(start, start + PAGE_SIZE);
  }, [filteredDebates, currentPage]);

  const handlePageChange = (newPage: number) => {
    playClick();
    setPage(newPage);
  };

  // Generate page numbers array with ellipsis if many pages
  const pageNumbers = useMemo(() => {
    if (totalPages <= 5) {
      return Array.from({ length: totalPages }, (_, i) => i + 1);
    }
    const pages: (number | string)[] = [];
    if (currentPage <= 3) {
      pages.push(1, 2, 3, 4, "...", totalPages);
    } else if (currentPage >= totalPages - 2) {
      pages.push(1, "...", totalPages - 3, totalPages - 2, totalPages - 1, totalPages);
    } else {
      pages.push(1, "...", currentPage - 1, currentPage, currentPage + 1, "...", totalPages);
    }
    return pages;
  }, [totalPages, currentPage]);

  // During loading, show ONLY the clay skeleton - do not show anything else
  if (loading && debates.length === 0) {
    return <HistorySkeleton />;
  }

  return (
    <div className="history-stage">
      {/* 1. Minimal Analytics */}
      {completed.length > 0 && (
        <div className="analytics-card">
          <div className="analytics-header">
            <h3 className="analytics-title">WIN RATE DISTRIBUTION</h3>
            <span className="analytics-sub">{completed.length} DEBATES</span>
          </div>

          <div className="win-distribution">
            <div className="win-labels">
              <div className="win-label-item opt-label">
                <span className="win-label-dot opt-dot" />
                <span className="win-label-name">OPTIMIST</span>
                <span className="win-label-val">{optPct}%</span>
              </div>
              <div className="win-label-item pes-label">
                <span className="win-label-val">{pesPct}%</span>
                <span className="win-label-name">PESSIMIST</span>
                <span className="win-label-dot pes-dot" />
              </div>
            </div>

            <div className="win-bar">
              <div
                className="win-opt"
                style={{ width: `${optPct}%` }}
                title={`Optimist: ${optPct}% (${optWins} wins)`}
              >
                {optPct >= 22 ? (
                  <span>OPTIMIST {optPct}%</span>
                ) : optPct >= 10 ? (
                  <span>{optPct}%</span>
                ) : null}
              </div>
              <div
                className="win-pes"
                style={{ width: `${pesPct}%` }}
                title={`Pessimist: ${pesPct}% (${pesWins} wins)`}
              >
                {pesPct >= 22 ? (
                  <span>PESSIMIST {pesPct}%</span>
                ) : pesPct >= 10 ? (
                  <span>{pesPct}%</span>
                ) : null}
              </div>
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
            onClick={() => {
              playClick();
              setFilterWinner("all");
            }}
          >
            ALL ({debates.length})
          </button>
          <button
            type="button"
            className={`filter-btn ${filterWinner === "optimist" ? "active" : ""}`}
            onClick={() => {
              playClick();
              setFilterWinner("optimist");
            }}
          >
            OPTIMIST ({optWins})
          </button>
          <button
            type="button"
            className={`filter-btn ${filterWinner === "pessimist" ? "active" : ""}`}
            onClick={() => {
              playClick();
              setFilterWinner("pessimist");
            }}
          >
            PESSIMIST ({pesWins})
          </button>
          <button
            type="button"
            className="filter-btn"
            onClick={() => {
              playClick();
              void refresh(false);
            }}
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

        {paginatedDebates.map((d) => (
          <div key={d.id} className="debate-card" onClick={() => void open(d.id)}>
            <div className="card-header">
              <span className="card-date">{fmtDate(d.created_at)} {fmtTime(d.created_at)}</span>
              <span className="card-winner">{d.winner ? d.winner.toUpperCase() : "UNDECIDED"}</span>
            </div>
            <h4 className="card-topic">{d.topic}</h4>
          </div>
        ))}
      </div>

      {/* 4. Pagination Controls */}
      {filteredDebates.length > 0 && (
        <div className="pagination-container">
          <span className="pagination-info">
            SHOWING {(currentPage - 1) * PAGE_SIZE + 1}–
            {Math.min(currentPage * PAGE_SIZE, filteredDebates.length)} OF {filteredDebates.length} DEBATES
          </span>

          {totalPages > 1 && (
            <div className="pagination-nav">
              <button
                type="button"
                className="page-btn"
                onClick={() => handlePageChange(1)}
                disabled={currentPage === 1}
                title="First Page"
              >
                «
              </button>
              <button
                type="button"
                className="page-btn"
                onClick={() => handlePageChange(currentPage - 1)}
                disabled={currentPage === 1}
                title="Previous Page"
              >
                ‹ PREV
              </button>

              {pageNumbers.map((p, idx) =>
                typeof p === "number" ? (
                  <button
                    key={p}
                    type="button"
                    className={`page-btn ${p === currentPage ? "active" : ""}`}
                    onClick={() => handlePageChange(p)}
                  >
                    {p}
                  </button>
                ) : (
                  <span key={`ellipsis-${idx}`} className="page-ellipsis">
                    {p}
                  </span>
                )
              )}

              <button
                type="button"
                className="page-btn"
                onClick={() => handlePageChange(currentPage + 1)}
                disabled={currentPage === totalPages}
                title="Next Page"
              >
                NEXT ›
              </button>
              <button
                type="button"
                className="page-btn"
                onClick={() => handlePageChange(totalPages)}
                disabled={currentPage === totalPages}
                title="Last Page"
              >
                »
              </button>
            </div>
          )}
        </div>
      )}

      {/* 5. Modal View (With Lenis scroll prevention & scroll containment) */}
      <AnimatePresence>
        {(selected || loadingDebateId) && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="modal-overlay"
            data-lenis-prevent="true"
            onClick={closeModal}
          >
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 10 }}
              className="modal-card"
              data-lenis-prevent="true"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="modal-header">
                <div>
                  <h3 className="modal-title">
                    {selected ? selected.topic : "Loading debate details..."}
                  </h3>
                  <span className="modal-meta">
                    {selected
                      ? `WINNER: ${selected.winner ? selected.winner.toUpperCase() : "UNDECIDED"} · ${fmtDate(selected.created_at)}`
                      : "RETRIEVING FULL TRANSCRIPT"}
                  </span>
                </div>

                <div className="modal-actions">
                  {selected && (
                    <button type="button" className="action-btn-sm" onClick={copyMarkdown}>
                      {copied ? "COPIED!" : "COPY MARKDOWN"}
                    </button>
                  )}
                  <button type="button" className="action-btn-sm" onClick={closeModal}>
                    CLOSE
                  </button>
                </div>
              </div>

              <div className="modal-body" data-lenis-prevent="true">
                {selected ? (
                  <Transcript turns={selected.turns ?? []} isLive={false} />
                ) : (
                  <ModalTranscriptSkeleton />
                )}
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}