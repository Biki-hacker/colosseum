import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { playClick } from "./sound";
import type { Speaker, Turn } from "./types";

interface TranscriptProps {
  turns: Turn[];
  scores?: { optimist: number; pessimist: number } | null;
  thinkingSpeaker?: Speaker | null;
  isLive?: boolean;
}

export function Transcript({ turns, thinkingSpeaker, isLive = true }: TranscriptProps) {
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const [userScrolledUp, setUserScrolledUp] = useState(false);
  const [lastTurnCount, setLastTurnCount] = useState(turns.length);
  const [unreadTurns, setUnreadTurns] = useState(0);

  const rows = [...turns].sort((a, b) => a.position - b.position);

  useEffect(() => {
    const handleScroll = () => {
      const scrollPos = window.innerHeight + window.scrollY;
      const threshold = document.documentElement.scrollHeight - 250;
      if (scrollPos < threshold) {
        setUserScrolledUp(true);
      } else {
        setUserScrolledUp(false);
        setUnreadTurns(0);
      }
    };

    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  useEffect(() => {
    if (turns.length > lastTurnCount) {
      if (userScrolledUp) {
        setUnreadTurns((prev) => prev + (turns.length - lastTurnCount));
      } else {
        bottomRef.current?.scrollIntoView({ behavior: "smooth" });
      }
      setLastTurnCount(turns.length);
    } else if (thinkingSpeaker && !userScrolledUp) {
      bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [turns.length, thinkingSpeaker, userScrolledUp, lastTurnCount]);

  const scrollToLatest = () => {
    playClick();
    setUserScrolledUp(false);
    setUnreadTurns(0);
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  return (
    <div className="transcript-flow">
      {rows.length === 0 && !thinkingSpeaker && (
        <div className="empty-transcript">
          <span>Awaiting opening proposition...</span>
        </div>
      )}

      <div className="speech-list">
        <AnimatePresence initial={false}>
          {rows.map((t) => {
            const isOpt = t.speaker === "optimist";

            return (
              <motion.div
                key={t.position}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.2 }}
                className={`speech-row ${isOpt ? "opt-row" : "pes-row"}`}
              >
                <div className="speech-bubble">
                  <div className="speech-meta">
                    <span className="speech-speaker">
                      {isOpt ? "THE OPTIMIST" : "THE PESSIMIST"}
                    </span>
                    <span className="speech-telemetry">
                      TURN {t.position + 1} · {t.tokens} TOKENS
                    </span>
                  </div>

                  <p className="speech-text">{t.text}</p>
                </div>
              </motion.div>
            );
          })}
        </AnimatePresence>
      </div>

      {thinkingSpeaker && (
        <div className={`speech-row ${thinkingSpeaker === "optimist" ? "opt-row" : "pes-row"}`}>
          <div className="speech-bubble thinking-bubble">
            <div className="speech-meta">
              <span className="speech-speaker">
                {thinkingSpeaker === "optimist" ? "THE OPTIMIST" : "THE PESSIMIST"}
              </span>
              <span className="speech-telemetry">THINKING</span>
            </div>
            <p className="thinking-text">Formulating counter-argument...</p>
          </div>
        </div>
      )}

      {userScrolledUp && isLive && (
        <button
          type="button"
          className="resume-scroll-btn"
          onClick={scrollToLatest}
        >
          RESUME SCROLL {unreadTurns > 0 ? `(${unreadTurns} NEW)` : ""}
        </button>
      )}

      <div ref={bottomRef} />
    </div>
  );
}