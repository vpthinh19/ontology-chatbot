"""Đọc và ghi ontology.trig theo một thứ tự cố định.

Từ ngày 13/9/2026 tệp TriG là nguồn duy nhất và được sửa bằng script. Trước khi ghi,
các câu được sắp theo túi, chủ thể, thuộc tính rồi giá trị, nên đầu ra chỉ phụ thuộc
vào nội dung: sửa một câu thì git diff chỉ đổi đúng chỗ đó. rdflib và cả Store của
pyoxigraph đều xáo thứ tự sau mỗi lần nạp lại, nên không dùng trình ghi của chúng.
"""

from __future__ import annotations

from pathlib import Path

import pyoxigraph as oxi

TRIG = Path(__file__).with_name("ontology.trig")
TIEN_TO = {
    "": "http://www.ntu.edu.vn/ontology/academic#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "skos": "http://www.w3.org/2004/02/skos/core#",
    "xsd": "http://www.w3.org/2001/XMLSchema#",
}


def doc(duong_dan: Path = TRIG) -> oxi.Store:
    store = oxi.Store()
    store.load(path=str(duong_dan), format=oxi.RdfFormat.TRIG)
    return store


def _khoa(quad: oxi.Quad) -> tuple[str, str, str, str]:
    tui = "" if isinstance(quad.graph_name, oxi.DefaultGraph) else str(quad.graph_name)
    return tui, str(quad.subject), str(quad.predicate), str(quad.object)


def ghi(store: oxi.Store, duong_dan: Path = TRIG) -> None:
    duong_dan.write_bytes(
        oxi.serialize(sorted(store, key=_khoa), format=oxi.RdfFormat.TRIG, prefixes=TIEN_TO)
    )
