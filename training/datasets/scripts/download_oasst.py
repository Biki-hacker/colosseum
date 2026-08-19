"""Download OASST1 (Apache-2.0) and extract English messages.

Produces:
  training/datasets/raw/oasst1/  (cached HF dataset)
  training/datasets/processed/oasst1_en.jsonl   (filtered English messages w/ metadata)
  training/datasets/processed/oasst1_en.txt      (plain text dump for tokenizer training)
"""

from __future__ import annotations

import argparse
import json
import os
import random

from datasets import load_dataset

OUT_RAW = "training/datasets/raw/oasst1"
OUT_PROCESSED = "training/datasets/processed"
OUT_JSONL = os.path.join(OUT_PROCESSED, "oasst1_en.jsonl")
OUT_TXT = os.path.join(OUT_PROCESSED, "oasst1_en.txt")


def clean_text(s: str) -> str:
    s = s.replace("\u00a0", " ").replace("\u200b", "").replace("\ufeff", "")
    s = "\n".join(line.strip() for line in s.splitlines())
    s = " ".join(s.split())
    return s.strip()


def is_english(row) -> bool:
    return row.get("lang") == "en" and not row.get("deleted", False) and bool(row.get("text", "").strip())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="0 = all")
    ap.add_argument("--seed", type=int, default=1337)
    args = ap.parse_args()

    os.makedirs(OUT_PROCESSED, exist_ok=True)
    print("downloading OASST1 ...")
    ds = load_dataset("OpenAssistant/oasst1", cache_dir=OUT_RAW)

    rows = []
    for split in ("train", "validation"):
        for row in ds[split]:
            if is_english(row):
                rows.append(
                    {
                        "message_id": row["message_id"],
                        "parent_id": row["parent_id"],
                        "message_tree_id": row["message_tree_id"],
                        "role": row["role"],
                        "text": clean_text(row["text"]),
                        "created_date": row["created_date"],
                    }
                )
    if args.limit:
        rng = random.Random(args.seed)
        rows = rng.sample(rows, min(args.limit, len(rows)))

    with open(OUT_JSONL, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    with open(OUT_TXT, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(r["text"] + "\n")

    total_tokens_est = sum(len(t.split()) for t in (r["text"] for r in rows))
    print(f"wrote {len(rows)} messages -> {OUT_JSONL}")
    print(f"plain text dump -> {OUT_TXT}")
    print(f"approx words: {total_tokens_est}")


if __name__ == "__main__":
    main()