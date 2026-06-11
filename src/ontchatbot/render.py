"""Render ``Fact[]`` → a Vietnamese chat reply.

One small template per fact *shape* (listing / self-set / relation / reason /
compare). Because the answer layer already produced edge-correct facts, the
renderer never reaches into the ontology — it only formats nodes, so it has no
owlready2 dependency and tests run on plain dataclasses.

Greeting / out-of-domain are policy, not data: an empty fact list with a
``GREETING`` intent greets; an empty list otherwise apologises with scope.
There is no keyword regex — the intent already decided.
"""

from __future__ import annotations

from .answer import Fact
from .graph import Node
from .nlu import GREETING, Query
from .text import is_url

GREETING_REPLY = (
    "Xin chào! Mình có thể tra cứu giúp bạn về quy trình học vụ, phòng ban "
    "hành chính, định mức học phí, biểu mẫu hoặc phương thức thanh toán. "
    "Bạn cần hỏi gì ạ?"
)
OUT_OF_DOMAIN_REPLY = (
    "Câu hỏi của bạn nằm ngoài phạm vi tri thức hiện có. Hãy thử hỏi về quy "
    "trình học vụ, phòng ban hành chính, học phí, biểu mẫu hoặc phương thức "
    "thanh toán."
)

# Data-property local name → header, in display order. Unlisted props are
# appended in declaration order, so a new property in Protégé still shows.
_DATA_LABEL: dict[str, str] = {
    "procedureDescription": "Mô tả",
    "feeNote": "Lưu ý",
    "feePerCredit": "Học phí mỗi tín chỉ",
    "appliesToTarget": "Áp dụng cho",
    "headOfOffice": "Phụ trách",
    "officeLocation": "Địa chỉ",
    "officeEmail": "Email",
    "officePhoneNumber": "Điện thoại",
    "officeWebsite": "Website",
    "formUrl": "Tải biểu mẫu",
}
_DATA_ORDER = list(_DATA_LABEL)

_CLASS_LABEL: dict[str, str] = {
    "AcademicProcedure": "quy trình học vụ",
    "AdministrativeOffice": "phòng ban hành chính",
    "Document": "biểu mẫu",
    "FeeCategory": "định mức học phí",
    "PaymentMethod": "phương thức thanh toán",
    "Condition": "điều kiện",
    "OutputResult": "kết quả",
    "Regulation": "quy định",
}


def render_reply(query: Query, facts: list[Fact]) -> str:
    """Final reply policy: facts win; else greeting vs out-of-domain by intent."""
    if not facts:
        return GREETING_REPLY if query.intent == GREETING else OUT_OF_DOMAIN_REPLY
    blocks = [b for b in (_render_fact(f) for f in facts) if b]
    if not blocks:
        return OUT_OF_DOMAIN_REPLY
    return "\n---\n".join(blocks)


def _render_fact(f: Fact) -> str:
    if f.intent == "ELIGIBILITY":
        return _render_reason(f)
    if f.intent == "COMPARE":
        return _render_compare(f)
    if f.cls and f.subject is None and f.predicate == "":
        return _render_listing(f)
    if f.subject is None:                      # self-set: anchors' own data
        return "\n\n".join(_render_node(n) for n in f.objects)
    return _render_relation(f)                 # walked relation


def _render_listing(f: Fact) -> str:
    head = f"Các {_CLASS_LABEL.get(f.cls, 'mục')} hiện có:"
    return "\n".join([head, *(f"• {n.label}" for n in f.objects)])


def _render_relation(f: Fact) -> str:
    """``<anchor> — <predicate>:`` then each walked target."""
    subj = f.subject.label if f.subject else ""
    if not f.objects:
        return f"{subj}\nHiện chưa có dữ liệu cho \"{f.predicate.lower()}\"."
    head = f"{subj} — {f.predicate}:"
    items = [_render_node(n, bullet="•") for n in f.objects]
    # Compact (label-only) targets stay tight; rich ones breathe.
    sep = "\n\n" if any("\n" in it for it in items) else "\n"
    return head + "\n" + sep.join(items)


def _render_reason(f: Fact) -> str:
    lines = [f"{f.subject.label if f.subject else ''} — {f.note}:"]
    for n in f.objects:
        lines.append(f"• {n.label}")
    if not f.objects:
        lines.append("• (chưa có điều kiện nào được khai báo)")
    return "\n".join(lines)


def _render_compare(f: Fact) -> str:
    lines = ["So sánh:"]
    for n in f.objects:
        lines.append(_render_node(n, bullet="•"))
    return "\n".join(lines)


def _render_node(node: Node, *, bullet: str = "") -> str:
    """Label + its data fields (ordered). ``bullet`` prefixes the label when
    the node is a list item under a header."""
    head = f"{bullet} {node.label}".strip() if bullet else node.label
    lines = [head]
    for key in _ordered_keys(node.data):
        value = node.data[key]
        if value in (None, "", []):
            continue
        lines.append("    " + _format_field(key, value))
    return "\n".join(lines)


def _ordered_keys(data: dict) -> list[str]:
    known = [k for k in _DATA_ORDER if k in data]
    rest = [k for k in data if k not in _DATA_LABEL]
    return known + rest


def _format_field(key: str, value) -> str:
    header = _DATA_LABEL.get(key, key)
    if key == "feePerCredit" and isinstance(value, (int, float)):
        return f"- {header}: {int(value):,} đ/tín chỉ".replace(",", ".")
    if isinstance(value, list):
        return f"- {header}: " + ", ".join(_scalar(v) for v in value)
    if is_url(value):
        return f"- {header}: [{header}]({_safe_url(value)})"
    return f"- {header}: {_scalar(value)}"


def _scalar(v) -> str:
    if isinstance(v, bool):
        return "Có" if v else "Không"
    if isinstance(v, int):
        return f"{v:,}".replace(",", ".")
    return str(v)


def _safe_url(url: str) -> str:
    return url.replace("(", "%28").replace(")", "%29")
