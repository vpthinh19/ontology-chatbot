"""Tests for the static-dataset compiler.

The compiler turns the hand-curated :data:`SAMPLES` list into BIO-tagged
``{tokens, ner_tags}`` rows. We verify alignment correctness on a handful of
fixtures, then run a *corpus-level* sweep that recompiles every entry in
the real source — guaranteeing the dataset is always shipping in a
self-consistent state."""

from __future__ import annotations

from collections import Counter

from ontchatbot.data.build_dataset import _stable_bucket, align, split
from ontchatbot.data.sources import SAMPLES
from ontchatbot.ner.dataset import bio_label_list


VALID_LABELS = set(bio_label_list())


def test_align_no_entity_marks_all_O():
    out = align(("xin chào ạ", []))
    assert all(t == "O" for t in out["ner_tags"])
    assert len(out["tokens"]) == len(out["ner_tags"]) > 0


def test_align_single_entity_emits_one_B():
    out = align(("quy trình bảo lưu thế nào", [("bảo lưu", "QuyTrinhHocVu")]))
    bs = [t for t in out["ner_tags"] if t.startswith("B-")]
    assert bs == ["B-QuyTrinhHocVu"]
    # The boundary must lie on the segmented "bảo_lưu" token.
    pos = out["ner_tags"].index("B-QuyTrinhHocVu")
    assert "bảo" in out["tokens"][pos] or "bảo_lưu" in out["tokens"][pos]


def test_align_multi_entity_same_class_yields_two_Bs():
    out = align((
        "học phí k65 và k67 khác nhau gì",
        [("k65", "DinhMucHocPhi"), ("k67", "DinhMucHocPhi")],
    ))
    bs = [t for t in out["ner_tags"] if t.startswith("B-")]
    assert bs == ["B-DinhMucHocPhi", "B-DinhMucHocPhi"]


def test_align_handles_segmenter_glue():
    """Underthesea sometimes glues an unrelated leading word into the same
    token as the entity start (e.g. ``có_học``). Char-level alignment must
    still mark exactly one ``B-`` and span the whole multi-word token."""
    out = align((
        "em hk này điểm thấp quá có học cải thiện kịp không",
        [("học cải thiện", "QuyTrinhHocVu")],
    ))
    bs = [t for t in out["ner_tags"] if t.startswith("B-")]
    assert bs == ["B-QuyTrinhHocVu"]
    assert any(t.startswith("I-QuyTrinhHocVu") for t in out["ner_tags"])


def test_align_overlap_raises():
    """An accidentally overlapping annotation must be rejected loudly so
    the dataset never silently ships double-labelled tokens."""
    import pytest
    with pytest.raises(ValueError):
        align(("bảo lưu kết quả", [
            ("bảo lưu", "QuyTrinhHocVu"),
            ("bảo lưu", "QuyTrinhHocVu"),  # second occurrence does not exist
        ]))


def test_corpus_compiles_cleanly_for_every_sample():
    """End-to-end sweep — every authored sample must align without raising
    and produce only valid BIO labels."""
    seen_texts: set[str] = set()
    bio_total: Counter[str] = Counter()
    for text, _ in SAMPLES:
        assert text not in seen_texts, f"duplicate source text: {text!r}"
        seen_texts.add(text)
    for sample in SAMPLES:
        out = align(sample)
        assert len(out["tokens"]) == len(out["ner_tags"])
        for t in out["ner_tags"]:
            assert t in VALID_LABELS, f"unknown tag {t!r} in {sample[0]!r}"
            bio_total[t] += 1
    # All five ontology classes must be represented somewhere.
    for tag in ("QuyTrinhHocVu", "PhongBanHanhChinh", "TaiLieuBieuMau",
                "DinhMucHocPhi", "PhuongThucThanhToan"):
        assert bio_total.get(f"B-{tag}", 0) >= 1, f"no B-{tag} in corpus"


def test_split_is_deterministic_and_disjoint():
    """The hash-based partition stays stable across reruns and never assigns
    the same text to both halves."""
    train_a, test_a = split(SAMPLES, test_pct=20)
    train_b, test_b = split(SAMPLES, test_pct=20)
    assert train_a == train_b and test_a == test_b
    train_texts = {t for t, _ in train_a}
    test_texts = {t for t, _ in test_a}
    assert train_texts.isdisjoint(test_texts)
    assert len(train_texts) + len(test_texts) == len(SAMPLES)


def test_stable_bucket_lies_in_range():
    for text, _ in SAMPLES[:50]:
        b = _stable_bucket(text)
        assert 0 <= b < 100
