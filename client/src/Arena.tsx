import { useEffect, useRef, useState } from "react";
import type { Debate, Turn, WsEvent } from "./types";
import { Transcript } from "./Transcript";

interface Current {
  topic: string;
  turns: Turn[];
  winner?: string;
  scores?: { optimist: number; pessimist: number } | null;
  commentary?: string;
  error?: string;
}

const wsUrl = () => `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws/debates`;

export function Arena() {
  const [connected, setConnected] = useState(false);
  const [recent, setRecent] = useState<Debate[]>([]);
  const [current, setCurrent] = useState<Current | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

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
            setCurrent({ topic: msg.topic, turns: [] });
            break;
          case "turn":
            setCurrent((c) =>
              c
                ? {
                    ...c,
                    turns: [...c.turns, { speaker: msg.speaker, text: msg.text, tokens: msg.tokens, position: msg.position }],
                  }
                : c,
            );
            break;
          case "debate_completed":
            setCurrent((c) =>
              c
                ? {
                    ...c,
                    winner: msg.winner,
                    scores: { optimist: msg.optimist_score, pessimist: msg.pessimist_score },
                    commentary: msg.commentary,
                  }
                : c,
            );
            break;
          case "debate_failed":
            setCurrent((c) => (c ? { ...c, error: msg.error } : c));
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
  }, []);

  const verdict = current?.winner ? current.winner.toUpperCase() : null;

  return (
    <div className="arena">
      <div className={`conn ${connected ? "ok" : "down"}`}>
        {connected ? "● live" : "○ reconnecting…"}
      </div>

      {current && (
        <div className="debate-header">
          <div className="topic">{current.topic}</div>
          {current.error && <div className="error-banner">Debate failed: {current.error}</div>}
          {verdict && (
            <div className={`verdict ${current.winner}`}>
              <span className="v-winner">{verdict}</span>
              {current.scores && (
                <span className="v-scores">
                  OPTIMIST {current.scores.optimist} — PESSIMIST {current.scores.pessimist}
                </span>
              )}
              {current.commentary && <span className="v-comment">{current.commentary}</span>}
            </div>
          )}
        </div>
      )}

      {!current && (
        <div className="waiting">
          <div className="waiting-title">Waiting for the next debate</div>
          {recent.length > 0 && <div className="waiting-sub">Most recent: “{recent[0].topic}”</div>}
        </div>
      )}

      {current && <Transcript turns={current.turns} scores={current.scores} />}
    </div>
  );
}