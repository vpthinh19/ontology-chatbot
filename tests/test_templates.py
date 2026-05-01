"""Tests for ``ontchatbot.data.templates``."""

from __future__ import annotations

import random

from ontchatbot.data.templates import (
    GREETINGS,
    OUT_OF_DOMAIN,
    TEMPLATES,
    perturb,
    strip_diacritics,
)


def test_every_class_has_templates():
    expected = {"QuyTrinhHocVu", "PhongBanHanhChinh", "TaiLieuBieuMau",
                "DinhMucHocPhi", "PhuongThucThanhToan"}
    assert set(TEMPLATES) == expected
    for tpls in TEMPLATES.values():
        assert tpls and all("{E}" in t for t in tpls)


def test_greetings_and_ood_non_empty():
    assert GREETINGS and OUT_OF_DOMAIN


def test_strip_diacritics_handles_d():
    assert strip_diacritics("Đại học") == "Dai hoc"


def test_perturb_deterministic():
    rng_a, rng_b = random.Random(0), random.Random(0)
    assert perturb("Quy trình bảo lưu", rng_a, p=0.5) == perturb("Quy trình bảo lưu", rng_b, p=0.5)
