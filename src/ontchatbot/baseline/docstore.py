"""Dựng KHO PHIẾU PHẲNG từ ontology cho baseline truy hồi.

Mỗi cá thể → MỘT phiếu, **id = IRI** (khớp ontology để chấm chung mức IRI). Nội dung là văn
xuôi tiếng Việt **trung thành tuyệt đối** với fact ontology (sinh chương-trình, không LLM → tái
lập được, không bịa): chỉ thông tin của CHÍNH cá thể (nhãn + alias + phân loại + giá trị data),
**loại bỏ mọi quan hệ** - đó chính là điểm yếu cấu trúc mà benchmark phơi ra. Phiếu fee chứa đủ
**facet** (mã khoá + tên/alias ngành) nên truy vấn lọc-giao có cơ hội công bằng (phẳng thua là do
thiếu suy luận, không phải lỗi dựng phiếu).
"""

from __future__ import annotations

import json

from ..config import RESOURCES
from ..ontology import Ontology, _ALIAS_PROP

# Artifact kho phẳng đã vật chất hoá (một dòng JSON mỗi cá thể) - ngang hàng với tệp ontology,
# sinh lại bằng ``scripts.build_flat_db`` mỗi khi ontology đổi.
FLAT_DB_PATH = RESOURCES / "baseline" / "flat_db.jsonl"


def _values(ind, prop) -> list[str]:
    return [str(v) for v in (getattr(ind, prop, []) or [])]


def _own_facts(ont: Ontology, ind) -> list[str]:
    """Các câu fact của CHÍNH cá thể (nhãn, alias, phân loại, giá trị data)."""
    label = ont._label_of(ind)
    parts = [f"{label}."]
    aliases = _values(ind, _ALIAS_PROP)
    if aliases:
        parts.append(f"Còn gọi là: {', '.join(aliases)}.")
    parts.append(f"Phân loại: {ont.class_label(ont._class_of(ind))}.")
    for prop in ont._data_props:
        if prop == _ALIAS_PROP:
            continue
        vals = _values(ind, prop)
        if vals:
            parts.append(f"{ont.property_label(prop)}: {', '.join(vals)}.")
    return parts


def build_corpus(ont: Ontology) -> dict[str, str]:
    """IRI → văn bản phiếu phẳng (fact của CHÍNH cá thể, loại bỏ mọi quan hệ)."""
    return {ind.name: " ".join(_own_facts(ont, ind)) for ind in ont._owl.individuals()}


def materialize(ont: Ontology, path=FLAT_DB_PATH) -> list[dict]:
    """Vật chất hoá kho phẳng từ ontology ra artifact JSONL (mỗi cá thể một dòng: id, class, text).

    Đây là bước "đập" ontology thành cơ sở dữ liệu phẳng: chạy lại mỗi khi ontology đổi để hai bên
    luôn khớp nội dung. Trả về danh sách bản ghi đã ghi."""
    records = [{"id": ind.name,
                "class": ont.class_label(ont._class_of(ind)),
                "text": " ".join(_own_facts(ont, ind))}
               for ind in ont._owl.individuals()]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in records), encoding="utf-8")
    return records


def load_flat_db(path=FLAT_DB_PATH) -> dict[str, str] | None:
    """Đọc artifact kho phẳng → IRI → văn bản. Thiếu artifact → ``None`` (nơi gọi tự dựng tạm)."""
    if not path.exists():
        return None
    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    return {r["id"]: r["text"] for r in rows}
