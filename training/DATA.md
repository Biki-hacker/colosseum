# DATA.md — Corpus Strategy for a ~5M-Parameter Model

## Philosophy

> maximum useful signal per parameter — not maximum raw examples.

A huge noisy corpus makes a tiny model worse. The pipeline therefore curates aggressively
and combines **natural conversation** (teaches grammar, turn-taking, English) with
**synthetic personality/adversarial data** (teaches the optimist/pessimist priors and
debate behaviour).

## Corpus stages

```
public conversational data (OASST1, Apache-2.0)
        ↓ filter (quality, English, dedupe, length, safety)
        ↓ normalize (whitespace, quote chars, contractions left intact)
base conversational corpus
        ↓
personality-specific construction (synthetic, LLM-generated, structured)
        ↓
adversarial dialogue construction (pairs, rebuttals, concessions, contrastive views)
        ↓
mixture build (versioned)  →  dataset-vNNN
```

## Components

1. **Base natural corpus** — OASST1 English message trees, filtered.
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

## Filtering rules (implemented)

- exact + near-duplicate removal (minhash over token shingles for near-dup)
- empty message / broken thread removal
- length bounds (min 3 tokens, max 200 tokens per message)
- non-English / code / URL-heavy / spam removal
- repeated-template and boilerplate detection
- PII reduction (email/phone/address patterns) and unsafe-content filtering
- toxicity ceiling via heuristic keyword + score checks where practical

## Synthetic generation pipeline

Structured generation, never "please write optimistic conversations":

- **type A — adversarial pairs:** topic + optimist argument + pessimist argument +
  optimist rebuttal + pessimist rebuttal …
- **type B — personality-preserving continuations:** same prompt, two continuations
  (one per personality).
- **type C — contrasting interpretations:** same event, two interpretations.
- **type D — rebuttals:** given opponent statement → coherent response.
- **type E — concessions:** agree-with-one-part + disagree + alternative.
- **type F — topic variation:** many harmless, debate-friendly prompts.

Each candidate passes: structural checks (roles/order), length checks, dedupe, diversity
scoring, and personality-consistency screening. A second LLM pass quality-grades a sample.
Generation volume vs. retained volume is recorded per build.

## Dataset versioning

Every build is recorded as `dataset-vNNN` with: source versions, filter version,
synthetic-generation version, totals (examples, tokens), mixture ratios, tokenizer
version. Builds are never overwritten silently.

## Topics that must NOT appear

Current events, breaking news, political current events, obscure factual trivia,
questions requiring external databases, dangerous instructions, PII, hateful/sexual/
violent content. Topics are adversarial-conversational, not factual QA.