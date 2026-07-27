"""Create concise, public reports for the canonical dataset and ontology."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from html import escape
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from rdflib import OWL, RDF, RDFS, Graph, URIRef

from ..runtime.sparql import load_ontology
from ..runtime.text import normalize_model_input
from ..settings import DATASET_DIR, ONTOLOGY_NS, ONTOLOGY_PATH, PROJECT_ROOT
from .dataset import REGISTER_ORDER, REQUIRED_SPLITS, load_release, validate_release
from .query_features import extract_query_features, query_feature_tags


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
    train_queries = {row["query_id"] for row in release["train"]}
    validation_queries = {row["query_id"] for row in release["val"]}
    test_queries = {row["query_id"] for row in release["test"]}
    object_properties = frozenset(
        str(subject).rsplit("#", 1)[-1]
        for subject in graph.subjects(RDF.type, OWL.ObjectProperty)
        if isinstance(subject, URIRef)
    )
    query_features_by_split = {
        split: _query_feature_counts(release[split], object_properties)
        for split in REQUIRED_SPLITS
    }

    report = {
        "dataset": {
            "records": len(all_rows),
            "queries": len({row["query_id"] for row in all_rows}),
            "targets": len({row["target"] for row in all_rows}),
            "splits": {
                split: {
                    "records": len(release[split]),
                    "queries": len({row["query_id"] for row in release[split]}),
                    "targets": len({row["target"] for row in release[split]}),
                }
                for split in REQUIRED_SPLITS
            },
            "registers": dict(sorted(Counter(row["register"] for row in all_rows).items())),
            "query_features": _query_feature_counts(all_rows, object_properties),
            "query_features_by_split": query_features_by_split,
            "input_words": _number_summary(word_lengths),
        },
        "in_domain_contract": {
            "train_queries": len(train_queries),
            "validation_queries_supported_by_train": len(
                validation_queries & train_queries
            ),
            "validation_queries": len(validation_queries),
            "test_queries_supported_by_train": len(test_queries & train_queries),
            "test_queries": len(test_queries),
        },
        "training_readiness": _build_training_readiness(release, validation),
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
    _write_bar_chart(
        figures / "registers.svg",
        "Phong cách câu hỏi",
        report["dataset"]["registers"],
        color="#7c3aed",
    )
    _write_grouped_bar_chart(
        figures / "query-features.svg",
        "Đặc trưng SPARQL theo train / validation / test",
        report["dataset"]["query_features_by_split"],
    )


def build_model_report(
    models_dir: Path,
    *,
    dataset_dir: Path = DATASET_DIR,
) -> dict[str, Any] | None:
    """Read independently reloaded model artifacts and their training logs."""

    names = ("bartpho", "vit5", "t5gemma2")
    release = load_release(dataset_dir)
    expected_records = {
        "validation": len(release["val"]),
        "benchmark": len(release["test"]),
    }
    dataset_manifest_sha256 = sha256_file(dataset_dir / "manifest.json")
    required_files = ("metrics.json", "validation_metrics.json", "benchmark_metrics.json")
    if not all(
        (models_dir / name / filename).is_file()
        for name in names
        for filename in required_files
    ):
        return None
    models = {}
    for name in names:
        directory = models_dir / name
        training_report = json.loads(
            (directory / "metrics.json").read_text(encoding="utf-8")
        )
        validation = json.loads(
            (directory / "validation_metrics.json").read_text(encoding="utf-8")
        )
        test = json.loads((directory / "benchmark_metrics.json").read_text(encoding="utf-8"))
        if not (
            _verified_artifact_evaluation(
                directory,
                name,
                validation,
                "validation",
                expected_records["validation"],
                dataset_manifest_sha256,
            )
            and _verified_artifact_evaluation(
                directory,
                name,
                test,
                "benchmark",
                expected_records["benchmark"],
                dataset_manifest_sha256,
            )
        ):
            return None
        training = training_report["training"]
        if training.get("dataset_manifest_sha256") != dataset_manifest_sha256:
            return None
        loss_curve = [
            {"epoch": item["epoch"], "value": item["loss"]}
            for item in training_report["training_log"]
            if "loss" in item and "epoch" in item
        ]
        validation_curve = [
            {"epoch": item["epoch"], "value": item["eval_answer_exact_rate"]}
            for item in training_report["training_log"]
            if "eval_answer_exact_rate" in item and "epoch" in item
        ]
        models[name] = {
            "model_id": training["model_id"],
            "validation": validation["overall"],
            "test": test["overall"],
            "test_by_register": test["by_register"],
            "test_by_query_feature": test["by_query_feature"],
            "test_errors": test["error_counts"],
            "training": {
                "records": training["train_records"],
                "runtime_seconds": training["train_runtime_seconds"],
                "peak_vram_bytes": training["peak_vram_bytes"],
                "epochs_completed": training.get(
                    "epochs_completed",
                    max(
                        point["epoch"]
                        for point in loss_curve + validation_curve
                    ),
                ),
                "artifact_roundtrip_verified": True,
            },
            "inference": validation.get("inference"),
            "curves": {"train_loss": loss_curve, "validation_answer_exact": validation_curve},
        }
    if len({model["test"]["count"] for model in models.values()}) != 1:
        return None
    return {
        "protocol": {
            "seed_runs_per_model": 1,
            "accuracy_batch_size": 1,
            "decoding": "greedy",
            "checkpoint_selection": "validation answer exact",
            "primary_metric": "execution answer exact",
            "test_records": next(iter(models.values()))["test"]["count"],
        },
        "models": models,
    }


def _verified_artifact_evaluation(
    directory: Path,
    model: str,
    report: Mapping[str, Any],
    suite: str,
    expected_records: int,
    dataset_manifest_sha256: str,
) -> bool:
    expected = {
        "backend": "transformers",
        "load_method": "from_pretrained",
        "model": model,
        "suite": suite,
        "dataset_manifest_sha256": dataset_manifest_sha256,
    }
    inference = report.get("inference", {})
    overall = report.get("overall", {})
    return (
        (directory / "model" / "config.json").is_file()
        and report.get("artifact_evaluation") == expected
        and inference.get("records") == overall.get("count")
        and overall.get("count") == expected_records
    )


def write_model_reports(report: Mapping[str, Any], *, output_dir: Path) -> None:
    figures = output_dir / "figures"
    figures.mkdir(parents=True, exist_ok=True)
    (output_dir / "models.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    models = report["models"]
    _write_line_chart(
        figures / "training-loss.svg",
        "Train loss theo epoch (thang log)",
        {name: value["curves"]["train_loss"] for name, value in models.items()},
        log_scale=True,
    )
    _write_line_chart(
        figures / "validation-curve.svg",
        "Validation answer exact theo epoch",
        {
            name: value["curves"]["validation_answer_exact"]
            for name, value in models.items()
        },
        percent=True,
    )
    _write_metric_chart(
        figures / "model-comparison.svg",
        "Chất lượng artifact trên validation và in-domain test",
        {
            name: {
                "validation answer exact": value["validation"]["answer_exact_rate"],
                "test answer exact": value["test"]["answer_exact_rate"],
                "test result F1": value["test"]["result_f1"],
            }
            for name, value in models.items()
        },
    )
    _write_metric_chart(
        figures / "test-by-register.svg",
        "Test answer exact theo phong cách câu hỏi",
        {
            name: {
                register: metrics["answer_exact_rate"]
                for register, metrics in value["test_by_register"].items()
            }
            for name, value in models.items()
        },
    )
    _write_metric_chart(
        figures / "test-by-query-feature.svg",
        "Test answer exact theo đặc trưng SPARQL",
        {
            name: {
                feature: metrics["answer_exact_rate"]
                for feature, metrics in value["test_by_query_feature"].items()
            }
            for name, value in models.items()
        },
    )


def write_manifest(report: Mapping[str, Any], path: Path) -> None:
    dataset = report["dataset"]
    manifest = {
        "schema": {
            "format": "jsonl",
            "fields": ["id", "query_id", "register", "input", "target"],
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
            "queries": dataset["queries"],
            "targets": dataset["targets"],
        },
        "split_contract": {
            "train": "model fitting over every supported canonical query",
            "val": "unseen wording for queries supported by train",
            "test": "unseen wording for queries supported by train",
            "query_catalogue_shared": True,
            "normalized_question_leakage": False,
            "near_duplicate_question_leakage": False,
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


def _query_feature_counts(
    rows: Iterable[Mapping[str, str]],
    object_properties: frozenset[str],
) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in rows:
        features = extract_query_features(
            row["target"],
            object_properties=object_properties,
        )
        counts.update(query_feature_tags(features))
    return dict(sorted(counts.items()))


def _build_training_readiness(
    release: Mapping[str, list[dict[str, str]]],
    validation: Mapping[str, Any],
) -> dict[str, Any]:
    gaps: list[dict[str, Any]] = []
    query_sets = {
        split: {row["query_id"] for row in release[split]}
        for split in REQUIRED_SPLITS
    }
    expected_queries = set().union(*query_sets.values())
    missing = {
        split: sorted(expected_queries - query_sets[split])
        for split in REQUIRED_SPLITS
        if expected_queries - query_sets[split]
    }
    if missing:
        gaps.append({"code": "queries_missing_from_split", "splits": missing})

    minimum_records = {
        "train": len(expected_queries) * 2,
        "val": len(expected_queries),
        "test": len(expected_queries),
    }
    short_splits = {
        split: {"records": len(release[split]), "minimum": minimum}
        for split, minimum in minimum_records.items()
        if len(release[split]) < minimum
    }
    if short_splits:
        gaps.append({"code": "insufficient_split_records", "splits": short_splits})

    imbalanced = {}
    for split in REQUIRED_SPLITS:
        counts = Counter(row["register"] for row in release[split])
        values = [counts.get(register, 0) for register in REGISTER_ORDER]
        if values and max(values) - min(values) > 1:
            imbalanced[split] = dict(sorted(counts.items()))
    if imbalanced:
        gaps.append({"code": "register_imbalance", "splits": imbalanced})

    empty_results = {
        split: report["empty_result_ids"]
        for split, report in validation["splits"].items()
        if report["empty_result_ids"]
    }
    if empty_results:
        gaps.append({"code": "empty_query_results", "splits": empty_results})

    return {"ready": not gaps, "gaps": gaps}


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
    width, height = max(980, len(categories) * 100 + 140), 420
    margin_left, margin_top, chart_width, chart_height = 80, 85, width - 130, 250
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


def _write_metric_chart(
    path: Path,
    title: str,
    groups: Mapping[str, Mapping[str, float]],
) -> None:
    colors = {"bartpho": "#2563eb", "vit5": "#f59e0b", "t5gemma2": "#10b981"}
    categories = sorted({name for values in groups.values() for name in values})
    width, height = max(1060, len(categories) * 100 + 140), 430
    margin_left, margin_top, chart_width, chart_height = 75, 90, width - 125, 250
    cluster_width = chart_width / len(categories)
    bar_width = cluster_width / (len(groups) + 1)
    parts = _svg_header(width, height, title)
    for group_index, (group, values) in enumerate(groups.items()):
        for category_index, category in enumerate(categories):
            value = values.get(category, 0.0)
            x = margin_left + category_index * cluster_width + (group_index + 0.5) * bar_width
            bar_height = chart_height * value
            y = margin_top + chart_height - bar_height
            parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_width - 4:.1f}" height="{bar_height:.1f}" rx="3" fill="{colors[group]}"/>')
            parts.append(f'<text x="{x + (bar_width - 4) / 2:.1f}" y="{y - 6:.1f}" text-anchor="middle" class="small">{value * 100:.1f}%</text>')
        legend_x = margin_left + group_index * 145
        parts.append(f'<rect x="{legend_x}" y="56" width="14" height="14" rx="2" fill="{colors[group]}"/>')
        parts.append(f'<text x="{legend_x + 21}" y="68" class="label">{escape(group)}</text>')
    for index, category in enumerate(categories):
        x = margin_left + (index + 0.5) * cluster_width
        parts.append(f'<text x="{x:.1f}" y="{margin_top + chart_height + 28}" text-anchor="middle" class="label">{escape(category.replace("_", " "))}</text>')
    parts.append(f'<line x1="{margin_left}" y1="{margin_top + chart_height}" x2="{margin_left + chart_width}" y2="{margin_top + chart_height}" class="axis"/>')
    parts.append("</svg>\n")
    path.write_text("".join(parts), encoding="utf-8")


def _write_line_chart(
    path: Path,
    title: str,
    series: Mapping[str, Sequence[Mapping[str, float]]],
    *,
    percent: bool = False,
    log_scale: bool = False,
) -> None:
    colors = {"bartpho": "#2563eb", "vit5": "#f59e0b", "t5gemma2": "#10b981"}
    width, height = 920, 430
    left, top, chart_width, chart_height = 78, 82, 790, 270
    transformed = {
        name: [
            (float(point["epoch"]), math.log10(max(float(point["value"]), 1e-6)) if log_scale else float(point["value"]))
            for point in points
        ]
        for name, points in series.items()
    }
    xs = [x for points in transformed.values() for x, _ in points]
    ys = [y for points in transformed.values() for _, y in points]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    if min_y == max_y:
        max_y += 1
    parts = _svg_header(width, height, title)
    for index in range(6):
        y = top + chart_height * index / 5
        value = max_y - (max_y - min_y) * index / 5
        label_value = 10**value if log_scale else value
        label = f"{label_value * 100:.0f}%" if percent else f"{label_value:.3g}"
        parts.append(f'<line x1="{left}" y1="{y:.1f}" x2="{left + chart_width}" y2="{y:.1f}" stroke="#e2e8f0"/>')
        parts.append(f'<text x="{left - 10}" y="{y + 4:.1f}" text-anchor="end" class="small">{label}</text>')
    for series_index, (name, points) in enumerate(transformed.items()):
        coordinates = []
        for x_value, y_value in points:
            x = left + chart_width * (x_value - min_x) / max(1e-9, max_x - min_x)
            y = top + chart_height * (max_y - y_value) / (max_y - min_y)
            coordinates.append(f"{x:.1f},{y:.1f}")
        parts.append(f'<polyline points="{" ".join(coordinates)}" fill="none" stroke="{colors[name]}" stroke-width="2.5"/>')
        legend_x = left + series_index * 145
        parts.append(f'<line x1="{legend_x}" y1="57" x2="{legend_x + 18}" y2="57" stroke="{colors[name]}" stroke-width="3"/>')
        parts.append(f'<text x="{legend_x + 25}" y="61" class="label">{escape(name)}</text>')
    parts.append(f'<line x1="{left}" y1="{top + chart_height}" x2="{left + chart_width}" y2="{top + chart_height}" class="axis"/>')
    parts.append(f'<text x="{left + chart_width / 2}" y="{top + chart_height + 40}" text-anchor="middle" class="label">epoch</text>')
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
    model_report = build_model_report(
        PROJECT_ROOT / "artifacts/models",
        dataset_dir=args.dataset_dir,
    )
    if model_report is not None:
        write_model_reports(model_report, output_dir=args.output_dir)
    print(
        json.dumps(
            {"dataset": report["dataset"], "models": model_report},
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
