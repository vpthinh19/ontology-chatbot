"""Tests for ``ontchatbot.ner.dataset`` — focus on BIO sub-word alignment."""

from __future__ import annotations

from ontchatbot.ner.dataset import _b_to_i_table, label_mappings, make_tokenize_fn


class _StubEncoding(dict):
    """Tokenizer-like result exposing ``word_ids``."""

    def __init__(self, word_ids_list: list[list[int | None]]):
        super().__init__()
        self._wids = word_ids_list
        self["input_ids"] = [[0] * len(w) for w in word_ids_list]
        self["attention_mask"] = [[1] * len(w) for w in word_ids_list]

    def word_ids(self, batch_index: int = 0) -> list[int | None]:
        return self._wids[batch_index]


class _StubTokenizer:
    """Captures the call and returns a preset encoding without loading PhoBERT."""

    def __init__(self, word_ids_list):
        self._enc = _StubEncoding(word_ids_list)

    def __call__(self, *_args, **_kwargs):
        return self._enc


def test_b_to_i_table_complete():
    _, l2i, i2l = label_mappings()
    table = _b_to_i_table(l2i)
    for label_id, mapped in table.items():
        assert i2l[label_id].startswith("B-")
        assert i2l[mapped] == "I-" + i2l[label_id][2:]


def test_continuation_subword_downgrades_b_to_i():
    """Word ``[B-Tag]`` split into 2 sub-words → ``[B-Tag, I-Tag]``."""
    _, l2i, i2l = label_mappings()
    tag = "QuyTrinhHocVu"
    b_id = l2i[f"B-{tag}"]
    i_id = l2i[f"I-{tag}"]
    o_id = l2i["O"]

    # Two words: word 0 carries B-Tag, word 1 is O.
    # Word 0 splits into 2 sub-words; word 1 stays as 1.
    word_ids = [[None, 0, 0, 1, None]]
    tokenizer = _StubTokenizer(word_ids)
    fn = make_tokenize_fn(tokenizer)
    out = fn({"tokens": [["w0", "w1"]], "tags": [[b_id, o_id]]})

    assert out["labels"][0] == [-100, b_id, i_id, o_id, -100]


def test_continuation_subword_keeps_o_and_i():
    _, l2i, _ = label_mappings()
    tag = "PhongBanHanhChinh"
    i_id = l2i[f"I-{tag}"]
    o_id = l2i["O"]

    word_ids = [[None, 0, 0, 1, 1, None]]
    tokenizer = _StubTokenizer(word_ids)
    fn = make_tokenize_fn(tokenizer)
    out = fn({"tokens": [["w0", "w1"]], "tags": [[i_id, o_id]]})

    # I-Tag stays I-Tag on continuation, O stays O.
    assert out["labels"][0] == [-100, i_id, i_id, o_id, o_id, -100]
