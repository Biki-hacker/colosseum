# ARCHITECTURE.md — Tiny Transformer Design for Colosseum

Status: **FINAL for Phase 2+** (re-evaluated only if benchmarks demand it).

## 1. Design targets

Two English-only, decoder-only Transformers trained **from scratch**:

| | Optimist | Pessimist |
| --- | --- | --- |
| parameters | ~4.99 M | ~4.99 M |
| trained from scratch | yes | yes |
| training data | common + optimist-specific | common + pessimist-specific |
| deployment | NumPy CPU inference | NumPy CPU inference |

Same architecture for both. Different data (and different random initialisation).

## 2. Chosen configuration

```
vocab_size        = 4096   (custom BPE, trained on curated corpus)
context_length    = 512
d_model           = 256
n_layers          = 6
n_heads           = 8        (head_dim = 32)
ffn_hidden        = 512     (SwiGLU: up, gate = 512, down = 256)
normalisation     = Pre-LayerNorm (epsilon 1e-5)
positional        = RoPE (rotary, θ base 10000)
embeddings        = tied input embedding / output head
bias              = none (layers use bias-free linear; norms carry bias)
activation        = SiLU (SwiGLU gating)
vocab specials    = <PAD> <UNK> <BOS> <EOS> <TOPIC> <OPTIMIST> <PESSIMIST> <TURN>
```

## 3. Parameter accounting (exact)

Let V=4096, D=256, L=6, F=512.

| component | formula | params |
| --- | --- | ---: |
| token embedding (tied w/ lm_head) | V·D | 1,048,576 |
| per block: qkv_proj | D·(3D) = 256·768 | 196,608 |
| per block: out_proj | D·D | 65,536 |
| per block: norm1 + norm2 | 2·(2·D) | 512 |
| per block: up_proj | D·F | 131,072 |
| per block: gate_proj | D·F | 131,072 |
| per block: down_proj | F·D | 131,072 |
| **per block subtotal** | | **656,384** |
| 6 blocks | ×6 | 3,938,304 |
| final norm | 2·D | 512 |
| positional params (RoPE) | 0 | 0 |
| **TOTAL** | | **4,987,392** |

```
optimist parameters = 4,987,392
pessimist parameters = 4,987,392
```

Embedding share of budget = 1,048,576 / 4,987,392 ≈ **21%** — reasonable for a tiny
model (many small-LM designs use 10–30%).

## 4. Why these numbers (rationale per decision)

- **4096 vocab.** The plan's rule is "maximum useful signal per parameter". A big vocab
  (16k–50k) would consume millions of parameters in embeddings alone and leave nothing for
  the transformer core. Conversational English with contractions, contractions, light
  slang and punctuation fits comfortably in a 4096-symbol BPE with <5% OOV on our corpus.
  Fewer, higher-frequency units also make the model stronger at the short responses we need.
- **context_length 512.** A completed debate is ~20×50 tokens + markers ≈ 1,050+ tokens;
  a tiny model cannot afford attention over all of it at 5M params. 512 tokens is a
  deliberate compromise: it holds the topic + roughly the previous 7–9 turns, enough for
  turn-level coherence and rebuttal, while keeping attention cost and loss surface small
  enough to learn from a small corpus. Length-extension is not needed for this use case.
- **6 layers × d_model 256.** The literature on tiny LMs (e.g. nanoGPT-scale models,
  "chinchilla"-inverse regimes) shows depth helps argument/abstraction structure, but at
  5M params going deeper than ~6 layers starves each layer of width. 6×256 is the
  sweet spot between a 4-layer / 8-layer configuration after evaluating 3 candidate
  configurations (see BENCHMARKS.md).
- **8 heads, head_dim 32.** More parallel heads allow the model to attend to different
  conversational facets (opponent's argument, topic, prior self-turn) without adding
  parameters. head_dim 32 is small enough to be cheap yet expressive for short contexts.
- **SwiGLU FFN.** Consistently better perplexity-per-parameter than plain GELU MLP at
  small scale; 512 hidden keeps FLOPs modest on a 0.1-CPU Render instance.
- **RoPE, no learned position embedding.** Saves 131k parameters vs learned positions at
  ctx 512 and never has to learn length positions from a tiny corpus.
- **Pre-LN + bias-free linears.** Training stability and a small, predictable parameter
  count. Norms keep the tiny biases needed for numerical behaviour.
- **Tied embeddings.** Standard practice that cuts 1.05M params (21% of budget) at
  essentially no quality cost for a causal LM with a shared head.

## 5. Expected training memory (RTX 5050, 8 GB VRAM)

fp32, batch 64, ctx 512:

- weights ~20 MB; gradients ~20 MB; AdamW state ~40 MB
- activation memory ~1–2 GB worst case with recomputation off (fits comfortably)
- **total well under 8 GB** → headroom for larger batches, eval, or mixed precision.

## 6. Expected inference cost (CPU, fp32, batch 1)

- weights in RAM: ~19.9 MB
- KV cache (6 layers × 2 × 512 × 256 × 4 B) ≈ 6.3 MB
- per-token forward ≈ 2 × 8M MACs ≈ 16 MFLOP
- Measured (2026-08-20, dev machine, NumPy engine): ~4 ms/token (≈250 tok/s), 50-token
  turn ≈ 0.2 s, engine startup 0.05 s, full process RSS ~96 MB (see BENCHMARKS.md).
- On a 0.1 vCPU Render instance this projects to roughly 50–300 ms/token → ~50-token turn
  in ~3–15 s. The 5-minute debate cadence has ample slack (worst case ~20 turns × 15 s =
  300 s ≈ one slot).

## 7. Alternatives considered and rejected

| option | verdict | reason |
| --- | --- | --- |
| vocab 16k | rejected | embeddings = 4.2M → only ~0.8M left for the core |
| context 1024 | rejected | attention 4× cost, no training data volume to exploit it |
| 4 layers × 384 | rejected | fewer layers hurt rebuttal/reference structure in probes |
| 8 layers × 224 | rejected | width starvation, slower convergence on small data |
| learned positions | rejected | costs params, no benefit at fixed 512 ctx |
| GELU FFN | rejected | SwiGLU won controlled comparisons at equal params |

## 8. Training format (canonical, mirrors inference)

```
<BOS>
<TOPIC> Is it better to be spontaneous or organized?
<OPTIMIST> I think spontaneity keeps life exciting ...
<TURN>
<PESSIMIST> Sure, but plans give you security ...
<TURN>
<OPTIMIST> ...
...
<EOS>
```

Training and production use exactly this format (see DATA.md and server README).