"""Answer layer: DNF grouping (same-class substitution) + shadow intersection.

The grouping rule is the novel, fiddly bit, so it is unit-tested directly on
constructed nodes (no graph). The execution path is checked end-to-end through
understand → answer on the real graph.
"""

from __future__ import annotations

from ontchatbot.answer import answer, build_groups
from ontchatbot.graph import Node
from ontchatbot.nlu import understand


def _n(iri: str, cls: str) -> Node:
    return Node(iri=iri, cls=cls, label=iri)


def _iris(groups):
    return [[n.iri for n in g] for g in groups]


# DNF — same-class-substitution rule (the two canonical examples).

def test_groups_substitute_same_class_keeps_following_filter():
    # "học phí k65 cntt với k67": cntt follows k65 → stays; k67 replaces k65.
    groups = build_groups([_n("KhoaK65", "Khoa"),
                           _n("NganhCNTT", "Nganh"),
                           _n("KhoaK67", "Khoa")])
    assert _iris(groups) == [["KhoaK65", "NganhCNTT"], ["KhoaK67"]]


def test_groups_inherit_preceding_filter():
    # "học phí cntt k65 với k67": cntt precedes k65 → inherited into both groups.
    groups = build_groups([_n("NganhCNTT", "Nganh"),
                           _n("KhoaK65", "Khoa"),
                           _n("KhoaK67", "Khoa")])
    assert _iris(groups) == [["NganhCNTT", "KhoaK65"], ["NganhCNTT", "KhoaK67"]]


def test_groups_split_two_same_class_values():
    # Two cohorts can never intersect → substitution splits them.
    groups = build_groups([_n("KhoaK65", "Khoa"), _n("KhoaK66", "Khoa")])
    assert _iris(groups) == [["KhoaK65"], ["KhoaK66"]]


def test_groups_single_constraint():
    assert _iris(build_groups([_n("KhoaK65", "Khoa")])) == [["KhoaK65"]]


# Execution — end-to-end node correctness.

def _result(text, graph):
    facts = answer(understand(text, graph.lexicon()), graph)
    return {n.iri for f in facts for n in f.objects}


def test_intersection_collapses_to_one(graph):
    assert _result("học phí k65 ngành cntt", graph) == {"HocPhiK65CongNgheThongTin"}


def test_union_of_groups(graph):
    # K65×CNTT → one fee; K67 → its two fees; unioned.
    assert _result("học phí k65 cntt với k67 như nào", graph) == {
        "HocPhiK65CongNgheThongTin", "HocPhiK67KinhTeQuanLy", "HocPhiK67KyThuat"}


def test_forward_relation(graph):
    assert _result("điều kiện bảo lưu", graph) == {
        "DieuKienBaoLuuCaNhan", "DieuKienBaoLuuQuocTe",
        "DieuKienBaoLuuVuTrang", "DieuKienBaoLuuYTe"}


def test_self_description(graph):
    assert _result("Phòng Công tác Sinh viên ở đâu", graph) == {"PhongCongTacSinhVien"}


def test_greeting_and_ood_yield_nothing(graph):
    assert _result("xin chào", graph) == set()
    assert _result("thời tiết hôm nay", graph) == set()
