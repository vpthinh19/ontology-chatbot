"""Integration tests: end-to-end mini pipeline."""

import pytest
import numpy as np
import torch
from datasets import load_dataset
from transformers import AutoTokenizer

from src.core.config import LABEL_MAP_PATH, TRAIN_DATASET_PATH
from src.utils.labels import build_mlb, load_label_names
from src.utils.preprocessing import preprocess_batch


class TestEndToEndPipeline:
    """Test the full data pipeline: load → preprocess → tokenize → dataset."""

    def test_pipeline_smoke(self):
        """Smoke test: run entire data pipeline on first 10 samples."""
        # 1. Load
        label_names = load_label_names(LABEL_MAP_PATH)
        mlb = build_mlb(label_names)
        
        ds = load_dataset("json", data_files={"train": TRAIN_DATASET_PATH}, split="train[:10]")

        assert len(ds) == 10

        # 2. Preprocess & Tokenize
        tokenizer = AutoTokenizer.from_pretrained("vinai/phobert-base-v2")

        def process_batch(examples):
            texts = preprocess_batch(examples["text"], word_segmentation=True)
            tokenized = tokenizer(
                texts,
                padding="max_length",
                truncation=True,
                max_length=64,
            )
            tokenized["labels"] = mlb.transform(examples["labels"]).astype(np.float32).tolist()
            return tokenized

        ds = ds.map(process_batch, batched=True, remove_columns=ds.column_names)
        ds.set_format("torch")

        assert "input_ids" in ds.column_names
        assert "labels" in ds.column_names
        
        assert len(ds) == 10
        item = ds[0]
        assert item["labels"].dtype == torch.float32
        assert item["labels"].shape[0] == len(label_names)
        assert item["input_ids"].shape[0] <= 64

    def test_label_consistency(self):
        """Verify that all labels in the dataset are valid label names."""
        label_names = load_label_names(LABEL_MAP_PATH)
        label_set = set(label_names)
        ds = load_dataset("json", data_files={"train": TRAIN_DATASET_PATH}, split="train")

        for i, sample_labels in enumerate(ds["labels"]):
            for label in sample_labels:
                assert label in label_set, (
                    f"Sample {i}: unknown label '{label}' not in label_map"
                )

    def test_no_empty_texts(self):
        """Verify no empty texts in the dataset."""
        ds = load_dataset("json", data_files={"train": TRAIN_DATASET_PATH}, split="train")
        for i, text in enumerate(ds["text"]):
            assert len(text.strip()) > 0, f"Sample {i}: empty text"

    def test_no_empty_labels(self):
        """Verify no samples without labels."""
        ds = load_dataset("json", data_files={"train": TRAIN_DATASET_PATH}, split="train")
        for i, sample_labels in enumerate(ds["labels"]):
            assert len(sample_labels) > 0, f"Sample {i}: no labels"
