"""Suy GOLD mức-IRI cho benchmark Phase 8 — KHÔNG vòng tròn.

Test set chỉ có **cây vàng** (đã qua oracle nghiêm `validate_dataset`), không lưu sẵn IRI đáp
án. Ở đây ta chạy chính cây vàng đó qua :meth:`Ontology.traverse` để vật-chất-hoá đáp án về
mức **tập IRI tài liệu liên quan** — đơn vị chung để so hệ ontology với hệ phẳng (id phiếu = IRI).

Vì sao không vòng tròn: cây vàng đã được oracle độc lập xác nhận đúng *trước* benchmark; traverse
chỉ đọc fact thô (không suy luận). Gold được **materialize ra file** (`gold.jsonl`) một lần để eval
đọc tĩnh, không tính-động bằng code đang-bị-đánh-giá (giảm tiếng "nội sinh", Codex review #3).

Đáp án quy về :class:`AnswerSpec`:
* ``node`` — truy vấn trả cá thể: ``iris`` = tập IRI node terminal.
* ``data`` — truy vấn trả giá trị: ``iris`` = IRI **chủ thể** mang giá trị (lấy từ ``trace`` —
  tập "before" của bước data đã khớp property); ``fields`` = các (property, giá trị).
* ``nonretrievable`` — greeting/ood/vague hoặc trượt hết: hệ phẳng không có khái niệm này.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..ontology import Ontology
from ..tree import DATA, QUERY, Tree


@dataclass(frozen=True)
class AnswerSpec:
    """Đáp án vật-chất-hoá mức IRI cho một truy vấn."""
    kind: str                       # node | data | nonretrievable
    iris: frozenset[str]            # tập tài liệu (IRI) liên quan = gold cho truy hồi
    fields: tuple                   # tuple[(prop, tuple[value])] — chỉ có ở kind=data (tầng đáp-án-cuối)


def answer_spec(tree: Tree, ont: Ontology) -> AnswerSpec:
    """Vật-chất-hoá đáp án của một cây (gold HOẶC predicted) về :class:`AnswerSpec`."""
    res = ont.traverse(tree)
    if tree.act != QUERY or res.vague:
        return AnswerSpec("nonretrievable", frozenset(), ())

    node_iris = {n.iri for n in res.nodes}
    # Chủ thể của lá data = các IRI trong "before" của bước DATA mà THỰC SỰ có assertion của
    # property đó (KHÔNG lấy nguyên before: `_present_index` coi prop là "present" nếu BẤT KỲ
    # IRI nào trong current có nó, nên before có thể chứa IRI không mang giá trị — Codex review #2).
    data_subjects: set[str] = set()
    for step in res.trace:
        if step.kind == DATA and step.resolved:
            prop = step.resolved[0]
            data_subjects.update(iri for iri in step.before
                                 if getattr(ont._owl[iri], prop, None))

    iris = frozenset(node_iris | data_subjects)
    fields = tuple((dv.prop, tuple(str(v) for v in dv.values)) for dv in res.values)

    if node_iris:
        kind = "node"
    elif res.values:
        kind = "data"
    else:
        kind = "nonretrievable"          # trượt hết (neg_child_miss…): không có tài liệu để truy hồi
    return AnswerSpec(kind=kind, iris=iris, fields=fields)
