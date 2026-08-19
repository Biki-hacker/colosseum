import pytest
import torch
import torch.nn.functional as F

from src.config import ModelConfig
from src.model import TinyGPT


@pytest.fixture(scope="module")
def cfg():
    return ModelConfig()


def test_param_count(cfg):
    model = TinyGPT(cfg)
    assert model.param_count() == 4_987_392
    assert model.param_count() == cfg.expected_params()


def test_forward_shape(cfg):
    model = TinyGPT(cfg)
    batch = torch.randint(0, cfg.vocab_size, (2, 64))
    targets = torch.randint(0, cfg.vocab_size, (2, 64))
    logits, loss = model(batch, targets)
    assert logits is None
    assert loss is not None and torch.isfinite(loss)


def test_loss_matches_full_ce(cfg):
    """Chunked CE must equal the full cross-entropy numerically."""
    torch.manual_seed(7)
    model = TinyGPT(cfg).eval()
    batch = torch.randint(0, cfg.vocab_size, (2, 96))
    targets = torch.randint(0, cfg.vocab_size, (2, 96))
    with torch.no_grad():
        _, loss8 = model(batch, targets, ce_chunks=8)
        _, loss1 = model(batch, targets, ce_chunks=1)
    assert torch.allclose(loss8, loss1, atol=1e-5)


def test_loss_ignores_mask(cfg):
    """Chunked CE with masked targets must equal explicit CE on unmasked tokens only."""
    torch.manual_seed(7)
    model = TinyGPT(cfg).eval()
    batch = torch.randint(0, cfg.vocab_size, (1, 32))
    targets = batch.clone()
    targets[0, 10:20] = -100
    with torch.no_grad():
        lg, _ = model(batch, None)
    mask = targets[0] != -100
    ce_ref = F.cross_entropy(lg[0][mask], targets[0][mask], reduction="sum") / int(mask.sum())
    with torch.no_grad():
        _, loss = model(batch, targets, ce_chunks=4)
    assert torch.allclose(loss, ce_ref, atol=1e-4)


def test_causality(cfg):
    """Later positions must not influence earlier logits (structural; fp32 tolerance)."""
    model = TinyGPT(cfg).eval()
    x1 = torch.randint(0, cfg.vocab_size, (1, 8))
    x2 = torch.cat([x1, torch.randint(0, cfg.vocab_size, (1, 1))], dim=1)
    l1, _ = model(x1)
    l2, _ = model(x2)
    diff = (l1[:, :8] - l2[:, :8]).abs()
    assert diff.max() < 1e-3  # fp32 matmul rounding only
    assert diff.mean() < 1e-4


def test_tied_embeddings(cfg):
    model = TinyGPT(cfg)
    assert torch.equal(model.tok_emb.weight, model.lm_head.weight)


def test_generate_respects_max_len(cfg):
    model = TinyGPT(cfg).eval()
    prompt = torch.randint(0, cfg.vocab_size, (1, 4))
    out = model.generate(prompt, max_new_tokens=10)
    assert out.shape[1] == 4 + 10


def test_generate_eos_stop(cfg):
    model = TinyGPT(cfg).eval()
    prompt = torch.randint(0, cfg.vocab_size, (1, 4))
    out = model.generate(prompt, max_new_tokens=50, eos_id=3)
    # must stop at or before 50 new tokens
    assert out.shape[1] <= 4 + 50


def test_checkpoint_roundtrip(cfg, tmp_path):
    model = TinyGPT(cfg)
    path = tmp_path / "ckpt.pt"
    torch.save({"model": model.state_dict(), "cfg": cfg}, path)
    m2 = TinyGPT(cfg)
    m2.load_state_dict(torch.load(path, weights_only=False)["model"])
    x = torch.randint(0, cfg.vocab_size, (2, 32))
    l1, _ = model(x)
    l2, _ = m2(x)
    assert torch.allclose(l1, l2, atol=1e-6)