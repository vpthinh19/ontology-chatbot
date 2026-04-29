"""Trainer using Asymmetric Loss."""

from __future__ import annotations

from ..losses import AsymmetricLoss
from .base import BaseMultiLabelTrainer


class AsymmetricTrainer(BaseMultiLabelTrainer):
    """Trainer using Asymmetric Loss (Ridnik et al., 2021)."""

    def __init__(
        self,
        *args,
        asl_gamma_pos: float = 0,
        asl_gamma_neg: float = 4,
        asl_clip: float = 0.05,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.loss_fn = AsymmetricLoss(
            gamma_pos=asl_gamma_pos,
            gamma_neg=asl_gamma_neg,
            clip=asl_clip,
        )
