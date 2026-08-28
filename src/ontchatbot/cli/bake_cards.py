"""Dựng sẵn bảng thẻ, để container không phải dựng lại ở mỗi lần khởi động."""

from __future__ import annotations

import argparse
from pathlib import Path

from ..runtime.cards import bake_cards
from ..settings import CARD_CACHE_PATH, ONTOLOGY_PATH, QUERY_CATALOGUE_PATH


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=CARD_CACHE_PATH)
    parser.add_argument("--ontology", type=Path, default=ONTOLOGY_PATH)
    parser.add_argument("--catalogue", type=Path, default=QUERY_CATALOGUE_PATH)
    args = parser.parse_args(argv)

    cards = bake_cards(
        args.out, ontology_path=args.ontology, catalogue_path=args.catalogue
    )
    print(
        f"bảng thẻ dựng sẵn: {args.out}, {len(cards)} thẻ, "
        f"{args.out.stat().st_size / 1e6:.2f} MB, đọc lại giống hệt"
    )


if __name__ == "__main__":
    main()
