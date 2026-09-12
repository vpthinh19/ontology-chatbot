"""Dòng chỉ mục: đơn vị nhỏ nhất đem đi tìm."""

from __future__ import annotations

from dataclasses import asdict, dataclass
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

    def to_dict(self) -> dict:
        """Dạng lưu tệp: bỏ trường rỗng."""

        payload = {key: value for key, value in asdict(self).items() if value is not None}
        payload["kind"] = self.kind.value
        return payload

    @classmethod
    def from_dict(cls, payload: dict) -> IndexEntry:
        return cls(
            kind=EntryKind(payload["kind"]),
            text=payload["text"],
            node=payload["node"],
            property=payload.get("property"),
            target=payload.get("target"),
        )
