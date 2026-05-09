"""Tests for training-data adapters now living on :class:`NerModel`."""

from __future__ import annotations

import pytest

from ontchatbot.ner_model import NerModel


def test_b_to_i_table_complete():
    _, l2i, i2l = NerModel.label_mappings()
    table = NerModel.b_to_i_table(l2i)
    for label_id, mapped in table.items():
        assert i2l[label_id].startswith("B-")
        assert i2l[mapped] == "I-" + i2l[label_id][2:]


def test_project_labels_downgrades_b_to_i():
    _, l2i, _ = NerModel.label_mappings()
    b = l2i["B-QuyTrinhHocVu"]
    i = l2i["I-QuyTrinhHocVu"]
    o = l2i["O"]
    table = NerModel.b_to_i_table(l2i)
    word_ids = [None, 0, 0, 1, None]
    out = NerModel.project_labels(word_ids, [b, o], table)
    assert out == [-100, b, i, o, -100]


def test_project_labels_keeps_o_and_i():
    _, l2i, _ = NerModel.label_mappings()
    i = l2i["I-PhongBanHanhChinh"]
    o = l2i["O"]
    table = NerModel.b_to_i_table(l2i)
    word_ids = [None, 0, 0, 1, 1, None]
    out = NerModel.project_labels(word_ids, [i, o], table)
    assert out == [-100, i, i, o, o, -100]


def test_bio_labels_size_matches_tags(ontology):
    """``NerModel.bio_labels`` is the canonical owner of the BIO schema."""
    labels = NerModel.bio_labels()
    tags = ontology.tags
    assert labels[0] == "O"
    assert len(labels) == 1 + 2 * len(tags)
    for tag in tags:
        assert f"B-{tag}" in labels and f"I-{tag}" in labels


@pytest.fixture(scope="module")
def phobert():
    from transformers import AutoTokenizer
    return AutoTokenizer.from_pretrained("vinai/phobert-base-v2")


def test_make_tokenize_fn_with_real_tokenizer(phobert):
    _, l2i, _ = NerModel.label_mappings()
    b = l2i["B-QuyTrinhHocVu"]
    o = l2i["O"]
    fn = NerModel.make_tokenize_fn(phobert)
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
    assert labels[1:-1][0] == b
