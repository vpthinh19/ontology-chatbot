"""Huấn luyện các model phân loại và ghi kết quả để chấm và vẽ."""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from ..research.classifier import ALL_MODELS, BASELINE, ENCODERS, train_baseline, train_encoder
from ..research.labels import load_splits

DEFAULT_OUT = Path("artifacts/entity-linking")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", default="all",
                        help="all, hoặc danh sách ngăn bằng dấu phẩy: " + ", ".join(ALL_MODELS))
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--epochs", type=int, default=32)
    parser.add_argument("--batch", type=int, default=32)
    parser.add_argument("--lr", type=float, default=2e-4)
    parser.add_argument("--seed", type=int, default=1)
    args = parser.parse_args()

    tags = list(ALL_MODELS) if args.models == "all" else args.models.split(",")
    unknown = [t for t in tags if t not in ALL_MODELS]
    if unknown:
        parser.error(f"không biết model: {', '.join(unknown)}")

    args.out.mkdir(parents=True, exist_ok=True)
    rows, labels = load_splits()
    freq = Counter(r["y"] for r in rows["train"])
    rare = sum(1 for i in range(len(labels)) if freq.get(i, 0) < 5)
    print(f"{len(labels)} nhãn sau khi gộp khoản/điểm lên Điều "
          f"(dưới 5 mẫu huấn luyện: {rare})")
    print(f"train {len(rows['train'])} · val {len(rows['val'])} · test {len(rows['test'])}")

    for tag in tags:
        if tag == BASELINE:
            train_baseline(rows, labels, args.out, seed=args.seed)
        else:
            train_encoder(tag, rows, labels, args.out, epochs=args.epochs,
                          batch=args.batch, lr=args.lr, seed=args.seed)


if __name__ == "__main__":
    main()
