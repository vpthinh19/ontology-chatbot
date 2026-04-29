"""Base Custom HuggingFace Trainer for multi-label classification."""

from __future__ import annotations

import torch.nn as nn
from transformers import Trainer


class BaseMultiLabelTrainer(Trainer):
    """Base trainer that computes loss via a pluggable ``loss_fn``."""

    loss_fn: nn.Module  # set by subclasses

    def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
        labels = inputs.pop("labels").float()
        outputs = model(**inputs)
        loss = self.loss_fn(outputs.logits, labels)
        return (loss, outputs) if return_outputs else loss
