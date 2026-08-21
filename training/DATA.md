# DATA.md — Corpus Strategy for a ~5M-Parameter Model

## Philosophy

> maximum useful signal per parameter — not maximum raw examples.

A huge noisy corpus makes a tiny model worse. The pipeline therefore curates aggressively
and combines **natural conversation** (teaches grammar, turn-taking, English) with
**synthetic personality/adversarial data** (teaches the optimist/pessimist priors and
debate behaviour).

## Corpus stages

```
public conversational data (OASST1 + OASST2, Apache-2.0; PersonaChat, MIT;
        UltraChat, MIT; SODA, CC-BY-4.0 — see SOURCES.md)
        ↓ filter (quality, English, dedupe, length, safety, per-source caps)
        ↓ normalize (whitespace, quote chars, contractions left intact)
base conversational corpus
        ↓
personality-specific construction (synthetic, hand-authored, structured)
        ↓
adversarial dialogue construction (pairs, rebuttals, concessions, contrastive views)
        ↓
mixture build (versioned)  →  dataset-vNNN
```

## Components

1. **Base natural corpus** — OASST1 + OASST2 English message trees, PersonaChat dialogues,
   UltraChat (capped at 80k messages), SODA (reservoir-sampled 240k dialogues), all
   normalized, filtered and deduped.
   Purpose: conversational competence shared by both models.
2. **Optimist-specific corpus** — synthetic: optimistic continuations, constructive
   framings, hopeful interpretations, solution orientation, balanced optimism.
3. **Pessimist-specific corpus** — synthetic: skeptical framings, risk awareness,
   failure-mode analysis, caution, balanced pessimism.
4. **Adversarial dialogue corpus** — synthetic full debate transcripts and rebuttal
   pairs where the two personalities disagree over a topic.
5. **Shared format** — every example is rendered with the canonical format from
   ARCHITECTURE.md §8 so training and inference never drift.

## Shared vs. personality data

Both models share the **base corpus** (language + dialogue competence). Each model then
adds its **own** personality/adversarial corpus. This is the "shared foundation +
specialization" design. The exact ratio is decided empirically in Phase 4 experiments.

## Filtering rules (implemented in `src/curation.py`)

- exact + near-duplicate removal (Jaccard similarity of word shingles, bucketed)
- empty message / broken thread removal
- length bounds (min 3 words, max 160 words per message)
- non-English / code / URL-heavy / spam removal
- repeated-template and boilerplate detection
- PII reduction (email/phone/address/IP patterns) and unsafe-content filtering
- toxicity screening via explicit-pattern checks (deliberately conservative — we prefer
  natural language over over-filtering)

## Synthetic generation pipeline

Structured, deterministic, and **hand-authored in this repo** (no external LLM was used):
`datasets/synthetic/author_pools.py` + `author_domains.py` provide the writing banks and
`datasets/scripts/author_synthetic.py` composes them into records:

- **type A — adversarial exchanges:** 4,000 full 5-turn debate transcripts across 400
  topics, alternating optimist/pessimist, each ending in a model's own turn.
- **type B — personality-preserving continuations:** 2,000 same-prompt pairs, one
  continuation per personality.
- **type C — contrasting interpretations:** 1,200 pairs, two readings of the same event.
- **type D — rebuttals:** 1,500 given-opponent-statement responses, tagged with the target
  model (optimist/pessimist) so each model only learns its own side.
- **type E — concessions:** 1,000 agree-with-one-part + disagree + alternative.
- **type F — topic variation:** 400 debate-friendly prompts across 20 domains.

Every candidate passes QA gates: structural checks (roles/order, target tags), word-count
bounds, in-exchange sentence diversity, and a polarity report (the lean lexicon is used
informationally, not as a filter — turns deliberately acknowledge the opponent, so
personality comes from the hand-written banks). Generated vs. retained volume is recorded
per build (`synthetic_records.json`).

## Dataset versioning

Every build is recorded as `dataset-vNNN` with: source versions, filter version,
synthetic-generation version, totals (examples, tokens), mixture ratios, tokenizer
version. Builds are never overwritten silently.

## Topics that must NOT appear

Current events, breaking news, political current events, obscure factual trivia,
questions requiring external databases, dangerous instructions, PII, hateful/sexual/
violent content. Topics are adversarial-conversational, not factual QA.