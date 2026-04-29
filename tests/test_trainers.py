"""Unit tests for custom HuggingFace Trainers."""

import pytest
import torch

from src.losses import AsymmetricLoss, ZLPRLoss
from src.trainers import AsymmetricTrainer, ZLPRTrainer
from src.trainers.base import BaseMultiLabelTrainer


class TestBaseMultiLabelTrainer:
    def test_is_subclass_of_trainer(self):
        from transformers import Trainer
        assert issubclass(BaseMultiLabelTrainer, Trainer)


class TestAsymmetricTrainer:
    def test_has_loss_fn(self):
        loss = AsymmetricLoss(gamma_pos=0, gamma_neg=4, clip=0.05)
        logits = torch.randn(4, 10)
        labels = torch.zeros(4, 10)
        labels[0, 0] = 1
        result = loss(logits, labels)
        assert torch.isfinite(result)


class TestZLPRTrainer:
    def test_has_loss_fn(self):
        loss = ZLPRLoss()
        logits = torch.randn(4, 10)
        labels = torch.zeros(4, 10)
        labels[0, 0] = 1
        result = loss(logits, labels)
        assert torch.isfinite(result)
