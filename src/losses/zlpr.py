"""ZLPR Loss for multi-label classification.

Ranking-based loss: positive labels must score above negatives.
Decomposes into two symmetric log-sum-exp terms.
No hyperparameters.

Reference:
    Su et al., "ZLPR: A Novel Loss for Multi-label Classification", 2022.
    https://arxiv.org/abs/2208.02955
"""

import torch
import torch.nn as nn


class ZLPRLoss(nn.Module):
    """Zero-shot Label-wise Positive-negative Ranking Loss.

    L = log(1 + sum_{i in pos} exp(-z_i)) + log(1 + sum_{j in neg} exp(z_j))

    Both terms use log-sum-exp trick for numerical stability.
    """

    def forward(self, logits: torch.Tensor, labels: torch.Tensor) -> torch.Tensor:
        """Compute ZLPR loss.

        Args:
            logits: Raw model outputs, shape (B, L).
            labels: Binary ground truth, shape (B, L).

        Returns:
            Scalar loss value.
        """
        pos_mask = labels.bool()
        zeros = torch.zeros(logits.size(0), dtype=logits.dtype, device=logits.device)

        # Positive term: log(1 + sum_{i in pos} exp(-z_i))
        pos_logits = (-logits).masked_fill(~pos_mask, float("-inf"))
        pos_term = torch.logaddexp(zeros, torch.logsumexp(pos_logits, dim=-1))

        # Negative term: log(1 + sum_{j in neg} exp(z_j))
        neg_logits = logits.masked_fill(pos_mask, float("-inf"))
        neg_term = torch.logaddexp(zeros, torch.logsumexp(neg_logits, dim=-1))

        return (pos_term + neg_term).mean()