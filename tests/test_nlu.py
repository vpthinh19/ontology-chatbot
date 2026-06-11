"""NLU baseline: intent classification, anchor-surface stripping, slots."""

from __future__ import annotations

import pytest

from ontchatbot.nlu import understand


@pytest.mark.parametrize("text, intent", [
    ("điều kiện bảo lưu là gì", "ASK_CONDITION"),
    ("Phòng CTSV ở đâu", "ASK_OFFICE"),
    ("Phòng CTSV phụ trách gì", "ASK_PROCEDURE"),
    ("học phí k65 bao nhiêu", "ASK_FEE"),
    ("thanh toán trên website ra sao", "ASK_PAYMENT"),
    ("các bước đóng học phí", "ASK_STEP"),
    ("quy trình bảo lưu căn cứ quy định nào", "ASK_REGULATION"),
    ("CPA 5.2 tốt nghiệp được không", "ELIGIBILITY"),
    ("xin chào ạ", "GREETING"),
    ("cảm ơn nhé", "GREETING"),
])
def test_intent_classification(text, intent):
    assert understand(text).intent == intent


def test_listing_detected():
    q = understand("trường có những phòng ban hành chính nào")
    assert q.is_listing


def test_anchor_surface_strips_filler_keeps_entity():
    # "ở đâu" goes; "Phòng CTSV" stays (ctsv expands to its full name in clean).
    surface = understand("Phòng CTSV ở đâu").entities[0].surface.lower()
    assert "công tác sinh viên" in surface
    assert "đâu" not in surface


def test_anchor_surface_protects_homograph_tokens():
    # "ban" (= bạn, filler) must not be stripped from "phòng ban" (department).
    q = understand("trường có những phòng ban hành chính nào")
    assert "ban" in q.entities[0].surface.lower()


def test_cohort_slot_from_raw_text():
    assert understand("học phí k65 bao nhiêu").slots.get("cohort") == "K65"


def test_cpa_slot_survives_teencode_expansion():
    # "cpa" expands to a phrase in clean(); the slot is read from raw text.
    assert understand("CPA 5.2 tốt nghiệp được không").slots.get("cpa") == 5.2


def test_greeting_has_no_entity():
    assert understand("xin chào").entities == []
