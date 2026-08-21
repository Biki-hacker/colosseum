import { useEffect, useRef, useState } from "react";
import type { Debate, Speaker, Turn, WsEvent } from "./types";
import { Transcript } from "./Transcript";

interface Current {
  topic: string;
  turns: Turn[];
  winner?: string;
  scores?: { optimist: number; pessimist: number } | null;
  commentary?: string;
  error?: string;
  thinkingSpeaker?: Speaker | null;
  totalTurns?: number;
}

const wsUrl = () => `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws/debates`;

export function Arena() {
  const [connected, setConnected] = useState(false);
  const [recent, setRecent] = useState<Debate[]>([]);
  const [current, setCurrent] = useState<Current | null>(null);
  const [soundEnabled, setSoundEnabled] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  // Play subtle turn notification chime if sound is enabled
  const playChime = () => {
    if (!soundEnabled) return;
    try {
      const ctx = new (window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext)();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "sine";
      osc.frequency.setValueAtTime(587.33, ctx.currentTime); // D5
      osc.frequency.exponentialRampToValueAtTime(880, ctx.currentTime + 0.15); // A5
      gain.gain.setValueAtTime(0.04, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.15);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + 0.15);
    } catch {
      // Audio context might be restricted before interaction
    }
  };

  useEffect(() => {
    let closed = false;
    let retry: ReturnType<typeof setTimeout>;

    const connect = () => {
      const ws = new WebSocket(wsUrl());
      wsRef.current = ws;
      ws.onopen = () => setConnected(true);
      ws.onclose = () => {
        setConnected(false);
        if (!closed) retry = setTimeout(connect, 2000);
      };
      ws.onmessage = (ev) => {
        const msg = JSON.parse(ev.data as string) as WsEvent;
        switch (msg.type) {
          case "recent":
            setRecent(msg.debates);
            break;
          case "active_debate":
            setCurrent({
              topic: msg.topic,
              turns: msg.turns || [],
              thinkingSpeaker: (msg.turns?.length ?? 0) % 2 === 0 ? "optimist" : "pessimist",
              totalTurns: 20,
            });
            break;
          case "debate_started":
            setCurrent({ topic: msg.topic, turns: [], thinkingSpeaker: "optimist", totalTurns: 20 });
            break;
          case "thinking":
            setCurrent((c) => (c ? { ...c, thinkingSpeaker: msg.speaker } : c));
            break;
          case "turn":
            playChime();
            setCurrent((c) =>
              c
                ? {
                    ...c,
                    thinkingSpeaker: msg.speaker === "optimist" ? "pessimist" : "optimist",
                    turns: [
                      ...c.turns,
                      { speaker: msg.speaker, text: msg.text, tokens: msg.tokens, position: msg.position },
                    ],
                  }
                : c,
            );
            break;
          case "debate_completed":
            setCurrent((c) =>
              c
                ? {
                    ...c,
                    thinkingSpeaker: null,
                    winner: msg.winner,
                    scores: { optimist: msg.optimist_score, pessimist: msg.pessimist_score },
                    commentary: msg.commentary,
                  }
                : c,
            );
            break;
          case "debate_failed":
            setCurrent((c) => (c ? { ...c, thinkingSpeaker: null, error: msg.error } : c));
            break;
        }
      };
    };

    connect();
    return () => {
      closed = true;
      clearTimeout(retry);
      wsRef.current?.close();
    };
  }, [soundEnabled]);

  // Smooth scroll to latest turn
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [current?.turns.length, current?.thinkingSpeaker]);

  const verdict = current?.winner ? current.winner.toUpperCase() : null;
  const turnProgress = current ? Math.min(current.turns.length, 20) : 0;
  const isOngoing = current && !current.winner && !current.error;
  const lastSpeaker = current && current.turns.length > 0 ? current.turns[current.turns.length - 1].speaker : null;

  return (
    <div className="arena-stage">
      {/* Top Combatant Head-to-Head Banner */}
      <div className="combatants-roster">
        {/* Optimist Gladiator */}
        <div className={`combatant-card opt-card ${current?.thinkingSpeaker === "optimist" ? "is-deliberating" : lastSpeaker === "optimist" ? "is-speaking" : ""}`}>
          <div className="combatant-avatar opt-avatar">
            <span className="avatar-icon">☀️</span>
            <div className="combatant-pulse-ring" />
          </div>
          <div className="combatant-meta">
            <span className="combatant-tag">CHAMPION ALPHA</span>
            <h3 className="combatant-title">THE OPTIMIST</h3>
            <span className="combatant-desc">Utopian Visionary · 5M Neural</span>
          </div>
          {current?.scores && (
            <div className="combatant-score-badge opt-score-badge">
              <span className="score-num">{current.scores.optimist}</span>
              <span className="score-denom">/10</span>
            </div>
          )}
        </div>

        {/* Center Arena Status */}
        <div className="arena-center-dial">
          <div className="vs-emblem">
            <span className="vs-text">VS</span>
          </div>
          {isOngoing && (
            <div className="dial-meta">
              <span className="dial-turn-tag">ROUND {turnProgress} / 20</span>
              <div className="dial-progress-track">
                <div
                  className="dial-progress-bar"
                  style={{ width: `${(turnProgress / (current.totalTurns || 20)) * 100}%` }}
                />
              </div>
            </div>
          )}
        </div>

        {/* Pessimist Gladiator */}
        <div className={`combatant-card pes-card ${current?.thinkingSpeaker === "pessimist" ? "is-deliberating" : lastSpeaker === "pessimist" ? "is-speaking" : ""}`}>
          <div className="combatant-meta text-right">
            <span className="combatant-tag">CHAMPION OMEGA</span>
            <h3 className="combatant-title">THE PESSIMIST</h3>
            <span className="combatant-desc">Pragmatic Skeptic · 5M Neural</span>
          </div>
          <div className="combatant-avatar pes-avatar">
            <span className="avatar-icon">🌙</span>
            <div className="combatant-pulse-ring" />
          </div>
          {current?.scores && (
            <div className="combatant-score-badge pes-score-badge">
              <span className="score-num">{current.scores.pessimist}</span>
              <span className="score-denom">/10</span>
            </div>
          )}
        </div>
      </div>

      {/* Arena Resolution Stage Header */}
      {current && (
        <div className="resolution-podium">
          <div className="resolution-header-bar">
            <div className="resolution-pill">
              <span className={`pill-dot ${connected ? "online" : "offline"}`} />
              <span>{connected ? "LIVE DISPUTE RESOLUTION" : "RECONNECTING TO ARENA…"}</span>
            </div>

            <div className="resolution-actions">
              <button
                type="button"
                className={`audio-btn ${soundEnabled ? "on" : ""}`}
                onClick={() => setSoundEnabled(!soundEnabled)}
                title={soundEnabled ? "Mute audio chimes" : "Enable ambient audio chimes"}
              >
                {soundEnabled ? "🔔 AUDIO ACTIVE" : "🔕 AUDIO MUTED"}
              </button>
            </div>
          </div>

          <h2 className="resolution-topic">{current.topic}</h2>

          {isOngoing && current.thinkingSpeaker && (
            <div className="deliberation-ticker">
              <div className="ticker-waveform">
                <span className="bar b1" />
                <span className="bar b2" />
                <span className="bar b3" />
                <span className="bar b4" />
                <span className="bar b5" />
              </div>
              <span className="ticker-text">
                {current.thinkingSpeaker === "optimist"
                  ? "THE OPTIMIST is crafting an adversarial counter-thesis..."
                  : "THE PESSIMIST is exposing rhetorical vulnerabilities..."}
              </span>
            </div>
          )}

          {current.error && (
            <div className="arena-alert-error">
              <span className="alert-icon">⚠️</span>
              <span>Dispute halted: {current.error}</span>
            </div>
          )}

          {/* Chief Justice Verdict Podium */}
          {verdict && (
            <div className={`verdict-vault ${current.winner}`}>
              <div className="vault-glow-overlay" />
              <div className="vault-header">
                <div className="laurel-crown">🏛️</div>
                <div className="vault-titles">
                  <span className="vault-pre">HIGH CHIEF JUSTICE DECREE</span>
                  <h3 className="vault-winner-name">{verdict} VICTORIOUS</h3>
                </div>
              </div>

              {current.scores && (
                <div className="vault-score-breakdown">
                  <div className="vault-gauge opt">
                    <div className="gauge-label">
                      <span>THE OPTIMIST</span>
                      <strong>{current.scores.optimist} PTS</strong>
                    </div>
                    <div className="gauge-track">
                      <div className="gauge-fill" style={{ width: `${current.scores.optimist * 10}%` }} />
                    </div>
                  </div>
                  <div className="vault-gauge pes">
                    <div className="gauge-label">
                      <span>THE PESSIMIST</span>
                      <strong>{current.scores.pessimist} PTS</strong>
                    </div>
                    <div className="gauge-track">
                      <div className="gauge-fill" style={{ width: `${current.scores.pessimist * 10}%` }} />
                    </div>
                  </div>
                </div>
              )}

              {current.commentary && (
                <div className="vault-decree-box">
                  <span className="decree-quote">“</span>
                  <p className="decree-text">{current.commentary}</p>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Waiting for Next Match Card */}
      {!current && (
        <div className="sanctum-waiting-card">
          <div className="sanctum-pillar-icon">🏛️</div>
          <h3 className="sanctum-waiting-title">Colosseum Sanctum Awaiting Match</h3>
          <p className="sanctum-waiting-sub">
            The autonomous scheduler initializes disputes every 5-minute cycle.
          </p>
          {recent.length > 0 && (
            <div className="previous-verdict-card">
              <span className="prev-label">LATEST CONCLUDED DISPUTE</span>
              <p className="prev-topic">“{recent[0].topic}”</p>
              {recent[0].winner && (
                <span className={`prev-winner-tag ${recent[0].winner}`}>
                  DECISION: {recent[0].winner.toUpperCase()} VICTORIOUS
                </span>
              )}
            </div>
          )}
        </div>
      )}

      {/* Structured Combat Log */}
      {current && (
        <Transcript
          turns={current.turns}
          scores={current.scores}
          thinkingSpeaker={current.thinkingSpeaker}
        />
      )}

      <div ref={bottomRef} />
    </div>
  );
}
