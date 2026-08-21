"""Debate execution: runs one full debate between the two models."""

from __future__ import annotations

import asyncio
from typing import List, Tuple

from .config import settings
from .np_inference import NPEngine
from .tokenizer import SimpleBPETokenizer

EVENT_STARTED = "debate_started"
EVENT_THINKING = "thinking"
EVENT_TURN = "turn"
EVENT_COMPLETED = "debate_completed"
EVENT_FAILED = "debate_failed"


class DebateRunner:
    def __init__(self, engine: NPEngine):
        self.engine = engine

    async def run(self, topic: str, on_event) -> Tuple[List[Tuple[str, str]], List[dict]]:
        """Runs the debate, emitting events via on_event(dict). Returns
        (turns, meta). on_event must be async-safe (coroutine)."""
        first = "optimist"
        history: List[Tuple[str, str]] = []
        meta: List[dict] = []
        await on_event({"type": EVENT_STARTED, "topic": topic, "first": first, "total_turns": settings.debate_turns})
        for i in range(settings.debate_turns):
            speaker = first if i % 2 == 0 else ("pessimist" if first == "optimist" else "optimist")
            await on_event({"type": EVENT_THINKING, "speaker": speaker, "position": i})
            if settings.turn_delay_seconds > 0:
                await asyncio.sleep(settings.turn_delay_seconds)
            text, nt, hit_marker = await asyncio.to_thread(
                self.engine.generate_turn,
                speaker,
                topic,
                history,
                settings.generation_temperature,
                settings.generation_top_k,
                settings.generation_top_p,
                settings.generation_repetition_penalty,
            )
            if not text:
                text = (
                    "I stand by my perspective on this topic."
                    if speaker == "optimist"
                    else "The complications and risks here are too significant to overlook."
                )
                nt = max(1, nt)

            history.append((speaker, text))
            meta.append({"speaker": speaker, "tokens": nt, "hit_marker": hit_marker})
            await on_event({"type": EVENT_TURN, "speaker": speaker, "text": text, "tokens": nt, "position": i})
        return history, meta



def make_engine() -> NPEngine:
    return NPEngine(settings.models_root, SimpleBPETokenizer)