"""Judge: scores a completed debate via the external LLM (or a deterministic
lexicon heuristic in mock mode)."""

from __future__ import annotations

from typing import Dict, List, Tuple

from .llm import LLMClient

JUDGE_SYSTEM = """You are the impartial judge of a debate between two AI personalities: an OPTIMIST and a PESSIMIST.
Evaluate the debate on: argument quality, engagement with the opponent's points, clarity, and personality consistency (the optimist should be hopeful and constructive; the pessimist cautious and skeptical).
Be fair: neither personality should win by default. A "tie" is a valid verdict.
Return JSON with exactly these keys:
- winner: "optimist" | "pessimist" | "tie"
- optimist_score: integer 1-10
- pessimist_score: integer 1-10
- commentary: 1-2 sentences"""

JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "winner": {"type": "string"},
        "optimist_score": {"type": "integer"},
        "pessimist_score": {"type": "integer"},
        "commentary": {"type": "string"},
    },
}

OPT_LEAN = [
    "opportunity", "hope", "growth", "positive", "better", "can", "together", "learn", "good", "love",
    "possibility", "future", "encourage", "strength", "solution", "confidence", "believe", "wonderful",
    "excited", "bright", "gain", "build", "change",
]
PES_LEAN = [
    "risk", "danger", "cost", "fail", "wrong", "hard", "difficult", "problem", "worse", "mistake",
    "harm", "lost", "trap", "doubt", "careful", "riskier", "fear", "unfair", "broken", "hopeless",
    "downside", "dangerous", "worry", "concern",
]


def _lean_score(text: str, pole: List[str]) -> float:
    words = text.lower().split()
    return sum(1 for w in words if w in pole) / max(len(words), 1)


def heuristic_judge(turns: List[Tuple[str, str]]) -> Dict:
    """Deterministic mock judge: lexicon lean + engagement (length)."""
    opt_len = sum(len(t[1].split()) for t in turns if t[0] == "optimist")
    pes_len = sum(len(t[1].split()) for t in turns if t[0] == "pessimist")
    opt_lean = sum(_lean_score(t[1], OPT_LEAN) for t in turns if t[0] == "optimist")
    pes_lean = sum(_lean_score(t[1], PES_LEAN) for t in turns if t[0] == "pessimist")
    o = min(10, max(1, int(3 + 2 * opt_lean / max(len(turns) / 2, 1) + min(opt_len / 200, 3))))
    p = min(10, max(1, int(3 + 2 * pes_lean / max(len(turns) / 2, 1) + min(pes_len / 200, 3))))
    if abs(o - p) <= 1:
        winner, commentary = "tie", "Too close to call."
    else:
        winner = "optimist" if o > p else "pessimist"
        commentary = f"Clear edge on engagement and consistency."
    return {"winner": winner, "optimist_score": o, "pessimist_score": p, "commentary": commentary}


def judge_debate(client: LLMClient, topic: str, turns: List[Tuple[str, str]]) -> Dict:
    transcript = "\n".join(f"{s.upper()}: {t}" for s, t in turns if t.strip())
    if not transcript:
        return {"winner": "tie", "optimist_score": 5, "pessimist_score": 5, "commentary": "Empty debate."}
    if client.mock:
        return heuristic_judge(turns)
    try:
        data = client.chat(JUDGE_SYSTEM, f"Topic: {topic}\n\nTranscript:\n{transcript}", json_schema=JUDGE_SCHEMA, temperature=0.2)
    except Exception:
        return heuristic_judge(turns)
    winner = data.get("winner", "tie")
    if winner not in ("optimist", "pessimist", "tie"):
        winner = "tie"
    try:
        o = max(1, min(10, int(data.get("optimist_score", 5))))
        p = max(1, min(10, int(data.get("pessimist_score", 5))))
    except (TypeError, ValueError):
        o = p = 5
    return {"winner": winner, "optimist_score": o, "pessimist_score": p, "commentary": str(data.get("commentary", ""))[:500]}