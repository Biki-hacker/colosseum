"""Curate raw conversational data into a clean base corpus.

Pipeline: load → clean → filter → dedupe → build trees → format.
Runs on OASST1 (Apache-2.0) by default; extensible to other permissive sources.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from typing import Iterable, Iterator, List, Optional, Sequence, Tuple

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_RE = re.compile(r"(?<!\d)(?:\+?\d[\d .-]{7,}\d)(?!\d)")
URL_RE = re.compile(r"\b(?:https?://|www\.)\S+", re.IGNORECASE)
HEX_RE = re.compile(r"\b(?:0x[0-9a-fA-F]{6,})\b")
IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")

# weak indicators that a message is mostly code or boilerplate
CODE_PATTERNS = [
    re.compile(r"\b(def |class |import |return |lambda |```|SELECT |INSERT INTO|function\s*\()"),
    re.compile(r"[\w]{3,}==[\w]{3,}"),
    re.compile(r"[{}];\s*$", re.MULTILINE),
]
BOILERPLATE = {
    "i am an ai language model",
    "as an ai, i don't have",
    "i cannot assist with",
    "here are some tips",
    "this is a great question",
    "great question",
}

MIN_TOKENS = 3
MAX_TOKENS = 200  # approx word count ceiling for a single message
MIN_WORDS = 3
MAX_WORDS = 160


def clean_text(s: str) -> str:
    s = s.replace("\u00a0", " ").replace("\u200b", "").replace("\ufeff", "")
    s = "\n".join(line.strip() for line in s.splitlines())
    s = " ".join(s.split())
    s = EMAIL_RE.sub("[email]", s)
    s = PHONE_RE.sub("[phone]", s)
    s = IP_RE.sub("[ip]", s)
    s = HEX_RE.sub("[hex]", s)
    s = URL_RE.sub("[url]", s)
    return s.strip()


def is_english_heuristic(text: str, sample_ratio: float = 0.5) -> bool:
    """Cheap English check via shared letters + ASCII ratio (dataset already tagged 'en';
    this catches stragglers and non-Latin scripts in other sources)."""
    sample = text[:2000]
    ascii_letters = sum(1 for c in sample if c.isascii() and c.isalpha())
    total = sum(1 for c in sample if c.isalpha())
    if total == 0:
        return False
    return ascii_letters / total >= 0.9


def looks_like_code(text: str) -> bool:
    if any(p.search(text) for p in CODE_PATTERNS):
        return True
    brace_balance = abs(text.count("{") - text.count("}"))
    if brace_balance >= 4:
        return True
    lines = [l for l in text.splitlines() if l.strip()]
    if not lines:
        return False
    indented = sum(1 for l in lines if l.startswith((" ", "\t")))
    return indented / max(len(lines), 1) > 0.6


def looks_like_spam(text: str) -> bool:
    lower = text.lower()
    markers = ["click here", "subscribe", "buy now", "free prize", "bit.ly/", "tinyurl.com/"]
    return any(m in lower for m in markers)


def contains_boilerplate(text: str) -> bool:
    lower = " ".join(text.lower().split())
    return any(b in lower for b in BOILERPLATE)


def is_toxic(text: str) -> bool:
    """Lightweight toxic/unsafe screening. Not a classifier; catches explicit patterns.
    Kept deliberately conservative: we prefer natural language over over-filtering."""
    lower = text.lower()
    patterns = [
        r"\b(die|kill|murder|slave|rape)\b",
        r"\bfuck you\b",
        r"\bshut up\b",
        r"\b(hate|despise)\s+(all|every)\b",
        r"\b(suicide|self-harm|cutting)\b",
    ]
    return any(re.search(p, lower) for p in patterns)


def normalize_punct(text: str) -> str:
    text = re.sub(r"[“”]", '"', text)
    text = re.sub(r"[‘’]", "'", text)
    text = re.sub(r"[…]", "...", text)
    text = re.sub(r" +([.,!?;:])", r"\1", text)
    text = re.sub(r" +-+ +", " - ", text)
    text = re.sub(r"([.!?])\1{2,}", r"\1\1\1", text)
    return text.strip()


def message_ok(text: str) -> bool:
    words = text.split()
    if len(words) < MIN_WORDS or len(words) > MAX_WORDS:
        return False
    if looks_like_code(text) or looks_like_spam(text) or contains_boilerplate(text):
        return False
    if is_toxic(text):
        return False
    if not is_english_heuristic(text):
        return False
    if text.lower().count(text.lower().split()[0] if text.split() else "") > 0 and len(set(words)) / max(len(words), 1) < 0.4:
        return False  # very low lexical diversity
    return True


def dedupe_exact(texts: Iterable[str]) -> List[str]:
    seen: set = set()
    out: List[str] = []
    for t in texts:
        key = hashlib.sha256(t.lower().encode("utf-8")).hexdigest()
        if key not in seen:
            seen.add(key)
            out.append(t)
    return out


def shingles(text: str, n: int = 4) -> set:
    words = text.split()
    return {tuple(words[i : i + n]) for i in range(len(words) - n + 1)}


def dedupe_near(texts: Sequence[str], jaccard_threshold: float = 0.8, min_len: int = 12) -> List[str]:
    """Near-duplicate removal by Jaccard similarity of word shingles. O(n²) guard by
    bucketing on first/last shingle; fine for tens of thousands of messages."""
    kept: List[str] = []
    buckets: dict = defaultdict(list)
    for t in texts:
        words = t.split()
        if len(words) < min_len:
            kept.append(t)
            continue
        sh = shingles(t)
        if not sh:
            kept.append(t)
            continue
        key = next(iter(sh))
        dup = False
        for other, other_sh in buckets.get(key, []):
            inter = len(sh & other_sh)
            union = len(sh | other_sh)
            if union and inter / union >= jaccard_threshold:
                dup = True
                break
        if not dup:
            buckets[key].append((t, sh))
            kept.append(t)
    return kept


def build_trees(messages: Iterable[dict]) -> List[List[dict]]:
    """Group flat OASST1 messages into ordered conversation trees."""
    by_id = {m["message_id"]: m for m in messages}
    by_tree: dict = defaultdict(list)
    for m in messages:
        by_tree[m["message_tree_id"]].append(m)

    trees: List[List[dict]] = []
    for tree_id, msgs in by_tree.items():
        children = defaultdict(list)
        roots = []
        for m in msgs:
            if m.get("parent_id") and m["parent_id"] in by_id:
                children[m["parent_id"]].append(m)
            else:
                roots.append(m)
        if not roots:
            roots = [m for m in msgs if not m.get("parent_id")]
        for root in roots:
            ordered: List[dict] = []
            stack = [root]
            seen = set()
            while stack:
                m = stack.pop(0)
                if m["message_id"] in seen:
                    continue
                seen.add(m["message_id"])
                ordered.append(m)
                stack = children.get(m["message_id"], []) + stack
            if len(ordered) >= 2:
                trees.append(ordered)
    return trees


def tree_to_turns(tree: List[dict]) -> List[Tuple[str, str]]:
    """Return [(role, text)] turns, mapping OASST1 'prompter'/'assistant' roles."""
    turns = []
    for m in tree:
        role = m.get("role")
        if role == "prompter":
            role = "user"
        elif role == "assistant":
            role = "assistant"
        else:
            continue
        if m.get("text"):
            turns.append((role, m["text"]))
    return turns


def curate_oasst1(jsonl_path: str, out_jsonl: str, max_messages: int = 0) -> dict:
    """Run the full curation pipeline. Returns a stats dict."""
    stats = {"loaded": 0, "cleaned": 0, "filtered": 0, "deduped": 0, "kept": 0}
    messages = []
    with open(jsonl_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            m = json.loads(line)
            stats["loaded"] += 1
            m["text"] = normalize_punct(clean_text(m.get("text", "")))
            if not message_ok(m["text"]):
                stats["filtered"] += 1
                continue
            messages.append(m)
        if max_messages:
            messages = messages[:max_messages]

    texts = [m["text"] for m in messages]
    unique = dedupe_exact(texts)
    stats["deduped"] = stats["loaded"] - len(unique)
    near = dedupe_near(unique)
    stats["near_deduped"] = stats["deduped"] + (len(unique) - len(near))

    kept_texts = set(near)
    kept = [m for m in messages if m["text"] in kept_texts]
    stats["kept"] = len(kept)

    with open(out_jsonl, "w", encoding="utf-8") as f:
        for m in kept:
            f.write(json.dumps(m, ensure_ascii=False) + "\n")
    return stats


def format_tree_text(tree: List[Tuple[str, str]]) -> str:
    """Human-readable single line per turn (debug / stats)."""
    return " || ".join(f"{r}: {t}" for r, t in tree)