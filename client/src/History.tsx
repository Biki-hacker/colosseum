import { useCallback, useEffect, useState } from "react";
import { fetchDebate, fetchDebates } from "./api";
import type { Debate, Turn } from "./types";
import { Transcript } from "./Transcript";

const fmt = (iso: string) =>
  new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });

export function History() {
  const [debates, setDebates] = useState<Debate[]>([]);
  const [selected, setSelected] = useState<Debate & { turns: Turn[] } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setDebates(await fetchDebates(30));
      setError(null);
    } catch (e) {
      setError(String(e));
    }
  }, []);

  useEffect(() => {
    void refresh();
    const t = setInterval(() => void refresh(), 15000);
    return () => clearInterval(t);
  }, [refresh]);

  const open = async (id: string) => {
    try {
      setSelected(await fetchDebate(id));
    } catch (e) {
      setError(String(e));
    }
  };

  return (
    <div className="history">
      <div className="history-list">
        <div className="list-head">
          <span>Recent debates</span>
          <button onClick={() => void refresh()}>Refresh</button>
        </div>
        {error && <div className="error-banner">{error}</div>}
        {debates.length === 0 && <div className="empty">No debates yet.</div>}
        {debates.map((d) => (
          <div key={d.id} className={`row ${selected?.id === d.id ? "sel" : ""}`} onClick={() => void open(d.id)}>
            <span className={`badge ${d.status}`}>{d.status}</span>
            <span className="row-topic">{d.topic}</span>
            <span className="row-winner">{d.winner ? d.winner.toUpperCase() : "—"}</span>
            <span className="row-time">{fmt(d.created_at)}</span>
          </div>
        ))}
      </div>
      {selected && (
        <div className="history-detail">
          <div className="detail-head">
            <button onClick={() => setSelected(null)}>← back</button>
            <span className="topic">{selected.topic}</span>
            <span className="winner-tag">{selected.winner?.toUpperCase() ?? selected.status}</span>
          </div>
          <Transcript turns={selected.turns ?? []} />
        </div>
      )}
    </div>
  );
}