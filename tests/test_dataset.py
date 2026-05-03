"""Tests for ``ontchatbot.ner.dataset``.

Covers:
* the ``B-X → I-X`` continuation rule applied via :func:`project_labels`;
* end-to-end ``make_tokenize_fn`` against the real PhoBERT slow tokenizer to
  guarantee training pre-processing actually executes.
"""

from __future__ import annotations

import pytest

from ontchatbot.ner.dataset import (
    b_to_i_table,
    label_mappings,
    make_tokenize_fn,
    project_labels,
)


def test_b_to_i_table_complete():
    _, l2i, i2l = label_mappings()
    table = b_to_i_table(l2i)
    for label_id, mapped in table.items():
        assert i2l[label_id].startswith("B-")
        assert i2l[mapped] == "I-" + i2l[label_id][2:]


def test_project_labels_downgrades_b_to_i():
    _, l2i, _ = label_mappings()
    b = l2i["B-QuyTrinhHocVu"]
    i = l2i["I-QuyTrinhHocVu"]
    o = l2i["O"]
    table = b_to_i_table(l2i)
    # Word 0 (B-Tag) split into 2 sub-words; word 1 stays O.
    word_ids = [None, 0, 0, 1, None]
    out = project_labels(word_ids, [b, o], table)
    assert out == [-100, b, i, o, -100]


def test_project_labels_keeps_o_and_i():
    _, l2i, _ = label_mappings()
    i = l2i["I-PhongBanHanhChinh"]
    o = l2i["O"]
    table = b_to_i_table(l2i)
    word_ids = [None, 0, 0, 1, 1, None]
    out = project_labels(word_ids, [i, o], table)
    assert out == [-100, i, i, o, o, -100]


@pytest.fixture(scope="module")
def phobert():
    from transformers import AutoTokenizer
    return AutoTokenizer.from_pretrained("vinai/phobert-base-v2")


def test_make_tokenize_fn_with_real_tokenizer(phobert):
    _, l2i, _ = label_mappings()
    b = l2i["B-QuyTrinhHocVu"]
    o = l2i["O"]
    fn = make_tokenize_fn(phobert)
    out = fn({
        "tokens": [["Quy_trình", "bảo_lưu", "thế_nào"]],
        "tags": [[b, o, o]],
    })
    assert "input_ids" in out and "labels" in out and "attention_mask" in out
    ids = out["input_ids"][0]
    labels = out["labels"][0]
    masks = out["attention_mask"][0]
    assert len(ids) == len(labels) == len(masks)
    assert ids[0] == phobert.cls_token_id and ids[-1] == phobert.sep_token_id
    assert labels[0] == -100 and labels[-1] == -100
    # The first sub-word of word 0 must be B-…; remaining word-0 sub-words must be I-… or absent.
    inner = labels[1:-1]
    assert inner[0] == b
