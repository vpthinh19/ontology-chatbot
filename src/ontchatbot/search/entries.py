"""Dòng chỉ mục: đơn vị nhỏ nhất đem đi tìm."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class EntryKind(str, Enum):
    LABEL = "label"
    DATATYPE_PROPERTY = "datatype_property"
    OBJECT_PROPERTY = "object_property"


@dataclass(frozen=True)
class IndexEntry:
    """Một dòng chữ trỏ về một thực thể. IRI viết gọn dạng ``:TenCucBo``."""

    kind: EntryKind
    text: str
    node: str
    property: str | None = None
    target: str | None = None
