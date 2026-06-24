"""Vật chất hoá CƠ SỞ DỮ LIỆU PHẲNG từ ontology (cho đối chứng).

    uv run --extra inference python -m ontchatbot.scripts.build_flat_db

Đọc ontology rồi "đập" mỗi cá thể thành một phiếu văn bản phẳng - gộp nhãn, tên gọi khác, phân
loại và các giá trị thuộc tính, đồng thời LOẠI BỎ mọi quan hệ - ghi ra artifact
``resources/baseline/flat_db.jsonl`` (mỗi dòng một cá thể). Artifact này là comparand ngang hàng
với tệp ontology; vì ontology còn được chỉnh sửa, hãy chạy lại lệnh này mỗi khi ontology đổi để
kho phẳng luôn khớp nội dung. Khâu đối chứng (``baseline.benchmark``) nạp thẳng artifact này.
"""
from __future__ import annotations

import sys

from ..baseline.docstore import FLAT_DB_PATH, materialize
from ..ontology import Ontology


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ont = Ontology()
    records = materialize(ont)
    print(f"[build_flat_db] {len(records)} phiếu phẳng → {FLAT_DB_PATH}")


if __name__ == "__main__":
    main()
