"""Shared test fixtures for PhoBERT pipeline tests."""

from __future__ import annotations

import json
import os
import tempfile

import pytest
import torch

from src.core.config import LABEL_MAP_PATH
from src.utils.labels import load_label_names


@pytest.fixture(scope="session")
def label_names() -> list[str]:
    """Load label names from the project's label_map.json."""
    return load_label_names(LABEL_MAP_PATH)


@pytest.fixture(scope="session")
def num_labels(label_names: list[str]) -> int:
    return len(label_names)


@pytest.fixture
def sample_texts() -> list[str]:
    """A few Vietnamese sample texts for testing."""
    return [
        "Em muốn đăng ký học phần kỳ này",
        "Cách nộp học phí online như thế nào?",
        "Xin chào admin, cho em hỏi về bảo lưu",
    ]


@pytest.fixture
def sample_labels() -> list[str]:
    """Single-class labels matching sample_texts (multiclass)."""
    return [
        "QuyTrinh_DangKyHocPhan",
        "QuyTrinh_NopHocPhi",
        "ChaoHoi",
    ]


@pytest.fixture
def tmp_dataset_file(sample_texts, sample_labels, tmp_path):
    """Create a temporary JSONL dataset file (multiclass schema)."""
    path = tmp_path / "test_data.jsonl"
    with open(path, "w", encoding="utf-8") as f:
        for text, label in zip(sample_texts, sample_labels):
            f.write(json.dumps({"text": text, "label": label}, ensure_ascii=False) + "\n")
    return str(path)


@pytest.fixture
def dummy_logits(num_labels) -> torch.Tensor:
    """Random logits tensor (5 samples)."""
    return torch.randn(5, num_labels)


@pytest.fixture
def dummy_labels() -> torch.Tensor:
    """Random multiclass labels tensor (5 samples)."""
    return torch.zeros(5, dtype=torch.long)
