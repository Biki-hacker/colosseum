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

  return (
    <div className="arena">
      <div className="arena-topbar">
        <div className={`conn-pill ${connected ? "ok" : "down"}`}>
          <span className="pulsing-dot" />
          {connected ? "LIVE ARENA" : "RECONNECTING…"}
        </div>
        <div className="arena-controls">
          <button
            type="button"
            className={`sound-toggle ${soundEnabled ? "on" : ""}`}
            onClick={() => setSoundEnabled(!soundEnabled)}
            title={soundEnabled ? "Mute audio cues" : "Enable subtle audio cues"}
          >
            {soundEnabled ? "🔔 Sound On" : "🔕 Sound Off"}
          </button>
        </div>
      </div>

      {current && (
        <div className="debate-header card-glass">
          <div className="topic-badge">Current Resolution</div>
          <h2 className="topic-title">{current.topic}</h2>

          {isOngoing && (
            <div className="round-meta">
              <div className="round-progress-bar">
                <div
                  className="progress-fill"
                  style={{ width: `${(turnProgress / (current.totalTurns || 20)) * 100}%` }}
                />
              </div>
              <div className="round-status-labels">
                <span className="turn-count">
                  Turn <strong>{turnProgress}</strong> of {current.totalTurns || 20}
                </span>
                {current.thinkingSpeaker && (
                  <span className={`thinking-badge ${current.thinkingSpeaker}`}>
                    <span className="pulse-ring" />
                    {current.thinkingSpeaker === "optimist"
                      ? "⚡ OPTIMIST is drafting a counter-argument…"
                      : "🛡️ PESSIMIST is dissecting vulnerabilities…"}
                  </span>
                )}
              </div>
            </div>
          )}

          {current.error && <div className="error-banner">⚠️ Debate interrupted: {current.error}</div>}

          {verdict && (
            <div className={`verdict-podium ${current.winner}`}>
              <div className="podium-glow" />
              <div className="podium-header">
                <span className="trophy-icon">🏆</span>
                <div className="winner-declaration">
                  <span className="sub">CHIEF JUSTICE VERDICT</span>
                  <span className="winner-name">{verdict} WINS</span>
                </div>
              </div>
              {current.scores && (
                <div className="score-meters">
                  <div className="meter opt">
                    <div className="meter-label">
                      <span>OPTIMIST</span>
                      <strong>{current.scores.optimist}/10</strong>
                    </div>
                    <div className="meter-bar">
                      <div className="fill" style={{ width: `${current.scores.optimist * 10}%` }} />
                    </div>
                  </div>
                  <div className="meter pes">
                    <div className="meter-label">
                      <span>PESSIMIST</span>
                      <strong>{current.scores.pessimist}/10</strong>
                    </div>
                    <div className="meter-bar">
                      <div className="fill" style={{ width: `${current.scores.pessimist * 10}%` }} />
                    </div>
                  </div>
                </div>
              )}
              {current.commentary && (
                <div className="judge-commentary">
                  <span className="quote-mark">“</span>
                  {current.commentary}
                  <span className="quote-mark">”</span>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {!current && (
        <div className="waiting-card card-glass">
          <div className="colosseum-gate-icon">⚔️</div>
          <h3 className="waiting-title">Colosseum Awaiting Next Match</h3>
          <p className="waiting-sub">
            The next scheduled resolution will start shortly on the 5-minute schedule.
          </p>
          {recent.length > 0 && (
            <div className="recent-preview">
              <span className="recent-tag">PREVIOUS DEBATE</span>
              <div className="recent-topic">“{recent[0].topic}”</div>
              {recent[0].winner && (
                <span className={`recent-winner ${recent[0].winner}`}>
                  Winner: {recent[0].winner.toUpperCase()}
                </span>
              )}
            </div>
          )}
        </div>
      )}

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