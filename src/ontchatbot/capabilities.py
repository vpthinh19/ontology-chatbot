"""Phân nhóm NĂNG LỰC truy vấn — trục đánh giá chung của cả hệ.

Đề tài lấy quy trình học vụ làm trung tâm, nên việc đánh giá cũng đo theo *năng lực suy luận*
cần để trả lời, không theo miền dữ liệu (vd học phí). Mỗi loại câu hỏi trong tập dữ liệu được
quy về một nhóm năng lực; riêng các câu về học phí gộp chung vào nhóm "lọc theo ràng buộc" vì
chúng là phép thử cho năng-lực-lọc (giao/hợp), không phải một chủ đề riêng.

Trục này dùng chung cho cả khâu đánh giá mô hình (``scripts.evaluate``) lẫn khâu đối chứng với
cơ sở dữ liệu phẳng (``baseline``), để hai nơi cùng một khung tư duy về "đang đo năng lực gì".
"""

from __future__ import annotations

# Thứ tự trình bày theo độ khó tăng dần. (khoá, nhãn hiển thị).
GROUPS: list[tuple[str, str]] = [
    ("lookup",     "Tra cứu trực tiếp"),
    ("forward",    "Đi một quan hệ"),
    ("multihop",   "Đi nhiều bước"),
    ("multifield", "Nhiều thuộc tính"),
    ("filter",     "Lọc theo ràng buộc"),
]
GROUP_KEYS = [k for k, _ in GROUPS]
GROUP_LABEL = dict(GROUPS)

# Loại câu hỏi (category trong tập dữ liệu) → nhóm năng lực. Chỉ gồm các loại truy vấn;
# các loại phi-truy-vấn (vague/ood/greeting/neg_*) KHÔNG nằm đây nên ``group_of`` giữ nguyên tên.
_CAT2GROUP = {
    "self_desc": "lookup", "data_leaf": "lookup",
    "forward_object": "forward",
    "multi_hop": "multihop",
    "multi_field": "multifield",
    "fee_cohort": "filter", "fee_data": "filter", "fee_intersect": "filter",
    "fee_major": "filter", "fee_union": "filter",
}


def group_of(category: str) -> str:
    """Loại câu hỏi → nhóm năng lực; giữ nguyên nếu chưa map (để lộ loại phi-truy-vấn/loại lạ)."""
    return _CAT2GROUP.get(category, category)
