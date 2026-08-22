"""Chấm điểm các model phân loại đã huấn luyện và dựng hình."""

from __future__ import annotations

import argparse
from pathlib import Path

from ..research.classifier_report import figures, report

DEFAULT_OUT = Path("artifacts/entity-linking")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--split", default="test", choices=("val", "test"))
    parser.add_argument("--no-figures", action="store_true")
    args = parser.parse_args()

    report(args.out, args.split)
    if not args.no_figures:
        figures(args.out, args.split)


if __name__ == "__main__":
    main()
