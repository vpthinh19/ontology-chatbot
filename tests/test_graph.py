"""Graph: schema BFS planner + ABox traversal + fuzzy anchor.

Asserts on stable v9 IRIs so a planner regression surfaces immediately.
"""

from __future__ import annotations

from ontchatbot.graph import Step


# Planner — direction is derived from the schema, never hard-coded.

def test_plan_forward_single_hop(graph):
    assert graph.plan("QuyTrinhHocVu", "DieuKien") == [Step("hasCondition", False)]


def test_plan_inverse_when_anchor_is_range(graph):
    # An office sits on the range side of handledBy → reach procedures via inverse.
    assert graph.plan("PhongBanHanhChinh", "QuyTrinhHocVu") == [
        Step("handledBy", True)]


def test_plan_two_hop_document_to_office(graph):
    # Document → (which procedure needs it) → (which office handles it).
    assert graph.plan("TaiLieuBieuMau", "PhongBanHanhChinh") == [
        Step("requiresDocument", True), Step("handledBy", False)]


def test_plan_self_is_empty(graph):
    assert graph.plan("PhongBanHanhChinh", "PhongBanHanhChinh") == []


def test_plan_unreachable_is_none(graph):
    # A target class absent from the schema graph is unreachable → None.
    assert graph.plan("QuyTrinhHocVu", "KhongTonTai") is None


# Executor — runs a plan over individuals.

def test_walk_forward_lists_conditions(graph):
    node = graph.node("QuyTrinhBaoLuu")
    out = graph.walk(node, graph.plan("QuyTrinhHocVu", "DieuKien"))
    assert {n.cls for n in out} == {"DieuKien"}
    assert len(out) >= 3


def test_walk_inverse_office_to_procedures(graph):
    node = graph.node("PhongCongTacSinhVien")
    out = graph.walk(node, graph.plan("PhongBanHanhChinh", "QuyTrinhHocVu"))
    assert "QuyTrinhBaoLuu" in {n.iri for n in out}


def test_walk_two_hop_document_to_office(graph):
    node = graph.node("DonXinBaoLuu")
    out = graph.walk(node, graph.plan("TaiLieuBieuMau", "PhongBanHanhChinh"))
    assert [n.iri for n in out] == ["PhongCongTacSinhVien"]


def test_walk_empty_steps_returns_self(graph):
    node = graph.node("PhongCongTacSinhVien")
    assert [n.iri for n in graph.walk(node, [])] == ["PhongCongTacSinhVien"]


# Anchor — resolve text → node set.

def test_anchor_exact_label(graph):
    anc = graph.anchor("Phòng Công tác Sinh viên", "PhongBanHanhChinh")
    assert [n.iri for n in anc.nodes] == ["PhongCongTacSinhVien"]


def test_anchor_class_label_wins_listing(graph):
    anc = graph.anchor("phòng ban hành chính")
    assert anc.class_won and anc.cls == "PhongBanHanhChinh"


def test_anchor_prefer_cls_breaks_alias_pollution(graph):
    # "học phí k65" matches the NopHocPhi procedure alias too; the fee bias wins.
    anc = graph.anchor("học phí k65", prefer_cls="DinhMucHocPhi")
    assert anc.cls == "DinhMucHocPhi"


def test_anchor_below_threshold_is_empty(graph):
    assert graph.anchor("thời tiết hôm nay").nodes == []


def test_node_data_has_no_object_links(graph):
    # Node.data carries only data properties; relations come via walk().
    data = graph.node("PhongCongTacSinhVien").data
    assert "officeEmail" in data and "handledBy" not in data


# v9 fee dimensions — cohort and program set arithmetic.

def test_filter_by_cohort_narrows_fees(graph):
    fees = graph.instances("DinhMucHocPhi")
    k65 = graph.filter_by(fees, cohort="K65")
    assert {n.iri for n in k65} == {"HocPhiK65QuanTriKinhDoanh",
                                    "HocPhiK65CongNgheThongTin"}


def test_filter_by_cohort_and_program_intersects_to_one(graph):
    # The research claim: K65 ∩ CNTT collapses two fee rows to exactly one.
    fees = graph.instances("DinhMucHocPhi")
    one = graph.filter_by(fees, cohort="K65", program="NganhCongNgheThongTin")
    assert [n.iri for n in one] == ["HocPhiK65CongNgheThongTin"]


def test_resolve_program_from_alias(graph):
    assert graph.resolve_program("học phí k65 ngành cntt") == "NganhCongNgheThongTin"
    assert graph.resolve_program("học phí k65") == ""
