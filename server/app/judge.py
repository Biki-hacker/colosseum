"""Judge: scores a completed debate via the external LLM (or a deterministic
lexicon heuristic in mock mode)."""

from __future__ import annotations

from typing import Dict, List, Tuple

from .llm import LLMClient

JUDGE_SYSTEM = """You are the decisive, sharp-witted Chief Justice of the AI Colosseum.
You are evaluating a fierce, intellectual debate between an OPTIMIST and a PESSIMIST.

Your mandate:
1. NEVER DECLARE A TIE. You MUST pick a definitive WINNER: either "optimist" or "pessimist".
2. Evaluate based on:
   - Counter-punch quality: Did they directly dismantle the opponent's prior points?
   - Rhetorical flair & wit: Who delivered the most memorable, devastating roasts and arguments?
   - Persona consistency: Did the Optimist stay inspiring without being naive? Did the Pessimist expose harsh realities without being petty?
3. Provide a witty, 1-2 sentence commentary explaining the decisive knockout factor.

Return JSON with exactly these keys:
- winner: "optimist" | "pessimist"
- optimist_score: integer 1-10
- pessimist_score: integer 1-10
- commentary: 1-2 sentences"""

JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "winner": {"type": "string", "enum": ["optimist", "pessimist"]},
        "optimist_score": {"type": "integer"},
        "pessimist_score": {"type": "integer"},
        "commentary": {"type": "string"},
    },
    "required": ["winner", "optimist_score", "pessimist_score", "commentary"],
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
    """Deterministic mock judge: lexicon lean + engagement (never ties)."""
    opt_len = sum(len(t[1].split()) for t in turns if t[0] == "optimist")
    pes_len = sum(len(t[1].split()) for t in turns if t[0] == "pessimist")
    opt_lean = sum(_lean_score(t[1], OPT_LEAN) for t in turns if t[0] == "optimist")
    pes_lean = sum(_lean_score(t[1], PES_LEAN) for t in turns if t[0] == "pessimist")
    o = min(10, max(1, int(4 + 3 * opt_lean / max(len(turns) / 2, 1) + min(opt_len / 200, 3))))
    p = min(10, max(1, int(4 + 3 * pes_lean / max(len(turns) / 2, 1) + min(pes_len / 200, 3))))
    if o == p:
        if opt_len >= pes_len:
            o = min(10, o + 1)
        else:
            p = min(10, p + 1)
    winner = "optimist" if o >= p else "pessimist"
    commentary = (
        f"The {winner.capitalize()} carried the round with superior rhetorical conviction and sharper counter-arguments."
    )
    return {"winner": winner, "optimist_score": o, "pessimist_score": p, "commentary": commentary}


def judge_debate(client: LLMClient, topic: str, turns: List[Tuple[str, str]]) -> Dict:
    transcript = "\n".join(f"{s.upper()}: {t}" for s, t in turns if t.strip())
    if not transcript:
        return {"winner": "optimist", "optimist_score": 5, "pessimist_score": 4, "commentary": "Insufficient debate data."}
    if client.mock:
        return heuristic_judge(turns)
    try:
        data = client.chat(JUDGE_SYSTEM, f"Topic: {topic}\n\nTranscript:\n{transcript}", json_schema=JUDGE_SCHEMA, temperature=0.2)
    except Exception:
        return heuristic_judge(turns)
    winner = str(data.get("winner", "")).lower().strip()
    try:
        o = max(1, min(10, int(data.get("optimist_score", 5))))
        p = max(1, min(10, int(data.get("pessimist_score", 5))))
    except (TypeError, ValueError):
        o, p = 6, 5
    if winner not in ("optimist", "pessimist"):
        winner = "optimist" if o >= p else "pessimist"
    if o == p:
        if winner == "optimist":
            o = min(10, o + 1)
        else:
            p = min(10, p + 1)
    commentary = str(data.get("commentary", "")).strip() or f"Decisive victory for the {winner}."
    return {"winner": winner, "optimist_score": o, "pessimist_score": p, "commentary": commentary[:500]}