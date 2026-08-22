"""Xuất bộ phân loại đã huấn luyện sang ONNX để phục vụ không cần thư viện huấn luyện."""

from __future__ import annotations

import argparse
from pathlib import Path

from ..research.export_onnx import export


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    target = export(args.model_dir, args.out)
    size = target.stat().st_size / 2**20
    print(f"đã xuất {target} ({size:.0f} MB)")


if __name__ == "__main__":
    main()
