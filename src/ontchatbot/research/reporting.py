"""Create concise, public reports for the canonical dataset and ontology."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from collections import Counter
from html import escape
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from rdflib import OWL, RDF, RDFS, Graph, URIRef

from ..runtime.sparql import load_ontology
from ..runtime.text import normalize_model_input
from ..settings import DATASET_DIR, ONTOLOGY_NS, ONTOLOGY_PATH, PROJECT_ROOT
from .dataset import REQUIRED_SPLITS, load_release, validate_release


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_dataset_report(
    release: Mapping[str, list[dict[str, str]]],
    graph: Graph,
    *,
    dataset_dir: Path = DATASET_DIR,
    ontology_path: Path = ONTOLOGY_PATH,
) -> dict[str, Any]:
    """Summarize the data contract without exposing curation history."""

    validation = validate_release(dict(release), graph)
    all_rows = [row for split in REQUIRED_SPLITS for row in release[split]]
    word_lengths = [len(normalize_model_input(row["input"]).split()) for row in all_rows]
    train_targets = {row["target"] for row in release["train"]}
    test_targets = {row["target"] for row in release["test"]}
    train_terms = _local_target_terms(release["train"])
    test_terms = _local_target_terms(release["test"])

    report = {
        "dataset": {
            "records": len(all_rows),
            "families": len({row["family_id"] for row in all_rows}),
            "targets": len({row["target"] for row in all_rows}),
            "splits": {
                split: {
                    "records": len(release[split]),
                    "families": len({row["family_id"] for row in release[split]}),
                    "targets": len({row["target"] for row in release[split]}),
                }
                for split in REQUIRED_SPLITS
            },
            "registers": dict(sorted(Counter(row["register"] for row in all_rows).items())),
            "query_shapes": dict(
                sorted(Counter(row["query_shape"] for row in all_rows).items())
            ),
            "query_shapes_by_split": {
                split: dict(
                    sorted(Counter(row["query_shape"] for row in release[split]).items())
                )
                for split in REQUIRED_SPLITS
            },
            "input_words": _number_summary(word_lengths),
        },
        "generalization_contract": {
            "validation_targets_seen_in_train": len(
                {row["target"] for row in release["val"]} & train_targets
            ),
            "validation_targets": len({row["target"] for row in release["val"]}),
            "test_targets_seen_in_train": len(test_targets & train_targets),
            "test_targets": len(test_targets),
            "test_schema_terms_missing_from_train": sorted(test_terms - train_terms),
        },
        "ontology": _ontology_summary(graph),
        "validation": validation,
        "sha256": {
            **{
                f"{split}.jsonl": sha256_file(Path(dataset_dir) / f"{split}.jsonl")
                for split in REQUIRED_SPLITS
            },
            "ontology.ttl": sha256_file(ontology_path),
        },
    }
    return report


def write_public_reports(
    report: Mapping[str, Any],
    *,
    output_dir: Path,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    figures = output_dir / "figures"
    figures.mkdir(parents=True, exist_ok=True)
    (output_dir / "dataset.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    split_values = {
        split: report["dataset"]["splits"][split]["records"]
        for split in REQUIRED_SPLITS
    }
    _write_bar_chart(
        figures / "dataset-splits.svg",
        "Số câu hỏi theo tập dữ liệu",
        split_values,
        color="#2563eb",
    )
    _write_grouped_bar_chart(
        figures / "query-shapes.svg",
        "Dạng truy vấn theo train / validation / test",
        report["dataset"]["query_shapes_by_split"],
    )


def write_manifest(report: Mapping[str, Any], path: Path) -> None:
    dataset = report["dataset"]
    manifest = {
        "schema": {
            "format": "jsonl",
            "fields": ["id", "family_id", "register", "query_shape", "input", "target"],
            "input": "Vietnamese natural-language question",
            "target": "one-line canonical SPARQL SELECT without PREFIX declarations",
        },
        "files": {
            split: {
                "path": f"{split}.jsonl",
                **dataset["splits"][split],
                "sha256": report["sha256"][f"{split}.jsonl"],
            }
            for split in REQUIRED_SPLITS
        },
        "totals": {
            "records": dataset["records"],
            "families": dataset["families"],
            "targets": dataset["targets"],
        },
        "split_contract": {
            "train": "model fitting",
            "val": "unseen paraphrase families whose exact targets occur in train",
            "test": "held-out semantic targets composed only from schema terms present in train",
            "family_leakage": False,
            "normalized_question_leakage": False,
        },
        "normalization": "Unicode NFC, collapsed whitespace, conservative Vietnamese abbreviation expansion",
        "ontology": {
            "path": "../ontology/ontology.ttl",
            "sha256": report["sha256"]["ontology.ttl"],
        },
    }
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _ontology_summary(graph: Graph) -> dict[str, Any]:
    typed = {
        "classes": set(graph.subjects(RDF.type, OWL.Class)),
        "object_properties": set(graph.subjects(RDF.type, OWL.ObjectProperty)),
        "datatype_properties": set(graph.subjects(RDF.type, OWL.DatatypeProperty)),
        "named_individuals": set(graph.subjects(RDF.type, OWL.NamedIndividual)),
    }
    named_resources = set().union(*typed.values())
    local_resources = {
        node
        for node in named_resources
        if isinstance(node, URIRef) and str(node).startswith(ONTOLOGY_NS)
    }
    missing_vi = []
    for node in sorted(local_resources, key=str):
        labels = list(graph.objects(node, RDFS.label))
        if not any(getattr(label, "language", None) == "vi" for label in labels):
            missing_vi.append(str(node)[len(ONTOLOGY_NS) :])
    return {
        "triples": len(graph),
        **{name: len(nodes) for name, nodes in typed.items()},
        "resources_missing_vietnamese_label": missing_vi,
    }


def _local_target_terms(rows: Iterable[Mapping[str, str]]) -> set[str]:
    pattern = re.compile(r"(?<![A-Za-z0-9]):([A-Za-z][A-Za-z0-9]*)")
    return {match for row in rows for match in pattern.findall(row["target"])}


def _number_summary(values: Sequence[int]) -> dict[str, int | float]:
    ordered = sorted(values)
    return {
        "min": ordered[0],
        "median": ordered[len(ordered) // 2],
        "p95": ordered[max(0, math.ceil(len(ordered) * 0.95) - 1)],
        "max": ordered[-1],
        "mean": round(sum(ordered) / len(ordered), 2),
    }


def _write_bar_chart(path: Path, title: str, values: Mapping[str, int], *, color: str) -> None:
    width, height = 760, 330
    margin_left, margin_top, chart_width, chart_height = 90, 62, 620, 210
    maximum = max(values.values())
    bar_width = chart_width / max(1, len(values)) * 0.55
    parts = _svg_header(width, height, title)
    for index, (label, value) in enumerate(values.items()):
        x = margin_left + (index + 0.5) * chart_width / len(values) - bar_width / 2
        bar_height = chart_height * value / maximum
        y = margin_top + chart_height - bar_height
        parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_width:.1f}" height="{bar_height:.1f}" rx="4" fill="{color}"/>')
        parts.append(f'<text x="{x + bar_width / 2:.1f}" y="{y - 9:.1f}" text-anchor="middle" class="value">{value}</text>')
        parts.append(f'<text x="{x + bar_width / 2:.1f}" y="{margin_top + chart_height + 28}" text-anchor="middle" class="label">{escape(label)}</text>')
    parts.append(f'<line x1="{margin_left}" y1="{margin_top + chart_height}" x2="{margin_left + chart_width}" y2="{margin_top + chart_height}" class="axis"/>')
    parts.append("</svg>\n")
    path.write_text("".join(parts), encoding="utf-8")


def _write_grouped_bar_chart(path: Path, title: str, groups: Mapping[str, Mapping[str, int]]) -> None:
    colors = {"train": "#2563eb", "val": "#f59e0b", "test": "#10b981"}
    categories = sorted({name for values in groups.values() for name in values})
    width, height = 980, 420
    margin_left, margin_top, chart_width, chart_height = 80, 85, 850, 250
    maximum = max(value for values in groups.values() for value in values.values())
    cluster_width = chart_width / len(categories)
    bar_width = cluster_width / (len(groups) + 1)
    parts = _svg_header(width, height, title)
    for group_index, (group, values) in enumerate(groups.items()):
        for category_index, category in enumerate(categories):
            value = values.get(category, 0)
            x = margin_left + category_index * cluster_width + (group_index + 0.5) * bar_width
            bar_height = chart_height * value / maximum
            y = margin_top + chart_height - bar_height
            parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_width - 4:.1f}" height="{bar_height:.1f}" rx="3" fill="{colors[group]}"/>')
            if value:
                parts.append(f'<text x="{x + (bar_width - 4) / 2:.1f}" y="{y - 6:.1f}" text-anchor="middle" class="small">{value}</text>')
        legend_x = margin_left + group_index * 115
        parts.append(f'<rect x="{legend_x}" y="56" width="14" height="14" rx="2" fill="{colors[group]}"/>')
        parts.append(f'<text x="{legend_x + 21}" y="68" class="label">{escape(group)}</text>')
    for index, category in enumerate(categories):
        x = margin_left + (index + 0.5) * cluster_width
        label = category.replace("_", " ")
        parts.append(f'<text x="{x:.1f}" y="{margin_top + chart_height + 28}" text-anchor="middle" class="label">{escape(label)}</text>')
    parts.append(f'<line x1="{margin_left}" y1="{margin_top + chart_height}" x2="{margin_left + chart_width}" y2="{margin_top + chart_height}" class="axis"/>')
    parts.append("</svg>\n")
    path.write_text("".join(parts), encoding="utf-8")


def _svg_header(width: int, height: int, title: str) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{escape(title)}">',
        '<style>text{font-family:Inter,system-ui,sans-serif;fill:#172033}.title{font-size:21px;font-weight:700}.label{font-size:13px}.value{font-size:14px;font-weight:700}.small{font-size:11px;font-weight:600}.axis{stroke:#94a3b8;stroke-width:1}</style>',
        f'<rect width="{width}" height="{height}" fill="#ffffff"/>',
        f'<text x="{width / 2}" y="31" text-anchor="middle" class="title">{escape(title)}</text>',
    ]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-dir", type=Path, default=DATASET_DIR)
    parser.add_argument("--ontology", type=Path, default=ONTOLOGY_PATH)
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "reports")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    release = load_release(args.dataset_dir)
    report = build_dataset_report(
        release,
        load_ontology(args.ontology),
        dataset_dir=args.dataset_dir,
        ontology_path=args.ontology,
    )
    write_manifest(report, args.dataset_dir / "manifest.json")
    write_public_reports(report, output_dir=args.output_dir)
    print(json.dumps(report["dataset"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
