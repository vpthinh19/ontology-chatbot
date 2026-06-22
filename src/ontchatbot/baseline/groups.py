"""Re-export trục nhóm năng lực (đã chuyển về lõi ``ontchatbot.capabilities``).

Giữ tệp này để mã benchmark cũ (``benchmark.py``, ``figures.py``) import không đổi; nguồn đúng
của taxonomy nay ở :mod:`ontchatbot.capabilities` vì nó dùng chung cho cả đánh giá lẫn đối chứng.
"""

from __future__ import annotations

from ..capabilities import GROUP_KEYS, GROUP_LABEL, GROUPS, group_of  # noqa: F401

__all__ = ["GROUPS", "GROUP_KEYS", "GROUP_LABEL", "group_of"]
