"""Sinh lại ba tập dữ liệu từ ontology, danh mục truy vấn và khung câu hỏi.

Chuỗi đầy đủ, chạy theo đúng thứ tự này:

1. ``python -m ontchatbot.research.inventory``      - danh sách đường đi trả lời được
2. ``python -m ontchatbot.research.build_catalogue`` - danh mục truy vấn
3. ``generate_sparql_dataset``                       - lệnh này
4. ``generate_reports``                              - manifest và báo cáo công khai
5. ``validate_sparql_dataset``                       - kiểm toàn chuỗi

Trước đợt này bước 3 chỉ chạy được bằng cách gõ tay trong trình thông dịch, nên
dataset không tái lập được từ đầu - và một artifact không dựng lại được thì không
kiểm chứng được.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from rdflib import Graph, URIRef

from ..catalogue import load_catalogue
from ..research.compose import load_frames
from ..research.generate_dataset import (
    build_bindings,
    executable_bindings,
    generate,
    split_safe_order,
    write_splits,
)
from ..research.mentions import mention_index, overloaded_mentions
from ..runtime.sparql import load_ontology
from ..settings import (
    DATASET_DIR,
    ONTOLOGY_NS,
    QUERY_CATALOGUE_PATH,
)

REJECTION_CHECKLIST_PATH = Path("resources/cases/rejection_checklist.json")


def _numbers(graph: Graph) -> tuple[tuple[str, ...], tuple[tuple[str, str], ...]]:
    """Số hiệu điều và khoản, suy thẳng từ ontology.

    Hai họ này ràng buộc theo SỐ chứ không theo IRI, nên danh sách giá trị không
    nằm trong danh mục - lấy sai là sinh ra truy vấn rỗng ruột.
    """

    article_of = URIRef(ONTOLOGY_NS + "articleNumber")
    clause_of = URIRef(ONTOLOGY_NS + "clauseNumber")
    articles = {str(value) for value in graph.objects(None, article_of)}
    clauses = {
        (str(next(graph.objects(node, article_of))), str(clause))
        for node, clause in graph.subject_objects(clause_of)
        if next(graph.objects(node, article_of), None) is not None
    }
    return tuple(sorted(articles, key=int)), tuple(sorted(clauses))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DATASET_DIR)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    graph = load_ontology()
    catalogue = load_catalogue(QUERY_CATALOGUE_PATH)
    declared = load_frames(DATASET_DIR / "frames.jsonl", catalogue)
    templates = {
        payload["class"]: tuple(payload["templates"])
        for payload in (
            json.loads(line)
            for line in (DATASET_DIR / "rejections.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
            if line.strip()
        )
    }
    requirements = json.loads(
        (DATASET_DIR / "coverage.json").read_text(encoding="utf-8")
    )

    anchors = tuple(
        sorted(
            {
                value[1:]
                for spec in catalogue.values()
                for slot in spec.slots.values()
                if slot.kind == "iri"
                for value in slot.values
            }
        )
    )
    resolved, _ = mention_index(graph, anchors)
    overloaded = overloaded_mentions(graph, anchors)

    # Xếp lại NGAY khi nạp: khung gần trùng nhau phải nằm cùng một tập, nếu không
    # validator đỏ ở tận cuối chuỗi với thông báo về hai dòng dataset, không nhắc
    # gì tới khung. Người soạn khung không phải nhớ luật này.
    #
    # Ước lượng bằng tên DÀI NHẤT của chính họ đó: độ giống tăng theo độ dài phần
    # chung, dùng tên ngắn hơn thực tế sẽ báo an toàn nhầm.
    def longest_anchor(query_id: str) -> str | None:
        slot = catalogue[query_id].slots.get("anchor")
        if slot is None:
            return None
        texts = [
            text for value in slot.values for text in resolved.get(value[1:], ())
        ]
        return max(texts, key=len) if texts else None

    frames = {
        query_id: split_safe_order(items, longest_anchor(query_id))
        for query_id, items in declared.items()
    }

    articles, clauses = _numbers(graph)
    bindings = executable_bindings(
        graph,
        catalogue,
        build_bindings(
            catalogue, frames, requirements["numeric_cases"], articles, clauses
        ),
    )

    splits, checklist = generate(
        graph,
        catalogue,
        frames,
        resolved,
        overloaded,
        bindings,
        templates,
        seed=args.seed,
    )
    write_splits(splits, args.output_dir)
    REJECTION_CHECKLIST_PATH.write_text(
        json.dumps(checklist, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    total = sum(len(rows) for rows in splits.values())
    rejections = sum(
        1 for rows in splits.values() for row in rows if row.query_id == "no-information"
    )
    print(
        f"{total} dòng ("
        + ", ".join(f"{name} {len(rows)}" for name, rows in splits.items())
        + f"); {rejections} câu từ chối; "
        f"{len({row.target for rows in splits.values() for row in rows})} đích khác nhau"
    )


if __name__ == "__main__":
    main()
