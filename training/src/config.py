from dataclasses import dataclass, field


@dataclass
class ModelConfig:
    vocab_size: int = 4096
    context_length: int = 512
    d_model: int = 256
    n_layers: int = 6
    n_heads: int = 8
    ffn_hidden: int = 512
    rope_theta: float = 10000.0
    tie_embeddings: bool = True
    dropout: float = 0.0
    bias: bool = False
    init_scale: float = 0.2887  # 1/sqrt(2*n_layers) — GPT-2 residual init trick

    @property
    def head_dim(self) -> int:
        return self.d_model // self.n_heads

    def expected_params(self) -> int:
        # embeddings (tied) + 6 blocks + final norm
        v, d, l, f = self.vocab_size, self.d_model, self.n_layers, self.ffn_hidden
        emb = v * d
        per_block = d * (3 * d) + d * d + 2 * (2 * d) + d * f + d * f + f * d
        norm = 2 * d
        return emb + l * per_block + norm


@dataclass
class TrainConfig:
    data_version: str = "dataset-v001"
    tokenizer_version: str = "tokenizer-v001"
    seed: int = 1337
    batch_size: int = 32
    context_length: int = 512
    grad_accum: int = 2
    lr: float = 6e-4
    min_lr: float = 1e-4
    warmup_steps: int = 200
    max_steps: int = 10000
    weight_decay: float = 0.1
    beta1: float = 0.9
    beta2: float = 0.95
    grad_clip: float = 1.0
    precision: str = "bf16"  # bf16 | fp32
    eval_every: int = 500
    eval_samples: int = 200
    log_every: int = 50
    save_every: int = 1000
    checkpoint_dir: str = "training/checkpoints"
    run_name: str = "exp_001"
    personality: str = "common"  # common | optimist | pessimist


@dataclass
class GenerationConfig:
    max_new_tokens: int = 50
    temperature: float = 0.8
    top_k: int = 40
    top_p: float = 0.9
    repetition_penalty: float = 1.15
    eos_stop: bool = True
    seed: int | None = None