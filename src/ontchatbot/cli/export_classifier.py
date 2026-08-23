"""Xuất bộ phân loại đã huấn luyện sang ONNX để phục vụ không cần thư viện huấn luyện."""

from __future__ import annotations

import argparse
from pathlib import Path

from ..research.export_onnx import export


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--precision", choices=("fp16", "fp32"), default="fp16")
    return parser.parse_args(argv)


def main() -> None:
    args = _parse_args()

    target = export(args.model_dir, args.out, precision=args.precision)
    size = sum(path.stat().st_size for path in args.out.iterdir()) / 2**20
    print(f"đã xuất {target} ({size:.0f} MB)")


if __name__ == "__main__":
    main()
