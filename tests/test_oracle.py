"""Oracle nghiêm: strict-parse + validate + MUTATION.

Mục tiêu: chứng minh oracle KHÔNG "xanh giả" - cây đột biến (sai type/label/cấu trúc)
PHẢI bị từ chối; còn phép hoán đổi commutative (thứ tự sibling, k65↔cntt cùng giao)
KHÔNG được từ chối. Đây là điều kiện đủ trước khi dùng traverse làm oracle cho dataset.
"""

from __future__ import annotations

import pytest

from ontchatbot.scripts.validate_dataset import (
    ExpectedValue,
    trace_signature,
    validate_case_strict,
)
from ontchatbot.tree import StrictParseError, parse, parse_strict


def ind(l, *c): return {"label": l, "type": "individual", "children": list(c)}
def obj(l, *c): return {"label": l, "type": "object", "children": list(c)}
def data(l):    return {"label": l, "type": "data", "children": []}
def q(root):    return {"act": "query", "entities": [root]}


def ok(ont, raw, **exp):
    return validate_case_strict("t", raw, ontology=ont, expected_act=raw["act"], **exp)


# ── strict-parse: bắt mọi bất thường parse() khoan dung nuốt ──────────────────

@pytest.mark.parametrize("raw", [
    {"act": "query", "entities": [ind("a"), ind("b")]},                  # >1 chủ thể
    {"act": "query", "entities": []},                                    # rỗng
    {"act": "query", "entities": [{"label": "x", "type": "data", "children": [ind("y")]}]},  # data có con
    {"act": "query", "entities": [obj("điều kiện")]},                    # gốc không individual
    {"act": "greeting", "entities": [ind("a")]},                         # greeting kèm entities
    {"act": "xxx", "entities": []},                                      # act sai
    {"act": "query", "entities": [{"label": "  ", "type": "individual", "children": []}]},  # label rỗng
])
def test_parse_strict_rejects(raw):
    with pytest.raises(StrictParseError):
        parse_strict(raw)


def test_parse_strict_accepts_valid():
    parse_strict(q(ind("bảo lưu", obj("điều kiện"))))
    parse_strict({"act": "greeting", "entities": []})


def test_parse_lenient_still_tolerant():
    # parse() production vẫn khoan dung (không raise) - tách bạch với strict
    assert parse({"act": "query", "entities": [ind("a"), ind("b")]}).root is not None


# ── validator happy-path ─────────────────────────────────────────────────────

def test_validate_forward_object_ok(ont):
    r = ok(ont, q(ind("bảo lưu", obj("điều kiện"))),
           expected_nodes={"DieuKienBaoLuuCaNhan", "DieuKienBaoLuuQuocTe",
                           "DieuKienBaoLuuVuTrang", "DieuKienBaoLuuYTe"})
    assert r.ok, r.errors


def test_validate_data_leaf_ok(ont):
    r = ok(ont, q(ind("phòng khtc", data("email"))),
           expected_values=[ExpectedValue("email", "khtc@ntu.edu.vn")])
    assert r.ok, r.errors


def test_validate_vague_root_ok(ont):
    assert ok(ont, q(ind("điều kiện")), expected_vague=True).ok


# ── MUTATION: cây sai PHẢI fail ──────────────────────────────────────────────

BASE = q(ind("bảo lưu", obj("điều kiện")))
BASE_EXP = {"DieuKienBaoLuuCaNhan", "DieuKienBaoLuuQuocTe",
            "DieuKienBaoLuuVuTrang", "DieuKienBaoLuuYTe"}


@pytest.mark.parametrize("mut, why", [
    (q(ind("bảo lưu", data("điều kiện"))),                       "type object→data"),
    (q(ind("bảo lưu", obj("kết quả"))),                          "label sang property khác"),
    (q(ind("bảo lưu", obj("điều kiện", ind("zzz")))),           "thêm con rác (thu hẹp rỗng)"),
    (q(ind("bảo lưu", obj("điều kiện"), obj("zzz"))),           "thêm sibling rác → miss"),
    (q(ind("chuyển ngành", obj("điều kiện"))),                  "đổi gốc sang cá thể khác"),
    (q(ind("bảo lưu", obj("phòng xử lý"))),                     "đổi quan hệ → node khác"),
])
def test_mutation_must_fail(ont, mut, why):
    r = validate_case_strict("t", mut, ontology=ont,
                             expected_act="query", expected_nodes=BASE_EXP)
    assert not r.ok, f"đột biến [{why}] lẽ ra phải fail nhưng pass"


def test_mutation_change_act_fails(ont):
    # cùng cây nhưng act bị đổi → act mismatch
    r = validate_case_strict("t", {"act": "vague", "entities": [ind("bảo lưu", obj("điều kiện"))]},
                             ontology=ont, expected_act="query", expected_nodes=BASE_EXP)
    assert not r.ok


def test_mutation_intersect_to_union_fails(ont):
    # k65>cntt (giao=PhiK65620k) → [k65, cntt] sibling (hợp) phải khác kết quả
    union = q(ind("học phí", ind("k65"), ind("cntt")))
    r = validate_case_strict("t", union, ontology=ont,
                             expected_act="query", expected_nodes={"PhiK65620k"})
    assert not r.ok


def test_mutation_facet_swap_fails(ont):
    # cntt → qtkd đổi mức phí
    r = validate_case_strict("t", q(ind("học phí", ind("k65", ind("quản trị kinh doanh")))),
                             ontology=ont, expected_act="query", expected_nodes={"PhiK65620k"})
    assert not r.ok


# ── Commutative: KHÔNG được over-fail ────────────────────────────────────────

def test_order_invariance_not_rejected(ont):
    # k65>cntt và cntt>k65 cùng giao ra PhiK65620k → cả hai hợp lệ
    for tree in (q(ind("học phí", ind("k65", ind("cntt")))),
                 q(ind("học phí", ind("cntt", ind("k65"))))):
        r = validate_case_strict("t", tree, ontology=ont,
                                 expected_act="query", expected_nodes={"PhiK65620k"})
        assert r.ok, r.errors


def test_sibling_reorder_not_rejected(ont):
    a = q(ind("học phí", ind("k65", ind("cntt")), ind("k67")))
    b = q(ind("học phí", ind("k67"), ind("k65", ind("cntt"))))
    exp = {"PhiK65620k", "PhiK67550k", "PhiK67620k"}
    assert ok(ont, a, expected_nodes=exp).ok
    assert ok(ont, b, expected_nodes=exp).ok


# ── Trace bắt "may mắn cùng node" ────────────────────────────────────────────

def test_trace_catches_lucky_same_node(ont):
    # gold: học phí > k65 > cntt (3 bước) → PhiK65620k.
    gold = q(ind("học phí", ind("k65", ind("cntt"))))
    sig = trace_signature(ont.traverse(parse_strict(gold)))
    # đột biến: bỏ tầng k65 → "học phí > cntt" cũng ra PhiK65620k (cùng node!)
    lucky = q(ind("học phí", ind("cntt")))
    # không ghim trace: node trùng nên LỌT (đúng giới hạn node-match)
    assert validate_case_strict("t", lucky, ontology=ont, expected_act="query",
                                expected_nodes={"PhiK65620k"}).ok
    # ghim trace: cấu trúc khác → BỊ BẮT
    r = validate_case_strict("t", lucky, ontology=ont, expected_act="query",
                             expected_nodes={"PhiK65620k"}, expected_trace=sig)
    assert not r.ok


# ── Khớp property CỤC BỘ + sàn điểm ──────────────────────────────────────────

def test_local_scope_absent_property_misses(ont):
    # QuyTrinhNopHocPhi KHÔNG có quan hệ "điều kiện" → con object 'điều kiện' phải MISS,
    # không được mượn property toàn cục để trả bậy.
    r = ont.traverse(parse(q(ind("học phí", obj("điều kiện")))))
    assert not r.nodes and "điều kiện" in r.misses


def test_local_floor_prevents_best_of_one(ont):
    # Mức phí chỉ có 1 object-prop (canCuQuyDinh). Nhãn rác 'phòng quy định' trùng-một-phần
    # (~33 điểm) < sàn 80 → MISS. (GLOBAL cũ không sàn sẽ khớp canCuQuyDinh → trả Quy định SAI.)
    r = ont.traverse(parse(q(ind("học phí", ind("k65", ind("cntt", obj("phòng quy định")))))))
    assert not r.nodes and r.misses


def test_local_scope_keeps_valid_paths(ont):
    # Đảm bảo cục-bộ-hoá KHÔNG phá đường đi hợp lệ: quan hệ có thật vẫn đi được.
    r = ont.traverse(parse(q(ind("bảo lưu", obj("phòng xử lý")))))
    assert {n.iri for n in r.nodes} == {"PhongCTSV"}
