"""Test tầng dữ liệu baseline Phase 8 (gold + docstore) — chạy dưới deps LÕI, KHÔNG cần BGE.

Khoá chặt 2 thứ dễ vỡ âm thầm: (1) suy gold mức-IRI từ cây-vàng đúng kind/iris/field; (2) phiếu
phẳng TRUNG THÀNH với fact ontology (không bịa, không sót) + đủ facet (chống artifact dựng phiếu).
"""

from __future__ import annotations

import json

import pytest

from ontchatbot.baseline.docstore import build_corpus
from ontchatbot.baseline.gold import answer_spec
from ontchatbot.config import TEST_PATH
from ontchatbot.ontology import _ALIAS_PROP
from ontchatbot.tree import parse


@pytest.fixture(scope="module")
def rows() -> list[dict]:
    return [json.loads(l) for l in TEST_PATH.read_text(encoding="utf-8").splitlines() if l.strip()]


def _by_cat(rows: list[dict], cat: str, n: int = 12) -> list[dict]:
    return [r for r in rows if r.get("category") == cat][:n]


# ── gold (suy IRI từ cây vàng) ───────────────────────────────────────────────

def test_gold_greeting_nonretrievable(ont, rows):
    for r in _by_cat(rows, "greeting"):
        s = answer_spec(parse(r["tree"]), ont)
        assert s.kind == "nonretrievable" and not s.iris


def test_gold_data_has_subject_and_field(ont, rows):
    sample = _by_cat(rows, "data_leaf")
    assert sample
    for r in sample:
        s = answer_spec(parse(r["tree"]), ont)
        assert s.kind == "data"
        assert s.iris                                   # có chủ thể (tài liệu mang giá trị)
        assert s.fields and all(p for p, _ in s.fields)  # có (property, value)


def test_gold_node_queries(ont, rows):
    for cat in ("forward_object", "self_desc"):
        for r in _by_cat(rows, cat):
            s = answer_spec(parse(r["tree"]), ont)
            assert s.kind == "node" and s.iris


def test_gold_fee_intersect_single(ont, rows):
    sample = _by_cat(rows, "fee_intersect")
    assert sample
    for r in sample:
        s = answer_spec(parse(r["tree"]), ont)
        assert s.kind == "node" and len(s.iris) == 1     # giao 2 facet → đúng 1 mức phí


def test_gold_fee_cohort_multiple(ont, rows):
    sample = _by_cat(rows, "fee_cohort")
    assert sample
    for r in sample:
        s = answer_spec(parse(r["tree"]), ont)
        assert s.kind == "node" and len(s.iris) >= 2     # cohort 1 facet → nhiều mức


# ── docstore (kho phiếu phẳng) ───────────────────────────────────────────────

def test_corpus_ids_are_iris(ont):
    c = build_corpus(ont)
    assert len(c) == 54
    assert set(c) == {i.name for i in ont._owl.individuals()}


def test_flat_doc_is_faithful(ont):
    """Mọi giá trị data của cá thể PHẢI xuất hiện nguyên văn trong phiếu phẳng (không bịa/sót)."""
    c = build_corpus(ont)
    for ind in ont._owl.individuals():
        doc = c[ind.name]
        for p in ont._data_props:
            if p == _ALIAS_PROP:
                continue
            for v in (getattr(ind, p, []) or []):
                assert str(v) in doc, f"{ind.name}.{p}={v} thiếu trong phiếu"


def test_fee_doc_has_all_facets(ont):
    """Phiếu fee chứa đủ alias (mã khoá + tên/alias ngành) → truy vấn GIAO công bằng cho phẳng."""
    c = build_corpus(ont)
    fees = [i for i in ont._owl.individuals() if i.name.startswith("Phi")]
    assert fees
    for ind in fees:
        doc = c[ind.name]
        for a in (getattr(ind, _ALIAS_PROP, []) or []):
            assert str(a) in doc, f"{ind.name} thiếu facet {a!r}"
