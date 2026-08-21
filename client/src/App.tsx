import { useEffect, useState } from "react";
import Lenis from "lenis";
import gsap from "gsap";
import { AnimatePresence, motion } from "framer-motion";
import { fetchHealth } from "./api";
import { Arena } from "./Arena";
import { History } from "./History";
import { CanvasBackground } from "./CanvasBackground";
import { isSoundEnabled, playClick, setSoundEnabled } from "./sound";
import type { Health } from "./types";

type Tab = "arena" | "history";

export function App() {
  const [tab, setTab] = useState<Tab>("arena");
  const [health, setHealth] = useState<Health | null>(null);
  const [soundActive, setSoundActive] = useState<boolean>(false);

  // Initialize Lenis smooth scroll
  useEffect(() => {
    const lenis = new Lenis({
      duration: 0.8,
      orientation: "vertical",
      smoothWheel: true,
    });

    function raf(time: number) {
      lenis.raf(time);
      requestAnimationFrame(raf);
    }
    requestAnimationFrame(raf);

    gsap.ticker.add((time) => {
      lenis.raf(time * 1000);
    });

    return () => lenis.destroy();
  }, []);

  useEffect(() => {
    setSoundActive(isSoundEnabled());
  }, []);

  // Poll server health
  useEffect(() => {
    const poll = () =>
      fetchHealth()
        .then(setHealth)
        .catch(() => setHealth(null));

    void poll();
    const interval = setInterval(poll, 4000);
    return () => clearInterval(interval);
  }, []);

  const handleSoundToggle = () => {
    const next = !soundActive;
    setSoundActive(next);
    setSoundEnabled(next);
    if (next) playClick();
  };

  const handleTabChange = (nextTab: Tab) => {
    playClick();
    setTab(nextTab);
  };

  return (
    <div className="brutalist-root">
      <CanvasBackground />

      <div className="app-container">
        {/* Minimal Clean Header */}
        <header className="site-header">
          <div className="brand-group">
            <h1 className="brand-title">COLOSSEUM</h1>
            <span className="brand-sub">5M Transformer Arena</span>
          </div>

          <nav className="nav-segment" role="tablist">
            <button
              type="button"
              role="tab"
              aria-selected={tab === "arena"}
              className={`nav-item ${tab === "arena" ? "active" : ""}`}
              onClick={() => handleTabChange("arena")}
            >
              LIVE ARENA
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={tab === "history"}
              className={`nav-item ${tab === "history" ? "active" : ""}`}
              onClick={() => handleTabChange("history")}
            >
              VERDICT ARCHIVE
            </button>
          </nav>

          <div className="header-controls">
            <button
              type="button"
              className={`audio-btn ${soundActive ? "active" : ""}`}
              onClick={handleSoundToggle}
              title={soundActive ? "Mute audio" : "Enable audio"}
            >
              {soundActive ? "AUDIO: ON" : "AUDIO: OFF"}
            </button>

            <div className="status-pill">
              <span className={`status-dot ${health?.status === "ok" ? "online" : "offline"}`} />
              <span>{health?.status === "ok" ? "ONLINE" : "CONNECTING"}</span>
            </div>
          </div>
        </header>

        {/* Viewport */}
        <main className="main-viewport">
          <AnimatePresence mode="wait">
            {tab === "arena" ? (
              <motion.div
                key="arena"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.15 }}
              >
                <Arena health={health} />
              </motion.div>
            ) : (
              <motion.div
                key="history"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.15 }}
              >
                <History />
              </motion.div>
            )}
          </AnimatePresence>
        </main>
      </div>
    </div>
  );
}