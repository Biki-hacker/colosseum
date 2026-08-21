"""Phase 6: local debate arena.

Runs many full 20-turn debates between the Optimist and Pessimist models and
measures conversational health: turn length, marker discipline, truncation rate,
repetition, diversity, and stance-lean. Writes transcripts for inspection.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from typing import Dict, List, Tuple

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import torch
from safetensors.torch import load_file

from src.config import ModelConfig
from src.model import TinyGPT
from src.simple_tokenizer import SimpleBPETokenizer
from src.synth import OPT_LEAN, PES_LEAN, lean_score
from src.topics import load_fallback_pool

MAX_TURNS = 10  # per speaker; 20 turns total
MAX_TOKENS = 50  # hard cap per turn (server spec)

MARK_TOKENS = {"<OPTIMIST>", "<PESSIMIST>", "<TURN>", "<EOS>", "<TOPIC>"}


def build_marker_ids(tok: SimpleBPETokenizer) -> Dict[str, int]:
    return {m: tok.encode(m)[0] for m in MARK_TOKENS}


def run_debate(
    models: Dict[str, TinyGPT],
    tok: SimpleBPETokenizer,
    topic: str,
    markers: Dict[str, int],
    gen_cfg: dict,
    device: str,
    rng: random.Random,
) -> dict:
    """One debate. Returns transcript + per-turn stats."""
    prompt = f"<BOS><TOPIC> {topic}<TURN>"
    first = rng.choice(["optimist", "pessimist"])
    turns: List[Tuple[str, str, int, bool]] = []  # (speaker, text, tokens, truncated)
    stop_ids = {markers[m] for m in ("<EOS>", "<TURN>", "<OPTIMIST>", "<PESSIMIST>")}

    for i in range(2 * MAX_TURNS):
        speaker = first if i % 2 == 0 else ("pessimist" if first == "optimist" else "optimist")
        prompt += f"<{speaker.upper()}>"
        ids = tok.encode(prompt)
        if len(ids) > 480:
            break  # context nearly full; end the debate
        with torch.no_grad():
            out = models[speaker].generate(
                torch.tensor([ids], device=device),
                max_new_tokens=MAX_TOKENS,
                eos_id=None,  # manual stop handling below
                temperature=gen_cfg["temperature"],
                top_k=gen_cfg["top_k"],
                top_p=gen_cfg["top_p"],
                repetition_penalty=gen_cfg["repetition_penalty"],
            )
        gen = out[0][len(ids):].tolist()
        # split at the first stop token (own marker, opponent marker, TURN, EOS)
        stopped: int | None = None
        text_tokens: List[int] = []
        for t in gen:
            if t in stop_ids:
                stopped = t
                break
            text_tokens.append(t)
        text = tok.decode(text_tokens).strip()
        if not text or len(text_tokens) == 0:
            text_tokens = text_tokens or [markers["<EOS>"]]
            text = ""
        turns.append((speaker, text, len(text_tokens), stopped is None))
        prompt += " " + text + "<TURN>"
        if not text:
            break  # blank turn: mirror the server, which stops only on empty text
    return {"topic": topic, "first": first, "turns": turns}


def repetition_rate(text: str) -> float:
    words = text.lower().split()
    if len(words) < 8:
        return 0.0
    ngrams = [" ".join(words[i : i + 4]) for i in range(len(words) - 3)]
    return 1.0 - len(set(ngrams)) / max(len(ngrams), 1)


def summarize(debates: List[dict]) -> dict:
    n = len(debates)
    per_speaker: Dict[str, Dict[str, float]] = {s: {"tokens": [], "trunc": 0, "blank": 0, "rep": [], "div": [], "opt_lean": [], "pes_lean": []} for s in ("optimist", "pessimist")}
    total_turns = 0
    for d in debates:
        for speaker, text, nt, truncated in d["turns"]:
            total_turns += 1
            st = per_speaker[speaker]
            st["tokens"].append(nt)
            if truncated:
                st["trunc"] += 1
            if not text:
                st["blank"] += 1
            st["rep"].append(repetition_rate(text))
            uniq = len(set(text.lower().split()))
            st["div"].append(uniq / max(len(text.split()), 1))
            st["opt_lean"].append(lean_score(text, OPT_LEAN))
            st["pes_lean"].append(lean_score(text, PES_LEAN))

    out: dict = {"debates": n, "turns": total_turns, "avg_turns_per_debate": total_turns / max(n, 1)}
    for s, st in per_speaker.items():
        nt = len(st["tokens"]) or 1
        out[s] = {
            "avg_tokens_per_turn": round(sum(st["tokens"]) / nt, 2),
            "truncated_frac": round(st["trunc"] / nt, 3),
            "blank_frac": round(st["blank"] / nt, 3),
            "avg_rep_4gram": round(sum(st["rep"]) / nt, 3),
            "avg_diversity": round(sum(st["div"]) / nt, 3),
            "opt_lean_score": round(sum(st["opt_lean"]) / nt, 4),
            "pes_lean_score": round(sum(st["pes_lean"]) / nt, 4),
            "lean_delta": round(sum(st["opt_lean"]) / nt - sum(st["pes_lean"]) / nt, 4),
        }
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--num-debates", type=int, default=200)
    ap.add_argument("--models-root", default="models")
    ap.add_argument("--topics", default="server/app/topics/fallback_pool.json")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--temperature", type=float, default=0.8)
    ap.add_argument("--top-k", type=int, default=40)
    ap.add_argument("--top-p", type=float, default=0.9)
    ap.add_argument("--repetition-penalty", type=float, default=1.15)
    ap.add_argument("--out", default="training/experiments/arena")
    args = ap.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    models: Dict[str, TinyGPT] = {}
    tok = None
    for pers in ("optimist", "pessimist"):
        root = os.path.join(args.models_root, pers)
        meta = json.load(open(os.path.join(root, "config.json"), encoding="utf-8"))
        mc = ModelConfig(**meta["model"])
        model = TinyGPT(mc).to(device).to(torch.bfloat16)
        sd = load_file(os.path.join(root, "model.safetensors"))
        if mc.tie_embeddings:
            sd["lm_head.weight"] = sd["tok_emb.weight"]
        model.load_state_dict(sd)
        model.eval()
        models[pers] = model
        if tok is None:
            tok = SimpleBPETokenizer.from_file(os.path.join(root, "tokenizer-portable.json"))

    topics = load_fallback_pool(args.topics)
    if len(topics) < 1:
        sys.exit("no topics")
    markers = build_marker_ids(tok)
    rng = random.Random(args.seed)
    gen_cfg = {"temperature": args.temperature, "top_k": args.top_k, "top_p": args.top_p, "repetition_penalty": args.repetition_penalty}

    os.makedirs(args.out, exist_ok=True)
    debates: List[dict] = []
    t0 = time.time()
    for i in range(args.num_debates):
        topic = rng.choice(topics)
        d = run_debate(models, tok, topic, markers, gen_cfg, device, rng)
        debates.append(d)
        if (i + 1) % 50 == 0:
            print(f"  {i + 1}/{args.num_debates} debates ({time.time() - t0:.0f}s)", flush=True)

    with open(os.path.join(args.out, "transcripts.jsonl"), "w", encoding="utf-8") as f:
        for d in debates:
            f.write(json.dumps({"topic": d["topic"], "turns": [[s, t, n, tr] for s, t, n, tr in d["turns"]]}) + "\n")

    stats = summarize(debates)
    with open(os.path.join(args.out, "arena_stats.json"), "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=1)
    print(json.dumps(stats, indent=1))


if __name__ == "__main__":
    main()