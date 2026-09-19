"""Quản trị ontology: đọc lược đồ, thêm, sửa, xoá mục và ghi lại tệp TriG.

    shapes.ttl ─► Schema ─► form của trang quản trị
    yêu cầu sửa ─► AdminStore ─► bản mới trong bộ nhớ ─► kiểm SHACL ─► (Cloud Storage) ─► ghi ontology.trig
               ─► nạp lại engine
"""

from .schema import ClassSpec, Field, Schema
from .store import AdminError, AdminStore, Conflict, NotFound, Unavailable
from .trig import iri_name, serialize, write_bytes

__all__ = [
    "AdminError", "AdminStore", "ClassSpec", "Conflict", "Field", "NotFound", "Schema",
    "Unavailable", "iri_name", "serialize", "write_bytes",
]
