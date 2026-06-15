"""Graph: schema BFS planner + ABox traversal + lexicon.

Asserts on stable v9 IRIs and camelCase property names so a planner or schema
regression surfaces immediately. The fuzzy anchor / filter_by handlers are gone
(query-graph redesign); resolution now lives in nlu via the lexicon.
"""

from __future__ import annotations

from ontchatbot.graph import Step


# Planner — direction is derived from the schema, never hard-coded.

def test_plan_forward_single_hop(graph):
    assert graph.plan("QuyTrinhHocVu", "DieuKien") == [Step("coDieuKien", False)]


def test_plan_inverse_when_anchor_is_range(graph):
    assert graph.plan("PhongBanHanhChinh", "QuyTrinhHocVu") == [
        Step("duocXuLyBoi", True)]


def test_plan_two_hop_document_to_office(graph):
    assert graph.plan("TaiLieuBieuMau", "PhongBanHanhChinh") == [
        Step("canTaiLieu", True), Step("duocXuLyBoi", False)]


def test_plan_cohort_to_fee_is_inverse(graph):
    # A cohort sits on the range side of apDungChoKhoa → reach fees inverse.
    assert graph.plan("Khoa", "DinhMucHocPhi") == [Step("apDungChoKhoa", True)]


def test_plan_self_is_empty(graph):
    assert graph.plan("PhongBanHanhChinh", "PhongBanHanhChinh") == []


def test_plan_unreachable_is_none(graph):
    assert graph.plan("QuyTrinhHocVu", "KhongTonTai") is None


# Executor — runs a plan over individuals.

def test_walk_forward_lists_conditions(graph):
    node = graph.node("QuyTrinhBaoLuu")
    out = graph.walk(node, graph.plan("QuyTrinhHocVu", "DieuKien"))
    assert {n.cls for n in out} == {"DieuKien"}
    assert len(out) == 4


def test_walk_inverse_office_to_procedures(graph):
    node = graph.node("PhongCongTacSinhVien")
    out = graph.walk(node, graph.plan("PhongBanHanhChinh", "QuyTrinhHocVu"))
    assert "QuyTrinhBaoLuu" in {n.iri for n in out}


def test_walk_two_hop_document_to_office(graph):
    node = graph.node("DonXinBaoLuu")
    out = graph.walk(node, graph.plan("TaiLieuBieuMau", "PhongBanHanhChinh"))
    assert [n.iri for n in out] == ["PhongCongTacSinhVien"]


def test_walk_cohort_to_fees(graph):
    node = graph.node("KhoaK65")
    out = graph.walk(node, graph.plan("Khoa", "DinhMucHocPhi"))
    assert {n.iri for n in out} == {"HocPhiK65QuanTriKinhDoanh",
                                    "HocPhiK65CongNgheThongTin"}


def test_walk_empty_steps_returns_self(graph):
    node = graph.node("PhongCongTacSinhVien")
    assert [n.iri for n in graph.walk(node, [])] == ["PhongCongTacSinhVien"]


def test_instances_lists_a_class(graph):
    iris = {n.iri for n in graph.instances("PhongBanHanhChinh")}
    assert iris == {"PhongCongTacSinhVien", "PhongDaoTaoDaiHoc",
                    "PhongKeHoachTaiChinh", "VanPhongTruong"}


def test_node_data_has_no_object_links(graph):
    # Node.data carries only data properties; relations come via walk().
    data = graph.node("PhongCongTacSinhVien").data
    assert "email" in data and "duocXuLyBoi" not in data


# Lexicon — the danh bạ the NLU scans against.

def test_lexicon_marks_class_vs_individual(graph):
    lex = graph.lexicon()
    by_phrase: dict[str, set] = {}
    for e in lex:
        by_phrase.setdefault(e.phrase, set()).add((e.kind, e.cls, e.iri))
    # "học phí" is a class alias (subject); "k65" an individual (constraint).
    assert ("class", "DinhMucHocPhi", "") in by_phrase["hoc phi"]
    assert ("individual", "Khoa", "KhoaK65") in by_phrase["k65"]
    assert ("individual", "Nganh", "NganhCongNgheThongTin") in by_phrase["cntt"]
