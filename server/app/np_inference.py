"""Phase 7: numpy-only CPU inference for the debate models.

Replaces the torch path for the 512MB-constrained server. Loads model.npz
(f32 arrays), runs the exact trained math (including the trained quirk: the
block's second LayerNorm is unused), and generates turns with the same stop
rules. Validated by logit-diff tests against the torch training model.
"""

from __future__ import annotations

import json
import math
import os
from typing import Dict, List, Tuple

import numpy as np

MAX_TOKENS = 50
STOP_STRINGS = ("<EOS>", "<TURN>", "<OPTIMIST>", "<PESSIMIST>", "<TOPIC>")


class NPModel:
    """Frozen transformer loaded from an exported .npz dict of f32 arrays."""

    def __init__(self, cfg: dict, arrays: Dict[str, np.ndarray]):
        self.cfg = cfg
        self.arrays = arrays
        d = cfg["d_model"]
        h = cfg["n_heads"]
        hd = d // h
        L = cfg["context_length"]
        theta = cfg.get("rope_theta", 10000.0)
        inv_freq = 1.0 / (theta ** (np.arange(0, hd, 2) / hd))
        t = np.arange(L, dtype=np.float64)[:, None]
        freqs = t * inv_freq[None, :]
        self.cos = np.repeat(np.cos(freqs), 2, axis=-1).astype(np.float32)
        self.sin = np.repeat(np.sin(freqs), 2, axis=-1).astype(np.float32)
        self.tril = np.tril(np.ones((L, L), dtype=bool))
        self._kc = None
        self._vc = None
        self._cache_len = None

    @staticmethod
    def _rot_half(x: np.ndarray) -> np.ndarray:
        x1, x2 = x[..., : x.shape[-1] // 2], x[..., x.shape[-1] // 2 :]
        return np.concatenate((-x2, x1), axis=-1)

    def _layer(self, i: int, x: np.ndarray, S: int, cos: np.ndarray, sin: np.ndarray, write_cache: bool) -> np.ndarray:
        """One transformer layer for the new positions only. Past positions are
        unchanged, so their k/v (and only those) come from the cache."""
        p = f"blocks.{i}."
        d = x.shape[-1]
        hd = d // self.cfg["n_heads"]
        H = self.cfg["n_heads"]
        n_new = x.shape[0]
        c = S - n_new
        ln1 = (x - x.mean(-1, keepdims=True)) * self.arrays[p + "ln1.weight"] / np.sqrt(x.var(-1, keepdims=True) + 1e-5) + self.arrays[p + "ln1.bias"]
        qkv = ln1 @ self.arrays[p + "attn.qkv.weight"].T
        q, k, v = np.split(qkv, 3, axis=-1)
        q = q.reshape(n_new, H, hd).transpose(1, 0, 2)  # (H, n_new, hd)
        k = k.reshape(n_new, H, hd).transpose(1, 0, 2)
        v = v.reshape(n_new, H, hd).transpose(1, 0, 2)
        q = q * cos[c:S] + self._rot_half(q) * sin[c:S]
        k = k * cos[c:S] + self._rot_half(k) * sin[c:S]
        if write_cache:
            self._kc[i][c:S] = k.transpose(1, 0, 2)  # (n_new, H, hd)
            self._vc[i][c:S] = v.transpose(1, 0, 2)
        if c > 0:
            k_old = self._kc[i][:c].transpose(1, 0, 2)  # (H, c, hd)
            v_old = self._vc[i][:c].transpose(1, 0, 2)
            att = np.concatenate([q @ k_old.transpose(0, 2, 1), q @ k.transpose(0, 2, 1)], axis=-1) / math.sqrt(hd)
            kv = np.concatenate([v_old, v], axis=1)
        else:
            att = np.where(self.tril[:S, :S][None, :, :], q @ k.transpose(0, 2, 1), -1e9) / math.sqrt(hd)
            kv = v
        att = np.exp(att - att.max(-1, keepdims=True))
        att = att / att.sum(-1, keepdims=True)
        y = (att @ kv).transpose(1, 0, 2).reshape(n_new, d)
        x = x + y @ self.arrays[p + "attn.out.weight"].T
        gu = (x @ self.arrays[p + "gate.weight"].T) * (x @ self.arrays[p + "up.weight"].T)
        return x + (gu * (1.0 / (1.0 + np.exp(-gu)))) @ self.arrays[p + "down.weight"].T

    def logits_cached(self, ids: List[int]) -> np.ndarray:
        """logits for the last position using a per-layer KV cache (exact).
        The cache is rebuilt if the sequence is shorter than a previous call."""
        n = len(ids)
        L = self.cfg["n_layers"]
        if self._cache_len is None or n < self._cache_len:
            maxS = self.cfg["context_length"]
            hd = self.cfg["d_model"] // self.cfg["n_heads"]
            self._kc = [np.zeros((maxS, self.cfg["n_heads"], hd), np.float32) for _ in range(L)]
            self._vc = [np.zeros((maxS, self.cfg["n_heads"], hd), np.float32) for _ in range(L)]
            self._cache_len = 0
        x = self.arrays["tok_emb.weight"][ids[self._cache_len :]]  # new positions only
        S = n
        cos, sin = self.cos[:S], self.sin[:S]
        for i in range(L):
            x = self._layer(i, x, S, cos, sin, write_cache=True)
        self._cache_len = n
        ln_f = (x - x.mean(-1, keepdims=True)) * self.arrays["ln_f.weight"] / np.sqrt(x.var(-1, keepdims=True) + 1e-5) + self.arrays["ln_f.bias"]
        return ln_f[-1] @ self.arrays["lm_head.weight"].T

    def logits(self, ids: List[int]) -> np.ndarray:
        """Uncached full forward for validation/tests (must match logits_cached)."""
        S = len(ids)
        cos, sin = self.cos[:S], self.sin[:S]
        x = self.arrays["tok_emb.weight"][ids]
        for i in range(self.cfg["n_layers"]):
            x = self._layer(i, x, S, cos, sin, write_cache=False)
        ln_f = (x - x.mean(-1, keepdims=True)) * self.arrays["ln_f.weight"] / np.sqrt(x.var(-1, keepdims=True) + 1e-5) + self.arrays["ln_f.bias"]
        return ln_f[-1] @ self.arrays["lm_head.weight"].T

    def generate(self, prompt_ids: List[int], temperature: float, top_k: int, top_p: float, repetition_penalty: float) -> Tuple[List[int], bool]:
        rng = np.random.default_rng()
        out: List[int] = []
        ids = prompt_ids
        self._kc = self._vc = None
        self._cache_len = None  # fresh prompt: rebuild cache
        for _ in range(MAX_TOKENS):
            lg = self.logits_cached(ids[-self.cfg["context_length"] :])
            lg = lg.astype(np.float64)
            if repetition_penalty > 1.0:
                for tok in set(ids[-MAX_TOKENS:] + out):
                    lg[tok] = lg[tok] / repetition_penalty if lg[tok] < 0 else lg[tok] * repetition_penalty
            if temperature != 1.0:
                lg = lg / temperature
            if top_k > 0:
                kth = np.sort(lg)[-top_k]
                lg[lg < kth] = -np.inf
            if top_p < 1.0:
                order = np.argsort(-lg)
                sorted_lg = lg[order]
                probs = np.exp(sorted_lg - sorted_lg.max())
                probs = probs / probs.sum()
                cum = np.cumsum(probs)
                keep = cum - probs <= top_p
                mask = np.full_like(lg, -np.inf)
                mask[order[keep]] = sorted_lg[keep]
                lg = mask
            probs = np.exp(lg - lg.max())
            probs = probs / probs.sum()
            nxt = int(rng.choice(len(probs), p=probs))
            if nxt in STOP_TOKEN_IDS:
                return out, True
            out.append(nxt)
            ids = ids + [nxt]
        return out, False


STOP_TOKEN_IDS: List[int] = []


class NPEngine:
    """Loads both personalities (numpy only) and runs debate turns."""

    def __init__(self, models_root: str, tokenizer_cls):
        self.models: Dict[str, NPModel] = {}
        self.tokenizer = None
        for pers in ("optimist", "pessimist"):
            root = os.path.join(models_root, pers)
            with open(os.path.join(root, "config.json"), encoding="utf-8") as f:
                meta = json.load(f)
            cfg = meta["model"]
            arrays = np.load(os.path.join(root, "model.npz"))
            arrays = {k: arrays[k] for k in arrays.files}
            if cfg.get("tie_embeddings", True) and "lm_head.weight" not in arrays:
                arrays["lm_head.weight"] = arrays["tok_emb.weight"]
            self.models[pers] = NPModel(cfg, arrays)
            if self.tokenizer is None:
                self.tokenizer = tokenizer_cls.from_file(os.path.join(root, "tokenizer-portable.json"))
        global STOP_TOKEN_IDS
        STOP_TOKEN_IDS = [self.tokenizer.encode(s)[0] for s in STOP_STRINGS]

    def generate_turn(
        self,
        speaker: str,
        topic: str,
        history: List[Tuple[str, str]],
        temperature: float = 0.8,
        top_k: int = 40,
        top_p: float = 0.9,
        repetition_penalty: float = 1.15,
    ) -> Tuple[str, int, bool]:
        parts = [f"<BOS><TOPIC> {topic}"]
        for s, text in history:
            parts.append(f"<TURN><{s.upper()}>{' ' + text if text else ''}")
        parts.append(f"<TURN><{speaker.upper()}>")
        ids = self.tokenizer.encode("".join(parts))
        text_ids, hit = self.models[speaker].generate(ids, temperature, top_k, top_p, repetition_penalty)
        return self.tokenizer.decode(text_ids).strip(), len(text_ids), hit