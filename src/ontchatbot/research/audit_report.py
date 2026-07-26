"""Human-readable and file outputs for dataset audits."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from .dataset import REQUIRED_SPLITS


def render_markdown(report: Mapping[str, Any]) -> str:
    """Render the compact human-facing audit report."""

    baseline = report["baseline"]
    distributions = report["distributions"]
    contract = report["learning_contract"]
    duplicates = report["duplicates"]
    ontology = report["ontology_coverage"]
    review = report["review"]
    lines = [
        "# Audit dataset SPARQL v1",
        "",
        "Trạng thái: **read-only; chưa sửa nội dung dataset**.",
        "",
        "## Tổng quan",
        "",
        f"- Record: {baseline['records']}",
        f"- Family: {distributions['families']['total']}",
        f"- Target SPARQL duy nhất: {distributions['targets']['total_unique']}",
        f"- Validator hiện tại: {'đạt' if baseline['validation']['ok'] else 'không đạt'}",
        f"- Exact duplicate sau normalizer: {duplicates['exact']['pair_count']}",
        f"- Ứng viên near-duplicate khác family: {duplicates['near']['pair_count']}",
        "",
        "### Theo split",
        "",
        "| Split | Record | Family | Target |",
        "|---|---:|---:|---:|",
    ]
    for split in REQUIRED_SPLITS:
        lines.append(
            f"| {split} | {distributions['records_by_split'][split]} | "
            f"{distributions['families']['by_split'][split]} | "
            f"{distributions['targets']['by_split'][split]} |"
        )

    lines.extend(
        [
            "",
            "## Những gì ảnh hưởng trực tiếp đến model học",
            "",
            f"- Target validation chưa từng xuất hiện nguyên vẹn ở train: "
            f"{len(contract['targets_missing_from_train']['val'])}",
            f"- Target test chưa từng xuất hiện nguyên vẹn ở train: "
            f"{len(contract['targets_missing_from_train']['test'])}",
            f"- Ontology term trong validation chưa xuất hiện ở target train: "
            f"{len(contract['ontology_terms_missing_from_train']['val'])}",
            f"- Ontology term trong test chưa xuất hiện ở target train: "
            f"{len(contract['ontology_terms_missing_from_train']['test'])}",
            f"- Family train/val có đúng một register: "
            f"{contract['family_register_profiles']['single_register_train_val_families']}",
            f"- Family train/val có đủ bốn register: "
            f"{contract['family_register_profiles']['four_register_train_val_families']}",
            f"- Family test chỉ có một record: "
            f"{contract['test_family_profiles']['singleton_families']} / "
            f"{contract['test_family_profiles']['families']}",
            f"- Số target train có đúng hai family: "
            f"{contract['target_family_support_by_split']['train'].get('2', 0)} / "
            f"{distributions['targets']['by_split']['train']}",
            f"- Target xuất hiện ở cả train/val/test: "
            f"{contract['target_membership_counts'].get('train+val+test', 0)} / "
            f"{distributions['targets']['total_unique']}",
            "",
            "### Độ dài generic",
            "",
            "| Đại lượng | p50 | p95 | max |",
            "|---|---:|---:|---:|",
            _length_row("Source words", distributions["lengths"]["source_words"]),
            _length_row("Normalized source words", distributions["lengths"]["normalized_source_words"]),
            _length_row("Target characters", distributions["lengths"]["target_characters"]),
        ]
    )

    if report["tokenizers"]:
        lines.extend(["", "### Tokenizer thực tế", ""])
        lines.extend(
            [
                "| Model | Source max | Source >128 | Source có `<unk>` | Target max | Target >160 | Target `<unk>` | Round-trip lỗi |",
                "|---|---:|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for name, item in report["tokenizers"].items():
            lines.append(
                f"| {name} | {item['source_tokens']['max']} | "
                f"{item['source_over_budget_records']} | {len(item['source_unknown_records'])} | "
                f"{item['target_tokens']['max']} | "
                f"{item['target_over_budget_targets']} | {item['target_unknown_tokens']} | "
                f"{item['target_roundtrip_failures']} |"
            )

    evidence = report["validation_learning_evidence"]
    if evidence["available"]:
        lines.extend(
            [
                "",
                "## Bằng chứng từ validation của model",
                "",
                "Chỉ dùng validation của các lượt train cũ; không đọc điểm test để đưa ra ưu tiên v2.",
                "",
                "| Model | Run | Observation | Answer exact |",
                "|---|---:|---:|---:|",
            ]
        )
        for name, item in evidence["by_model"].items():
            lines.append(
                f"| {name} | {item['runs']} | {item['observations']} | "
                f"{item['answer_exact_rate']:.2%} |"
            )
        model_names = sorted(evidence["by_model"])
        lines.extend(
            [
                "",
                "### Theo register",
                "",
                "| Register | " + " | ".join(model_names) + " |",
                "|---|" + "---:|" * len(model_names),
            ]
        )
        for register in sorted(evidence["by_register"]):
            values = [
                evidence["by_model"][model]["by_register"][register]["answer_exact_rate"]
                for model in model_names
            ]
            lines.append(
                f"| {register} | " + " | ".join(f"{value:.2%}" for value in values) + " |"
            )
        lines.extend(
            [
                "",
                "### Theo query shape",
                "",
                "| Query shape | " + " | ".join(model_names) + " |",
                "|---|" + "---:|" * len(model_names),
            ]
        )
        for shape in sorted(evidence["by_query_shape"]):
            values = [
                evidence["by_model"][model]["by_query_shape"][shape]["answer_exact_rate"]
                for model in model_names
            ]
            lines.append(
                f"| {shape} | " + " | ".join(f"{value:.2%}" for value in values) + " |"
            )
        lines.extend(
            [
                "",
                "### Theo độ mới của target so với train",
                "",
                "| Nhóm | Observation | Answer exact |",
                "|---|---:|---:|",
            ]
        )
        for novelty, item in evidence["by_target_novelty"].items():
            lines.append(
                f"| {novelty} | {item['observations']} | {item['answer_exact_rate']:.2%} |"
            )
        lines.extend(
            [
                "",
                f"- Record validation sai ở mọi lượt quan sát: "
                f"{len(evidence['persistently_failed_records'])}",
                f"- Persistent failure theo register: "
                f"{_inline_counts(evidence['persistently_failed_by_register'])}",
                f"- Persistent failure theo shape: "
                f"{_inline_counts(evidence['persistently_failed_by_query_shape'])}",
                f"- Family validation có answer exact ≤ 50%: "
                f"{len(evidence['hard_families'])}",
                f"- Phân loại lỗi: {_inline_counts(evidence['error_counts'])}",
            ]
        )

    lines.extend(
        [
            "",
            "## Coverage ontology",
            "",
            f"- Named individual được neo trực tiếp trong target: {ontology['named_individuals']['covered']} / "
            f"{ontology['named_individuals']['total']}",
            f"- Datatype property xuất hiện trong target: {ontology['datatype_properties']['covered']} / "
            f"{ontology['datatype_properties']['total']}",
            f"- Object property xuất hiện trong target: {ontology['object_properties']['covered']} / "
            f"{ontology['object_properties']['total']}",
            f"- Class xuất hiện trong target: {ontology['classes']['covered']} / "
            f"{ontology['classes']['total']}",
            "",
            "Named individual không được neo trực tiếp vẫn có thể được lấy qua object property. "
            "Các term chưa xuất hiện chỉ là ứng viên kiểm tra coverage; không tự động thêm câu hỏi.",
            "",
            "## Worksheet review",
            "",
            f"- Tổng family: {review['families']}",
            f"- Priority: {_inline_counts(review['priority_counts'])}",
            f"- Flag: {_inline_counts(review['flag_counts'])}",
            "- Audit không tự quyết định keep/fix/split/merge/drop.",
            "",
            "## Giới hạn",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in report["limitations"])
    return "\n".join(lines) + "\n"


def write_audit_outputs(
    output_dir: Path,
    report: Mapping[str, Any],
    worksheet: Sequence[Mapping[str, Any]],
) -> None:
    """Write stable JSON, Markdown and JSONL review artifacts."""

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "report.md").write_text(render_markdown(report), encoding="utf-8")
    (output_dir / "family_review.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in worksheet),
        encoding="utf-8",
    )


def _length_row(name: str, item: Mapping[str, Any]) -> str:
    return f"| {name} | {item['p50']} | {item['p95']} | {item['max']} |"


def _inline_counts(counts: Mapping[str, int]) -> str:
    return ", ".join(f"{name}={count}" for name, count in counts.items()) or "không có"
