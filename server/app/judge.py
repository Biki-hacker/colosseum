"""Judge: scores a completed debate via the external LLM (or a deterministic
lexicon heuristic in mock mode)."""

from __future__ import annotations

from typing import Dict, List, Tuple

from .llm import LLMClient

JUDGE_SYSTEM = """You are the impartial, sharp-witted Chief Justice of the AI Colosseum.
You are evaluating a philosophical debate between two AI models: an OPTIMIST and a PESSIMIST.

Your mandate:
1. BE COMPLETELY UNBIASED between optimism and pessimism. Value constructive vision, agency, and resilience just as much as cautionary critique and risk analysis.
2. Evaluate fairly based on:
   - Persuasiveness & Conviction: Who presented the more compelling, well-articulated worldview on the topic?
   - Rebuttal strength: Did they address and reframe the opponent's points effectively?
   - Persona fidelity: Did the Optimist champion possibility, agency, and progress? Did the Pessimist articulate grounded risks, trade-offs, and cautionary truths?
3. NEVER DECLARE A TIE. Pick a definitive WINNER: either "optimist" or "pessimist" based strictly on performance in this round.
4. Provide a witty, sharp 1-2 sentence commentary explaining the decisive winning factor.

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
    "excited", "bright", "gain", "build", "change", "start", "trying", "effort", "pride", "gift",
    "hopeful", "progress", "strong", "grounding", "reward", "difference", "accomplishment", "benefit",
    "connected", "satisfying", "possible", "action", "forward", "meaning", "reach", "joy",
]
PES_LEAN = [
    "risk", "danger", "cost", "fail", "wrong", "hard", "difficult", "problem", "worse", "mistake",
    "harm", "lost", "trap", "doubt", "careful", "riskier", "fear", "unfair", "broken", "hopeless",
    "downside", "dangerous", "worry", "concern", "trade-off", "reality", "fatigue", "exhausted",
    "cynicism", "unravel", "expensive", "pressure", "consequences",
]


def _lean_score(text: str, pole: List[str]) -> float:
    words = text.lower().split()
    return sum(1 for w in words if w in pole) / max(len(words), 1)


def heuristic_judge(turns: List[Tuple[str, str]]) -> Dict:
    """Deterministic mock judge: lexicon lean + engagement + variety (balanced, never ties)."""
    opt_turns = [t[1] for t in turns if t[0] == "optimist"]
    pes_turns = [t[1] for t in turns if t[0] == "pessimist"]

    opt_len = sum(len(t.split()) for t in opt_turns)
    pes_len = sum(len(t.split()) for t in pes_turns)

    opt_lean = sum(_lean_score(t, OPT_LEAN) for t in opt_turns) / max(len(opt_turns), 1)
    pes_lean = sum(_lean_score(t, PES_LEAN) for t in pes_turns) / max(len(pes_turns), 1)

    opt_vocab = len(set(" ".join(opt_turns).lower().split())) / max(opt_len, 1) if opt_len else 0
    pes_vocab = len(set(" ".join(pes_turns).lower().split())) / max(pes_len, 1) if pes_len else 0

    opt_raw = 5.0 + 4.0 * opt_lean + 2.0 * opt_vocab + min(opt_len / max(len(turns) * 20, 1), 1.0)
    pes_raw = 5.0 + 4.0 * pes_lean + 2.0 * pes_vocab + min(pes_len / max(len(turns) * 20, 1), 1.0)

    o = min(10, max(1, int(round(opt_raw))))
    p = min(10, max(1, int(round(pes_raw))))

    if o == p:
        if opt_raw >= pes_raw:
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