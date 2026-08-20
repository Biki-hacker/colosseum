import type { Turn } from "./types";

export function Transcript({ turns, scores }: { turns: Turn[]; scores?: { optimist: number; pessimist: number } | null }) {
  const rows = [...turns].sort((a, b) => a.position - b.position);
  return (
    <div className="transcript">
      {rows.length === 0 && <div className="empty">No turns yet.</div>}
      {rows.map((t) => {
        const opt = t.speaker === "optimist";
        return (
          <div key={t.position} className={`bubble-row ${opt ? "opt" : "pes"}`}>
            <div className="bubble">
              <div className="bubble-head">
                <span className="speaker-name">{opt ? "OPTIMIST" : "PESSIMIST"}</span>
                <span className="tokens">{t.tokens} tok</span>
              </div>
              <div className="bubble-text">{t.text}</div>
            </div>
          </div>
        );
      })}
      {scores && rows.length > 0 && (
        <div className="score-line">
          Score — <span className="opt">{scores.optimist}</span> : <span className="pes">{scores.pessimist}</span>
        </div>
      )}
    </div>
  );
}