export type Speaker = "optimist" | "pessimist";

export interface Turn {
  speaker: Speaker;
  text: string;
  tokens: number;
  position: number;
}

export interface Debate {
  id: string;
  topic: string;
  status: "scheduled" | "running" | "completed" | "failed";
  winner: string | null;
  created_at: string;
  updated_at?: string;
  ended_at?: string | null;
  turns?: Turn[];
  optimist_score?: number;
  pessimist_score?: number;
  commentary?: string;
}

export interface Health {
  status: string;
  uptime_s: number;
  next_debate_in_s: number;
  interval_s: number;
  llm: string;
  storage: string;
}

export type WsEvent =
  | { type: "recent"; debates: Debate[] }
  | { type: "active_debate"; debate_id: string; topic: string; status: string; turns: Turn[] }
  | { type: "debate_started"; debate_id: string; topic: string; first: string }
  | {
      type: "turn";
      debate_id: string;
      speaker: Speaker;
      text: string;
      tokens: number;
      position: number;
    }
  | {
      type: "thinking";
      debate_id: string;
      speaker: Speaker;
      position: number;
    }
  | {
      type: "debate_completed";
      debate_id: string;
      winner: string;
      optimist_score: number;
      pessimist_score: number;
      commentary: string;
    }
  | { type: "debate_failed"; debate_id: string; error: string };