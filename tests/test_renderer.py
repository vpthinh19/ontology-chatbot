"""Tests for :class:`ontchatbot.renderer.Renderer` — driven by mock dicts.

Loads no OWL — Renderer's contract is a plain dict, so unit tests stay fast.
"""

from __future__ import annotations

import pytest

from ontchatbot.renderer import GREETING_REPLY, OUT_OF_DOMAIN_REPLY, Renderer


@pytest.fixture(scope="module")
def renderer() -> Renderer:
    return Renderer.get()


# Compose policy

def test_compose_blocks_take_priority(renderer: Renderer):
    assert renderer.compose("BLOCK", greeting=True).strip() == "BLOCK"
    assert renderer.compose("BLOCK", greeting=False).strip() == "BLOCK"


def test_compose_greeting_only(renderer: Renderer):
    assert renderer.compose("", greeting=True).strip() == GREETING_REPLY


def test_compose_out_of_domain(renderer: Renderer):
    assert renderer.compose("", greeting=False).strip() == OUT_OF_DOMAIN_REPLY


# Individual rendering — synthetic dicts

def test_render_individual_inline_single_value(renderer: Renderer):
    out = renderer.render({
        "type": "individual", "iri": "X",
        "class": "AdministrativeOffice", "label": "Phòng Tài chính",
        "Email liên hệ": "ctsv@ntu.edu.vn",
    })
    # AdministrativeOffice has no class emoji (intentionally removed) —
    # the title is the bare label.
    assert out.startswith("Phòng Tài chính")
    assert "• Email liên hệ: ctsv@ntu.edu.vn" in out


def test_render_individual_url_data_becomes_markdown_link(renderer: Renderer):
    out = renderer.render({
        "type": "individual", "iri": "X",
        "class": "AdministrativeOffice", "label": "Phòng X",
        "Website": "https://example.com/",
    })
    # URL has no parens → encoding is a no-op, matches verbatim.
    assert "• Website: [https://example.com/](https://example.com/)" in out


def test_render_md_link_encodes_parens_in_url(renderer: Renderer):
    """Regression: URL parens are percent-encoded inside the markdown ``href``
    so the frontend regex doesn't truncate at an inner ``)``. The display
    label may still show raw parens — only the href needs to be parse-safe."""
    out = renderer.render({
        "type": "individual", "iri": "R", "class": "Regulation",
        "label": "Quyết định 729/QĐ-ĐHNT",
        "Đường dẫn tải biểu mẫu": "https://x.vn/p-729-(2025)-(2).pdf",
    })
    # The href substring must have parens encoded.
    assert "](https://x.vn/p-729-%282025%29-%282%29.pdf)" in out


def test_render_individual_multi_value_data_uses_sub_bullets(renderer: Renderer):
    out = renderer.render({
        "type": "individual", "iri": "X",
        "class": "FeeCategory", "label": "Học phí",
        "Áp dụng cho đối tượng/ngành": ["CNTT", "QTKD", "Kế toán"],
    })
    assert "• Áp dụng cho đối tượng/ngành:\n" in out
    assert "  – CNTT" in out and "  – QTKD" in out


def test_render_individual_object_property_target_with_data(renderer: Renderer):
    """Single rich target → label inlined with header, sub-sections use ◦."""
    out = renderer.render({
        "type": "individual", "iri": "P",
        "class": "AcademicProcedure", "label": "Quy trình X",
        "Áp dụng mức học phí": [
            {"type": "individual", "iri": "Phi_K65", "class": "FeeCategory",
             "label": "Học phí K65 (CNTT)",
             "Áp dụng cho đối tượng/ngành": "CNTT",
             "Mức học phí/1 Tín chỉ (VNĐ)": 620000},
        ],
    })
    # Single target — label inlined as ``• Header: label``
    assert "• Áp dụng mức học phí: Học phí K65 (CNTT)" in out
    # Nested data uses ◦ marker, indented one level
    assert "  ◦ Áp dụng cho đối tượng/ngành: CNTT" in out
    assert "  ◦ Mức học phí/1 Tín chỉ (VNĐ): 620,000" in out


def test_render_individual_multi_object_targets_with_data(renderer: Renderer):
    """Multi rich targets → list with – markers; data nested under each."""
    out = renderer.render({
        "type": "individual", "iri": "P",
        "class": "AcademicProcedure", "label": "Quy trình X",
        "Áp dụng mức học phí": [
            {"type": "individual", "iri": "A", "class": "FeeCategory",
             "label": "Học phí A", "Mức học phí/1 Tín chỉ (VNĐ)": 100000},
            {"type": "individual", "iri": "B", "class": "FeeCategory",
             "label": "Học phí B", "Mức học phí/1 Tín chỉ (VNĐ)": 200000},
        ],
    })
    assert "• Áp dụng mức học phí:" in out
    # Each target is a ``– label`` item indented under the section
    assert "  – Học phí A" in out and "  – Học phí B" in out
    # Target data uses ◦ and is indented one level deeper than the – item
    assert "    ◦ Mức học phí/1 Tín chỉ (VNĐ): 100,000" in out
    assert "    ◦ Mức học phí/1 Tín chỉ (VNĐ): 200,000" in out


def test_render_target_compact_when_only_url(renderer: Renderer):
    """Single target with only identity + URL stays compact (no nested ◦)."""
    out = renderer.render({
        "type": "individual", "iri": "P",
        "class": "AcademicProcedure", "label": "Quy trình X",
        "Cần biểu mẫu/văn bản": [
            {"type": "individual", "iri": "DonX",
             "class": "Document", "label": "Đơn xin Y",
             "Đường dẫn tải biểu mẫu": "https://example.com/form.docx"}
        ],
    })
    # Compact — label inlined as link, no ``◦`` sub-bullets needed.
    assert "• Cần biểu mẫu/văn bản: [Đơn xin Y](https://example.com/form.docx)" in out
    assert "◦" not in out


def test_render_individual_object_property_without_url(renderer: Renderer):
    out = renderer.render({
        "type": "individual", "iri": "P",
        "class": "AcademicProcedure", "label": "Quy trình X",
        "Yêu cầu điều kiện": [
            {"type": "individual", "iri": "C1", "class": "Condition",
             "label": "Điều kiện 1"},
            {"type": "individual", "iri": "C2", "class": "Condition",
             "label": "Điều kiện 2"},
        ],
    })
    assert "• Yêu cầu điều kiện:\n  – Điều kiện 1\n  – Điều kiện 2" in out


def test_render_individual_paragraph_property_no_bullet(renderer: Renderer):
    """Convention: leading newline marks free-flow paragraph (no bullet)."""
    out = renderer.render({
        "type": "individual", "iri": "P",
        "class": "AcademicProcedure", "label": "Quy trình X",
        "Mô tả quy trình": "\nDòng 1\nDòng 2",
    })
    assert "Dòng 1\nDòng 2" in out
    assert "• Mô tả quy trình" not in out


def test_render_individual_paragraph_single_line_no_bullet(renderer: Renderer):
    out = renderer.render({
        "type": "individual", "iri": "P",
        "class": "AcademicProcedure", "label": "Quy trình X",
        "Mô tả quy trình": "\nMột dòng duy nhất.",
    })
    assert "Một dòng duy nhất." in out
    assert "• Mô tả quy trình" not in out


def test_render_individual_currency_thousands_separator(renderer: Renderer):
    out = renderer.render({
        "type": "individual", "iri": "F",
        "class": "FeeCategory", "label": "Học phí K65",
        "Mức học phí/1 Tín chỉ (VNĐ)": 550000,
    })
    assert "550,000" in out


def test_render_individual_class_emoji_lookup(renderer: Renderer):
    out = renderer.render({
        "type": "individual", "iri": "X",
        "class": "FeeCategory", "label": "Học phí",
    })
    assert out.startswith("💰 ")


def test_render_individual_unknown_class_no_emoji(renderer: Renderer):
    """A class without an emoji entry renders its title without any prefix —
    no fallback bullet, so the label stands clean."""
    out = renderer.render({
        "type": "individual", "iri": "X",
        "class": "SomeFutureClass", "label": "Something",
    })
    assert out.strip().startswith("Something")


# Listing

def test_render_listing(renderer: Renderer):
    out = renderer.render({
        "type": "listing", "class": "AcademicProcedure",
        "label": "Quy trình học vụ",
        "items": [
            {"type": "individual", "iri": "Q1",
             "class": "AcademicProcedure", "label": "Quy trình A"},
            {"type": "individual", "iri": "Q2",
             "class": "AcademicProcedure", "label": "Quy trình B"},
        ],
    })
    assert "📘 Quy trình học vụ" in out
    assert "• Quy trình A" in out and "• Quy trình B" in out


def test_render_blocks_dedupes_same_iri(renderer: Renderer):
    d = {"type": "individual", "iri": "X",
         "class": "AdministrativeOffice", "label": "Phòng X",
         "Email liên hệ": "x@y.vn"}
    out = renderer.render_blocks([d, d])
    assert out.count("x@y.vn") == 1


def test_render_blocks_separates_with_blank_line(renderer: Renderer):
    out = renderer.render_blocks([
        {"type": "individual", "iri": "A", "class": "FeeCategory", "label": "A"},
        {"type": "individual", "iri": "B", "class": "FeeCategory", "label": "B"},
    ])
    assert "\n\n" in out
