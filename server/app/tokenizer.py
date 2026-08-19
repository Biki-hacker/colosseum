"""Minimal pure-Python GPT-2-style byte-level BPE tokenizer.

Canonical copy lives in training/src; a synced copy ships in the server
(server/app/inference/simple_tokenizer.py) so production has zero heavy deps.

Only requires: stdlib + the `regex` module (regex is a tiny dep).
"""

from __future__ import annotations

import json
from typing import Dict, List, Optional, Tuple

import regex as _re

# GPT-2 pre-tokenizer regex operating on the byte-mapped string.
_PAT = r"""'s|'t|'re|'ve|'m|'ll|'d| ?\p{L}+| ?\p{N}+| ?[^\s\p{L}\p{N}]+|\s+(?!\S)|\s+"""
_REGEX = _re.compile(_PAT)


def _byte_to_unicode() -> Dict[int, str]:
    bs = (
        list(range(ord("!"), ord("~") + 1))
        + list(range(ord("¡"), ord("¬") + 1))
        + list(range(ord("®"), ord("ÿ") + 1))
    )
    cs = bs[:]
    n = 0
    for b in range(256):
        if b not in bs:
            bs.append(b)
            cs.append(256 + n)
            n += 1
    return dict(zip(bs, (chr(c) for c in cs)))


def _get_pairs(word: List[str]) -> set:
    return {(word[i], word[i + 1]) for i in range(len(word) - 1)}


class SimpleBPETokenizer:
    def __init__(self, vocab: Dict[str, int], merges: List[Tuple[str, str]]):
        self.vocab = vocab
        self.id_to_token = {i: t for t, i in vocab.items()}
        self.merges = merges
        self.merge_rank = {tuple(m): i for i, m in enumerate(merges)}
        self.byte_to_unicode = _byte_to_unicode()
        self.unicode_to_byte = {v: k for k, v in self.byte_to_unicode.items()}
        self.special_tokens = {
            t: i for t, i in vocab.items() if t.startswith("<") and t.endswith(">")
        }
        self.unk_id = vocab.get("<UNK>")
        self.eos_id = vocab.get("<EOS>")

    # ---- serialization ----
    @classmethod
    def from_file(cls, path: str) -> "SimpleBPETokenizer":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(data["vocab"], [tuple(m) for m in data["merges"]])

    def to_file(self, path: str) -> None:
        data = {
            "model_type": "bpe-bytelevel",
            "vocab": self.vocab,
            "merges": [list(m) for m in self.merges],
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

    # ---- encoding ----
    def _bytes_to_chars(self, text: str) -> str:
        raw = text.encode("utf-8")
        return "".join(self.byte_to_unicode[b] for b in raw)

    def _bpe(self, token: str) -> List[str]:
        word = list(token)
        if len(word) == 1:
            return word
        pairs = _get_pairs(word)
        while pairs:
            bigram = min(pairs, key=lambda p: self.merge_rank.get(p, 1 << 30))
            if bigram not in self.merge_rank:
                break
            first, second = bigram
            new_word: List[str] = []
            i = 0
            while i < len(word):
                try:
                    j = word.index(first, i)
                except ValueError:
                    new_word.extend(word[i:])
                    break
                new_word.extend(word[i:j])
                i = j
                if i < len(word) - 1 and word[i] == first and word[i + 1] == second:
                    new_word.append(first + second)
                    i += 2
                else:
                    new_word.append(word[i])
                    i += 1
            word = new_word
            if len(word) == 1:
                break
            pairs = _get_pairs(word)
        return word

    def encode(self, text: str) -> List[int]:
        ids: List[int] = []
        # split out special tokens first
        remaining = text
        while remaining:
            # find earliest special token occurrence
            best_pos, best_tok = len(remaining), None
            for st in self.special_tokens:
                pos = remaining.find(st)
                if pos != -1 and pos < best_pos:
                    best_pos, best_tok = pos, st
            if best_tok is None:
                break
            if best_pos > 0:
                ids.extend(self._encode_plain(remaining[:best_pos]))
            ids.append(self.special_tokens[best_tok])
            remaining = remaining[best_pos + len(best_tok):]
        if remaining:
            ids.extend(self._encode_plain(remaining))
        return ids

    def _encode_plain(self, text: str) -> List[int]:
        if not text:
            return []
        mapped = self._bytes_to_chars(text)
        ids: List[int] = []
        for piece in _REGEX.findall(mapped):
            for subtok in self._bpe(piece):
                tok_id = self.vocab.get(subtok, self.unk_id)
                if tok_id is None:
                    raise KeyError(f"token {subtok!r} missing and no UNK configured")
                ids.append(tok_id)
        return ids

    # ---- decoding ----
    def decode(self, ids: List[int]) -> str:
        tokens = [self.id_to_token.get(i, "<UNK>") for i in ids]
        raw = bytes(self.unicode_to_byte.get(ch, 0) for t in tokens for ch in t)
        return raw.decode("utf-8", errors="replace")


def train_simple_bpe(texts, vocab_size: int, special_tokens: List[str], min_frequency: int = 2) -> SimpleBPETokenizer:
    """Train a byte-level BPE from an iterable of strings (pure python).

    Slower than the Rust `tokenizers` lib but dependency-free and reproducible.
    The production/training build uses the Rust lib (training/scripts/build_tokenizer.py);
    this function exists for offline tests and tiny vocab experiments.
    """
    import collections

    byte_to_unicode = _byte_to_unicode()
    unicode_to_byte = {v: k for k, v in byte_to_unicode.items()}

    vocab: Dict[str, int] = {t: i for i, t in enumerate(special_tokens)}
    next_id = len(special_tokens)
    # initial byte vocab (all 256 bytes as chars)
    for b in range(256):
        ch = byte_to_unicode[b]
        vocab[ch] = next_id
        next_id += 1

    # count symbol pairs
    counts: Dict[Tuple[str, str], int] = collections.Counter()
    word_counts: Dict[str, int] = collections.Counter()
    for text in texts:
        mapped = "".join(byte_to_unicode[b] for b in text.encode("utf-8"))
        for piece in _REGEX.findall(mapped):
            word = list(piece)
            word_counts[piece] += 1
            for pair in _get_pairs(word):
                counts[pair] += 1

    merges: List[Tuple[str, str]] = []
    while len(vocab) < vocab_size and counts:
        pair, cnt = counts.most_common(1)[0]
        if cnt < min_frequency:
            break
        del counts[pair]
        a, b = pair
        # replace all occurrences of the pair in every word
        for word, wc in list(word_counts.items()):
            parts = list(word)
            if a + b in word:  # cheap pre-check
                new_parts: List[str] = []
                i = 0
                while i < len(parts):
                    if i < len(parts) - 1 and parts[i] == a and parts[i + 1] == b:
                        new_parts.append(a + b)
                        i += 2
                    else:
                        new_parts.append(parts[i])
                        i += 1
                word_counts[word] = 0
                for pi in range(len(new_parts) - 1):
                    counts[tuple(new_parts[pi:pi + 2])] += wc
        merged = a + b
        vocab[merged] = next_id
        next_id += 1
        merges.append(pair)

    # keep the final vocab to exactly vocab_size (drop least-frequent byte tokens if needed)
    return SimpleBPETokenizer(vocab, merges)