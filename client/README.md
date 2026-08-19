# client/ — Live Arena Frontend

React + TypeScript (Vite) immersive public showcase.

Populated in Phase 9. Sections planned:

- LIVE ARENA — current topic, live transcript, speaker indicator, turn counter,
  generation state, live score
- UPCOMING TOPICS — the next 12 scheduled topics
- RECENT DEBATES — archived transcripts + results (48h window)
- MODEL RECORDS — win/loss, streaks, average scores
- ABOUT THE MODELS — honest explanation of the experiment

Realtime: WebSocket with automatic reconnect; on reconnect the client fetches the server
snapshot and replaces stale local state before resuming the live stream. No authentication,
no user-generated content — visitors watch only.