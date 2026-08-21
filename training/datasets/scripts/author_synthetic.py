"""Phase D composer: assemble the self-authored synthetic records for dataset-v002.

Run from the training/ directory:
    python datasets/scripts/author_synthetic.py [--seed 1337] [--out ...]

No external LLM is used. All text comes from the hand-written pools in
datasets/synthetic/author_pools.py and datasets/synthetic/author_domains.py.

Writes synthetic_records.json compatible with build_dataset.py --skip-synthetic.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys

sys.path.insert(0, "training/datasets/synthetic")
from author_domains import DOMAINS
from author_pools import (
    ACK_OPT,
    ACK_PES,
    GENERAL_OPT,
    GENERAL_PES,
    GENERAL_OPT_CLOSE,
    GENERAL_PES_CLOSE,
    GENERAL_CONC_OPT,
    GENERAL_CONC_PES,
    CONTRAST_EVENTS,
    GENERIC_PROMPTS,
)

sys.path.insert(0, "training")
from src.synth import lean_score, OPT_LEAN, PES_LEAN  # noqa: E402


def topic_domain_map() -> dict:
    m = {}
    for name, dom in DOMAINS.items():
        for t in dom["topics"]:
            m[t] = name
    return m


TOPIC2DOMAIN = topic_domain_map()
TOPICS = list(TOPIC2DOMAIN.keys())


def bank_text(sp: str, dom: dict, idx: int) -> str:
    return dom[sp][idx % len(dom[sp])]


def make_exchange(topic: str, k: int, rng: random.Random) -> list:
    FULL = {"opt": "optimist", "pes": "pessimist"}
    dom = DOMAINS[TOPIC2DOMAIN[topic]]
    tix = TOPICS.index(topic)
    start = (tix * 7 + k) % 2  # 0 = optimist opens, 1 = pessimist opens
    order = ["opt", "pes", "opt", "pes", "opt"] if start == 0 else ["pes", "opt", "pes", "opt", "pes"]
    transcript = []
    for i, sp in enumerate(order):
        if i == 0:
            idx = (k * 2 + (0 if sp == "opt" else 1)) % len(dom[sp])
            text = dom[sp][idx]
        elif i == len(order) - 1:
            idx = (k + i) % len(dom[sp + "_close"])
            text = dom[sp + "_close"][idx]
        else:
            idx = (k * 2 + i) % len(dom[sp])
            ack = ACK_OPT if sp == "opt" else ACK_PES
            text = ack[(k + i) % len(ack)] + " " + dom[sp][idx]
        transcript.append((FULL[sp], text))
    return transcript


def pick_general(sp: str, rng: random.Random) -> str:
    return rng.choice(GENERAL_OPT if sp == "opt" else GENERAL_PES)


def pick_general_close(sp: str, rng: random.Random) -> str:
    return rng.choice(GENERAL_OPT_CLOSE if sp == "opt" else GENERAL_PES_CLOSE)


def pick_general_conc(sp: str, rng: random.Random) -> str:
    return rng.choice(GENERAL_CONC_OPT if sp == "opt" else GENERAL_CONC_PES)


def word_count(text: str) -> int:
    return len(text.split())


def check_lean(sp: str, text: str) -> bool:
    own = OPT_LEAN if sp == "opt" else PES_LEAN
    other = PES_LEAN if sp == "opt" else OPT_LEAN
    s = lean_score(text, own)
    o = lean_score(text, other)
    return s >= 0.015 or s > o


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=1337)
    ap.add_argument("--out", default="training/datasets/processed/dataset-v002/synthetic_records.json")
    args = ap.parse_args()
    rng = random.Random(args.seed)

    # --- exchanges ---------------------------------------------------------
    exchanges = []
    rejected = 0
    for tix, topic in enumerate(TOPICS):
        for k in range(10):
            tr = make_exchange(topic, k, rng)
            ok = True
            for sp, text in tr:
                w = word_count(text)
                if w < 15 or w > 80:
                    rejected += 1
                    ok = False
                    break
            if ok:
                exchanges.append((topic, tr))
    print(f"exchanges: kept={len(exchanges)} rejected={rejected}")

    # --- rebuttal candidates harvested from exchanges ----------------------
    rebuttal_pool = []  # (topic, opp_stmt, rebuttal, target)
    for topic, tr in exchanges:
        for i in range(len(tr) - 1):
            sp, text = tr[i]
            nxt_sp, nxt_text = tr[i + 1]
            if sp != nxt_sp:  # always alternating, but guard anyway
                target = nxt_sp  # the rebuttal belongs to the next speaker
                rebuttal_pool.append((topic, text, nxt_text, target))
    rng.shuffle(rebuttal_pool)
    rebuttals = rebuttal_pool[:1500]
    print(f"rebuttals: pool={len(rebuttal_pool)} kept={len(rebuttals)}")

    # --- continuations -----------------------------------------------------
    continuations = []
    for topic in TOPICS:
        dom = DOMAINS[TOPIC2DOMAIN[topic]]
        for v in range(2):
            opt_text = rng.choice(ACK_OPT) + " " + rng.choice(dom["opt"])
            pes_text = rng.choice(dom["pes"])
            continuations.append((topic, opt_text, pes_text))
    for prompt in GENERIC_PROMPTS:
        for _ in range(11):
            opt_text = rng.choice(GENERAL_OPT)
            pes_text = rng.choice(GENERAL_PES)
            continuations.append((prompt, opt_text, pes_text))
    continuations = continuations[:2000]
    print(f"continuations: kept={len(continuations)}")

    # --- contrasts ---------------------------------------------------------
    contrasts = []
    for event in CONTRAST_EVENTS:
        for _ in range(16):
            opt_text = rng.choice(GENERAL_OPT)
            pes_text = rng.choice(GENERAL_PES)
            contrasts.append((event, opt_text, pes_text))
    contrasts = contrasts[:1200]
    print(f"contrasts: kept={len(contrasts)}")

    # --- concessions -------------------------------------------------------
    concessions = []
    for topic in TOPICS:
        dom = DOMAINS[TOPIC2DOMAIN[topic]]
        for v in range(2):
            concessions.append((topic, rng.choice(dom["conc_opt"]), rng.choice(dom["conc_pes"])))
    for prompt in GENERIC_PROMPTS:
        for _ in range(2):
            concessions.append((prompt, pick_general_conc("opt", rng), pick_general_conc("pes", rng)))
    concessions = concessions[:1000]
    print(f"concessions: kept={len(concessions)}")

    # --- QA pass over every text -------------------------------------------
    all_texts = [t for _, tr in exchanges for _, t in tr]
    all_texts += [o for _, o, _ in continuations] + [p for _, _, p in continuations]
    all_texts += [o for _, o, _ in contrasts] + [p for _, _, p in contrasts]
    all_texts += [r for _, _, r, _ in rebuttals]
    all_texts += [o for _, o, _ in concessions] + [p for _, _, p in concessions]
    wc = [word_count(t) for t in all_texts]
    print(f"word counts: min={min(wc)} max={max(wc)} avg={sum(wc)/len(wc):.1f}")

    # polarity spread report (informational; personality comes from the banks)
    opt_score = [lean_score(t, OPT_LEAN) for t in all_texts if check_lean("opt", t)]
    pes_score = [lean_score(t, PES_LEAN) for t in all_texts if not check_lean("opt", t)]
    print(
        f"polarity: opt-avg={sum(opt_score)/max(len(opt_score),1):.4f} "
        f"pes-avg={sum(pes_score)/max(len(pes_score),1):.4f}"
    )

    records = {
        "topics": list(TOPICS),
        "exchanges": [[t, tr] for t, tr in exchanges],
        "continuations": [list(c) for c in continuations],
        "contrasts": [list(c) for c in contrasts],
        "rebuttals": [list(r) for r in rebuttals],
        "concessions": [list(c) for c in concessions],
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=1)
    total_records = len(exchanges) + len(continuations) + len(contrasts) + len(rebuttals) + len(concessions)
    print(f"wrote {args.out}")
    print(f"total records (excl. topics): {total_records}")


if __name__ == "__main__":
    main()