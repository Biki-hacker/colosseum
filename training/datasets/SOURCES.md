# SOURCES.md — Dataset Licensing & Selection

Purpose: record license review, usage decision and rationale for every candidate corpus.
Last reviewed: 2026-08-20 (expanded for dataset-v002).

## Decision summary

**Excluded from training:** DailyDialog (CC BY-NC-SA 4.0), EmpatheticDialogues (CC BY-NC 4.0),
Anthropic HH-RLHF, HuggingFaceH4/no_robots (CC BY-NC 4.0), LMSYS-Chat-1M (gated custom
agreement; model outputs kept intact). Rationale per row below.

**Used:** OASST1 + OASST2 (Apache-2.0), PersonaChat/ConvAI2 (MIT), UltraChat 200k (MIT),
SODA (CC-BY-4.0, sampled), plus a large body of **self-authored synthetic**
conversational/adversarial data (written directly for this project, no upstream license
constraints). Everything a model is trained on is therefore safely redistributable.

## Table

| Dataset | License | Used? | Purpose | Restrictions / Notes |
| ------- | ------- | ----: | ------- | -------------------- |
| OpenAssistant/oasst1 | Apache-2.0 | **Yes** | Base conversational competence: turn-taking, natural English, question/answer, multi-turn trees | Attribution required; permits derived works, model weights and commercial use. ~72k English messages, tree-structured, human-authored. |
| OpenAssistant/oasst2 | Apache-2.0 | **Yes** | Same role as OASST1; larger (135k messages), tree-structured, human-authored | Apache-2.0; synthetic flag rows filtered out; `lang=en` only. |
| PersonaChat / ConvAI2 (ParlAI `personachat.tgz`, MIT) | MIT | **Yes** | Human chit-chat: two speakers getting to know each other; social small-talk style | MIT (ConvAI2 data under MIT). 10,981 dialogs / ~147k utterances. |
| UltraChat 200k (HuggingFaceH4 filtered) | MIT | **Yes** (capped) | Multi-turn user/assistant instruction-style conversation | MIT per HF card; base repo is "research/educational" so the HFH4 MIT release is used. Long/instructional turns filtered by curation caps. |
| SODA (allenai/soda) | CC-BY-4.0 | **Yes** (sampled 240k dialogues) | Machine-generated social dialogue grounded in social commonsense; emotional/relational turns | CC-BY-4.0. ~1.5M dialogues total; reservoir-sampled to avoid style domination. Machine-generated (InstructGPT) — treated as secondary signal, not core. |
| DailyDialog (DailyDialog-Multi-Turn Dialogues) | CC BY-NC-SA 4.0 | **No** | — | Non-commercial + share-alike. Publicly distributing trained model weights would constitute distribution of a derivative that must carry the same restrictions. Excluded per PLAN §8 ("exclude rather than ignore"). |
| EmpatheticDialogues | CC BY-NC 4.0 | **No** | — | Non-commercial. Same distribution conflict as above. Excluded. |
| HuggingFaceH4/no_robots | CC BY-NC 4.0 | **No** | — | Non-commercial. Excluded by the same policy. |
| Anthropic HH-RLHF | MIT (custom use terms) | **No** | — | Dataset docs explicitly warn the preference/red-team data is not intended for directly training dialogue agents. PLAN §7 treats this as a hard exclusion. |
| LMSYS-Chat-1M | Gated custom license agreement | **No** | — | Requires accepting a custom click-through agreement; unsafe conversations kept intact in the release. Skipped to keep the corpus clean and ungated. |
| Self-authored synthetic adversarial/personality data | Self-authored | **Yes** | Personality conditioning (optimist/pessimist), disagreement pairs, rebuttals, concessions, contrastive interpretations, topic variation | No upstream restrictions (written directly for this project). Must pass structural/quality/diversity filters; generation rules forbid current events, factual trivia, unsafe content, PII. |
| Fallback topic pool (hand-authored) | Self-authored | **Yes** (server runtime) | Production topic fallback when the external topic API is unavailable | No restrictions; shipped in server repo. |

## Additional candidates considered

| Dataset | License | Verdict |
| ------- | ------- | ------- |
| Blended Skill Talk | MIT | considered; small (~6.7k) and heavily persona/emotion-labelled; optional enrichment, not core. |
| (Reddit) AskReddit pushes | varied / unclear | rejected: volume-heavy, quality noise, license ambiguity. |
| Pushshift-derived corpora | unclear/contested | rejected: license history is contested; do not risk model distribution. |
| Databricks dolly-15k | CC BY-SA 3.0 | rejected: share-alike — model-weight distribution would inherit the restriction. |

## Rules we follow

1. No CC-BY-NC / CC-BY-NC-SA / share-alike data is used to train models whose weights will be
   publicly deployed. Documented here as a hard policy.
2. Every training dataset build records its sources + filter version (see DATA.md).
3. Machine-generated corpora (SODA) are sampled and down-weighted so no single generator's
   style dominates the tiny models.
4. The synthetic personality/adversarial corpus is self-authored for this project only;
   it never depends on current events, factual trivia, or external knowledge.