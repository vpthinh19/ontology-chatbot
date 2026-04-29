"""Unit tests for data utilities."""

import pytest
from src.utils.labels import build_mlb, load_label_names
from src.core.config import LABEL_MAP_PATH


class TestLoadLabelNames:
    def test_loads_correct_count(self, label_names):
        assert len(label_names) == 19

    def test_returns_strings(self, label_names):
        assert all(isinstance(name, str) for name in label_names)

    def test_known_labels_present(self, label_names):
        assert "QuyTrinh_DangKyHocPhan" in label_names
        assert "ChaoHoi" in label_names
        assert "NgoaiLe" in label_names

    def test_order_preserved(self, label_names):
        assert label_names[0] == "QuyTrinh_BaoLuu"
        assert label_names[-1] == "NgoaiLe"


class TestBuildMlb:
    def test_binarization(self, label_names):
        mlb = build_mlb(label_names)
        result = mlb.transform([["ChaoHoi"]])
        assert result.shape == (1, len(label_names))
        assert result.sum() == 1

    def test_multi_label(self, label_names):
        mlb = build_mlb(label_names)
        result = mlb.transform([["ChaoHoi", "NgoaiLe"]])
        assert result.sum() == 2

    def test_empty_labels(self, label_names):
        mlb = build_mlb(label_names)
        result = mlb.transform([[]])
        assert result.sum() == 0
