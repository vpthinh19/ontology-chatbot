"""Graph: schema BFS planner + ABox traversal + fuzzy anchor.

Asserts on stable v8 IRIs so a planner regression surfaces immediately.
"""

from __future__ import annotations

from ontchatbot.graph import Step


# Planner — direction is derived from the schema, never hard-coded.

def test_plan_forward_single_hop(graph):
    assert graph.plan("AcademicProcedure", "Condition") == [Step("hasCondition", False)]


def test_plan_inverse_when_anchor_is_range(graph):
    # An office sits on the range side of handledBy → reach procedures via inverse.
    assert graph.plan("AdministrativeOffice", "AcademicProcedure") == [
        Step("handledBy", True)]


def test_plan_two_hop_document_to_office(graph):
    # Document → (which procedure needs it) → (which office handles it).
    assert graph.plan("Document", "AdministrativeOffice") == [
        Step("requiresDocument", True), Step("handledBy", False)]


def test_plan_self_is_empty(graph):
    assert graph.plan("AdministrativeOffice", "AdministrativeOffice") == []


def test_plan_unreachable_is_none(graph):
    # A target class absent from the schema graph is unreachable → None.
    assert graph.plan("AcademicProcedure", "KhongTonTai") is None


# Executor — runs a plan over individuals.

def test_walk_forward_lists_conditions(graph):
    node = graph.node("QuyTrinh_BaoLuu")
    out = graph.walk(node, graph.plan("AcademicProcedure", "Condition"))
    assert {n.cls for n in out} == {"Condition"}
    assert len(out) >= 3


def test_walk_inverse_office_to_procedures(graph):
    node = graph.node("PhongCTSV")
    out = graph.walk(node, graph.plan("AdministrativeOffice", "AcademicProcedure"))
    assert "QuyTrinh_BaoLuu" in {n.iri for n in out}


def test_walk_two_hop_document_to_office(graph):
    node = graph.node("DonXinBaoLuu")
    out = graph.walk(node, graph.plan("Document", "AdministrativeOffice"))
    assert [n.iri for n in out] == ["PhongCTSV"]


def test_walk_empty_steps_returns_self(graph):
    node = graph.node("PhongCTSV")
    assert [n.iri for n in graph.walk(node, [])] == ["PhongCTSV"]


# Anchor — resolve text → node set.

def test_anchor_exact_label(graph):
    anc = graph.anchor("Phòng Công tác Sinh viên", "PhongBanHanhChinh")
    assert [n.iri for n in anc.nodes] == ["PhongCTSV"]


def test_anchor_class_label_wins_listing(graph):
    anc = graph.anchor("phòng ban hành chính")
    assert anc.class_won and anc.cls == "AdministrativeOffice"


def test_anchor_prefer_cls_breaks_alias_pollution(graph):
    # "học phí k65" matches the NopHocPhi procedure alias too; the fee bias wins.
    anc = graph.anchor("học phí k65", prefer_cls="FeeCategory")
    assert anc.cls == "FeeCategory"


def test_anchor_below_threshold_is_empty(graph):
    assert graph.anchor("thời tiết hôm nay").nodes == []


def test_node_data_has_no_object_links(graph):
    # Node.data carries only data properties; relations come via walk().
    data = graph.node("PhongCTSV").data
    assert "officeEmail" in data and "handledBy" not in data


def test_filter_by_cohort_narrows_fees(graph):
    fees = graph.instances("FeeCategory")
    k65 = graph.filter_by(fees, cohort="K65")
    assert {n.iri for n in k65} == {"Phi_K65_550k", "Phi_K65_620k"}
