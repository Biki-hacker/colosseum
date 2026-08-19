"""Phase 7 benchmark for the numpy inference engine (512MB-friendly)."""

from __future__ import annotations

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import psutil

from app.np_inference import NPEngine
from app.tokenizer import SimpleBPETokenizer

TOPICS = [
    "Should people always pursue their passion?",
    "Is technology making us less social?",
    "Would life be better if everyone could read minds?",
    "Is failure a necessary part of success?",
]


def rss_mb() -> float:
    return psutil.Process(os.getpid()).memory_info().rss / 1e6


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models-root", default=os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "models")))
    ap.add_argument("--debates", type=int, default=10)
    args = ap.parse_args()

    t0 = time.time()
    engine = NPEngine(args.models_root, SimpleBPETokenizer)
    load_s = time.time() - t0
    rss = rss_mb()

    n_turns = 0
    n_tokens = 0
    t0 = time.time()
    for i in range(args.debates):
        topic = TOPICS[i % len(TOPICS)]
        first = "optimist" if i % 2 == 0 else "pessimist"
        history, meta = [], []
        for j in range(20):
            speaker = first if j % 2 == 0 else ("pessimist" if first == "optimist" else "optimist")
            text, nt, hit = engine.generate_turn(speaker, topic, history)
            history.append((speaker, text))
            meta.append((speaker, nt, hit))
            if not text:
                break
        n_turns += len(history)
        n_tokens += sum(m[1] for m in meta)
        assert len(history) >= 1 and history[-1][1], f"debate {i} produced empty transcript"
    debate_s = time.time() - t0

    print(f"load time:           {load_s:.1f}s")
    print(f"RSS after load:      {rss:.0f} MB")
    print(f"debates:             {args.debates} ({debate_s:.1f}s total, {debate_s / args.debates:.1f}s/debate)")
    print(f"turns:               {n_turns} ({n_turns / args.debates:.1f}/debate)")
    print(f"tokens:              {n_tokens} ({n_tokens / n_turns:.1f}/turn)")
    print(f"inference:           {debate_s * 1000 / max(n_tokens, 1):.0f} ms/token")
    print(f"RSS delta during:    {rss_mb() - rss:+.0f} MB")


if __name__ == "__main__":
    main()