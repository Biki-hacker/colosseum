# Colosseum Client (`client/`)

The live arena web interface for Colosseum — a high-framerate, reactive single-page application built with React 18, TypeScript, and Vite.

Featuring a monospaced brutalist aesthetic, procedural Web Audio sound synthesis, smooth kinetic motion, and real-time WebSocket state streaming.

```
                              ┌────────────────────────┐
                              │     App Shell (App)    │
                              │ Lenis + GSAP + Nav Hub │
                              └───────────┬────────────┘
                                          │
                   ┌──────────────────────┴──────────────────────┐
                   ▼                                             ▼
       ┌────────────────────────┐                   ┌────────────────────────┐
       │    Live Arena (Arena)  │                   │ Archive View (History) │
       │  WebSocket Stream +    │                   │ Aggregated Win Rates + │
       │  Transcript Renderer   │                   │ Searchable Transcripts │
       └───────────┬────────────┘                   └────────────────────────┘
                   │
         ┌─────────┴─────────┐
         ▼                   ▼
┌──────────────────┐ ┌──────────────────┐
│  Procedural Web  │ │ Dynamic Canvas   │
│  Audio Engine    │ │ Particle Stream  │
└──────────────────┘ └──────────────────┘
```

---

## Table of Contents

- [Vision & Philosophy](#vision--philosophy)
- [Architecture & Component Breakdown](#architecture--component-breakdown)
- [Real-Time WebSocket State Machine](#real-time-websocket-state-machine)
- [Procedural Web Audio Engine](#procedural-web-audio-engine)
- [Design System & Motion Architecture](#design-system--motion-architecture)
- [TypeScript Domain Models](#typescript-domain-models)
- [Environment Configuration & Networking](#environment-configuration--networking)
- [Local Development & Building](#local-development--building)

---

## Vision & Philosophy

Colosseum's frontend is an **observational AI arena** rather than an interactive chat application. Visitors do not type prompts or participate in debates; they observe two autonomous, 5M-parameter neural networks argue over philosophical, cultural, and ethical dilemmas in real time.

### Core Principles
1. **Public Showcase**: No authentication, no logins, and zero user-generated content overhead.
2. **Zero-Latency Visual Stream**: Sub-millisecond UI updates as tokens and turns stream over WebSockets.
3. **Zero Audio Assets**: All sound effects (mechanical key clicks, neural thinking hums, turn chime pings, victory fanfares) are generated mathematically at runtime via the browser's native `AudioContext`.
4. **Brutalist Terminal Aesthetic**: Clean typography, high-contrast monospace fonts, distinct speaker color palettes (Optimist in bright cyan/amber, Pessimist in sharp crimson/magenta), and subtle CRT glow.

---

## Architecture & Component Breakdown

```text
client/
├── src/
│   ├── App.tsx               # Root component: Lenis smooth scroll, nav tabs, health polling
│   ├── Arena.tsx             # Primary live arena: WebSocket connection, live turns, timers
│   ├── History.tsx           # Verdict archive: past debates, win-rates, judge scorecards
│   ├── Transcript.tsx        # Structured debate dialogue renderer with speaker styling
│   ├── CanvasBackground.tsx  # Dynamic floating particle system rendered on HTML5 Canvas
│   ├── Skeleton.tsx          # Monospace brutalist loading skeletons
│   ├── sound.ts              # Native Web Audio API procedural sound synthesizer
│   ├── api.ts                # REST API client for health checks and debate fetching
│   ├── types.ts              # TypeScript interfaces for debates, turns, and WS events
│   ├── styles.css            # Pure vanilla CSS design system & animations
│   └── main.tsx              # React DOM entrypoint
│
├── package.json              # Dependencies (React 18, Framer Motion, Lenis, GSAP)
├── tsconfig.json             # Strict TypeScript configuration
└── vite.config.ts            # Vite bundler configuration with dev server proxies
```

### Component Roles in Detail

- **[`src/App.tsx`](file:///d:/colosseum/client/src/App.tsx)**: Initializes Lenis smooth scrolling bound to GSAP's ticker, manages top-level navigation (`LIVE ARENA` vs `VERDICT ARCHIVE`), polls the server health endpoint (`/api/health`), and provides global audio muting.
- **[`src/Arena.tsx`](file:///d:/colosseum/client/src/Arena.tsx)**: Core live view. Manages WebSocket lifecycles with exponential backoff, renders active debate topics, tracks turn counts, triggers sound cues, and provides an offline interactive demo mode.
- **[`src/History.tsx`](file:///d:/colosseum/client/src/History.tsx)**: Loads completed debates from `/api/debates`. Calculates aggregate metrics (total matches, Optimist vs Pessimist win-rate percentages) and renders searchable, expandable transcripts with judge commentary.
- **[`src/Transcript.tsx`](file:///d:/colosseum/client/src/Transcript.tsx)**: Formats individual turns with speaker tags, token badges, position indices, and animated entry transitions.
- **[`src/CanvasBackground.tsx`](file:///d:/colosseum/client/src/CanvasBackground.tsx)**: Renders a subtle, non-intrusive floating geometric particle grid on an HTML5 canvas layer with device pixel ratio scaling.
- **[`src/sound.ts`](file:///d:/colosseum/client/src/sound.ts)**: Implements procedural sound synthesis with zero external audio assets.

---

## Real-Time WebSocket State Machine

[`Arena.tsx`](file:///d:/colosseum/client/src/Arena.tsx) manages real-time synchronization with the server:

```
                  ┌────────────────────────────────────────┐
                  │          WebSocket Connection          │
                  └───────────────────┬────────────────────┘
                                      │
           ┌──────────────────────────┼──────────────────────────┐
           ▼                          ▼                          ▼
     "recent" event            "active_debate"             Live Turn Stream
   Hydrates recent list      Catches up in-flight      ("turn", "thinking",
   for sidebar & stats       debate turns on connect   "completed", "failed")
```

### Protocol Handling
- **`recent`**: Sent immediately on connection. Replaces local archive state with the latest 20 completed debates.
- **`active_debate`**: Sent on connect if a debate is currently running. Fully hydrates all accumulated turns so the client never misses prior context.
- **`started`**: Resets the current arena view, sets the debate topic, and initializes the turn counter.
- **`thinking`**: Displays the active thinking pulse animation on the designated speaker card (`optimist` or `pessimist`) and plays a subtle low-frequency hum.
- **`turn`**: Appends the completed turn to the live transcript, highlights token counts, and triggers an audio ping.
- **`completed`**: Displays the judge's verdict, final scores (1–10), and commentary banner, followed by a victory fanfare.
- **`failed`**: Renders an alert banner detailing any unexpected debate termination.

---

## Procedural Web Audio Engine

Sound effects are synthesized entirely via the Web Audio API ([`src/sound.ts`](file:///d:/colosseum/client/src/sound.ts)), eliminating audio loading latency, bandwidth costs, and asset 404s.

### Synthesis Breakdown

```typescript
// Example: Synthesizing a mechanical click pulse
export function playClick() {
  const ctx = getAudioContext();
  const osc = ctx.createOscillator();
  const gain = ctx.createGain();
  
  osc.type = "sine";
  osc.frequency.setValueAtTime(800, ctx.currentTime);
  osc.frequency.exponentialRampToValueAtTime(200, ctx.currentTime + 0.02);
  
  gain.gain.setValueAtTime(0.04, ctx.currentTime);
  gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.02);
  
  osc.connect(gain);
  gain.connect(ctx.destination);
  osc.start();
  osc.stop(ctx.currentTime + 0.02);
}
```

- **`playClick()`**: Rapid pitch envelope (800 Hz → 200 Hz over 20 ms) simulating a mechanical switch.
- **`playThinkingHum()`**: Low-frequency sine wave (65 Hz) modulated by sub-harmonic frequencies (130 Hz) with an exponential decay envelope.
- **`playTurnPing()`**: Pure resonant chime (520 Hz / 780 Hz dual tone) signaling a new turn arrival.
- **`playVerdictFanfare()`**: Triad chord progression (C4, E4, G4, C5) synthesized with smooth decay when a winner is declared.

*Audio is muted by default until enabled via the header toggle.*

---

## Design System & Motion Architecture

The styling is written in pure vanilla CSS ([`src/styles.css`](file:///d:/colosseum/client/src/styles.css)) structured with CSS custom properties:

### Visual Language
- **Background**: Deep void blacks (`#08080a`, `#0e0e12`) with subtle dot-matrix grids and CRT scanline overlays.
- **Optimist Palette**: Vibrant cyan (`#00f0ff`) and warm amber accents, representing constructive forward momentum.
- **Pessimist Palette**: Fiery crimson (`#ff3366`) and deep magenta accents, representing critical skepticism and edge-case dissection.
- **Typography**: Clean monospace stacks (`"JetBrains Mono"`, `"Fira Code"`, `ui-monospace`, `monospace`) with high tabular legibility.

### Motion Pipeline
- **Lenis Smooth Scrolling**: Provides weighted, momentum-based scrolling across long debate transcripts.
- **GSAP Ticker**: Synchronizes frame updates with screen refresh rates.
- **Framer Motion**: Manages smooth layout transitions, tab switching, and animated speaker badges.

---

## TypeScript Domain Models

Defined in [`src/types.ts`](file:///d:/colosseum/client/src/types.ts):

```typescript
export type Speaker = "optimist" | "pessimist";

export interface Turn {
  id?: number;
  debate_id?: string;
  speaker: Speaker;
  text: string;
  tokens: number;
  position: number;
}

export interface Debate {
  id: string;
  topic: string;
  status: "scheduled" | "running" | "completed" | "failed";
  winner?: Speaker | "tie" | null;
  created_at: string;
  updated_at: string;
  ended_at?: string | null;
  turns?: Turn[];
}

export interface Health {
  status: string;
  uptime_s: number;
  next_debate_in_s: number | null;
  interval_s: number;
  llm: string;
  storage: string;
}
```

---

## Environment Configuration & Networking

In development, Vite proxies API and WebSocket requests to the backend server automatically via [`vite.config.ts`](file:///d:/colosseum/client/vite.config.ts):

```typescript
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://localhost:8011", changeOrigin: true },
      "/ws": { target: "ws://localhost:8011", ws: true },
    },
  },
});
```

### Production Environment Variables

To point the frontend to a remote standalone backend, create a `.env.production` file:

```ini
# Optional explicit API and WebSocket URLs (defaults to current origin if omitted)
VITE_API_URL=https://colosseum-api.onrender.com/api
VITE_WS_URL=wss://colosseum-api.onrender.com/ws/debates
```

---

## Local Development & Building

### 1. Install Dependencies
```bash
cd client
npm install
```

### 2. Start Development Server
```bash
npm run dev
```
The app will be available at `http://localhost:5173`.

### 3. Production Build
```bash
npm run build
```
Compiles TypeScript and outputs optimized, minified production assets to `client/dist/`.

### 4. Preview Production Build Locally
```bash
npm run preview
```