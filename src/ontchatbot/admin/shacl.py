"""Kiểm đồ thị bằng SHACL. pyshacl và rdflib chỉ được nạp ở lần kiểm đầu tiên."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pyoxigraph as oxi

from ..rdf import SH, local_id


@dataclass(frozen=True)
class Violation:
    focus: str
    #: IRI đầy đủ của thuộc tính bị vi phạm; rỗng khi không có.
    path: str
    value: str | None
    #: Tên cục bộ của ràng buộc, ví dụ ``MinCountConstraintComponent``.
    component: str
    message: str


class ShaclValidator:
    """Giữ đồ thị lược đồ của shapes.ttl giữa các lần kiểm; lược đồ mới thì đọc từ nội dung được đưa."""

    def __init__(self, shapes_path: Path) -> None:
        self.shapes_path = shapes_path
        self._shapes = None

    def shapes(self, turtle: bytes | None = None):
        """Đồ thị lược đồ: của ``turtle`` nếu có, không thì của tệp shapes.ttl (đọc một lần)."""

        from rdflib import Graph

        if turtle is not None:
            return Graph().parse(data=turtle.decode("utf-8"), format="turtle")
        if self._shapes is None:
            self._shapes = Graph().parse(self.shapes_path, format="turtle")
        return self._shapes

    def adopt(self, shapes) -> None:
        """Lược đồ vừa được ghi thành shapes.ttl."""

        self._shapes = shapes

    def forget(self) -> None:
        """shapes.ttl vừa được thay trên đĩa."""

        self._shapes = None

    @staticmethod
    def check(store: oxi.Store, shapes) -> list[Violation]:
        import pyshacl
        from rdflib import RDF, Graph, Namespace

        data = Graph().parse(data="".join(f"{q.subject} {q.predicate} {q.object} .\n" for q in store), format="nt")
        conforms, results, _ = pyshacl.validate(data, shacl_graph=shapes, inference="none")
        if conforms:
            return []
        sh = Namespace(SH)
        found = []
        for result in results.subjects(RDF.type, sh.ValidationResult):
            value = results.value(result, sh.value)
            found.append(Violation(
                focus=local_id(str(results.value(result, sh.focusNode))),
                path=str(results.value(result, sh.resultPath) or ""),
                value=local_id(str(value)) if value is not None else None,
                component=str(results.value(result, sh.sourceConstraintComponent)).rsplit("#", 1)[-1],
                message=str(results.value(result, sh.resultMessage)),
            ))
        return found
