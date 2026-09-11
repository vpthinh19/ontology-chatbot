"""Dựng chỉ mục tìm kiếm của ontology và tìm thử bằng dòng lệnh.

    ontology_search build
    ontology_search search "điện thoại phòng đào tạo"
    ontology_search search "nghỉ học tạm thời" "bảo lưu" --json
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from ..settings import ONTOLOGY_PATH, SEARCH_INDEX_DIR


class ResponsePrinter:
    """In kết quả tìm kiếm cho người đọc."""

    def print(self, response) -> None:
        print(f"Từ khoá: {' · '.join(response.keywords)}")
        if not response.results:
            print("  → không có thông tin")
            return
        for rank, result in enumerate(response.results, 1):
            profile = result.profile
            print(f"\n[{rank}] {result.label}  ({', '.join(profile.classes)})  điểm {result.score:.2f}")
            for hit in result.matched[:3]:
                print(f"    khớp [{hit.entry.kind.value}] {hit.entry.text}  ({hit.score:.2f})")
            for sources, facts in profile.facts_by_source():
                heading = " · ".join(source.citation for source in sources) or "(không có nguồn)"
                print(f"    Nguồn: {heading}")
                for fact in facts:
                    print(f"      - {fact.subject_label} | {fact.property_label}: {self._short(fact.value)}")
            if profile.incoming:
                print("    Được trỏ tới bởi:")
                for relation in profile.incoming:
                    print(f"      - {relation.subject_label} | {relation.property_label}")

    @staticmethod
    def _short(text: str, limit: int = 160) -> str:
        text = " ".join(text.split())
        return text if len(text) <= limit else text[: limit - 1] + "…"


def build(arguments: argparse.Namespace) -> None:
    from ..search import IndexBuilder, Ontology, SearchIndex, TextAnalyzer, TurtleFileSource

    source = TurtleFileSource(arguments.ontology)
    started = time.perf_counter()
    ontology = Ontology.from_source(source)
    entries = IndexBuilder(ontology).build_entries()
    index = SearchIndex.build(entries, TextAnalyzer(), source.fingerprint())
    index.save(arguments.out)
    counts: dict[str, int] = {}
    for entry in entries:
        counts[entry.kind.value] = counts.get(entry.kind.value, 0) + 1
    elapsed = (time.perf_counter() - started) * 1000
    print(f"Đã dựng {len(entries)} dòng {counts} vào {arguments.out} trong {elapsed:.0f} ms")


def search(arguments: argparse.Namespace) -> None:
    from ..search import SearchEngine, TurtleFileSource

    index_directory = arguments.index if Path(arguments.index).exists() else None
    engine = SearchEngine.open(
        TurtleFileSource(arguments.ontology), index_directory=index_directory, top_k=arguments.top_k
    )
    response = engine.search(arguments.keywords)
    if arguments.json:
        print(json.dumps(response.to_dict(), ensure_ascii=False, indent=2))
    else:
        ResponsePrinter().print(response)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="ontology_search", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--ontology", type=Path, default=ONTOLOGY_PATH)
    commands = parser.add_subparsers(dest="command", required=True)

    build_command = commands.add_parser("build", help="dựng chỉ mục từ ontology và lưu ra thư mục")
    build_command.add_argument("--out", type=Path, default=SEARCH_INDEX_DIR)
    build_command.set_defaults(handler=build)

    search_command = commands.add_parser("search", help="tìm bằng một hoặc nhiều từ khoá")
    search_command.add_argument("keywords", nargs="+")
    search_command.add_argument(
        "--index", type=Path, default=SEARCH_INDEX_DIR, help="thư mục chỉ mục; không có thì dựng trong bộ nhớ"
    )
    search_command.add_argument("--top-k", type=int, default=3)
    search_command.add_argument("--json", action="store_true")
    search_command.set_defaults(handler=search)
    return parser.parse_args(argv)


def main() -> None:
    arguments = _parse_args()
    arguments.handler(arguments)


if __name__ == "__main__":
    main()
