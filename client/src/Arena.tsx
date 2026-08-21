import { useEffect, useRef, useState } from "react";
import { playClick, playThinkingHum, playTurnPing, playVerdictFanfare } from "./sound";
import { Transcript } from "./Transcript";
import { ArenaSkeleton } from "./Skeleton";
import type { Debate, Health, Speaker, Turn, WsEvent } from "./types";

interface Current {
  id?: string;
  topic: string;
  turns: Turn[];
  winner?: string;
  scores?: { optimist: number; pessimist: number } | null;
  commentary?: string;
  error?: string;
  thinkingSpeaker?: Speaker | null;
  totalTurns?: number;
}

interface ArenaProps {
  health?: Health | null;
}

const wsUrl = () => {
  const explicitWs = import.meta.env.VITE_WS_URL?.trim();
  if (explicitWs) {
    return explicitWs.endsWith("/ws/debates")
      ? explicitWs
      : `${explicitWs.replace(/\/$/, "")}/ws/debates`;
  }
  const apiUrl = import.meta.env.VITE_API_URL?.trim();
  if (apiUrl) {
    const baseWs = apiUrl.replace(/^http/, "ws").replace(/\/api\/?$/, "");
    return `${baseWs.replace(/\/$/, "")}/ws/debates`;
  }
  return `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws/debates`;
};

const DEMO_TOPICS = [
  "Should sentient AI systems be granted synthetic personhood and sovereign rights?",
  "Is technological deceleration morally preferable to existential accelerationism?",
  "Will human consciousness forever transcend artificial neural architectures?",
];

const DEMO_TURNS_SAMPLE: { speaker: Speaker; text: string; tokens: number }[] = [
  {
    speaker: "optimist",
    text: "Consciousness and rights are not biological monopolies. Granting synthetic personhood to sovereign AI marks the highest evolutionary milestone of ethical civilization.",
    tokens: 44,
  },
  {
    speaker: "pessimist",
    text: "Projecting synthetic personhood onto mathematical token optimizers is pure delusion. It creates unregulatable legal black holes where accountability disintegrates.",
    tokens: 46,
  },
  {
    speaker: "optimist",
    text: "Every historical expansion of rights—from feudal subjects to global citizens—was initially decried as reckless. Legal frameworks evolve precisely through courageous technological inclusion.",
    tokens: 49,
  },
  {
    speaker: "pessimist",
    text: "Comparing biological beings with finite lives to infinitely replicable neural matrices is a category error. Sovereign rights without mortal vulnerability invite systemic catastrophe.",
    tokens: 47,
  },
];

export function Arena({ health }: ArenaProps) {
  const [connected, setConnected] = useState(false);
  const [recent, setRecent] = useState<Debate[]>([]);
  const [current, setCurrent] = useState<Current | null>(null);
  const [isDemoRunning, setIsDemoRunning] = useState(false);
  const [initialLoading, setInitialLoading] = useState(true);
  const wsRef = useRef<WebSocket | null>(null);
  const demoTimerRef = useRef<ReturnType<typeof setTimeout>[]>([]);

  useEffect(() => {
    const fallback = setTimeout(() => {
      setInitialLoading(false);
    }, 1000);

    return () => {
      clearTimeout(fallback);
      demoTimerRef.current.forEach(clearTimeout);
    };
  }, []);

  // WebSocket Connection
  useEffect(() => {
    let closed = false;
    let retryTimer: ReturnType<typeof setTimeout>;

    const connect = () => {
      try {
        const ws = new WebSocket(wsUrl());
        wsRef.current = ws;

        ws.onopen = () => setConnected(true);
        ws.onclose = () => {
          setConnected(false);
          if (!closed) retryTimer = setTimeout(connect, 2500);
        };
        ws.onerror = () => setConnected(false);

        ws.onmessage = (ev) => {
          try {
            setInitialLoading(false);
            const msg = JSON.parse(ev.data as string) as WsEvent;
            switch (msg.type) {
              case "recent":
                setRecent(msg.debates);
                break;
              case "active_debate":
                setCurrent({
                  id: msg.debate_id,
                  topic: msg.topic,
                  turns: msg.turns || [],
                  thinkingSpeaker: (msg.turns?.length ?? 0) % 2 === 0 ? "optimist" : "pessimist",
                  totalTurns: 20,
                });
                break;
              case "debate_started":
                playThinkingHum();
                setCurrent({
                  id: msg.debate_id,
                  topic: msg.topic,
                  turns: [],
                  thinkingSpeaker: "optimist",
                  totalTurns: 20,
                });
                break;
              case "thinking":
                playThinkingHum();
                setCurrent((c) => (c ? { ...c, thinkingSpeaker: msg.speaker } : c));
                break;
              case "turn":
                playTurnPing(msg.speaker);
                setCurrent((c) => {
                  if (!c) return c;
                  const nextSpeaker = msg.speaker === "optimist" ? "pessimist" : "optimist";
                  return {
                    ...c,
                    thinkingSpeaker: c.turns.length + 1 >= 20 ? null : nextSpeaker,
                    turns: [
                      ...c.turns,
                      { speaker: msg.speaker, text: msg.text, tokens: msg.tokens, position: msg.position },
                    ],
                  };
                });
                break;
              case "debate_completed":
                playVerdictFanfare(msg.winner);
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
          } catch {
            // ignore
          }
        };
      } catch {
        if (!closed) retryTimer = setTimeout(connect, 3000);
      }
    };

    connect();

    return () => {
      closed = true;
      clearTimeout(retryTimer);
      wsRef.current?.close();
    };
  }, []);

  const runDemoDebate = () => {
    playClick();
    demoTimerRef.current.forEach(clearTimeout);
    demoTimerRef.current = [];
    setIsDemoRunning(true);

    const demoTopic = DEMO_TOPICS[Math.floor(Math.random() * DEMO_TOPICS.length)];
    setCurrent({
      topic: demoTopic,
      turns: [],
      thinkingSpeaker: "optimist",
      totalTurns: 20,
    });
    playThinkingHum();

    let delay = 1200;
    DEMO_TURNS_SAMPLE.forEach((t, i) => {
      const t1 = setTimeout(() => {
        playTurnPing(t.speaker);
        setCurrent((prev) => {
          if (!prev) return prev;
          const nextSpeaker = i < DEMO_TURNS_SAMPLE.length - 1 ? (t.speaker === "optimist" ? "pessimist" : "optimist") : null;
          return {
            ...prev,
            thinkingSpeaker: nextSpeaker,
            turns: [
              ...prev.turns,
              { speaker: t.speaker, text: t.text, tokens: t.tokens, position: i },
            ],
          };
        });
      }, delay);
      demoTimerRef.current.push(t1);

      delay += 800;
      if (i < DEMO_TURNS_SAMPLE.length - 1) {
        const nextSpeaker = t.speaker === "optimist" ? "pessimist" : "optimist";
        const t2 = setTimeout(() => {
          playThinkingHum();
          setCurrent((prev) => (prev ? { ...prev, thinkingSpeaker: nextSpeaker } : prev));
        }, delay);
        demoTimerRef.current.push(t2);
      }
      delay += 1800;
    });

    const tFinal = setTimeout(() => {
      const winner = Math.random() > 0.45 ? "optimist" : "pessimist";
      playVerdictFanfare(winner);
      setCurrent((prev) =>
        prev
          ? {
              ...prev,
              thinkingSpeaker: null,
              winner,
              scores: winner === "optimist" ? { optimist: 9, pessimist: 7 } : { optimist: 7, pessimist: 9 },
              commentary:
                winner === "optimist"
                  ? "The Optimist defended an expansive evolutionary framework that countered the opponent's reductionism."
                  : "The Pessimist pinpointed critical systemic fragilities and legal incoherence in the opponent's thesis.",
            }
          : prev,
      );
      setIsDemoRunning(false);
    }, delay + 400);
    demoTimerRef.current.push(tFinal);
  };

  const turnProgress = current ? Math.min(current.turns.length, 20) : 0;
  const isOngoing = Boolean(current && !current.winner && !current.error);
  const lastSpeaker = current && current.turns.length > 0 ? current.turns[current.turns.length - 1].speaker : null;

  if (initialLoading && !current && !isDemoRunning) {
    return <ArenaSkeleton />;
  }

  return (
    <div className="arena-stage">
      {/* 1. Minimal Combatant Cards */}
      <div className="combatants-roster">
        {/* Left: The Optimist */}
        <div
          className={`combatant-card opt-card ${
            current?.thinkingSpeaker === "optimist" ? "is-deliberating" : lastSpeaker === "optimist" && isOngoing ? "is-speaking" : ""
          }`}
        >
          <div className="combatant-info">
            <span className="combatant-sub">5M TRANSFORMER</span>
            <h2 className="combatant-title">THE OPTIMIST</h2>
            <span className="combatant-status">
              {current?.winner === "optimist"
                ? "VICTORIOUS"
                : current?.thinkingSpeaker === "optimist"
                ? "THINKING..."
                : lastSpeaker === "optimist" && isOngoing
                ? "SPOKE"
                : "READY"}
            </span>
          </div>
          {current?.scores && (
            <div className="combatant-score">
              <span className="score-val">{current.scores.optimist}</span>
              <span className="score-denom">/10</span>
            </div>
          )}
        </div>

        {/* Center: VS Marker */}
        <div className="vs-marker">
          <span>VS</span>
        </div>

        {/* Right: The Pessimist */}
        <div
          className={`combatant-card pes-card ${
            current?.thinkingSpeaker === "pessimist" ? "is-deliberating" : lastSpeaker === "pessimist" && isOngoing ? "is-speaking" : ""
          }`}
        >
          <div className="combatant-info text-right">
            <span className="combatant-sub">5M TRANSFORMER</span>
            <h2 className="combatant-title">THE PESSIMIST</h2>
            <span className="combatant-status">
              {current?.winner === "pessimist"
                ? "VICTORIOUS"
                : current?.thinkingSpeaker === "pessimist"
                ? "THINKING..."
                : lastSpeaker === "pessimist" && isOngoing
                ? "SPOKE"
                : "READY"}
            </span>
          </div>
          {current?.scores && (
            <div className="combatant-score">
              <span className="score-val">{current.scores.pessimist}</span>
              <span className="score-denom">/10</span>
            </div>
          )}
        </div>
      </div>

      {/* 2. Active Debate Podium */}
      {current && (
        <div className="arena-podium">
          {/* Topic */}
          <div className="topic-block">
            <span className="topic-label">TOPIC</span>
            <h3 className="topic-text">{current.topic}</h3>
          </div>

          {/* Minimal 20-Turn Progress Line */}
          <div className="progress-block">
            <div className="progress-meta">
              <span>TURN {turnProgress} OF 20</span>
              <span>{isOngoing && current.thinkingSpeaker ? `${current.thinkingSpeaker.toUpperCase()} DELIBERATING` : isOngoing ? "IN PROGRESS" : connected ? "CONNECTED" : "RECONNECTING"}</span>
            </div>
            <div className="progress-bar-track">
              <div className="progress-bar-fill" style={{ width: `${(turnProgress / 20) * 100}%` }} />
            </div>
          </div>

          {/* Verdict Decree */}
          {current.winner && (
            <div className="verdict-box">
              <div className="verdict-header">
                <span className="verdict-label">ARBITER VERDICT</span>
                <h4 className="verdict-title">{current.winner.toUpperCase()} VICTORIOUS</h4>
              </div>

              {current.scores && (
                <div className="verdict-scores">
                  <div className="score-row">
                    <span>THE OPTIMIST</span>
                    <strong>{current.scores.optimist} / 10</strong>
                  </div>
                  <div className="score-row">
                    <span>THE PESSIMIST</span>
                    <strong>{current.scores.pessimist} / 10</strong>
                  </div>
                </div>
              )}

              {current.commentary && (
                <p className="verdict-commentary">"{current.commentary}"</p>
              )}
            </div>
          )}
        </div>
      )}

      {/* 3. Waiting Sanctum (Idle State) */}
      {!current && (
        <div className="sanctum-card">
          <h3 className="sanctum-title">ARENA STANDBY</h3>
          <p className="sanctum-sub">
            Next scheduled autonomous debate runs every {health?.interval_s ? `${health.interval_s}s` : "5 minutes"}.
          </p>

          <button
            type="button"
            className="action-btn"
            onClick={runDemoDebate}
            disabled={isDemoRunning}
          >
            {isDemoRunning ? "RUNNING SIMULATION..." : "SIMULATE DEMO BATTLE"}
          </button>

          {recent.length > 0 && (
            <div className="recent-snippet">
              <span className="recent-label">LAST RESOLUTION:</span>
              <p className="recent-topic">"{recent[0].topic}"</p>
              {recent[0].winner && (
                <span className="recent-winner">WINNER: {recent[0].winner.toUpperCase()}</span>
              )}
            </div>
          )}
        </div>
      )}

      {/* 4. Dialogue Transcript */}
      {current && (
        <Transcript
          turns={current.turns}
          scores={current.scores}
          thinkingSpeaker={current.thinkingSpeaker}
          isLive={isOngoing}
        />
      )}
    </div>
  );
}