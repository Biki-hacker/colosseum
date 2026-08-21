import type { Speaker, Turn } from "./types";

interface TranscriptProps {
  turns: Turn[];
  scores?: { optimist: number; pessimist: number } | null;
  thinkingSpeaker?: Speaker | null;
}

export function Transcript({ turns, scores, thinkingSpeaker }: TranscriptProps) {
  const rows = [...turns].sort((a, b) => a.position - b.position);

  return (
    <div className="transcript-flow">
      <div className="transcript-section-divider">
        <span className="divider-line" />
        <span className="divider-badge">DISPUTE PROCEEDINGS · COMBAT LOG</span>
        <span className="divider-line" />
      </div>

      {rows.length === 0 && !thinkingSpeaker && (
        <div className="transcript-empty-state">
          <div className="empty-radar-ring" />
          <span className="empty-state-text">Gladiators are formulating opening theses...</span>
        </div>
      )}

      {rows.map((t) => {
        const isOpt = t.speaker === "optimist";
        return (
          <div
            key={t.position}
            className={`speech-entry ${isOpt ? "opt-entry" : "pes-entry"} entry-appear`}
          >
            <div className="speech-crest">
              <div className={`crest-symbol-box ${isOpt ? "opt-box" : "pes-box"}`}>
                <span>{isOpt ? "☀️" : "🌙"}</span>
              </div>
              <div className="crest-connector" />
            </div>

            <div className="speech-content-card">
              <div className="speech-header">
                <div className="speech-speaker-meta">
                  <span className={`speaker-name-tag ${isOpt ? "opt-tag" : "pes-tag"}`}>
                    {isOpt ? "THE OPTIMIST" : "THE PESSIMIST"}
                  </span>
                  <span className="speech-role">
                    {t.position === 0
                      ? "OPENING PROPOSITION"
                      : t.position % 2 === 0
                      ? `ARGUMENT #${Math.floor(t.position / 2) + 1}`
                      : `REBUTTAL #${Math.floor(t.position / 2) + 1}`}
                  </span>
                </div>
                <div className="speech-telemetry">
                  <span className="telemetry-turn">#{t.position + 1}</span>
                  <span className="telemetry-tokens">{t.tokens} TOKENS</span>
                </div>
              </div>

              <div className="speech-body">
                <p className="speech-text">{t.text}</p>
              </div>
            </div>
          </div>
        );
      })}

      {thinkingSpeaker && (
        <div
          className={`speech-entry ${thinkingSpeaker === "optimist" ? "opt-entry" : "pes-entry"} thinking-entry entry-appear`}
        >
          <div className="speech-crest">
            <div
              className={`crest-symbol-box ${thinkingSpeaker === "optimist" ? "opt-box" : "pes-box"} pulsing`}
            >
              <span>{thinkingSpeaker === "optimist" ? "☀️" : "🌙"}</span>
            </div>
          </div>

          <div className="speech-content-card deliberating-card">
            <div className="speech-header">
              <div className="speech-speaker-meta">
                <span
                  className={`speaker-name-tag ${thinkingSpeaker === "optimist" ? "opt-tag" : "pes-tag"}`}
                >
                  {thinkingSpeaker === "optimist" ? "THE OPTIMIST" : "THE PESSIMIST"}
                </span>
                <span className="speech-role">COMPUTING REBUTTAL...</span>
              </div>
              <div className="thinking-waveform-mini">
                <span className="wave-bar" />
                <span className="wave-bar" />
                <span className="wave-bar" />
                <span className="wave-bar" />
              </div>
            </div>

            <div className="deliberating-glow-box">
              <span className="deliberating-caption">
                Synthesizing adversarial counter-punch based on opponent's immediate logic...
              </span>
            </div>
          </div>
        </div>
      )}

      {scores && rows.length > 0 && (
        <div className="transcript-conclusion-banner">
          <span className="banner-title">OFFICIAL ROUND SCORECARD</span>
          <div className="banner-score-row">
            <div className="opt-score-item">
              <span className="item-label">OPTIMIST</span>
              <strong className="item-value">{scores.optimist} / 10</strong>
            </div>
            <span className="score-vs-divider">VS</span>
            <div className="pes-score-item">
              <span className="item-label">PESSIMIST</span>
              <strong className="item-value">{scores.pessimist} / 10</strong>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
