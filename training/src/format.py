"""Canonical conversation formatting + packing.

Canonical format (identical in training and production inference):

  Base corpus (model M, full loss):
    <BOS> <TOPIC> <first user msg> <M> <resp> <TURN> <user msg> <M> <resp> ... <EOS>

  Adversarial sample for model M (loss only on the final own turn):
    <BOS> <TOPIC> <topic> <TURN> <opp> <opp text> <TURN> <M> <own text>
    ... <TURN> <opp> <opp text> <TURN> <M> <own text> <EOS>

Generation (production):
    <BOS> <TOPIC> <topic> <TURN> <opp> <opp text> ... <TURN> <M>
    → model generates its own turn (≤50 tokens, stops at <EOS>)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence, Tuple

import numpy as np

from .simple_tokenizer import SimpleBPETokenizer

SPECIAL = ["<PAD>", "<UNK>", "<BOS>", "<EOS>", "<TOPIC>", "<OPTIMIST>", "<PESSIMIST>", "<TURN>"]

MARK_BOS = "<BOS>"
MARK_EOS = "<EOS>"
MARK_TOPIC = "<TOPIC>"
MARK_OPT = "<OPTIMIST>"
MARK_PES = "<PESSIMIST>"
MARK_TURN = "<TURN>"

MARK_FOR = {"optimist": MARK_OPT, "pessimist": MARK_PES}


@dataclass
class PackedSample:
    ids: np.ndarray  # (ctx,) uint16
    mask: np.ndarray  # (ctx,) bool — True positions contribute to the loss


def format_base_turns(turns: Sequence[Tuple[str, str]], personality: str) -> str:
    """Format a base conversation: first user msg under <TOPIC>, later user msgs under
    <TURN>, every assistant response under the model's own marker. Full loss."""
    mark = MARK_FOR[personality]
    parts = [MARK_BOS, MARK_TOPIC]
    for i, (role, text) in enumerate(turns):
        if role == "user":
            if i == 0:
                parts.append(" " + text)
            else:
                parts.append(MARK_TURN + " " + text)
        else:
            parts.append(mark + " " + text)
    parts.append(MARK_EOS)
    return "".join(parts)


def format_debate_prefix(topic: str, turns: Sequence[Tuple[str, str]]) -> str:
    """Format a full debate transcript up to (not including) the final own turn."""
    parts = [MARK_BOS, MARK_TOPIC + " " + topic]
    for speaker, text in turns:
        parts.append(MARK_TURN + MARK_FOR[speaker] + " " + text)
    return "".join(parts)


def format_debate_sample(
    topic: str,
    turns: Sequence[Tuple[str, str]],
    own: str,
    own_text: str,
) -> Tuple[str, str]:
    """Build one training example ending in the model's own turn.

    Returns (full_text, loss_text) where loss_text is the substring on which loss is
    computed (the final <M> ... <EOS> segment).
    """
    prefix = format_debate_prefix(topic, turns)
    mark = MARK_FOR[own]
    segment = MARK_TURN + mark + " " + own_text + MARK_EOS
    return prefix + segment, segment


def tokenize_sample(
    tokenizer: SimpleBPETokenizer,
    full_text: str,
    loss_text: str | None,
    context_length: int,
    pad_id: int = 0,
) -> PackedSample:
    """Tokenize a (possibly truncated) sample and produce a padded, loss-masked block.

    loss_text None means full loss over the whole (non-padded) sample.
    """
    ids = tokenizer.encode(full_text)
    if len(ids) > context_length:
        # keep the tail (the final own turn is the target; losing the oldest context
        # is acceptable under the 512-token budget)
        ids = ids[-context_length:]
    n = len(ids)
    mask = np.ones(n, dtype=bool)
    if loss_text is not None:
        loss_ids = tokenizer.encode(loss_text)
        # loss_text is a suffix of full_text → its ids are a suffix of full ids
        loss_n = len(loss_ids)
        mask[: n - loss_n] = False
    padded = np.full(context_length, pad_id, dtype=np.uint16)
    padded[:n] = np.asarray(ids, dtype=np.uint16)
    pmask = np.zeros(context_length, dtype=bool)
    pmask[:n] = mask
    return PackedSample(padded, pmask)


def pack_samples(
    samples: Sequence[Tuple[str, str | None]],
    tokenizer: SimpleBPETokenizer,
    context_length: int,
    pad_id: int = 0,
) -> Tuple[np.ndarray, np.ndarray]:
    """Batch-tokenize + pad a list of (full_text, loss_text) into (ids, mask) arrays."""
    ids_list, mask_list = [], []
    for full_text, loss_text in samples:
        ps = tokenize_sample(tokenizer, full_text, loss_text, context_length, pad_id)
        ids_list.append(ps.ids)
        mask_list.append(ps.mask)
    return np.stack(ids_list), np.stack(mask_list)