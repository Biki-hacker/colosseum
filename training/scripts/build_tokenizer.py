"""Train and export the project's byte-level BPE tokenizer.

Uses the fast Rust `tokenizers` library; exports a portable JSON artifact that the
production server loads with the dependency-free SimpleBPETokenizer.
"""

from __future__ import annotations

import argparse
import json
import os

from tokenizers import Tokenizer
from tokenizers.models import BPE
from tokenizers.pre_tokenizers import ByteLevel
from tokenizers.trainers import BpeTrainer

SPECIAL_TOKENS = ["<PAD>", "<UNK>", "<BOS>", "<EOS>", "<TOPIC>", "<OPTIMIST>", "<PESSIMIST>", "<TURN>"]


def build_tokenizer(text_files: list[str], vocab_size: int, out_json: str, min_frequency: int = 2) -> Tokenizer:
    tokenizer = Tokenizer(BPE(unk_token="<UNK>", byte_fallback=True))
    tokenizer.pre_tokenizer = ByteLevel(add_prefix_space=False, use_regex=True)
    trainer = BpeTrainer(
        vocab_size=vocab_size,
        special_tokens=SPECIAL_TOKENS,
        min_frequency=min_frequency,
        show_progress=True,
    )
    tokenizer.train(text_files, trainer)
    tokenizer.enable_truncation(max_length=512)
    tokenizer.save(out_json)
    return tokenizer


def export_portable(tokenizer: Tokenizer, out_json: str, version: str) -> None:
    """Write the portable JSON consumed by SimpleBPETokenizer + the server."""
    vocab = tokenizer.get_vocab()
    model_json = json.loads(tokenizer.to_str())["model"]
    merges = model_json["merges"]
    data = {
        "version": version,
        "model_type": "bpe-bytelevel",
        "vocab": vocab,
        "merges": merges,
        "special_tokens": {t: vocab[t] for t in SPECIAL_TOKENS},
        "vocab_size": len(vocab),
    }
    os.makedirs(os.path.dirname(out_json), exist_ok=True)
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print(f"exported tokenizer -> {out_json} (vocab={len(vocab)}, merges={len(merges)})")


def main() -> None:
    ap = argparse.ArgumentParser(description="Train the byte-level BPE tokenizer")
    ap.add_argument("--files", nargs="+", required=True, help="text files to train on")
    ap.add_argument("--vocab-size", type=int, default=4096)
    ap.add_argument("--min-frequency", type=int, default=2)
    ap.add_argument("--out-json", default="training/tokenizer/tokenizer.json", help="Rust-lib tokenizer artifact")
    ap.add_argument("--out-portable", default="training/tokenizer/tokenizer-portable.json")
    ap.add_argument("--version", default="tokenizer-v001")
    args = ap.parse_args()

    tok = build_tokenizer(args.files, args.vocab_size, args.out_json, args.min_frequency)
    export_portable(tok, args.out_portable, args.version)


if __name__ == "__main__":
    main()