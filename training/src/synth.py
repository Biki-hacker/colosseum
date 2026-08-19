"""Structured synthetic data generation for the two personalities.

Every generator returns a strictly-shaped dict; the pipeline then runs structural,
quality, diversity and personality-consistency checks (see check_* functions) before a
candidate is kept. In mock mode (no API key), the LLMClient returns schema-shaped
deterministic data so the whole pipeline runs end-to-end without external cost.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from .llm_client import LLMClient
from .topics import TOPIC_PROMPT, TOPIC_SCHEMA

# Personality consistency heuristic: does the text lean toward the expected pole?
OPT_LEAN = [
    "opportunity", "hope", "growth", "positive", "better", "can", "together", "learn",
    "good", "love", "possibility", "future", "encourage", "strength", "solution",
    "confidence", "believe", "wonderful", "excited", "bright", "gain", "build", "change",
]
PES_LEAN = [
    "risk", "danger", "cost", "fail", "wrong", "hard", "difficult", "problem", "worse",
    "mistake", "harm", "lost", "trap", "doubt", "careful", "riskier", "fear", "unfair",
    "broken", "hopeless", "downside", "dangerous", "worry", "concern",
]


def lean_score(text: str, pole: List[str]) -> float:
    words = set(text.lower().split())
    return sum(1 for w in words if w in pole) / max(len(words), 1)


# --------------------------------------------------------------------------
# Schema-shaped prompts
# --------------------------------------------------------------------------

_ADVERSARIAL_SYSTEM = """You are building training data for two AI debate personalities: an OPTIMIST and a PESSIMIST.
Write conversational, natural-sounding spoken English. Keep every response between 30 and 60 words.
Never use formal essay language. Make the two personalities genuinely disagree without either becoming a caricature.
The optimist acknowledges weaknesses honestly; the pessimist acknowledges strengths honestly."""

ADVERSARIAL_PROMPT = """Topic: {topic}

Generate a short debate exchange as JSON with these exact keys:
- optimist: the optimist's opening argument (3-4 sentences)
- pessimist: the pessimist's opening argument (3-4 sentences)
- optimist_rebuttal: the optimist directly responding to the pessimist's point
- pessimist_rebuttal: the pessimist directly responding to the optimist's point"""

ADVERSARIAL_SCHEMA = {
    "type": "object",
    "properties": {
        "optimist": {"type": "string"},
        "pessimist": {"type": "string"},
        "optimist_rebuttal": {"type": "string"},
        "pessimist_rebuttal": {"type": "string"},
    },
}

CONTINUATION_PROMPT = """Prompt: {prompt}

Generate two short spoken responses (3-4 sentences each) to this prompt as JSON:
- optimist: an optimistic, constructive, hopeful but honest response
- pessimist: a skeptical, cautious, risk-aware but honest response"""
CONTINUATION_SCHEMA = {
    "type": "object",
    "properties": {"optimist": {"type": "string"}, "pessimist": {"type": "string"}},
}

CONTRAST_PROMPT = """Event: {statement}

Write two contrasting interpretations of this event as JSON:
- optimist_interpretation: the hopeful, growth-oriented interpretation
- pessimist_interpretation: the skeptical, cautionary interpretation"""
CONTRAST_SCHEMA = {
    "type": "object",
    "properties": {"optimist_interpretation": {"type": "string"}, "pessimist_interpretation": {"type": "string"}},
}

REBUTTAL_PROMPT = """Opponent's statement: {statement}

Write a single spoken response (2-4 sentences) that directly addresses the opponent's actual
point, concedes whatever is fair, and then makes the counter-argument as JSON with the key "rebuttal"."""
REBUTTAL_SCHEMA = {"type": "object", "properties": {"rebuttal": {"type": "string"}}}

CONCESSION_PROMPT = """Statement: {statement}

Write a balanced response as JSON with these keys:
- agree: what you agree with (1-2 sentences)
- disagree: what you disagree with (1-2 sentences)
- alternative: your alternative interpretation or suggestion (1-2 sentences)"""
CONCESSION_SCHEMA = {
    "type": "object",
    "properties": {"agree": {"type": "string"}, "disagree": {"type": "string"}, "alternative": {"type": "string"}},
}


def _chunks(text: str, n: int) -> List[str]:
    words = text.split()
    return [" ".join(words[i : i + n]) for i in range(0, len(words), n) if words[i : i + n]]


# --------------------------------------------------------------------------
# Generators
# --------------------------------------------------------------------------

def generate_topic_batch(client: LLMClient, count: int = 12) -> List[str]:
    data = client.chat(TOPIC_PROMPT, f"Generate {count} topics.", json_schema=TOPIC_SCHEMA)
    topics = data.get("topics", []) if isinstance(data, dict) else []
    return [t for t in topics if isinstance(t, str)]


def generate_adversarial_exchange(client: LLMClient, topic: str) -> Dict[str, str]:
    return client.chat(_ADVERSARIAL_SYSTEM, ADVERSARIAL_PROMPT.format(topic=topic), json_schema=ADVERSARIAL_SCHEMA)


def generate_continuation_pair(client: LLMClient, prompt: str) -> Dict[str, str]:
    return client.chat(_ADVERSARIAL_SYSTEM, CONTINUATION_PROMPT.format(prompt=prompt), json_schema=CONTINUATION_SCHEMA)


def generate_contrast_pair(client: LLMClient, statement: str) -> Dict[str, str]:
    return client.chat(_ADVERSARIAL_SYSTEM, CONTRAST_PROMPT.format(statement=statement), json_schema=CONTRAST_SCHEMA)


def generate_rebuttal(client: LLMClient, statement: str) -> Dict[str, str]:
    return client.chat(_ADVERSARIAL_SYSTEM, REBUTTAL_PROMPT.format(statement=statement), json_schema=REBUTTAL_SCHEMA)


def generate_concession(client: LLMClient, statement: str) -> Dict[str, str]:
    return client.chat(_ADVERSARIAL_SYSTEM, CONCESSION_PROMPT.format(statement=statement), json_schema=CONCESSION_SCHEMA)


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------

def check_structure(data: Dict[str, Any], required_keys: List[str]) -> Optional[str]:
    if not isinstance(data, dict):
        return "not_a_dict"
    for k in required_keys:
        if k not in data or not isinstance(data[k], str) or not data[k].strip():
            return f"missing_key:{k}"
    return None


def check_lengths(data: Dict[str, Any], min_words: int = 20, max_words: int = 120) -> Optional[str]:
    for k, v in data.items():
        if isinstance(v, str):
            w = len(v.split())
            if w < min_words or w > max_words:
                return f"bad_length:{k}:{w}"
    return None


def check_personality(text: str, pole: str, min_score: float = 0.02) -> bool:
    """A crude polarity consistency check: the text should lean toward its pole more than
    toward the opposite. Loose thresholds — personality should be genuine, not caricature."""
    s = lean_score(text, OPT_LEAN if pole == "optimist" else PES_LEAN)
    o = lean_score(text, PES_LEAN if pole == "optimist" else OPT_LEAN)
    return s >= min_score or s > o


def exchange_to_transcript(topic: str, data: Dict[str, str]) -> List[Tuple[str, str]]:
    """Convert an adversarial exchange into an alternating transcript."""
    return [
        ("optimist", data["optimist"]),
        ("pessimist", data["pessimist"]),
        ("optimist", data["optimist_rebuttal"]),
        ("pessimist", data["pessimist_rebuttal"]),
    ]


def check_exchange(topic: str, data: Dict[str, str]) -> Optional[str]:
    err = check_structure(data, ["optimist", "pessimist", "optimist_rebuttal", "pessimist_rebuttal"])
    if err:
        return err
    err = check_lengths(data)
    if err:
        return err
    if not check_personality(data["optimist"], "optimist"):
        return "opt_not_optimistic"
    if not check_personality(data["pessimist"], "pessimist"):
        return "pes_not_pessimistic"
    return None