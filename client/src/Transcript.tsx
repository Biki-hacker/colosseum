import type { Speaker, Turn } from "./types";

interface TranscriptProps {
  turns: Turn[];
  scores?: { optimist: number; pessimist: number } | null;
  thinkingSpeaker?: Speaker | null;
}

export function Transcript({ turns, scores, thinkingSpeaker }: TranscriptProps) {
  const rows = [...turns].sort((a, b) => a.position - b.position);

  return (
    <div className="transcript">
      {rows.length === 0 && !thinkingSpeaker && (
        <div className="empty-transcript">
          <div className="empty-pulse" />
          <span>Opening arguments are being prepared…</span>
        </div>
      )}

      {rows.map((t) => {
        const opt = t.speaker === "optimist";
        return (
          <div key={t.position} className={`bubble-row ${opt ? "opt" : "pes"} fade-in-up`}>
            <div className="avatar-badge">{opt ? "⚡" : "🛡️"}</div>
            <div className="bubble">
              <div className="bubble-head">
                <span className="speaker-name">{opt ? "OPTIMIST" : "PESSIMIST"}</span>
                <div className="bubble-meta">
                  <span className="turn-tag">Turn #{t.position + 1}</span>
                  <span className="tokens">{t.tokens} tok</span>
                </div>
              </div>
              <div className="bubble-text">{t.text}</div>
            </div>
          </div>
        );
      })}

      {thinkingSpeaker && (
        <div className={`bubble-row ${thinkingSpeaker === "optimist" ? "opt" : "pes"} thinking-row fade-in-up`}>
          <div className="avatar-badge">{thinkingSpeaker === "optimist" ? "⚡" : "🛡️"}</div>
          <div className="bubble thinking-bubble">
            <div className="bubble-head">
              <span className="speaker-name">
                {thinkingSpeaker === "optimist" ? "OPTIMIST" : "PESSIMIST"}
              </span>
              <span className="deliberating-text">Deliberating counter-punch…</span>
            </div>
            <div className="typing-indicator">
              <span className="dot" />
              <span className="dot" />
              <span className="dot" />
            </div>
          </div>
        </div>
      )}

      {scores && rows.length > 0 && (
        <div className="transcript-score-card">
          <span className="score-title">Final Round Scorecard</span>
          <div className="score-split">
            <span className="opt-score">OPTIMIST: {scores.optimist}</span>
            <span className="vs-divider">VS</span>
            <span className="pes-score">PESSIMIST: {scores.pessimist}</span>
          </div>
        </div>
      )}
    </div>
  );
}