"""Tìm thử trong ontology bằng dòng lệnh.

    ontology_search search "vị trí phòng đào tạo"
    ontology_search search "nghỉ học tạm thời" "bảo lưu" --json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..settings import ONTOLOGY_PATH


def _short(text: str, limit: int = 160) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def print_response(response) -> None:
    print(f"Từ khoá: {' · '.join(response.keywords)}")
    if not response.results:
        print("  → không có thông tin")
        return
    for rank, result in enumerate(response.results, 1):
        profile = result.profile
        print(f"\n[{rank}] {result.label}  ({', '.join(profile.classes)})  điểm {result.score:.2f}")
        for hit in result.matched[:3]:
            print(f"    khớp [{hit.entry.kind.value}] {hit.entry.text}  ({hit.score:.2f})")
        for source, facts in profile.groups:
            print(f"    Nguồn: {source.citation if source else '(không có nguồn)'}")
            for fact in facts:
                print(f"      - {fact.subject_label} | {fact.property_label}: {_short(fact.value)}")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="ontology_search", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--ontology", type=Path, default=ONTOLOGY_PATH)
    commands = parser.add_subparsers(dest="command", required=True)
    search = commands.add_parser("search", help="tìm bằng một hoặc nhiều từ khoá")
    search.add_argument("keywords", nargs="+")
    search.add_argument("--top-k", type=int, default=5)
    search.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    from ..search import SearchEngine, TriGFileSource

    arguments = _parse_args(argv)
    response = SearchEngine.open(TriGFileSource(arguments.ontology), top_k=arguments.top_k).search(arguments.keywords)
    if arguments.json:
        print(json.dumps(response.to_dict(), ensure_ascii=False, indent=2))
    else:
        print_response(response)


if __name__ == "__main__":
    main()
