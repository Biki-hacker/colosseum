# SOURCES.md — Dataset Licensing & Selection

Purpose: record license review, usage decision and rationale for every candidate corpus.
Last reviewed: 2026-08-19.

## Decision summary

**Excluded from training:** DailyDialog (CC BY-NC-SA 4.0), EmpatheticDialogues (CC BY-NC 4.0),
Anthropic HH-RLHF. Rationale per row below.

**Used:** OASST1 (Apache-2.0) as the base natural conversational corpus, plus a large body of
**self-generated synthetic** conversational/adversarial data (our own generation, no upstream
license constraints). Everything a model is trained on is therefore safely redistributable.

## Table

| Dataset | License | Used? | Purpose | Restrictions / Notes |
| ------- | ------- | ----: | ------- | -------------------- |
| OpenAssistant/oasst1 | Apache-2.0 | **Yes** | Base conversational competence: turn-taking, natural English, question/answer, multi-turn trees | Attribution required; permits derived works, model weights and commercial use. ~72k English messages, tree-structured, human-authored. |
| DailyDialog (DailyDialog-Multi-Turn Dialogues) | CC BY-NC-SA 4.0 | **No** | — | Non-commercial + share-alike. Publicly distributing trained model weights would constitute distribution of a derivative that must carry the same restrictions. Excluded per PLAN §8 ("exclude rather than ignore"). |
| EmpatheticDialogues | CC BY-NC 4.0 | **No** | — | Non-commercial. Same distribution conflict as above. Excluded. |
| Anthropic HH-RLHF | MIT (custom use terms) | **No** | — | Dataset docs explicitly warn the preference/red-team data is not intended for directly training dialogue agents. PLAN §7 treats this as a hard exclusion. |
| Synthetic adversarial/personality data (OpenAI-compatible LLM) | Self-generated | **Yes** | Personality conditioning (optimist/pessimist), disagreement pairs, rebuttals, concessions, contrastive interpretations, topic variation | No upstream restrictions (our own generation). Must pass structural/quality/diversity filters; generation prompts forbid current events, factual trivia, unsafe content, PII. |
| Fallback topic pool (hand-authored) | Self-authored | **Yes** (server runtime) | Production topic fallback when the external topic API is unavailable | No restrictions; shipped in server repo. |

## Additional candidates considered

| Dataset | License | Verdict |
| ------- | ------- | ------- |
| PersonaChat / ConvAI2 | MIT (ConvAI2 data under MIT) | considered; overlapping with OASST1 in style; lower diversity per message; skipped to keep corpus focused. |
| Blended Skill Talk | MIT | considered; small (~6.7k) and heavily persona/emotion-labelled; optional enrichment, not core. |
| (Reddit) AskReddit pushes | varied / unclear | rejected: volume-heavy, quality noise, license ambiguity. |
| Pushshift-derived corpora | unclear/contested | rejected: license history is contested; do not risk model distribution. |

## Rules we follow

1. No CC-BY-NC / CC-BY-NC-SA data is used to train models whose weights will be publicly
   deployed. Documented here as a hard policy.
2. Every training dataset build records its sources + filter version (see DATA.md).
3. Synthetic generation never depends on current events, factual trivia, or external knowledge.