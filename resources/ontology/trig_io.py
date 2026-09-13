"""Đọc và ghi ontology.trig cho các script dữ liệu.

Trình ghi theo thứ tự cố định nằm trong ``ontchatbot.admin.trig``, cùng chỗ trang quản trị
dùng, nên script và trang quản trị ghi ra cùng một dạng tệp.
"""

from __future__ import annotations

from pathlib import Path

import pyoxigraph as oxi

from ontchatbot.admin.trig import load, write

TRIG = Path(__file__).with_name("ontology.trig")


def doc(duong_dan: Path = TRIG) -> oxi.Store:
    return load(duong_dan)


def ghi(store: oxi.Store, duong_dan: Path = TRIG) -> None:
    write(store, duong_dan)
