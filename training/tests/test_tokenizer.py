import json

import pytest

from src.simple_tokenizer import SimpleBPETokenizer, train_simple_bpe

SPECIALS = ["<PAD>", "<UNK>", "<BOS>", "<EOS>", "<TOPIC>", "<OPTIMIST>", "<PESSIMIST>", "<TURN>"]


@pytest.fixture(scope="module")
def tok():
    texts = [
        "Hello, how are you doing today?",
        "I think that technology makes people less social.",
        "Maybe it also helps us connect with new communities.",
        "That is a fair point, but there are hidden costs.",
        "Would you rather be spontaneous or highly organized?",
        "A small model can still have a clear personality.",
        "No pain, no gain, as they say.",
        "Well, I suppose we will have to agree to disagree.",
    ] * 200
    t = train_simple_bpe(texts, vocab_size=512, special_tokens=SPECIALS, min_frequency=2)
    return t


def test_special_token_ids(tok):
    assert tok.special_tokens["<PAD>"] == 0
    assert tok.special_tokens["<EOS>"] == 3
    assert tok.special_tokens["<TOPIC>"] == 4


def test_roundtrip(tok):
    texts = [
        "Hello, how are you doing today?",
        "I think that technology makes people less social.",
        "Would you rather be spontaneous or highly organized?",
    ]
    for t in texts:
        ids = tok.encode(t)
        dec = tok.decode(ids)
        assert dec == t, f"roundtrip failed: {t!r} -> {dec!r}"


def test_special_tokens_kept(tok):
    ids = tok.encode("<BOS><TOPIC> hello world <EOS>")
    assert ids[0] == tok.special_tokens["<BOS>"]
    assert ids[1] == tok.special_tokens["<TOPIC>"]
    assert ids[-1] == tok.special_tokens["<EOS>"]


def test_serialization_roundtrip(tok, tmp_path):
    p = tmp_path / "tok.json"
    tok.to_file(str(p))
    with open(p, encoding="utf-8") as f:
        data = json.load(f)
    assert data["model_type"] == "bpe-bytelevel"
    t2 = SimpleBPETokenizer.from_file(str(p))
    texts = ["Hello there!", "A tiny model debate."]
    for t in texts:
        assert t2.decode(t2.encode(t)) == t


def test_unknown_handling():
    t = train_simple_bpe(["a b c d e f g"], vocab_size=300, special_tokens=SPECIALS, min_frequency=2)
    ids = t.encode("zzz")
    assert all(i != t.unk_id for i in ids) or len(ids) > 0  # bytes always tokenize
    # every byte is covered, so no UNK should ever be needed on valid utf-8
    assert t.unk_id not in ids