"""Nhóm NĂNG LỰC truy vấn cho benchmark Phase 8 (chốt 2026-06-21).

Trục phân loại theo **năng lực suy luận** (hợp đề tài quy trình học vụ), KHÔNG theo miền học phí.
Mỗi category dataset gốc → một nhóm năng lực. Học phí (fee_*) gộp về MỘT nhóm "lọc theo ràng buộc"
vì nó là bộ thử cho năng-lực-lọc giao/hợp, không phải trọng tâm "tiền học phí".
"""

from __future__ import annotations

# Thứ tự trình bày: dễ → khó (gradient năng lực). (key, nhãn hiển thị).
GROUPS: list[tuple[str, str]] = [
    ("lookup",     "Tra cứu trực tiếp"),
    ("forward",    "Đi một quan hệ"),
    ("multihop",   "Đi nhiều bước"),
    ("multifield", "Nhiều thuộc tính"),
    ("filter",     "Lọc theo ràng buộc"),
]
GROUP_KEYS = [k for k, _ in GROUPS]
GROUP_LABEL = dict(GROUPS)

_CAT2GROUP = {
    "self_desc": "lookup", "data_leaf": "lookup",
    "forward_object": "forward",
    "multi_hop": "multihop",
    "multi_field": "multifield",
    "fee_cohort": "filter", "fee_data": "filter", "fee_intersect": "filter",
    "fee_major": "filter", "fee_union": "filter",
}


def group_of(category: str) -> str:
    """Category dataset → nhóm năng lực (giữ nguyên nếu chưa map, để lộ category lạ)."""
    return _CAT2GROUP.get(category, category)
