import math

import torch
import torch.nn as nn
import torch.nn.functional as F

from .config import ModelConfig


def _rotate_half(x: torch.Tensor) -> torch.Tensor:
    x1 = x[..., : x.shape[-1] // 2]
    x2 = x[..., x.shape[-1] // 2 :]
    return torch.cat((-x2, x1), dim=-1)


def precompute_rope(seq_len: int, head_dim: int, theta: float = 10000.0, device=None) -> tuple[torch.Tensor, torch.Tensor]:
    inv_freq = 1.0 / (theta ** (torch.arange(0, head_dim, 2, device=device).float() / head_dim))
    t = torch.arange(seq_len, device=device).float()
    freqs = torch.outer(t, inv_freq)
    cos = freqs.cos().repeat_interleave(2, dim=-1)
    sin = freqs.sin().repeat_interleave(2, dim=-1)
    return cos, sin


def apply_rotary(q: torch.Tensor, k: torch.Tensor, cos: torch.Tensor, sin: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    cos = cos.unsqueeze(0).unsqueeze(0)
    sin = sin.unsqueeze(0).unsqueeze(0)
    q = (q * cos) + (_rotate_half(q) * sin)
    k = (k * cos) + (_rotate_half(k) * sin)
    return q, k


class CausalSelfAttention(nn.Module):
    def __init__(self, cfg: ModelConfig):
        super().__init__()
        self.n_heads = cfg.n_heads
        self.head_dim = cfg.head_dim
        self.d_model = cfg.d_model
        self.qkv = nn.Linear(cfg.d_model, 3 * cfg.d_model, bias=cfg.bias)
        self.out = nn.Linear(cfg.d_model, cfg.d_model, bias=cfg.bias)

    def forward(self, x: torch.Tensor, cos: torch.Tensor, sin: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
        B, S, D = x.shape
        qkv = self.qkv(x).view(B, S, 3, self.n_heads, self.head_dim).permute(2, 0, 3, 1, 4)
        q, k, v = qkv[0], qkv[1], qkv[2]
        q, k = apply_rotary(q, k, cos, sin)
        attn = (q @ k.transpose(-2, -1)) * (1.0 / math.sqrt(self.head_dim))
        attn = attn.masked_fill(mask.unsqueeze(0).unsqueeze(0) == 0, float("-inf"))
        attn = F.softmax(attn, dim=-1)
        y = attn @ v
        y = y.transpose(1, 2).contiguous().view(B, S, D)
        return self.out(y)


class Block(nn.Module):
    def __init__(self, cfg: ModelConfig):
        super().__init__()
        self.ln1 = nn.LayerNorm(cfg.d_model)
        self.attn = CausalSelfAttention(cfg)
        self.ln2 = nn.LayerNorm(cfg.d_model)
        self.up = nn.Linear(cfg.d_model, cfg.ffn_hidden, bias=cfg.bias)
        self.gate = nn.Linear(cfg.d_model, cfg.ffn_hidden, bias=cfg.bias)
        self.down = nn.Linear(cfg.ffn_hidden, cfg.d_model, bias=cfg.bias)

    def forward(self, x: torch.Tensor, cos: torch.Tensor, sin: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
        x = x + self.attn(self.ln1(x), cos, sin, mask)
        h = self.gate(x) * self.up(x)
        x = x + self.down(F.silu(h))
        return x


class TinyGPT(nn.Module):
    def __init__(self, cfg: ModelConfig):
        super().__init__()
        self.cfg = cfg
        self.tok_emb = nn.Embedding(cfg.vocab_size, cfg.d_model)
        self.blocks = nn.ModuleList([Block(cfg) for _ in range(cfg.n_layers)])
        self.ln_f = nn.LayerNorm(cfg.d_model)
        self.lm_head = nn.Linear(cfg.d_model, cfg.vocab_size, bias=False)
        if cfg.tie_embeddings:
            self.lm_head.weight = self.tok_emb.weight
        self.apply(self._init_weights)
        # Zero-ish scaled residual output projections (ReZero/PaLM-style). At init the
        # block outputs are ~0 so the residual stream starts as a clean embedding lookup;
        # this prevents the pathological "copy the input token" init regime and makes
        # early training stable at aggressive learning rates.
        for blk in self.blocks:
            blk.attn.out.weight.data.mul_(cfg.init_scale)
            blk.down.weight.data.mul_(cfg.init_scale)
        cos, sin = precompute_rope(cfg.context_length, cfg.head_dim, cfg.rope_theta)
        self.register_buffer("cos", cos, persistent=False)
        self.register_buffer("sin", sin, persistent=False)
        mask = torch.tril(torch.ones(cfg.context_length, cfg.context_length, dtype=torch.bool))
        self.register_buffer("mask", mask, persistent=False)

    @staticmethod
    def _init_weights(m: nn.Module) -> None:
        if isinstance(m, nn.Linear):
            nn.init.normal_(m.weight, mean=0.0, std=0.02)
            if m.bias is not None:
                nn.init.zeros_(m.bias)
        elif isinstance(m, nn.Embedding):
            nn.init.normal_(m.weight, mean=0.0, std=0.02)
        elif isinstance(m, nn.LayerNorm):
            nn.init.ones_(m.weight)
            nn.init.zeros_(m.bias)

    def forward(
        self,
        idx: torch.Tensor,
        targets: torch.Tensor | None = None,
        ce_chunks: int = 8,
    ) -> tuple[torch.Tensor, torch.Tensor | None]:
        """Forward pass. With targets, returns (None, loss) using chunked CE over the
        sequence dimension to avoid materializing (B, S, V) logits at full size —
        the output head dominates VRAM for a 4096-vocab model."""
        S = idx.shape[1]
        x = self.tok_emb(idx)
        for blk in self.blocks:
            x = blk(x, self.cos[:S], self.sin[:S], self.mask[:S, :S])
        x = self.ln_f(x)
        if targets is None:
            return self.lm_head(x), None
        V = self.cfg.vocab_size
        chunk = max(1, (S + ce_chunks - 1) // ce_chunks)
        loss_sum = torch.zeros((), device=x.device, dtype=torch.float32)
        count = 0
        for i in range(0, S, chunk):
            lg = self.lm_head(x[:, i : i + chunk])
            loss_sum = loss_sum + F.cross_entropy(
                lg.reshape(-1, V),
                targets[:, i : i + chunk].reshape(-1),
                ignore_index=-100,
                reduction="sum",
            )
            count += int((targets[:, i : i + chunk] != -100).sum())
        loss = loss_sum / max(count, 1)
        return None, loss

    @torch.no_grad()
    def generate(
        self,
        idx: torch.Tensor,
        max_new_tokens: int = 50,
        temperature: float = 1.0,
        top_k: int = 0,
        top_p: float = 1.0,
        repetition_penalty: float = 1.0,
        eos_id: int | None = None,
    ) -> torch.Tensor:
        self.eval()
        device = idx.device
        for _ in range(max_new_tokens):
            window = idx[:, -self.cfg.context_length:]
            logits = self(window)[0][:, -1, :]
            if repetition_penalty > 1.0:
                gen = idx[:, -max_new_tokens:]
                if gen.numel() > 0:
                    for tok in gen[0].unique().tolist():
                        logits[0, tok] = logits[0, tok] * repetition_penalty if logits[0, tok] < 0 else logits[0, tok] / repetition_penalty
            if temperature != 1.0:
                logits = logits / temperature
            if top_k > 0:
                v, _ = torch.topk(logits, min(top_k, logits.size(-1)))
                logits[logits < v[:, [-1]]] = float("-inf")
            if top_p < 1.0:
                sorted_logits, sorted_idx = torch.sort(logits, descending=True)
                probs = F.softmax(sorted_logits, dim=-1)
                cum = probs.cumsum(dim=-1)
                remove = cum - probs > top_p
                sorted_logits[remove] = float("-inf")
                logits = sorted_logits.scatter(1, sorted_idx, sorted_logits)
            probs = F.softmax(logits, dim=-1)
            nxt = torch.multinomial(probs, num_samples=1)
            idx = torch.cat([idx, nxt], dim=1)
            if eos_id is not None and nxt.item() == eos_id:
                break
        return idx

    def param_count(self) -> int:
        return sum(p.numel() for p in self.parameters())