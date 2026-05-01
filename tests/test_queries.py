"""Tests for ``ontchatbot.ontology.queries``."""

from __future__ import annotations

from ontchatbot.ontology.queries import (
    fetch_dinh_muc,
    fetch_phong_ban,
    fetch_phuong_thuc,
    fetch_quy_trinh,
    fetch_tai_lieu,
)


def test_quy_trinh_has_description_and_links(onto):
    rec = fetch_quy_trinh("QuyTrinh_BaoLuu")
    assert rec["kind"] == "QuyTrinhHocVu"
    assert rec["label"] and "bảo lưu" in rec["label"].lower()
    assert rec["description"]
    assert any(x["name"] == "PhongCTSV" for x in rec["handled_by"])
    assert {x["name"] for x in rec["conditions"]} == {
        "DieuKienBaoLuu_CaNhan", "DieuKienBaoLuu_QuocTe",
        "DieuKienBaoLuu_VuTrang", "DieuKienBaoLuu_YTe",
    }
    assert any(x.get("url") for x in rec["documents"])


def test_phong_ban_returns_contact_card(onto):
    rec = fetch_phong_ban("PhongCTSV")
    assert rec["email"] == "ctsv@ntu.edu.vn"
    assert rec["phone"] and rec["website"]


def test_dinh_muc_fee_per_credit(onto):
    rec = fetch_dinh_muc("Phi_K65_550k")
    assert rec["fee_per_credit"] == 550000
    assert rec["target"] and rec["decision"]


def test_tai_lieu_form_url(onto):
    rec = fetch_tai_lieu("DonXinBaoLuu")
    assert rec["form_url"] and rec["form_url"].startswith("http")


def test_phuong_thuc_has_label(onto):
    rec = fetch_phuong_thuc("PayOnline")
    assert rec["label"] and "sinhvien" in rec["label"].lower()
