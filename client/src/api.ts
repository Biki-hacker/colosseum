import type { Debate, Health, Turn } from "./types";

const BASE = "/api";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json() as Promise<T>;
}

export function fetchHealth(): Promise<Health> {
  return get<Health>("/health");
}

export function fetchDebates(limit = 20): Promise<Debate[]> {
  return get<Debate[]>(`/debates?limit=${limit}`);
}

export async function fetchDebate(id: string): Promise<Debate & { turns: Turn[] }> {
  return get<Debate & { turns: Turn[] }>(`/debates/${id}`);
}