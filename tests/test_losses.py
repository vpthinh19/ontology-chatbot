"""Unit tests for custom loss functions."""

import pytest
import torch

from src.losses import AsymmetricLoss, ZLPRLoss


@pytest.fixture
def batch_data():
    """Returns (logits, labels) tensors."""
    logits = torch.randn(8, 15, requires_grad=True)
    labels = torch.zeros(8, 15)
    # Set some positive labels
    labels[0, 0] = 1
    labels[1, 1] = 1
    labels[2, [0, 2]] = 1
    labels[3, [3, 4, 5]] = 1
    return logits, labels



class TestAsymmetricLoss:
    def test_output_scalar(self, batch_data):
        logits, labels = batch_data
        loss = AsymmetricLoss()(logits, labels)
        assert loss.ndim == 0

    def test_non_negative(self, batch_data):
        logits, labels = batch_data
        loss = AsymmetricLoss()(logits, labels)
        assert loss.item() >= 0

    def test_gradient_flows(self, batch_data):
        logits, labels = batch_data
        loss = AsymmetricLoss()(logits, labels)
        loss.backward()
        assert logits.grad is not None

    def test_custom_params(self, batch_data):
        logits, labels = batch_data
        loss = AsymmetricLoss(gamma_pos=1, gamma_neg=3, clip=0.1)(logits, labels)
        assert loss.item() >= 0

    def test_no_clip(self, batch_data):
        logits, labels = batch_data
        loss = AsymmetricLoss(clip=0)(logits, labels)
        assert torch.isfinite(loss)


class TestZLPRLoss:
    def test_output_scalar(self, batch_data):
        logits, labels = batch_data
        loss = ZLPRLoss()(logits, labels)
        assert loss.ndim == 0

    def test_non_negative(self, batch_data):
        logits, labels = batch_data
        loss = ZLPRLoss()(logits, labels)
        assert loss.item() >= 0

    def test_gradient_flows(self, batch_data):
        logits, labels = batch_data
        loss = ZLPRLoss()(logits, labels)
        loss.backward()
        assert logits.grad is not None

    def test_single_sample(self):
        logits = torch.randn(1, 10, requires_grad=True)
        labels = torch.zeros(1, 10)
        labels[0, 0] = 1
        loss = ZLPRLoss()(logits, labels)
        assert torch.isfinite(loss)
        loss.backward()
        assert logits.grad is not None
