"""render: act routing + format KetQua (chạy trên dataclass thuần, không owlready2)."""

from __future__ import annotations

from ontchatbot.ontology import GiaTri, KetQua, OntNode
from ontchatbot.render import GREETING_REPLY, OOD_REPLY, VAGUE_REPLY, render_reply
from ontchatbot.tree import GREETING, OOD, QUERY, VAGUE, Cay


def _qreply(kq: KetQua) -> str:
    return render_reply(Cay(act=QUERY), kq)


def test_acts():
    assert render_reply(Cay(act=GREETING), KetQua()) == GREETING_REPLY
    assert render_reply(Cay(act=OOD), KetQua()) == OOD_REPLY
    assert render_reply(Cay(act=VAGUE), KetQua()) == VAGUE_REPLY


def test_single_node_self_desc_keeps_phone_string():
    n = OntNode(iri="PhongKHTC", cls="PhongBanHanhChinh", label="Phòng Tài chính",
                data={"email": "khtc@ntu.edu.vn", "soDienThoai": "02583831150"})
    out = _qreply(KetQua(nodes=[n]))
    assert "Phòng Tài chính" in out
    assert "khtc@ntu.edu.vn" in out
    assert "02583831150" in out          # số 0 đầu giữ nguyên, không bị format dấu chấm


def test_fee_per_credit_format():
    n = OntNode(iri="PhiK65620k", cls="DinhMucHocPhi", label="Học phí K65 (CNTT)",
                data={"hocPhiMoiTinChi": 620000})
    assert "620.000 đ/tín chỉ" in _qreply(KetQua(nodes=[n]))


def test_multiple_nodes_bulleted():
    a = OntNode(iri="A", cls="", label="Alpha")
    b = OntNode(iri="B", cls="", label="Beta")
    out = _qreply(KetQua(nodes=[a, b]))
    assert "•" in out and "Alpha" in out and "Beta" in out


def test_data_value_render():
    out = _qreply(KetQua(values=[GiaTri(prop="email", values=("khtc@ntu.edu.vn",))]))
    assert "Email: khtc@ntu.edu.vn" in out


def test_paragraph_value_render():
    out = _qreply(KetQua(values=[GiaTri(prop="noiDung", values=("Dòng 1\nDòng 2",))]))
    assert out == "Dòng 1\nDòng 2"


def test_miss_render():
    out = _qreply(KetQua(misses=["điều kiện"]))
    assert "Không có thông tin" in out and "«điều kiện»" in out


def test_empty_query_falls_back():
    assert _qreply(KetQua()) == OOD_REPLY
