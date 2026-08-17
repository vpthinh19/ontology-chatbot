"""Create concise, public reports for the canonical dataset and ontology."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from collections import Counter
from html import escape
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from rdflib import OWL, RDF, RDFS, Graph, URIRef

from ..runtime.text import normalize_model_input
from ..settings import (
    DATASET_DIR,
    ONTOLOGY_NS,
    ONTOLOGY_PATH,
    PROJECT_ROOT,
    QUERY_CATALOGUE_PATH,
    REPORTS_DIR,
    REJECTION_CHECKLIST_PATH,
)
from ..catalogue import load_catalogue
from .coverage import assess_coverage, load_coverage_requirements
from .dataset import (
    HELD_OUT_REGISTERS_PER_QUERY,
    HELD_OUT_ROWS_PER_QUERY,
    REGISTER_ORDER,
    REQUIRED_SPLITS,
    TRAIN_MIN_ROWS_PER_QUERY,
    load_release,
    validate_release,
)
from .query_features import extract_query_features, query_feature_tags
from .mentions import mention_index


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

    catalogue_path = QUERY_CATALOGUE_PATH
    catalogue = load_catalogue(catalogue_path)
    named_nodes = tuple(
        sorted(
            {
                value[1:]
                for spec in catalogue.values()
                if spec.tier == "primary" and spec.domain != "out-of-domain"
                for slot in spec.slots.values()
                if slot.kind == "iri"
                for value in slot.values
            }
        )
    )
    resolved_mentions, _ = mention_index(graph, named_nodes)
    validation = validate_release(
        dict(release),
        graph,
        catalogue,
        require_complete_catalogue=True,
    )
    coverage = assess_coverage(
        release,
        catalogue,
        load_coverage_requirements(Path(dataset_dir) / "coverage.json", catalogue),
        _load_rejection_checklist(dataset_dir),
        resolved_mentions,
    )
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
    in_domain_rows = [row for row in all_rows if catalogue[row["query_id"]].domain != "out-of-domain"]
    query_features_by_split = {
        split: _query_feature_counts(
            [
                row
                for row in release[split]
                if catalogue[row["query_id"]].domain != "out-of-domain"
            ],
            object_properties,
        )
        for split in REQUIRED_SPLITS
    }

    report = {
        "dataset": {
            "records": len(all_rows),
            "query_families": len({row["query_id"] for row in all_rows}),
            "catalogue_families": len(catalogue),
            "targets": len({row["target"] for row in all_rows}),
            "domains": validation["domains"],
            "splits": {
                split: {
                    "records": len(release[split]),
                    "query_families": len({row["query_id"] for row in release[split]}),
                    "targets": len({row["target"] for row in release[split]}),
                    "domains": validation["splits"][split]["domains"],
                }
                for split in REQUIRED_SPLITS
            },
            "registers": dict(sorted(Counter(row["register"] for row in all_rows).items())),
            "query_features": _query_feature_counts(in_domain_rows, object_properties),
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
        "coverage": coverage,
        "training_readiness": _build_training_readiness(release, validation, coverage),
        "ontology": _ontology_summary(graph),
        "validation": validation,
        "sha256": {
            **{
                f"{split}.jsonl": sha256_file(Path(dataset_dir) / f"{split}.jsonl")
                for split in REQUIRED_SPLITS
            },
            "catalogue.jsonl": sha256_file(catalogue_path),
            "coverage.json": sha256_file(Path(dataset_dir) / "coverage.json"),
            "ontology.ttl": sha256_file(ontology_path),
        },
    }
    return report


def _write_dataset_figures(
    report: Mapping[str, Any],
    *,
    output_dir: Path,
) -> None:
    figures = output_dir / "figures"
    figures.mkdir(parents=True, exist_ok=True)
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


def write_consistency_snapshot(
    snapshot: Any,
    *,
    paths: Any,
    reports_dir: Path,
) -> None:
    """Write only the derived artifacts represented by a validated snapshot."""

    write_json_report(snapshot.inventory, paths.inventory)
    write_json_report(snapshot.manifest, paths.manifest)
    write_json_report(snapshot.dataset_report, paths.dataset_report)
    write_json_report(snapshot.procedure_report, paths.procedure_report)
    write_json_report(snapshot.provenance, paths.provenance)
    _write_dataset_figures(snapshot.dataset_report, output_dir=reports_dir)


def build_model_report(
    models_dir: Path,
    *,
    dataset_dir: Path = DATASET_DIR,
) -> dict[str, Any] | None:
    """Read the locked three-model benchmark and its training logs."""

    names = ("bartpho", "vit5", "t5gemma2")
    release = load_release(dataset_dir)
    expected_records = {
        "validation": len(release["val"]),
        "benchmark": len(release["test"]),
    }
    dataset_manifest_sha256 = sha256_file(dataset_dir / "manifest.json")
    required_files = ("metrics.json", "benchmark_metrics.json")
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
        test = json.loads((directory / "benchmark_metrics.json").read_text(encoding="utf-8"))
        training = training_report["training"]
        validation = training_report
        if not _verified_locked_benchmark(
            directory,
            training_report,
            test,
            expected_records=expected_records,
            dataset_manifest_sha256=dataset_manifest_sha256,
        ):
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
                "merged_artifact": training.get("merged_artifact") is True,
            },
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


def _verified_locked_benchmark(
    directory: Path,
    training_report: Mapping[str, Any],
    benchmark_report: Mapping[str, Any],
    *,
    expected_records: Mapping[str, int],
    dataset_manifest_sha256: str,
) -> bool:
    training = training_report.get("training", {})
    return (
        (directory / "model" / "config.json").is_file()
        and training.get("dataset_manifest_sha256") == dataset_manifest_sha256
        and training.get("merged_artifact") is True
        and training_report.get("overall", {}).get("count")
        == expected_records["validation"]
        and benchmark_report.get("overall", {}).get("count")
        == expected_records["benchmark"]
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
        "Chất lượng ba mô hình trên validation và test",
        {
            name: {
                "validation answer exact": value["validation"]["answer_exact_rate"],
                "test answer exact": value["test"]["answer_exact_rate"],
                "test system exact": value["test"]["system_answer_exact_rate"],
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


def write_json_report(payload: Mapping[str, Any], path: Path) -> None:
    """Write a JSON report using the repository's deterministic format."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def build_manifest(
    report: Mapping[str, Any],
    *,
    manifest_path: Path,
    ontology_path: Path,
) -> dict[str, Any]:
    """Build a dataset manifest whose paths resolve from the manifest itself."""

    dataset = report["dataset"]
    ontology_relative = Path(
        os.path.relpath(
            Path(ontology_path).resolve(),
            start=Path(manifest_path).parent.resolve(),
        )
    ).as_posix()
    return {
        "schema": {
            "format": "jsonl",
            "fields": ["id", "query_id", "register", "input", "target"],
            "input": "Vietnamese natural-language question",
            "target": "one-line canonical SPARQL SELECT or the exact rejection marker",
        },
        "files": {
            split: {
                "path": f"{split}.jsonl",
                **dataset["splits"][split],
                "sha256": report["sha256"][f"{split}.jsonl"],
            }
            for split in REQUIRED_SPLITS
        },
        "catalogue": {
            "path": "catalogue.jsonl",
            "query_families": dataset["query_families"],
            "sha256": report["sha256"]["catalogue.jsonl"],
        },
        "coverage": {
            "path": "coverage.json",
            "sha256": report["sha256"]["coverage.json"],
        },
        "totals": {
            "records": dataset["records"],
            "query_families": dataset["query_families"],
            "targets": dataset["targets"],
            "domains": dataset["domains"],
        },
        "split_contract": {
            "train": "model fitting over every supported canonical query",
            "val": "unseen wording for queries supported by train",
            "test": "unseen wording for queries supported by train",
            "train_min_rows_per_query": TRAIN_MIN_ROWS_PER_QUERY,
            "train_registers_per_query": len(REGISTER_ORDER),
            "val_min_rows_per_query": HELD_OUT_ROWS_PER_QUERY,
            "test_min_rows_per_query": HELD_OUT_ROWS_PER_QUERY,
            "held_out_min_registers_per_query": HELD_OUT_REGISTERS_PER_QUERY,
            "catalogue_path": "catalogue.jsonl",
            "query_catalogue_shared": True,
            "normalized_question_leakage": False,
            "near_duplicate_question_leakage": False,
        },
        "normalization": "Unicode NFC, collapsed whitespace, conservative Vietnamese abbreviation expansion",
        "ontology": {
            "path": ontology_relative,
            "sha256": report["sha256"]["ontology.ttl"],
        },
    }


def build_procedure_dataset_report(
    release: Mapping[str, list[dict[str, str]]],
    *,
    dataset_dir: Path = DATASET_DIR,
) -> dict[str, Any]:
    """Derive the academic-procedure coverage report from release rows.

    Nhận diện họ quy trình bằng miền khai trong danh mục, không bằng tiền tố tên:
    tiền tố là một cách gọi có thể đổi, và lọc theo nó thì báo cáo công khai âm
    thầm bỏ sót phần lớn số đích thuộc trọng tâm của dự án.
    """

    catalogue = load_catalogue(QUERY_CATALOGUE_PATH)
    procedure_families = {
        query_id
        for query_id, spec in catalogue.items()
        if spec.domain == "procedure"
    }
    procedure_rows = {
        split: [row for row in release[split] if row["query_id"] in procedure_families]
        for split in REQUIRED_SPLITS
    }
    train_target_counts = Counter(row["target"] for row in procedure_rows["train"])
    # Họ secondary không thuộc hợp đồng huấn luyện; chỉ họ primary được yêu cầu.
    primary_procedure_families = {
        query_id
        for query_id in procedure_families
        if catalogue[query_id].tier == "primary"
    }
    taught_families = {row["query_id"] for row in procedure_rows["train"]}

    split_reports: dict[str, Any] = {}
    for split in REQUIRED_SPLITS:
        rows = procedure_rows[split]
        target_counts = Counter(row["target"] for row in rows)
        register_counts = Counter(
            len({row["register"] for row in rows if row["target"] == target})
            for target in target_counts
        )
        no_information_records = sum(
            row["query_id"] == "no-information" for row in release[split]
        )
        split_reports[split] = {
            "records": len(release[split]),
            "procedure_records": len(rows),
            "no_information_records": no_information_records,
            "procedure_to_no_information_ratio": round(
                len(rows) / no_information_records,
                6,
            ),
            "procedure_targets": len(target_counts),
            "samples_per_target_histogram": {
                str(count): frequency
                for count, frequency in sorted(Counter(target_counts.values()).items())
            },
            "registers_per_target_histogram": {
                str(count): frequency
                for count, frequency in sorted(register_counts.items())
            },
            "sha256": sha256_file(Path(dataset_dir) / f"{split}.jsonl"),
        }

    return {
        "scope": "academic-procedure",
        "procedure_target_count": len(train_target_counts),
        "procedure_family_count": len(procedure_families),
        "splits": split_reports,
        "contracts": {
            # Huấn luyện phủ mọi họ primary; mỗi họ dùng đủ các phong cách. Tập
            # giữ lại đo cách hỏi mới trên các neo đã được dạy.
            "every_primary_procedure_family_is_taught": taught_families
            >= primary_procedure_families,
            "every_procedure_family_has_all_four_registers": all(
                len(
                    {
                        row["register"]
                        for row in procedure_rows["train"]
                        if row["query_id"] == query_id
                    }
                )
                == len(REGISTER_ORDER)
                for query_id in taught_families
            ),
            # Mọi đích ở val/test phải xuất hiện trong train.
            "every_evaluated_target_was_taught": all(
                {row["target"] for row in procedure_rows[split]}
                <= set(train_target_counts)
                for split in ("val", "test")
            ),
            # Một shape lấy toàn bộ node qua biến predicate.
            "every_held_out_split_has_procedure_questions": all(
                bool(procedure_rows[split]) for split in ("val", "test")
            ),
        },
    }


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
    coverage: Mapping[str, object] | None = None,
) -> dict[str, Any]:
    gaps: list[dict[str, Any]] = []
    if validation.get("catalogue_coverage_required") is False:
        gaps.append({"code": "catalogue_not_fully_covered"})
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

    missing_slots = [
        {
            "query_id": query_id,
            "slot": slot,
            "values": details["missing_train"],
        }
        for query_id, slots in validation.get("slot_coverage", {}).items()
        for slot, details in slots.items()
        if details["missing_train"]
    ]
    if missing_slots:
        gaps.append({"code": "finite_slots_missing_from_train", "slots": missing_slots})

    if coverage is not None and coverage.get("complete") is False:
        gaps.append(
            {
                "code": "coverage_incomplete",
                **{
                    name: _coverage_gap_count(coverage.get(name))
                    for name in (
                        "missing_query_ids",
                        "missing_train_registers",
                        "missing_priority_registers",
                        "missing_numeric_cases",
                        "missing_rejection_coverage",
                        "name_coverage",
                    )
                },
            }
        )

    return {
        "ready": not gaps,
        "finite_slots_missing_from_train": missing_slots,
        "gaps": gaps,
    }


def _load_rejection_checklist(dataset_dir: Path) -> dict[str, list[str]]:
    return json.loads(REJECTION_CHECKLIST_PATH.read_text(encoding="utf-8"))


def _coverage_gap_count(value: object) -> int:
    if isinstance(value, Mapping):
        return sum(_coverage_gap_count(item) for item in value.values())
    if isinstance(value, list):
        return len(value)
    return 0


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
    parser.add_argument("--output-dir", type=Path, default=REPORTS_DIR)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    from .consistency import ArtifactPaths, build_consistency_snapshot

    paths = ArtifactPaths(
        inventory=args.ontology.parent / "answer_inventory.json",
        manifest=args.dataset_dir / "manifest.json",
        dataset_report=args.output_dir / "dataset.json",
        procedure_report=args.output_dir / "procedure-dataset.json",
        provenance=args.output_dir / "provenance.json",
    )
    snapshot = build_consistency_snapshot(
        dataset_dir=args.dataset_dir,
        ontology_path=args.ontology,
        paths=paths,
    )
    write_consistency_snapshot(snapshot, paths=paths, reports_dir=args.output_dir)
    model_report = build_model_report(
        PROJECT_ROOT / "artifacts/model-benchmark",
        dataset_dir=args.dataset_dir,
    )
    if model_report is not None:
        write_model_reports(model_report, output_dir=args.output_dir)
    print(
        json.dumps(
            {
                "dataset": snapshot.dataset_report["dataset"],
                "provenance": snapshot.provenance,
                "models": model_report,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
