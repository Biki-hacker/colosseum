"""Build a versioned training dataset for both personalities.

Pipeline: curate base corpus → generate + validate synthetic data → build per-model
training samples (canonical format, per-turn loss masking) → pack into numpy arrays.

Run: python training/scripts/build_dataset.py --config training/configs/data_v001.yaml
The synthetic stage uses the real LLM when an API key is present, otherwise a
deterministic mock so the pipeline runs end-to-end with zero cost.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from collections import Counter
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import numpy as np
import yaml

from src.curation import build_trees, curate_oasst1, tree_to_turns
from src.format import (
    format_base_turns,
    format_debate_sample,
    pack_samples,
)
from src.llm_client import LLMClient
from src.simple_tokenizer import SimpleBPETokenizer
from src.synth import (
    check_exchange,
    exchange_to_transcript,
    generate_adversarial_exchange,
    generate_continuation_pair,
    generate_contrast_pair,
    generate_topic_batch,
)
from src.topics import validate_topic, validate_topic_batch, dedupe_topics

PERSONALITIES = ["optimist", "pessimist"]
OPPONENT = {"optimist": "pessimist", "pessimist": "optimist"}


def log(msg: str) -> None:
    print(f"[build_dataset] {msg}", flush=True)


def build_base_samples(
    jsonl_path: str, tokenizer: SimpleBPETokenizer, cfg: dict, out_dir: str
) -> Tuple[List[Tuple[str, str | None]], List[Tuple[str, str | None]]]:
    """Curate OASST1 and format base conversations for both personalities."""
    log("curating OASST1 ...")
    curated = os.path.join(out_dir, "oasst1_curated.jsonl")
    stats = curate_oasst1(jsonl_path, curated)
    log(f"  {stats}")

    messages = []
    with open(curated, encoding="utf-8") as f:
        for line in f:
            messages.append(json.loads(line))
    trees = build_trees(messages)
    log(f"  {len(trees)} conversation trees")

    optimist_samples: List[Tuple[str, str | None]] = []
    pessimist_samples: List[Tuple[str, str | None]] = []
    dropped = 0
    for tree in trees:
        turns = tree_to_turns(tree)
        if len(turns) < 2:
            dropped += 1
            continue
        txt_opt = format_base_turns(turns, "optimist")
        txt_pes = format_base_turns(turns, "pessimist")
        if len(tokenizer.encode(txt_opt)) < 8:
            dropped += 1
            continue
        optimist_samples.append((txt_opt, None))
        pessimist_samples.append((txt_pes, None))
    log(f"  base samples: optimist={len(optimist_samples)} pessimist={len(pessimist_samples)} dropped={dropped}")
    return optimist_samples, pessimist_samples


def generate_synthetic(client: LLMClient, cfg: dict, out_dir: str) -> Dict[str, list]:
    """Run the structured generation pipeline. Returns filtered, validated records."""
    syn = cfg["synthetic"]
    rng = random.Random(cfg["seed"])

    log("generating topics ...")
    topics: List[str] = []
    batch_n = int(syn.get("topic_batch", 12))
    calls = max(1, -(-int(syn["topics"]) // batch_n))
    for _ in range(calls):
        batch = generate_topic_batch(client, batch_n)
        topics.extend(validate_topic_batch(dedupe_topics(batch)))
    topics = dedupe_topics(topics)
    log(f"  {len(topics)} valid topics (target {syn['topics']})")

    exchanges: List[Tuple[str, List[Tuple[str, str]]]] = []  # (topic, transcript)
    continuations: List[Tuple[str, str, str]] = []  # (prompt, opt, pes)
    contrasts: List[Tuple[str, str, str]] = []  # (statement, opt, pes)
    rebuttals: List[Tuple[str, str, str]] = []  # (topic, opponent_stmt, rebuttal)

    log("generating adversarial exchanges ...")
    for topic in topics:
        for _ in range(int(syn["exchanges_per_topic"])):
            data = generate_adversarial_exchange(client, topic)
            err = check_exchange(topic, data)
            if err:
                log(f"  exchange rejected: {err}")
                continue
            transcript = exchange_to_transcript(topic, data)
            exchanges.append((topic, transcript))
            # rebuttal material: each turn can serve as an opponent statement
            for i in range(len(transcript) - 1):
                opp_speaker, opp_stmt = transcript[i]
                rebuttals.append((topic, opp_stmt, transcript[i + 1][1]))

    log("generating continuation pairs ...")
    extra_prompts = [t for t in topics] + [
        "What should I do if I keep failing at something?",
        "Should I trust my gut feeling or make a detailed plan?",
        "Is it better to have a stable routine or constant variety?",
        "Would you rather be admired for talent or for kindness?",
        "Is it better to say what you think or keep the peace?",
    ]
    for _ in range(int(syn["continuations"])):
        prompt = rng.choice(extra_prompts)
        data = generate_continuation_pair(client, prompt)
        if not isinstance(data, dict) or "optimist" not in data or "pessimist" not in data:
            continue
        continuations.append((prompt, data["optimist"], data["pessimist"]))

    log("generating contrasts ...")
    statements = [
        "A friend cancels your plans at the last minute.",
        "You get a promotion that means moving to a new city.",
        "Your favorite project is rejected by a committee.",
        "A stranger compliments you out of nowhere.",
        "You wake up to a rainy morning on a day off.",
        "Your team loses an important competition.",
        "Someone borrows money and forgets to pay it back.",
        "You discover a new hobby you love.",
    ]
    for _ in range(int(syn["contrasts"])):
        statement = rng.choice(statements)
        data = generate_contrast_pair(client, statement)
        if not isinstance(data, dict) or "optimist_interpretation" not in data or "pessimist_interpretation" not in data:
            continue
        contrasts.append((statement, data["optimist_interpretation"], data["pessimist_interpretation"]))

    log(f"  exchanges={len(exchanges)} continuations={len(continuations)} contrasts={len(contrasts)} rebuttals={len(rebuttals)}")
    return {"topics": topics, "exchanges": exchanges, "continuations": continuations, "contrasts": contrasts, "rebuttals": rebuttals}


def build_synthetic_samples(records: Dict[str, list], own: str) -> List[Tuple[str, str | None]]:
    """Build per-own-turn masked training samples for one model from synthetic records."""
    opp = OPPONENT[own]
    samples: List[Tuple[str, str | None]] = []

    for topic, transcript in records["exchanges"]:
        # examples ending at each of this model's own turns
        for i, (speaker, text) in enumerate(transcript):
            if speaker == own:
                prefix = transcript[:i]
                full, loss = format_debate_sample(topic, prefix, own, text)
                samples.append((full, loss))

    for prompt, opt_txt, pes_txt in records["continuations"]:
        my_txt = opt_txt if own == "optimist" else pes_txt
        full, loss = format_debate_sample(prompt, [], own, my_txt)
        samples.append((full, loss))

    for statement, opt_txt, pes_txt in records["contrasts"]:
        my_txt = opt_txt if own == "optimist" else pes_txt
        full, loss = format_debate_sample(statement, [], own, my_txt)
        samples.append((full, loss))

    for topic, opp_stmt, rebuttal in records["rebuttals"]:
        # only keep rebuttals where the opponent's turn precedes this model's response
        full, loss = format_debate_sample(topic, [("optimist" if own == "pessimist" else "pessimist", opp_stmt)], own, rebuttal)
        samples.append((full, loss))

    return samples


def pack_and_split(
    samples: List[Tuple[str, str | None]],
    tokenizer: SimpleBPETokenizer,
    cfg: dict,
    out_dir: str,
    personality: str,
    synth_flags: Optional[List[bool]] = None,
) -> Dict[str, int]:
    """Tokenize, pack, and split into train/val numpy arrays."""
    rng = random.Random(cfg["seed"])
    order = list(range(len(samples)))
    rng.shuffle(order)
    samples = [samples[i] for i in order]
    if synth_flags is not None:
        synth_flags = [synth_flags[i] for i in order]
    ids, mask = pack_samples(samples, tokenizer, cfg["context_length"], cfg["pad_id"])
    n = len(ids)
    split = int(n * cfg["train_fraction"])
    train_ids, train_mask = ids[:split], mask[:split]
    val_ids, val_mask = ids[split:], mask[split:]

    os.makedirs(out_dir, exist_ok=True)
    np.savez_compressed(
        os.path.join(out_dir, f"{personality}_train.npz"),
        ids=train_ids,
        mask=train_mask,
    )
    np.savez_compressed(
        os.path.join(out_dir, f"{personality}_val.npz"),
        ids=val_ids,
        mask=val_mask,
    )
    if synth_flags is not None:
        sf = np.asarray(synth_flags, dtype=bool)
        np.savez_compressed(
            os.path.join(out_dir, f"{personality}_train_meta.npz"),
            is_synth=sf[:split],
        )
        np.savez_compressed(
            os.path.join(out_dir, f"{personality}_val_meta.npz"),
            is_synth=sf[split:],
        )
    stats = {
        "samples": n,
        "train_samples": len(train_ids),
        "val_samples": len(val_ids),
        "non_pad_tokens": int((ids != cfg["pad_id"]).sum()),
        "non_pad_train": int((train_ids != cfg["pad_id"]).sum()),
        "non_pad_val": int((val_ids != cfg["pad_id"]).sum()),
        "loss_positions_train": int(train_mask.sum()),
        "loss_positions_val": int(val_mask.sum()),
        "avg_loss_tokens_per_sample": float(train_mask.sum() / max(len(train_mask), 1)),
    }
    return stats


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="training/configs/data_v001.yaml")
    ap.add_argument("--skip-synthetic", action="store_true", help="reuse previously generated synthetic records")
    args = ap.parse_args()

    with open(args.config, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    out_dir = cfg["output_dir"]
    os.makedirs(out_dir, exist_ok=True)

    tok = SimpleBPETokenizer.from_file(cfg["tokenizer_json"])

    # persist config for reproducibility
    with open(os.path.join(out_dir, "config.yaml"), "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f)

    base_opt, base_pes = build_base_samples(cfg["oasst1_jsonl"], tok, cfg, out_dir)

    records_file = os.path.join(out_dir, "synthetic_records.json")
    if args.skip_synthetic and os.path.exists(records_file):
        log("reusing synthetic records ...")
        with open(records_file, encoding="utf-8") as f:
            records = {k: v for k, v in json.load(f).items()}
    else:
        client = LLMClient()
        log(f"LLM mode: {'MOCK' if client.mock else 'REAL ' + client.model}")
        records = generate_synthetic(client, cfg, out_dir)
        # records contain tuples → convert to plain structures for JSON
        json_records = {
            "topics": records["topics"],
            "exchanges": [[t, tr] for t, tr in records["exchanges"]],
            "continuations": [list(c) for c in records["continuations"]],
            "contrasts": [list(c) for c in records["contrasts"]],
            "rebuttals": [list(r) for r in records["rebuttals"]],
        }
        with open(records_file, "w", encoding="utf-8") as f:
            json.dump(json_records, f, ensure_ascii=False, indent=1)
        records = {
            "topics": json_records["topics"],
            "exchanges": [(t, tr) for t, tr in json_records["exchanges"]],
            "continuations": [tuple(c) for c in json_records["continuations"]],
            "contrasts": [tuple(c) for c in json_records["contrasts"]],
            "rebuttals": [tuple(r) for r in json_records["rebuttals"]],
        }

    log("building per-model sample sets ...")
    syn_opt = build_synthetic_samples(records, "optimist")
    syn_pes = build_synthetic_samples(records, "pessimist")

    all_opt = base_opt + syn_opt
    all_pes = base_pes + syn_pes
    log(f"sample counts  optimist: base={len(base_opt)} synth={len(syn_opt)} total={len(all_opt)}")
    log(f"sample counts  pessimist: base={len(base_pes)} synth={len(syn_pes)} total={len(all_pes)}")

    stats = {}
    for p, samples in (("optimist", all_opt), ("pessimist", all_pes)):
        flags = [s in syn_opt for s in samples] if p == "optimist" else [s in syn_pes for s in samples]
        s = pack_and_split(samples, tok, cfg, out_dir, p, flags)
        stats[p] = s
        log(f"{p}: {s}")

    with open(os.path.join(out_dir, "stats.json"), "w", encoding="utf-8") as f:
        json.dump({"config": cfg, "stats": stats}, f, indent=1, default=str)
    log(f"done -> {out_dir}")


if __name__ == "__main__":
    main()