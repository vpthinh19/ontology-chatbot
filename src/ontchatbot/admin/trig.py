"""Đọc và ghi ontology.trig theo một thứ tự cố định.

Trước khi ghi, các câu được sắp theo túi, chủ ngữ, thuộc tính rồi giá trị, nên đầu ra chỉ
phụ thuộc vào nội dung: sửa một câu thì git diff chỉ đổi đúng chỗ đó. Trình ghi mặc định
của thư viện xáo thứ tự sau mỗi lần nạp lại, nên không dùng.
"""

from __future__ import annotations

import os
import re
import tempfile
import unicodedata
from pathlib import Path

import pyoxigraph as oxi

from ..rdf import RDFS, SKOS, XSD
from ..settings import ONTOLOGY_NS

PREFIXES = {"": ONTOLOGY_NS, "rdfs": RDFS, "skos": SKOS, "xsd": XSD}


def _order(quad: oxi.Quad) -> tuple[str, str, str, str]:
    bag = "" if isinstance(quad.graph_name, oxi.DefaultGraph) else str(quad.graph_name)
    return bag, str(quad.subject), str(quad.predicate), str(quad.object)


def serialize(store: oxi.Store) -> bytes:
    """Nội dung TriG theo thứ tự cố định: cùng một đồ thị luôn ra cùng một chuỗi byte."""

    return oxi.serialize(sorted(store, key=_order), format=oxi.RdfFormat.TRIG, prefixes=PREFIXES)


def write_bytes(data: bytes, path: Path | str) -> None:
    """Ghi qua tệp tạm rồi thay tên, để một lần ghi hỏng giữa chừng không để lại tệp dở."""

    path = Path(path)
    handle, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(handle, "wb") as file:
            file.write(data)
        if path.exists():
            os.chmod(temporary, path.stat().st_mode & 0o777)
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def iri_name(label: str) -> str:
    """Tên cục bộ của IRI sinh từ nhãn: bỏ dấu, viết hoa chữ đầu mỗi từ, nối liền.

    "Thủ tục nghỉ học tạm thời" thành ``ThuTucNghiHocTamThoi``.
    """

    text = label.replace("đ", "d").replace("Đ", "D")
    text = "".join(c for c in unicodedata.normalize("NFD", text) if not unicodedata.combining(c))
    return "".join(word if word.isdigit() else word[:1].upper() + word[1:].lower()
                   for word in re.findall(r"[A-Za-z0-9]+", text))
