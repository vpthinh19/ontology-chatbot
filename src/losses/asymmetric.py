"""Asymmetric Loss (ASL) for multi-label classification.

Treats positive and negative samples asymmetrically:
- Low gamma for positives  (preserve gradient signal)
- High gamma for negatives (suppress easy negatives)
- Probability shifting (clip) to further reduce negative contribution

Reference:
    Ridnik et al., "Asymmetric Loss For Multi-Label Classification", ICCV 2021.
    https://arxiv.org/abs/2009.14119
"""

import torch
import torch.nn as nn


class AsymmetricLoss(nn.Module):
    """Asymmetric Loss for multi-label classification.

    Args:
        gamma_pos: Focusing parameter for positive samples.
        gamma_neg: Focusing parameter for negative samples.
        clip: Hard threshold for probability shifting on negatives.
    """

    def __init__(
        self,
        gamma_pos: float = 0,
        gamma_neg: float = 4,
        clip: float = 0.05,
    ) -> None:
        super().__init__()
        self.gamma_pos = gamma_pos
        self.gamma_neg = gamma_neg
        self.clip = clip

    def forward(self, logits: torch.Tensor, labels: torch.Tensor) -> torch.Tensor:
        """Compute asymmetric loss.

        Args:
            logits: Raw model outputs, shape (B, L).
            labels: Binary ground truth, shape (B, L).

        Returns:
            Scalar loss value.
        """
        probs = torch.sigmoid(logits)

        # Positive term: -y * (1-p)^gamma_pos * log(p)
        pos_loss = labels * torch.log(probs.clamp(min=1e-8))
        if self.gamma_pos > 0:
            pos_loss = pos_loss * (1.0 - probs) ** self.gamma_pos

        # Negative term with probability shifting
        neg_probs = (probs - self.clip).clamp(min=0) if self.clip > 0 else probs
        neg_loss = (1.0 - labels) * torch.log((1.0 - neg_probs).clamp(min=1e-8))
        if self.gamma_neg > 0:
            neg_loss = neg_loss * neg_probs ** self.gamma_neg

        return -(pos_loss + neg_loss).mean()
