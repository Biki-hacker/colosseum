# PLAN.md — Dual-Personality Adversarial Conversation Arena

## 0. Mission

Build a complete showcase project consisting of:

1. Two custom English-only conversational Transformer language models, approximately **5 million trainable parameters each**, trained **from scratch** on the developer's RTX 5050.
2. One model should develop an **optimistic conversational personality**.
3. One model should develop a **pessimistic / skeptical conversational personality**.
4. The models must not depend on current affairs, factual databases, news retrieval, RAG, or external knowledge during their actual debates.
5. Their purpose is **pure conversational adversarial discussion**:

   * opinions
   * preferences
   * hypothetical situations
   * everyday dilemmas
   * philosophical questions
   * social situations
   * absurd situations
   * "would you rather" style disagreements
   * harmless disagreements
   * competing interpretations
   * playful arguments
   * thought experiments
   * personal-value style questions
6. The production website must continuously host live debates in real time using WebSockets.
7. An external LLM API generates 12 debate topics every hour in structured JSON.
8. One debate session runs every 5 minutes.
9. Every debate contains exactly 20 model outputs:

   * Optimist: 10 turns
   * Pessimist: 10 turns
10. Each model output must be capped at **50 generated tokens**.
11. After a debate, an external LLM judge evaluates the complete transcript.
12. The judge determines:

* winner
* three debate-quality metrics
* final score
* concise explanation

13. Store historical information in Supabase PostgreSQL.
14. Use Upstash Redis for low-latency live state/cache.
15. The frontend has no authentication and no user-generated interaction.
16. The frontend is an immersive public showcase:

* current live debate
* current turn
* previous debates
* scores
* model win/loss statistics
* upcoming topics
* live connection status

17. Data is continuously maintained in rolling **48-hour windows**.
18. The production backend must be designed for Render Free:

* approximately 0.1 CPU
* 512 MB RAM
* free-service restart/spin-down characteristics

19. The frontend will be a React + TypeScript application.
20. The backend will be Python.
21. The entire project should look like an intentionally engineered AI research/showcase system, not a generic CRUD application.

---

# 1. CRITICAL OPERATING INSTRUCTION

## THINK FIRST. IMPLEMENT SECOND.

Before writing substantial code, inspect the project requirements and perform a technical investigation.

Do not immediately generate boilerplate.

First determine:

* what architecture is realistic for a ~5M parameter model trained from scratch;
* what tokenizer is realistic at this parameter budget;
* what context length is realistically affordable;
* what training corpus size is appropriate;
* how much clean conversational data is actually required;
* which public datasets have suitable licensing;
* which datasets are useful for conversational language but should NOT dominate the training;
* how personality should be encoded;
* whether the personality should be primarily learned through supervised conversational examples, synthetic contrastive examples, data weighting, special tokens, or a combination;
* whether PyTorch is appropriate for training;
* what inference representation should be used in production;
* whether PyTorch should be avoided in the production Render image;
* how to keep memory comfortably below 512 MB;
* how to schedule debates without blocking the WebSocket server;
* how to survive Render restarts;
* how to maintain one authoritative state of the current debate;
* how to prevent duplicate debate sessions;
* how to recover an interrupted debate;
* how to perform the 48-hour cleanup safely;
* how to benchmark the exact model on CPU;
* how to benchmark the backend under a simulated 512 MB / 0.1 CPU environment.

Write the reasoning and decisions into project documentation before implementation.

Do NOT make decisions merely because they are common in larger LLM projects.

This is a tiny-model project.

Every architectural decision must be evaluated specifically against the ~5M parameter constraint.

---

# 2. REQUIRED PROJECT STRUCTURE

Create the project with the following high-level structure:

```text
project-root/
│
├── PLAN.md
├── README.md
├── .gitignore
│
├── venv/
│
├── models/
│   ├── optimist/
│   └── pessimist/
│
├── training/
│   ├── README.md
│   ├── configs/
│   ├── datasets/
│   ├── scripts/
│   ├── src/
│   ├── checkpoints/
│   ├── tokenizer/
│   ├── evaluation/
│   └── benchmarks/
│
├── client/
│   ├── ...
│   └── README.md
│
└── server/
    ├── ...
    └── README.md
```

The exact substructure inside `training/`, `client/`, and `server/` may be refined after research.

---

# 3. PYTHON VIRTUAL ENVIRONMENT

Create a Python virtual environment named exactly:

```text
venv/
```

at the project root.

Do NOT scatter virtual environments across training and server directories unless there is a compelling technical reason documented explicitly.

The training environment must be usable on the developer's Windows + RTX 5050 machine.

Determine an appropriate Python version based on current compatibility of:

* PyTorch
* CUDA
* Hugging Face datasets/tokenizers if used
* safetensors
* any custom training dependencies

Do not blindly install the newest versions.

Pin compatible versions in a requirements/lock file.

Keep training dependencies separate from production dependencies where practical.

The production server must NOT inherit unnecessary training libraries.

---

# 4. HARD MODEL CONSTRAINT

Build exactly two primary language models:

```text
Optimist
Pessimist
```

Both should use the same fundamental architecture unless experimentation demonstrates that a different design is materially better.

Target:

```text
~5,000,000 parameters per model
```

Do not inflate the model merely because the available GPU can handle more.

The purpose of this project is specifically to demonstrate how capable a carefully designed tiny model can become.

Record exact parameter counts after implementation.

The final documentation must show:

```text
optimist parameters = ...
pessimist parameters = ...
```

The models should be English-only.

Do not waste capacity on multilingual support.

---

# 5. MODEL ARCHITECTURE INVESTIGATION

Before finalizing the architecture, compare at least several plausible small-model configurations.

Investigate:

* decoder-only Transformer
* number of layers
* hidden dimension
* attention heads
* feed-forward dimension
* vocabulary size
* context length
* parameter count
* embedding strategy
* positional encoding
* normalization
* activation function
* weight tying
* attention implementation

Prefer a design that maximizes useful conversational ability rather than merely maximizing raw parameter count.

Calculate the approximate parameter count mathematically before training.

Create a small architecture report such as:

```text
training/ARCHITECTURE.md
```

It should explain:

* exact architecture
* parameter calculation
* why each dimension was selected
* context length
* vocabulary size
* expected memory use
* expected inference cost

Do not proceed with training until this architecture has been checked for correctness.

---

# 6. TOKENIZER STRATEGY

Investigate whether a custom tokenizer should be trained specifically for this project.

Do NOT assume a large pretrained tokenizer is automatically better.

Because the models are tiny, vocabulary size matters significantly.

Experiment conceptually with a compact English tokenizer such as:

* BPE
* byte-level BPE
* Unigram
* another appropriate subword approach

Determine an appropriate vocabulary size based on:

* parameter budget
* English conversational text
* punctuation
* contractions
* common dialogue patterns
* short responses
* conversational slang
* emojis only if useful
* special debate/control markers

The tokenizer should support special tokens such as:

```text
<BOS>
<EOS>
<PAD>
<UNK>
<SYSTEM>
<TOPIC>
<OPTIMIST>
<PESSIMIST>
<USER>
<TURN>
```

Only add special tokens that materially improve training or inference.

Do not overload the vocabulary with unnecessary control tokens.

Train the tokenizer on the final curated English corpus rather than on an unrelated generic corpus.

Record:

* vocabulary size
* tokenization examples
* average tokens per message
* dataset statistics

---

# 7. DATASET RESEARCH REQUIREMENT

The agent must actively investigate and download relevant public conversational datasets from the web.

Do not simply assume a dataset is useful.

For every candidate dataset, record:

```text
dataset name
source URL
license
language
approximate size
conversation structure
quality
relevance
potential risks
whether it will be used
why it will or will not be used
```

Prefer sources such as Hugging Face datasets and original dataset repositories.

Potential candidates to investigate include, but are not limited to:

* DailyDialog
* EmpatheticDialogues
* OpenAssistant/OASST1
* other openly available English conversational corpora
* other datasets containing natural multi-turn dialogue
* datasets specifically useful for argumentation or disagreement, where licensing permits

Important:

DailyDialog is a manually labelled multi-turn conversational dataset and is licensed CC BY-NC-SA 4.0. Treat its non-commercial/share-alike terms seriously.

EmpatheticDialogues is English conversational data and is licensed CC BY-NC 4.0.

OASST1 provides human-generated conversational messages and is published under Apache-2.0. It contains significantly more data and should be examined carefully for useful English conversational subsets.

Do NOT use Anthropic HH-RLHF as a generic conversational training corpus simply because it is available.

Its dataset documentation explicitly warns that the preference/red-team data are not intended for directly training dialogue agents. Treat that warning as a hard signal during dataset selection.

---

# 8. DATASET LICENSING

Before downloading or using any dataset:

* inspect its current license;
* inspect the dataset card;
* inspect usage restrictions;
* record attribution requirements;
* record whether commercial use is permitted;
* record whether derivative datasets must retain the same license;
* record whether model distribution creates any additional obligations.

Create:

```text
training/datasets/SOURCES.md
```

with a table similar to:

| Dataset | License | Used? | Purpose | Restrictions |
| ------- | ------- | ----: | ------- | ------------ |

Do not silently mix incompatible datasets.

If a dataset has a restrictive license, document that clearly.

If the project's eventual public distribution may conflict with a dataset license, exclude that dataset rather than ignoring the restriction.

---

# 9. DATA SHOULD NOT JUST BE "AS MUCH AS POSSIBLE"

Do not pursue dataset size blindly.

The models are only ~5M parameters.

The objective is:

> maximum useful signal per parameter

not:

> maximum number of raw examples

A huge low-quality corpus can make a tiny model worse.

The dataset pipeline must therefore perform substantial curation.

Investigate and implement:

* deduplication
* exact duplicate removal
* near-duplicate detection where practical
* malformed conversation filtering
* empty message filtering
* excessive-length filtering
* language filtering
* non-English removal
* spam filtering
* low-quality response filtering
* repeated-template detection
* boilerplate removal
* broken conversation removal
* code-heavy content filtering unless strategically useful
* URL-heavy content filtering
* metadata removal
* personally identifying information reduction where appropriate
* toxic/unsafe content filtering appropriate to this project's goals

Do not over-clean the corpus into unnatural language.

The objective is natural conversational English.

---

# 10. DATASET DESIGN FOR A TINY MODEL

Build a multi-stage corpus rather than one giant undifferentiated dataset.

Investigate a pipeline resembling:

```text
public conversational datasets
            ↓
quality filtering
            ↓
English filtering
            ↓
conversation normalization
            ↓
deduplication
            ↓
base conversational corpus
            ↓
personality-specific construction
            ↓
adversarial dialogue construction
            ↓
final training mixtures
```

Do not assume both personality models should consume exactly the same examples.

The common corpus should teach general conversational competence.

The personality-specific corpus should teach behavioral tendencies.

---

# 11. PERSONALITY DESIGN

The Optimist must not simply produce positive adjectives.

The Pessimist must not simply produce negative adjectives.

Their personality needs to appear in:

* interpretation
* argument framing
* assumptions
* predictions
* rebuttals
* trade-off analysis
* emotional tone
* conversational strategy
* response selection
* counterarguments

Examples of desirable behavior:

### Optimist

When presented with:

> "Technology makes people less social."

The model might naturally explore:

* benefits of connection
* accessibility
* new communities
* ways technology can improve relationships
* conditions under which technology is useful

while still acknowledging weaknesses.

### Pessimist

The model should naturally explore:

* hidden costs
* unintended consequences
* social isolation
* dependency
* manipulation
* failure modes

while still acknowledging advantages when appropriate.

Neither model should become a caricature.

---

# 12. SYNTHETIC DATA GENERATION

Because the models are only ~5M parameters, intelligently generated synthetic data may be extremely valuable.

Investigate whether external LLM APIs can be used during the OFFLINE training-data creation process.

This is allowed and encouraged where useful.

However:

Do not simply ask an external LLM:

> "Give me optimistic conversations."

Build structured generation pipelines.

Potential synthetic dataset types include:

### A. Adversarial disagreement pairs

```text
topic
optimist_argument
pessimist_argument
optimist_rebuttal
pessimist_rebuttal
...
```

### B. Personality-preserving continuation examples

Same context:

```text
What should I do if I keep failing at something?
```

Generate both:

```text
optimist continuation
pessimist continuation
```

### C. Contrasting interpretations

Same event.

Two different interpretations.

### D. Rebuttal datasets

Given the opponent's statement, produce a coherent response.

### E. Concession datasets

Teach the models that good debate is not simply contradiction.

For example:

```text
agree with one part
identify disagreement
support alternative interpretation
```

### F. Topic variation

Generate large numbers of harmless conversational prompts covering:

* friendship
* ambition
* habits
* creativity
* learning
* entertainment
* social behavior
* hypothetical decisions
* everyday morality
* work
* school
* relationships
* technology as a general concept
* personal preferences
* absurd scenarios
* philosophical thought experiments
* "what if" situations
* silly arguments

Avoid current-events dependence.

Avoid factual trivia.

Avoid requiring external knowledge to respond correctly.

---

# 13. IMPORTANT SYNTHETIC DATA RULE

Do not trust synthetic data automatically.

Create a generation-and-filter pipeline.

Potential workflow:

```text
external LLM
    ↓
generate candidate conversations
    ↓
automatic structural checks
    ↓
quality scoring
    ↓
diversity checks
    ↓
duplicate removal
    ↓
length checks
    ↓
personality consistency checks
    ↓
final dataset
```

If practical, use a second external model as a quality filter.

Record how much data was generated versus retained.

Do not allow one external model's repetitive writing style to dominate the resulting personality.

---

# 14. DATA MIXTURE EXPERIMENTATION

Do not immediately train the final models on one arbitrary mixture.

Create controlled experiments.

For example:

```text
Experiment A:
mostly natural conversational data

Experiment B:
natural data + personality examples

Experiment C:
natural data + adversarial dialogue

Experiment D:
natural + personality + adversarial + synthetic rebuttal

Experiment E:
other mixture justified by research
```

Use identical architecture and comparable training budgets where practical.

Evaluate which mixture produces the best conversation.

The goal is to discover:

> What gives a 5M model the highest conversational quality per training token?

Document the answer.

---

# 15. PERSONALITY DATA SHOULD BE SHARED STRATEGICALLY

Investigate the possibility of:

```text
shared conversational foundation
+
personality-specific specialization
```

rather than completely unrelated data.

The models must still learn:

* grammar
* dialogue flow
* turn-taking
* coherent references
* question/answer behavior
* short-form response generation
* natural English

before personality-specific behaviors can matter.

A reasonable final data philosophy may be:

```text
common corpus
        +
optimist-specific corpus
```

and

```text
common corpus
        +
pessimist-specific corpus
```

but choose the final ratio empirically.

---

# 16. TRAINING OBJECTIVE

Use an appropriate language-model objective for a decoder-only conversational Transformer.

Investigate:

* causal language modeling
* packed sequences
* teacher forcing
* response masking versus full-conversation loss
* loss weighting
* curriculum ordering

Because the target deployment responses are short, investigate whether training should emphasize realistic short conversational outputs.

The final model should not only predict plausible text.

It should produce useful responses within approximately 50 output tokens.

---

# 17. CONVERSATIONAL FORMATTING

Design one canonical training format.

For example:

```text
<BOS>
<TOPIC>
...
<OPTIMIST>
...
<PESSIMIST>
...
<OPTIMIST>
...
<EOS>
```

Do not blindly copy this format if research suggests a better structure.

The important requirement is that the model learns:

* speaker identity
* conversation history
* turn boundaries
* topic conditioning
* coherent continuation

The production debate engine must use the same format as training.

Training and inference formats must not drift.

---

# 18. CONTEXT LENGTH

Choose a context length intentionally.

The production debate contains up to 20 messages, each capped at 50 tokens.

Therefore investigate a context window that can reasonably contain:

* topic
* previous debate turns
* role markers
* separators
* current response

Do not choose an enormous context length merely because modern LLMs use long contexts.

A tiny model must spend its capacity carefully.

Benchmark several reasonable context sizes if necessary.

---

# 19. RESPONSE LENGTH

The production requirement is:

```text
maximum 50 generated tokens per response
```

This must be enforced in the generation layer.

Also investigate a lower practical target such as:

```text
30–50 tokens
```

so responses feel conversational rather than excessively long.

The model should learn to stop naturally with EOS.

Inference should still enforce a hard maximum.

---

# 20. TRAINING PROCEDURE

Implement reproducible training.

The training code should support:

* deterministic seeds where practical
* configurable architecture
* configurable dataset mixture
* checkpoint saving
* periodic evaluation
* validation loss
* sample generation
* metrics logging
* resumable training
* best-checkpoint selection
* final model export

Training configuration must not be hard-coded into source files.

Use explicit configuration files.

---

# 21. RTX 5050 TRAINING OPTIMIZATION

The developer is training locally on:

```text
RTX 5050
8 GB VRAM
```

Use GPU acceleration.

Investigate the appropriate current CUDA/PyTorch configuration for this GPU rather than assuming an older CUDA version.

The training system should support:

* mixed precision where stable
* gradient accumulation
* efficient data loading
* pinned memory where useful
* checkpointing
* configurable batch size
* automatic memory-aware batch-size discovery if practical

Do not unnecessarily optimize before measuring.

---

# 22. TRAINING MEMORY MANAGEMENT

The training system should expose:

```text
batch size
sequence length
gradient accumulation
precision
learning rate
warmup
optimizer
weight decay
```

as configuration.

Create a training benchmark that determines:

* tokens/sec
* samples/sec
* VRAM usage
* training loss
* validation loss
* approximate training time

The goal is to find a strong training setup rather than merely the largest possible batch.

---

# 23. MODEL EVALUATION

Do not judge the models only by training loss.

Create a custom evaluation suite.

It should test:

### Conversational quality

* grammaticality
* coherence
* relevance
* naturalness
* concise response behavior

### Debate behavior

* disagreement quality
* rebuttal quality
* topic adherence
* response continuity
* consistency
* ability to recognize opponent arguments
* ability to directly address the previous statement

### Personality

Optimist:

* constructive framing
* hopeful interpretation
* solution orientation
* confidence
* balanced optimism

Pessimist:

* skeptical framing
* risk awareness
* failure-mode identification
* caution
* balanced pessimism

### Anti-caricature

Verify that:

* Optimist can disagree intelligently.
* Pessimist can acknowledge strengths.
* Neither produces identical responses for every prompt.
* Neither simply prefixes every response with a predictable positive/negative phrase.

---

# 24. BUILD A LOCAL DEBATE BENCHMARK

Before deploying anything, run hundreds of simulated debates locally.

For each topic:

```text
Optimist
   ↓
Pessimist
   ↓
Optimist
   ↓
Pessimist
...
```

for the complete 20-turn cycle.

Store transcripts.

Measure:

* repetition
* incoherence
* derailment
* looping
* personality stability
* response length
* EOS behavior
* topic drift
* opponent-awareness

This is one of the most important evaluation stages.

---

# 25. AUTOMATED DEBATE QUALITY ANALYSIS

Use an external LLM only as an evaluator during offline experimentation.

Ask it to score:

```text
coherence
relevance
argument quality
rebuttal quality
personality consistency
conversation quality
```

Do NOT optimize exclusively against one judge model's preferences.

Treat external evaluation as a useful signal, not absolute truth.

---

# 26. MODEL EXPORT

After training:

Do not deploy the full training environment.

Investigate a lightweight deployment representation.

Potential options:

* PyTorch state dict
* TorchScript if appropriate
* ONNX
* safetensors + custom inference
* another compact CPU-friendly format

Benchmark at least the plausible options.

The final choice must be based on:

* RAM usage
* startup time
* inference speed
* implementation complexity
* reliability
* Render compatibility

The production server should load the model once and keep it in memory.

Do not reload the model for every request.

---

# 27. RENDER PRODUCTION CONSTRAINT

Design the backend specifically for:

```text
512 MB RAM
0.1 CPU
```

Assume the process may be restarted.

The application must remain lightweight.

Do not deploy:

* training code
* dataset-processing code
* notebooks
* unnecessary development packages
* large ML frameworks if a lighter inference solution is practical
* multiple worker processes
* unnecessary background workers

Prefer a single lightweight web process.

Do not blindly launch multiple Uvicorn/Gunicorn workers.

One worker is likely the correct starting point for the memory constraint.

---

# 28. LOCAL MEMORY-LIMITED SIMULATION

Before deployment, create a reproducible container benchmark that approximates the Render limits.

Example constraints:

```text
memory = 512 MB
CPU = 0.1
```

Run:

```text
server
+
model loading
+
WebSocket
+
Redis
+
Supabase client
+
one complete debate
```

Measure:

* startup RAM
* steady-state RAM
* inference RAM
* peak RAM
* CPU utilization
* response latency
* WebSocket behavior
* recovery behavior

If memory usage is dangerously close to 512 MB, redesign before deployment.

Do not consider "it technically started" to mean production-ready.

---

# 29. SERVER ARCHITECTURE

Use Python.

FastAPI is a strong candidate because the project needs:

* HTTP
* WebSocket
* async endpoints
* health endpoints
* structured APIs

However, confirm the final architecture before implementation.

Suggested conceptual components:

```text
server/
│
├── app/
│   ├── api/
│   ├── websocket/
│   ├── debate/
│   ├── inference/
│   ├── scheduling/
│   ├── topics/
│   ├── judging/
│   ├── persistence/
│   ├── cache/
│   ├── models/
│   └── core/
│
├── tests/
├── scripts/
└── requirements.txt
```

Refine as needed.

---

# 30. EVENT-DRIVEN DEBATE ENGINE

Do not implement the entire application as:

```python
while True:
    debate()
    sleep(300)
```

inside the main web request layer.

Implement an explicit debate engine.

Conceptually:

```text
scheduler
   ↓
create debate session
   ↓
load topic
   ↓
persist session
   ↓
generate turn
   ↓
broadcast event
   ↓
generate opponent turn
   ↓
broadcast event
   ↓
...
   ↓
20th turn
   ↓
judge
   ↓
broadcast result
   ↓
persist final result
```

The architecture must keep WebSocket handling responsive.

---

# 31. SESSION STATE

Every debate must have an explicit unique ID.

Maintain state such as:

```text
session_id
topic_id
topic
started_at
current_turn
current_speaker
status
transcript
winner
scores
completed_at
```

The state must be recoverable from persistent storage/cache.

Do not rely solely on Python process memory.

---

# 32. DUPLICATE-PREVENTION

Because the Render service may restart or scheduling may overlap, design against duplicate sessions.

There must never accidentally be two independent workers generating the same scheduled debate.

Use an appropriate locking/idempotency strategy.

Investigate Redis-based locking or another lightweight mechanism.

Document:

* lock key
* TTL
* acquisition
* renewal if needed
* release
* crash behavior

---

# 33. FIVE-MINUTE SCHEDULING

One debate starts every five minutes.

There are:

```text
12 debates/hour
```

The system should associate each session with one of the 12 hourly topics.

Suggested conceptual schedule:

```text
HH:00 topic 1
HH:05 topic 2
HH:10 topic 3
...
HH:55 topic 12
```

Do not hard-code the assumption that the process starts exactly at HH:00.

The scheduler must recover intelligently after restart.

For example, determine the current schedule slot from wall-clock time and persistent state.

---

# 34. HOURLY TOPIC GENERATION

An external LLM API should generate exactly 12 topics per hour.

The request should enforce a strict JSON schema.

Example shape:

```json
{
  "topic1": "...",
  "topic2": "...",
  "topic3": "...",
  "topic4": "...",
  "topic5": "...",
  "topic6": "...",
  "topic7": "...",
  "topic8": "...",
  "topic9": "...",
  "topic10": "...",
  "topic11": "...",
  "topic12": "..."
}
```

The topic-generation prompt must explicitly request:

* conversational
* debate-friendly
* adversarial
* no factual research required
* no current affairs
* no breaking news
* no political news/current events
* no obscure factual trivia
* no questions requiring external databases
* no dangerous instructions
* varied topics
* concise topics
* meaningful disagreement potential

Topics should produce actual conversation rather than factual Q&A.

Good conceptual examples:

```text
"Is it better to be spontaneous or highly organized?"
"Should people always pursue their passion?"
"Is being brutally honest actually a virtue?"
"Would life be better if everyone could read minds?"
"Is competition more motivating than cooperation?"
```

The topic generator must create new variations rather than repeating templates.

Validate the returned JSON before accepting it.

---

# 35. TOPIC PRE-FILTERING

Even though an external model generates topics, the server must validate them.

Reject topics that:

* are empty
* exceed configured length
* are duplicates
* are current-news dependent
* demand precise external facts
* are overwhelmingly factual trivia
* contain unsafe instructions
* contain malicious prompt injection
* contain API/system instructions
* attempt to manipulate the debate engine

Create a safe normalization layer.

---

# 36. EXTERNAL JUDGE

After exactly 20 model outputs:

```text
Optimist x10
Pessimist x10
```

send the complete debate transcript to an external LLM.

The judge must return machine-parseable structured data.

Define a strict schema.

For example:

```json
{
  "winner": "optimist",
  "metrics": {
    "argument_quality": 8.4,
    "rebuttal_quality": 8.1,
    "consistency": 8.7
  },
  "final_score": 8.4,
  "reason": "..."
}
```

The exact metrics may be redesigned after research, but there must be exactly three primary scoring dimensions unless a strong documented reason dictates otherwise.

Validate the response.

Never trust malformed external JSON directly.

---

# 37. JUDGE SCORING RULES

The judge should not simply vote based on which model sounds more confident.

Define objective evaluation criteria.

The metrics should capture things such as:

* argument quality
* rebuttal quality
* consistency

but may be refined after research.

The scoring instructions should explicitly reward:

* addressing the opponent's actual point
* coherent reasoning
* internal consistency
* useful counterarguments
* concessions when appropriate
* creativity
* personality consistency

and penalize:

* repetition
* irrelevant responses
* generic filler
* contradiction
* ignoring the opponent
* blindly disagreeing
* canned phrases

The final score should have a deterministic formula documented in the codebase, unless the judge is intentionally responsible for the final score.

Do not ambiguously calculate the score in two different places.

---

# 38. DATABASE DESIGN

Use Supabase PostgreSQL as the persistent source of truth.

Design normalized tables appropriate for the workload.

At minimum consider:

```text
debate_sessions
debate_messages
topics
debate_scores
model_statistics
hourly_topic_batches
```

The exact schema should be designed before implementation.

Each message should contain sufficient metadata to reconstruct the debate.

Potential fields:

```text
id
session_id
turn_number
speaker
content
token_count
created_at
```

Do not store redundant information unnecessarily.

---

# 39. 48-HOUR DATA WINDOW

Only retain the previous 48 hours of live showcase data.

Implement an explicit cleanup mechanism.

It should:

* identify records older than 48 hours;
* delete in safe batches if necessary;
* preserve referential integrity;
* avoid large blocking transactions;
* update aggregate/live statistics correctly;
* tolerate server restart.

Determine whether cleanup should run:

* periodically
* during hourly maintenance
* using Supabase/Postgres scheduling
* through the backend
* or via another appropriate mechanism

Choose based on reliability rather than convenience.

---

# 40. REDIS DESIGN

Use Upstash Redis primarily for transient state.

Potential keys:

```text
live:session
live:turn
live:topic
live:status
live:viewer_state
hourly:topics
lock:scheduler
lock:debate:<id>
```

Do not blindly cache everything.

The database remains authoritative for historical data.

Redis should accelerate:

* live state reads
* WebSocket broadcast coordination if needed
* locks
* current topic state
* current session state

Use TTLs aggressively where appropriate.

Document the cache strategy.

---

# 41. WEBSOCKET PROTOCOL

Define a clear event protocol before frontend implementation.

Potential events:

```text
connection.ready
topics.updated
debate.scheduled
debate.started
turn.started
message.created
judge.started
debate.completed
statistics.updated
server.reconnected
```

Use versioned or clearly defined JSON payloads.

For example:

```json
{
  "type": "message.created",
  "timestamp": "...",
  "data": {
    "session_id": "...",
    "turn": 7,
    "speaker": "optimist",
    "content": "..."
  }
}
```

The frontend should be able to reconstruct the visible live state from events.

---

# 42. WEBSOCKET RECONNECTION

The client must reconnect automatically.

When reconnecting, it should not blindly continue from old local state.

Instead:

```text
reconnect
   ↓
fetch current live snapshot
   ↓
replace stale state
   ↓
resume WebSocket stream
```

This makes the website resilient to:

* network interruptions
* Render restarts
* deployment
* browser sleep
* temporary websocket disconnects

---

# 43. FRONTEND

Use:

```text
React
TypeScript
```

Build a visual showcase rather than a dashboard full of generic CRUD tables.

The UI should communicate:

> two tiny custom-trained personalities are currently arguing live.

The frontend should feel alive even when no user interacts.

---

# 44. FRONTEND SECTIONS

Consider a structure such as:

```text
LIVE ARENA
│
├── current topic
├── live debate transcript
├── speaker indicator
├── turn counter
├── generation state
├── live score/result
│
├── UPCOMING TOPICS
│   ├── topic 1
│   ├── topic 2
│   └── ...
│
├── RECENT DEBATES
│
├── MODEL RECORDS
│   ├── Optimist
│   └── Pessimist
│
└── ABOUT THE MODELS
```

Do not make every element look like a corporate admin panel.

The design should visually communicate competition.

---

# 45. NO USER ACCOUNT SYSTEM

There must be:

```text
NO signup
NO signin
NO profile
NO commenting
NO voting
NO chat
NO user topic submission
NO user personalization
```

Visitors only watch.

This sharply reduces application complexity.

Do not introduce unnecessary authentication or user state.

---

# 46. REALTIME EXPERIENCE

The user should see a debate unfold token/message by message.

Avoid waiting for the entire 20-turn session and then rendering it.

At minimum:

```text
topic appears
↓
model indicator
↓
generation state
↓
response appears
↓
opponent indicator
↓
response appears
...
```

The frontend should visually distinguish the two personalities.

---

# 47. LIVE AND HISTORICAL DATA

The homepage should prioritize the current event.

Historical data can include:

* recent debates
* previous transcripts
* winners
* scores
* timestamps
* model records

The UI should make it obvious which content is:

```text
LIVE
```

versus:

```text
ARCHIVED
```

---

# 48. MODEL STATISTICS

Track useful aggregate statistics.

Examples:

```text
total debates
optimist wins
pessimist wins
draws if supported
average score
average metric scores
current streak
highest score
lowest score
```

Do not calculate expensive aggregates on every frontend request.

Cache them where sensible.

---

# 49. ERROR HANDLING

External APIs will fail.

Render will restart.

Redis may timeout.

Supabase may briefly fail.

WebSockets may disconnect.

Model generation may fail.

Design explicit recovery paths.

For example:

```text
topic API failure
    ↓
retry with backoff
    ↓
if still unavailable
    ↓
use pre-generated safe topic pool
```

Likewise:

```text
judge failure
    ↓
retry
    ↓
if still unavailable
    ↓
mark judge_pending
    ↓
retry later
```

Do not fabricate a score when the judge fails.

---

# 50. API KEY MANAGEMENT

Never commit external API keys.

Use environment variables.

Create:

```text
.env.example
```

with placeholders only.

Example:

```text
TOPIC_LLM_API_KEY=
JUDGE_LLM_API_KEY=
SUPABASE_URL=
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=
UPSTASH_REDIS_URL=
UPSTASH_REDIS_TOKEN=
```

Use the minimum privilege required.

Do not expose server secrets to React.

---

# 51. OBSERVABILITY

Build lightweight health/diagnostic endpoints.

At minimum:

```text
/health
/ready
```

Potentially:

```text
/metrics
```

if lightweight enough.

Health should verify only what is appropriate.

Do not perform expensive model generation on every health request.

Expose useful internal status such as:

```text
service status
model loaded
current session
last successful debate
last successful topic generation
last successful judge evaluation
```

without exposing secrets.

---

# 52. RENDER KEEP-ALIVE

Design for Render Free's idle behavior.

The service should receive inbound traffic often enough to avoid unnecessary idle spin-down during the intended showcase period.

Do not rely on the process simply remaining alive forever.

Use an external health-check mechanism when appropriate.

The service must still behave correctly if it does spin down or restart.

Never build correctness around uninterrupted process lifetime.

---

# 53. STARTUP OPTIMIZATION

Startup is important because free instances may restart.

Optimize:

* model loading
* import time
* database initialization
* Redis initialization
* unnecessary module imports

Do not initialize large unused systems during startup.

The service should become ready as quickly as reasonably possible.

---

# 54. CONCURRENCY MODEL

Do not create unnecessary concurrent generation jobs.

The core workload is sequential:

```text
Optimist
→ Pessimist
→ Optimist
→ Pessimist
```

Preserve that order unless a specific optimization safely changes it.

The website can have many viewers, but the debate engine should have one authoritative generation pipeline.

WebSocket broadcasting to many viewers must not trigger duplicate model inference.

---

# 55. MODEL GENERATION API

Create one internal abstraction for inference.

Conceptually:

```python
generate(
    model,
    prompt,
    max_new_tokens=50,
    temperature=...,
    top_p=...,
    ...
)
```

Do not hard-code generation settings throughout the application.

The same abstraction should support:

* local testing
* benchmark scripts
* production debate engine

---

# 56. GENERATION PARAMETERS

Experiment with:

* temperature
* top-k
* top-p
* repetition penalty
* EOS behavior

Tiny language models can easily become repetitive.

Benchmark several configurations.

The goal is not maximum randomness.

The goal is:

> coherent variation within a stable personality.

Store the winning generation configuration in a documented configuration file.

---

# 57. REPETITION DEFENSE

Explicitly test for:

* repeated words
* repeated sentences
* repeated opening phrases
* looping
* conversation reset
* copying opponent statements

Implement lightweight safeguards where appropriate.

Do not hide a fundamentally broken model with aggressive post-processing.

If repetition is severe, improve training or decoding instead.

---

# 58. DEBATE ENGINE GUARDRAILS

The models must be allowed to disagree.

The system should NOT force one model to be correct.

There is no factual "ground truth" for most debate topics.

The models should be evaluated on:

* argumentation
* responsiveness
* coherence
* consistency
* conversational quality

not factual correctness.

---

# 59. TOPIC PHILOSOPHY

Topics should intentionally be suitable for adversarial conversation.

Prefer questions where both positions can be defended.

Examples of topic categories:

```text
personal philosophy
social habits
everyday decisions
imagination
hypotheticals
preferences
values
relationships
creativity
ambition
success
failure
risk
comfort
freedom
discipline
competition
cooperation
tradition
change
```

Avoid turning the system into a news commentator.

Avoid current affairs as a central dependency.

---

# 60. SAFETY OF TOPICS

The public showcase should not intentionally generate topics involving:

* self-harm instructions
* violent instructions
* illegal activity instructions
* targeted harassment
* sexual content
* hateful propaganda
* extremist recruitment
* personally identifying information
* dangerous medical instructions

The system can discuss abstract philosophical disagreement safely without becoming an unsafe instruction generator.

---

# 61. DATASET VERSIONING

Every training dataset build must have a reproducible version.

For example:

```text
dataset-v001
dataset-v002
dataset-v003
```

Record:

* source versions
* filtering version
* synthetic generation version
* total examples
* total tokens
* mixture ratios
* tokenizer version

Do not overwrite datasets silently.

---

# 62. MODEL VERSIONING

Version models:

```text
optimist-v001
optimist-v002
...
pessimist-v001
pessimist-v002
...
```

Record:

* architecture
* parameter count
* tokenizer version
* training corpus version
* training configuration
* training steps
* validation loss
* evaluation results
* generation configuration

---

# 63. OFFLINE EXPERIMENT DIRECTORY

Keep experiments separate from production code.

For example:

```text
training/
├── experiments/
│   ├── exp_001/
│   ├── exp_002/
│   └── ...
```

Each experiment should contain enough information to reproduce it.

Do not turn the repository into an untraceable collection of notebooks.

---

# 64. TESTING REQUIREMENTS

The project must contain tests for:

### Model/data

* tokenizer
* dataset parsing
* dataset filtering
* conversation formatting
* parameter count
* checkpoint loading

### Backend

* topic validation
* topic scheduling
* debate state
* turn sequencing
* generation limits
* judge JSON validation
* persistence
* Redis cache
* lock behavior
* restart recovery
* 48-hour cleanup

### WebSocket

* connect
* reconnect
* event ordering
* snapshot recovery

### Frontend

* event parsing
* live state updates
* reconnection
* current debate rendering
* historical rendering

---

# 65. INTEGRATION TEST

Create a local full-system simulation.

It should run:

```text
topic generation mock
        ↓
topic scheduling
        ↓
20-turn debate
        ↓
judge mock
        ↓
Redis
        ↓
Supabase test/local target if practical
        ↓
WebSocket
        ↓
React client
```

The whole system should be demonstrable without requiring paid external APIs.

Use mocks for external providers during automated tests.

---

# 66. COST CONTROL

The project should assume limited budget.

Where possible:

* use open-source datasets
* use the developer's RTX 5050 for training
* avoid paid ML infrastructure
* minimize external API calls
* cache topic generation
* generate 12 topics in one external call
* judge one completed debate once
* never call the judge every turn
* keep Redis operations small
* avoid unnecessary bandwidth

Document expected external API usage.

---

# 67. EXTERNAL TOPIC API FAILURE FALLBACK

Maintain a small locally stored safe fallback topic pool.

This is NOT intended to replace hourly generation.

It exists so the public showcase does not completely break if the topic provider is temporarily unavailable.

The fallback pool should contain many generic adversarial conversational topics.

Do not continuously reuse the same few topics.

---

# 68. JUDGE FAILURE FALLBACK

Do not invent a fake evaluation.

Use a state such as:

```text
judge_pending
```

and retry.

The live debate should remain visible even if scoring is delayed.

---

# 69. LIVE STATE RECOVERY

After process restart:

1. connect to Redis/Postgres;
2. determine the current schedule slot;
3. inspect whether a debate was active;
4. determine whether the last session completed;
5. determine whether a session should be resumed or marked interrupted;
6. avoid duplicate execution;
7. rebuild live state;
8. allow WebSocket clients to reconnect.

Document the exact restart algorithm.

---

# 70. DO NOT LOSE THE EXPERIMENTAL STORY

The final README should explain that the project is not:

> "two prompts talking to each other."

It is:

> two independently trained tiny language models with deliberately different conversational priors, continuously participating in an adversarial conversation arena under severe production resource constraints.

The technical story matters.

---

# 71. DOCUMENT THE MODEL LIMITATIONS HONESTLY

The project must explicitly explain:

* 5M parameters is tiny by modern LLM standards;
* the models are specialized conversational experiments;
* they are not general-purpose assistants;
* they may hallucinate;
* they do not possess reliable world knowledge;
* their debates are entertainment/research demonstrations;
* the external judge is also a model and therefore imperfect.

Do not market them as more capable than they are.

---

# 72. REQUIRED DOCUMENTATION

Create at minimum:

```text
README.md

training/
    README.md
    ARCHITECTURE.md
    DATA.md
    SOURCES.md
    EVALUATION.md
    BENCHMARKS.md

server/
    README.md

client/
    README.md
```

The main README should contain:

* architecture diagram
* project motivation
* model details
* parameter counts
* training approach
* dataset strategy
* inference strategy
* realtime architecture
* storage architecture
* deployment architecture
* resource constraints
* benchmark results
* limitations

---

# 73. FINAL ARCHITECTURE SHOULD LOOK ROUGHLY LIKE

```text
                         ┌───────────────────────┐
                         │  External Topic LLM   │
                         │  12 topics / hour     │
                         └───────────┬───────────┘
                                     │
                                     ▼
                              ┌─────────────┐
                              │   Server    │
                              │   Python    │
                              └──────┬──────┘
                                     │
             ┌───────────────────────┼──────────────────────┐
             │                       │                      │
             ▼                       ▼                      ▼
       ┌──────────┐            ┌──────────┐         ┌────────────┐
       │ Optimist │            │ Pessimist│         │  Upstash   │
       │   ~5M    │            │   ~5M    │         │   Redis    │
       └────┬─────┘            └────┬─────┘         └────────────┘
            │                       │
            └──────────┬────────────┘
                       │
                  20-turn debate
                       │
                       ▼
               ┌────────────────┐
               │ External Judge │
               └───────┬────────┘
                       │
                       ▼
                ┌──────────────┐
                │   Supabase   │
                │  PostgreSQL  │
                └──────────────┘

                       │
                       │ WebSocket
                       ▼

                ┌───────────────┐
                │ React + TS    │
                │ Live Arena    │
                └───────────────┘
```

This is conceptual only.

The agent must improve the architecture where research demonstrates a better solution.

---

# 74. IMPLEMENTATION ORDER

Do not build everything simultaneously.

Follow approximately this sequence:

## Phase 1 — Research

* inspect current PyTorch/CUDA compatibility;
* inspect RTX 5050 environment;
* inspect tokenizer options;
* inspect datasets;
* inspect licensing;
* inspect tiny-transformer design literature/implementations;
* inspect lightweight inference options;
* inspect Render constraints;
* inspect Supabase and Upstash usage patterns.

Produce written decisions.

## Phase 2 — Tiny model prototype

Build one minimal Transformer.

Verify:

* parameter count
* tokenizer
* forward pass
* loss calculation
* generation
* checkpoint save/load

Do this before building both full personalities.

## Phase 3 — Data pipeline

Implement:

* downloading
* parsing
* filtering
* deduplication
* normalization
* personality transformation
* synthetic generation
* mixture construction

Generate dataset statistics.

## Phase 4 — Training experiments

Train controlled experiments.

Compare:

* loss
* conversational samples
* personality
* debate behavior
* repetition
* coherence

Select a final configuration.

## Phase 5 — Two final models

Train:

```text
Optimist final
Pessimist final
```

Export both.

## Phase 6 — Local debate arena

Run full 20-turn simulated debates.

Fix:

* looping
* repetition
* topic drift
* weak rebuttals
* personality collapse

## Phase 7 — Lightweight inference service

Implement the backend model layer.

Benchmark memory and latency.

## Phase 8 — Full server

Implement:

* scheduling
* topics
* debates
* judging
* Redis
* Supabase
* WebSockets
* recovery
* cleanup

## Phase 9 — Frontend

Build the realtime arena experience.

## Phase 10 — Full integration

Run the complete system locally.

## Phase 11 — Resource-constrained test

Run under approximately:

```text
512 MB RAM
0.1 CPU
```

Fix all major issues.

## Phase 12 — Deployment

Deploy the backend to Render.

Deploy the frontend separately.

Configure:

* environment variables
* Supabase
* Upstash
* external LLM provider
* keepalive/health checks
* deployment health checks

---

# 75. NON-NEGOTIABLE REQUIREMENTS

The implementation must satisfy all of these:

* [ ] Two models, not one.
* [ ] Both approximately 5M parameters.
* [ ] Both trained from scratch.
* [ ] English only.
* [ ] Optimist and Pessimist have meaningfully different behavior.
* [ ] Models do not depend on current affairs.
* [ ] Debate is adversarial conversation, not factual QA.
* [ ] Maximum 50 generated tokens per model response.
* [ ] Exactly 20 model turns per completed debate.
* [ ] 10 turns per personality.
* [ ] One debate every 5 minutes.
* [ ] 12 topics generated per hour.
* [ ] Topic generation uses strict JSON validation.
* [ ] Completed debates are externally judged.
* [ ] Three primary evaluation metrics.
* [ ] Winner recorded.
* [ ] Final score recorded.
* [ ] Supabase stores historical data.
* [ ] Upstash Redis handles transient/live state.
* [ ] 48-hour retention window is enforced.
* [ ] React + TypeScript frontend.
* [ ] Python backend.
* [ ] WebSocket realtime delivery.
* [ ] No user accounts.
* [ ] No comments.
* [ ] No user chat.
* [ ] No user voting.
* [ ] No user-generated content.
* [ ] Production model inference is memory-conscious.
* [ ] Training dependencies are separated from production dependencies where practical.
* [ ] Root-level `venv/` exists for local training development.
* [ ] Render restart/spin-down is treated as normal.
* [ ] WebSocket reconnection exists.
* [ ] Debate scheduling is restart-safe.
* [ ] Duplicate debate execution is prevented.
* [ ] External API failures have recovery paths.
* [ ] All secrets are environment variables.
* [ ] Automated tests exist.
* [ ] A 512 MB / 0.1 CPU simulation is performed before deployment.
* [ ] README documents what was actually built and measured.

---

# 76. WHAT NOT TO DO

Do NOT:

* start coding before the research/architecture phase;
* use a 1B/3B/7B model;
* fine-tune a pretrained LLM and call it a from-scratch model;
* make personality a system prompt;
* use RAG for the model debate;
* depend on web search during the debate;
* make current affairs central;
* blindly download every conversational dataset available;
* ignore dataset licenses;
* use Anthropic HH-RLHF as generic dialogue training data;
* train on huge quantities of noisy text simply because the GPU can handle it;
* assume bigger dataset = better tiny model;
* deploy the entire PyTorch training stack to Render without benchmarking;
* create multiple backend workers unnecessarily;
* rely entirely on in-memory state;
* rely on a process remaining alive forever;
* store historical data only in Redis;
* let each browser connection trigger its own model generation;
* generate a second debate if the scheduler retries the same slot;
* expose API keys to the frontend;
* create authentication when it is not required;
* silently fabricate judge results when the external judge fails;
* skip local simulation;
* skip resource-constrained testing;
* claim the tiny models are general-purpose intelligent assistants.

---

# 77. DEFINITION OF DONE

The project is complete only when:

### Training

```text
Optimist ~5M
Pessimist ~5M
```

both successfully generate coherent English responses.

### Personality

Given the same prompt, the two models consistently tend toward substantially different interpretations and arguments.

### Debate

A complete session executes:

```text
topic
→ 20 model responses
→ external judge
→ scores
→ winner
→ persistence
→ realtime display
```

without manual intervention.

### Scheduling

The system can operate continuously at:

```text
12 sessions/hour
```

and recover correctly from restart.

### Realtime

A browser connected during a live debate sees responses arrive as the debate happens.

### Persistence

The completed debate can be reloaded from Supabase.

### Cache

Live state can be recovered from Redis/persistent state.

### Retention

Data older than 48 hours is removed.

### Resource usage

The backend is demonstrated to run within a realistic approximation of:

```text
512 MB RAM
0.1 CPU
```

or the architecture is adjusted until it can.

### Public showcase

A visitor can open the website and immediately understand:

> Two tiny custom-trained AI personalities are arguing with each other live.

No account, configuration, or interaction is required.

---

# 78. FINAL AGENT INSTRUCTION

Do not treat this PLAN.md as a command to blindly implement every suggested technology.

Treat it as an engineering mission.

Your process must be:

```text
RESEARCH
   ↓
CHALLENGE ASSUMPTIONS
   ↓
DESIGN
   ↓
DOCUMENT DECISIONS
   ↓
PROTOTYPE
   ↓
BENCHMARK
   ↓
REFINE
   ↓
IMPLEMENT
   ↓
TEST
   ↓
RESOURCE-CONSTRAINED TEST
   ↓
DEPLOY
   ↓
VERIFY
```

Whenever a requirement conflicts with the physical constraints of a 5M-parameter model or 512 MB Render instance:

1. identify the conflict;
2. measure it;
3. propose alternatives;
4. choose the smallest reliable solution;
5. document the decision.

Do not conceal limitations.

Do not replace engineering with assumptions.

Do not optimize for theoretical elegance at the expense of actually running the system.

The final product should be technically defensible, reproducible, resource-conscious, visually impressive, and genuinely interesting as an experiment in **tiny language models developing contrasting conversational personalities**.
