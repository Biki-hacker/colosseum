"""Download permissive conversational datasets from the web and normalize them.

Sources (license-checked, see training/datasets/SOURCES.md):
  - OpenAssistant/oasst2       (Apache-2.0, tree-structured human conversations)
  - bavard/personachat         (MIT, ConvAI2/PersonaChat human chit-chat)
  - HuggingFaceH4/ultrachat_200k (MIT, multi-turn user/assistant)
  - allenai/soda               (CC-BY-4.0, machine-generated social dialogue, sampled)

Every source is written as a normalized JSONL in training/datasets/raw/<source>/:
  {source, message_id, parent_id, message_tree_id, role: prompter|assistant, text}
plus a plain-text dump (<source>_en.txt) for tokenizer training.

Sequential dialogues are chained into trees via synthetic parent ids so the
existing curation tree-builder consumes all sources uniformly.
"""

from __future__ import annotations

import argparse
import json
import os
import random

from datasets import load_dataset

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
RAW = os.path.join(ROOT, "training", "datasets", "raw")


def clean_text(s: str) -> str:
    s = s.replace("\u00a0", " ").replace("\u200b", "").replace("\ufeff", "")
    s = "\n".join(line.strip() for line in s.splitlines())
    s = " ".join(s.split())
    return s.strip()


def write_clean(messages: list[dict], source: str, limit: int, seed: int) -> dict:
    """Write normalized messages + text dump. Returns stats."""
    out_dir = os.path.join(RAW, source)
    os.makedirs(out_dir, exist_ok=True)
    if limit:
        rng = random.Random(seed)
        messages = rng.sample(messages, min(limit, len(messages)))
    jsonl_path = os.path.join(out_dir, f"{source}_en.jsonl")
    txt_path = os.path.join(out_dir, f"{source}_en.txt")
    with open(jsonl_path, "w", encoding="utf-8") as f, open(txt_path, "w", encoding="utf-8") as tf:
        for m in messages:
            f.write(json.dumps(m, ensure_ascii=False) + "\n")
            tf.write(m["text"] + "\n")
    words = sum(len(m["text"].split()) for m in messages)
    print(f"[{source}] wrote {len(messages)} messages -> {jsonl_path} ({words} words)")
    return {"messages": len(messages), "words": words}


def chain_turns(dialogues: list[list[str]], source: str, roles_from_index: bool = True) -> list[dict]:
    """Turn a list of dialogue-turn-lists into normalized message dicts (chained trees)."""
    messages: list[dict] = []
    for tree_id, turns in enumerate(dialogues):
        prev = None
        for i, text in enumerate(turns):
            text = clean_text(text)
            if not text:
                continue
            role = "prompter" if (i % 2 == 0) else "assistant"
            mid = f"{source}-{tree_id}-{i}"
            messages.append(
                {
                    "source": source,
                    "message_id": mid,
                    "parent_id": prev,
                    "message_tree_id": f"{source}-{tree_id}",
                    "role": role,
                    "text": text,
                }
            )
            prev = mid
    return messages


# --------------------------------------------------------------------------
# Sources
# --------------------------------------------------------------------------

def oasst2(limit: int, seed: int) -> None:
    ds = load_dataset("OpenAssistant/oasst2", cache_dir=os.path.join(RAW, "oasst2_hf"))
    messages = []
    for split in ("train", "validation"):
        for row in ds[split]:
            if row.get("lang") != "en" or row.get("deleted") or row.get("synthetic"):
                continue
            text = clean_text(row.get("text", ""))
            if not text:
                continue
            messages.append(
                {
                    "source": "oasst2",
                    "message_id": row["message_id"],
                    "parent_id": row.get("parent_id"),
                    "message_tree_id": row["message_tree_id"],
                    "role": row["role"],
                    "text": text,
                }
            )
    write_clean(messages, "oasst2", limit, seed)


def persona(limit: int, seed: int) -> None:
    """Parse the official ParlAI PersonaChat files (MIT, ConvAI2).
    Format per dialogue: 'your persona:' metadata lines then tab-separated
    'text: <turn>\tlabels: <reply>' lines; dialogues separated by blank lines."""
    base = os.path.join(RAW, "personachat", "personachat")
    dialogues: list[list[str]] = []
    for split in ("train_self_original", "valid_self_original"):
        path = os.path.join(base, f"{split}.txt")
        if not os.path.exists(path):
            print(f"[persona] missing {path}; download personachat.tgz from parl.ai first")
            continue
        with open(path, encoding="utf-8") as f:
            block: list[str] = []
            for line in f:
                line = line.strip()
                if not line:
                    if block:
                        dialogues.append(block)
                        block = []
                    continue
                if line.startswith("your persona:") or line.startswith("partner's persona:"):
                    continue
                block.append(line)
            if block:
                dialogues.append(block)
    turns_all: list[list[str]] = []
    for block in dialogues:
        turns: list[str] = []
        for line in block:
            if "\t" not in line:
                continue
            text_part, labels_part = line.split("\t", 1)
            text = clean_text(text_part.removeprefix("text:").strip())
            labels = labels_part.removeprefix("labels:").strip().split("|")
            label = clean_text(labels[0]) if labels else ""
            if text:
                turns.append(text)
            if label:
                turns.append(label)
        if len(turns) >= 2:
            turns_all.append(turns)
    messages = chain_turns(turns_all, "personachat")
    write_clean(messages, "personachat", limit, seed)


def ultrachat(limit: int, seed: int) -> None:
    ds = load_dataset("HuggingFaceH4/ultrachat_200k", cache_dir=os.path.join(RAW, "ultrachat_hf"))
    dialogues: list[list[str]] = []
    for split in ("train_sft", "test_sft"):
        for row in ds[split]:
            msgs = row.get("messages") or []
            turns = []
            for m in msgs:
                role = m.get("role")
                text = clean_text(m.get("content", ""))
                if role == "user":
                    turns.append(text)
                elif role == "assistant" and text:
                    turns.append(text)
            if len(turns) >= 2:
                dialogues.append(turns)
    messages = chain_turns(dialogues, "ultrachat")
    write_clean(messages, "ultrachat", limit, seed)


def _reservoir(items, k: int, seed: int):
    """Deterministic reservoir sample of k items from an iterator."""
    rng = random.Random(seed)
    pool = []
    for i, it in enumerate(items):
        if i < k:
            pool.append(it)
        else:
            j = rng.randrange(i + 1)
            if j < k:
                pool[j] = it
    return pool


def soda(limit: int, seed: int) -> None:
    """SODA (CC-BY-4.0) machine-generated social dialogues. Reservoir-sampled."""
    train = load_dataset("allenai/soda", split="train", cache_dir=os.path.join(RAW, "soda_hf"), streaming=True)
    valid = load_dataset("allenai/soda", split="validation", cache_dir=os.path.join(RAW, "soda_hf"), streaming=True)

    def dialogues_from(rows, cap: int):
        out: list[list[str]] = []
        for row in rows:
            dialog = row.get("dialogue") or []
            turns = []
            for line in dialog:
                line = clean_text(line)
                if line:
                    turns.append(line)
            if len(turns) >= 2:
                out.append(turns)
            if len(out) >= cap:
                break
        return out

    sampled = _reservoir(dialogues_from(train, 1_200_000), k=200_000, seed=seed)
    sampled += _reservoir(dialogues_from(valid, 160_000), k=40_000, seed=seed)
    print(f"[soda] sampled {len(sampled)} dialogues")
    messages = chain_turns(sampled, "soda")
    write_clean(messages, "soda", limit, seed)


SOURCES = {
    "oasst2": oasst2,
    "persona": persona,
    "ultrachat": ultrachat,
    "soda": soda,
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=list(SOURCES) + ["all"], default="all")
    ap.add_argument("--limit", type=int, default=0, help="0 = all (persona/soda sampled via --limit)")
    ap.add_argument("--seed", type=int, default=1337)
    args = ap.parse_args()
    sources = list(SOURCES) if args.source == "all" else [args.source]
    for s in sources:
        print(f"downloading {s} ...")
        SOURCES[s](args.limit, args.seed)


if __name__ == "__main__":
    main()