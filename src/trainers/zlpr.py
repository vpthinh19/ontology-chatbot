"""Trainer using ZLPR Loss."""

from __future__ import annotations

from ..losses import ZLPRLoss
from .base import BaseMultiLabelTrainer


class ZLPRTrainer(BaseMultiLabelTrainer):
    """Trainer using ZLPR Loss (Su et al., 2022). No hyperparameters."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.loss_fn = ZLPRLoss()
