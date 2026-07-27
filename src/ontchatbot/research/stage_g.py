"""Build the reproducible Stage G learning and benchmark audit."""

from __future__ import annotations

import hashlib
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

from ..settings import PROJECT_ROOT
from .dataset import load_release
from .stage_e import DATASET_DIR, MANIFEST_PATH, ONTOLOGY_PATH

MODELS = ("bartpho", "vit5", "t5gemma2")
SEEDS = (42,)
REPORT_DIR = PROJECT_ROOT / "reports/dataset_review_v2"
PROTOCOL_PATH = REPORT_DIR / "stage_g_protocol.json"
AUDIT_PATH = REPORT_DIR / "stage_g_audit.json"
REPORT_PATH = REPORT_DIR / "stage_g_report.md"


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _mean(values: Iterable[float]) -> float:
    return statistics.fmean(values)


def _rate(cases: list[Mapping[str, Any]]) -> float:
    return _mean(float(case["answer_exact"]) for case in cases) if cases else 0.0


def _record_summary(row: Mapping[str, str]) -> dict[str, str]:
    return {
        key: row[key]
        for key in ("id", "family_id", "register", "query_shape", "input")
    }


def _evaluation_evidence(
    release: Mapping[str, list[dict[str, str]]],
    reports: Mapping[str, list[Mapping[str, Any]]],
    holdout_families: set[str],
) -> dict[str, Any]:
    test_by_id = {row["id"]: row for row in release["test"]}
    train_targets = {row["target"] for row in release["train"]}
    observations: dict[str, list[tuple[str, bool]]] = defaultdict(list)
    by_model: dict[str, Any] = {}

    for model, model_reports in reports.items():
        run_rates = []
        novelty: dict[str, list[float]] = defaultdict(list)
        model_observations: dict[str, list[bool]] = defaultdict(list)
        for report in model_reports:
            cases = report["cases"]
            if {case["id"] for case in cases} != set(test_by_id):
                raise ValueError(f"{model} benchmark cases do not match frozen test")
            run_rates.append(_rate(cases))
            grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
            for case in cases:
                row = test_by_id[case["id"]]
                group = (
                    "unseen_exact_target"
                    if row["target"] not in train_targets
                    else "seen_exact_target"
                )
                grouped[group].append(case)
                exact = bool(case["answer_exact"])
                observations[row["id"]].append((model, exact))
                model_observations[row["id"]].append(exact)
            for group, group_cases in grouped.items():
                novelty[group].append(_rate(group_cases))

        persistent_ids = sorted(
            record_id
            for record_id, exacts in model_observations.items()
            if not any(exacts)
        )
        by_model[model] = {
            "runs": len(model_reports),
            "answer_exact_rate": {
                "mean": _mean(run_rates),
                "sample_std": statistics.stdev(run_rates) if len(run_rates) > 1 else 0.0,
                "values": run_rates,
            },
            "by_target_novelty": {
                group: {
                    "records": sum(
                        row["target"] not in train_targets
                        if group == "unseen_exact_target"
                        else row["target"] in train_targets
                        for row in release["test"]
                    ),
                    "mean_answer_exact_rate": _mean(values),
                    "values": values,
                }
                for group, values in sorted(novelty.items())
            },
            "persistent_failure_count": len(persistent_ids),
            "persistent_failure_ids": persistent_ids,
        }

    persistent_ids = sorted(
        record_id
        for record_id, model_exacts in observations.items()
        if not any(exact for _, exact in model_exacts)
    )
    persistent_rows = [test_by_id[record_id] for record_id in persistent_ids]
    unseen_rows = [row for row in release["test"] if row["target"] not in train_targets]
    if {row["family_id"] for row in unseen_rows} != holdout_families:
        raise ValueError("test target novelty does not match compositional holdout families")
    return {
        "test_records": len(test_by_id),
        "unseen_exact_target_records": len(unseen_rows),
        "compositional_holdout_families": sorted(holdout_families),
        "by_model": by_model,
        "persistent_failures_across_all_official_runs": {
            "count": len(persistent_ids),
            "by_register": dict(sorted(Counter(row["register"] for row in persistent_rows).items())),
            "by_query_shape": dict(
                sorted(Counter(row["query_shape"] for row in persistent_rows).items())
            ),
            "records": [_record_summary(row) for row in persistent_rows],
        },
    }


def build_stage_g_audit(
    artifact_root: Path,
    learning_root: Path,
) -> dict[str, Any]:
    """Combine frozen protocol, learning checks and official one-seed results."""

    protocol = _read_json(PROTOCOL_PATH)
    release = load_release(DATASET_DIR)
    manifest = _read_json(MANIFEST_PATH)
    if _sha256(MANIFEST_PATH) != protocol["dataset"]["manifest_sha256"]:
        raise ValueError("frozen dataset manifest changed after protocol lock")
    if _sha256(ONTOLOGY_PATH) != protocol["ontology"]["sha256"]:
        raise ValueError("ontology changed after protocol lock")

    learning_audit = {}
    diagnostic = {}
    reports: dict[str, list[dict[str, Any]]] = defaultdict(list)
    source_hashes = {}
    checkpoint_integrity = []
    for model in MODELS:
        learning_path = learning_root / "learning_audit" / model / "metrics.json"
        diagnostic_path = learning_root / "diagnostic" / model / "seed-42" / "metrics.json"
        if learning_path.is_file():
            learning = _read_json(learning_path)
            source_hashes[str(learning_path)] = _sha256(learning_path)
            learning_audit[model] = {
                "records": learning["overall"]["count"],
                "optimizer_steps": learning["training"]["max_steps"],
                "answer_exact_rate": learning["overall"]["answer_exact_rate"],
                "parse_rate": learning["overall"]["parse_rate"],
                "runtime_seconds": learning["training"]["train_runtime_seconds"],
                "peak_vram_bytes": learning["training"]["peak_vram_bytes"],
            }
        if diagnostic_path.is_file():
            diag = _read_json(diagnostic_path)
            source_hashes[str(diagnostic_path)] = _sha256(diagnostic_path)
            diagnostic[model] = {
                "epochs": diag["training"]["epochs"],
                "answer_exact_rate": diag["overall"]["answer_exact_rate"],
                "parse_rate": diag["overall"]["parse_rate"],
                "by_register": diag["by_register"],
                "by_query_shape": diag["by_query_shape"],
            }
        for seed in SEEDS:
            run_dir = artifact_root / model / f"seed-{seed}"
            validation_path = run_dir / "metrics.json"
            benchmark_path = run_dir / "benchmark_metrics.json"
            validation = _read_json(validation_path)
            benchmark = _read_json(benchmark_path)
            source_hashes[str(validation_path)] = _sha256(validation_path)
            source_hashes[str(benchmark_path)] = _sha256(benchmark_path)
            reports[model].append(benchmark)
            expected = next(
                item for item in protocol["frozen_checkpoints"]
                if item["model"] == model and item["seed"] == seed
            )
            if (
                validation["training"]["model"] != model
                or validation["training"]["seed"] != seed
                or validation["overall"]["answer_exact_rate"]
                != expected["validation_answer_exact_rate"]
            ):
                raise ValueError(f"checkpoint selection mismatch: {model} seed {seed}")
            model_path = run_dir / "model" / "model.safetensors"
            actual_model_hash = _sha256(model_path)
            if actual_model_hash != expected["model_sha256"]:
                raise ValueError(f"frozen model hash mismatch: {model} seed {seed}")
            checkpoint_integrity.append(
                {
                    "model": model,
                    "seed": seed,
                    "model_sha256": actual_model_hash,
                    "passed": True,
                }
            )

    summary_path = artifact_root / "summary_seed42.json"
    summary = _read_json(summary_path)
    source_hashes[str(summary_path)] = _sha256(summary_path)
    generalization = _evaluation_evidence(
        release,
        reports,
        set(manifest["split"]["compositional_holdout_families"]["test"]),
    )
    return {
        "stage": "G",
        "status": "complete_test_evaluated_once",
        "protocol": str(PROTOCOL_PATH.relative_to(PROJECT_ROOT)),
        "dataset_manifest_sha256": _sha256(MANIFEST_PATH),
        "ontology_sha256": _sha256(ONTOLOGY_PATH),
        "source_report_sha256": dict(sorted(source_hashes.items())),
        "checkpoint_integrity": checkpoint_integrity,
        "learning_audit": learning_audit,
        "diagnostic": diagnostic,
        "official": summary,
        "generalization": generalization,
        "conclusion": {
            "dataset_is_learnable": all(
                summary["models"][model]["validation"]["answer_exact_rate"]["mean"] > 0.6
                for model in MODELS
            ),
            "syntax_is_stable": all(
                summary["models"][model]["benchmark"]["parse_rate"]["mean"] >= 0.99
                for model in MODELS
            ),
            "semantic_generalization_is_solved": False,
            "release_decision": "keep_v2_frozen; address weaknesses only in a future v3",
        },
    }


def render_stage_g_report(audit: Mapping[str, Any]) -> str:
    models = audit["official"]["models"]
    gen = audit["generalization"]
    lines = [
        "# Stage G — nghiệm thu khả năng học của dataset v2",
        "",
        "Stage G đã hoàn tất theo protocol khóa trước khi mở test của từng model. Ba checkpoint "
        "(3 model × seed 42) được chọn chỉ bằng validation; mỗi checkpoint chỉ đọc test một lần.",
        "",
        "## Kết quả chính",
        "",
        "| Model | Validation answer exact | Test answer exact | Test parse |",
        "|---|---:|---:|---:|",
    ]
    for model in MODELS:
        item = models[model]
        lines.append(
            f"| {model} | {item['validation']['answer_exact_rate']['mean']:.2%} | "
            f"{item['benchmark']['answer_exact_rate']['mean']:.2%} | "
            f"{item['benchmark']['parse_rate']['mean']:.2%} |"
        )
    lines.extend([
        "",
        "`answer exact` nghĩa là kết quả dữ liệu khi chạy câu SPARQL sinh ra giống hệt "
        "kết quả của câu chuẩn; đây là chỉ số chất lượng chính. `parse` chỉ cho biết câu sinh ra "
        "có đúng cú pháp SPARQL, không đảm bảo model hiểu đúng câu hỏi.",
        "",
        "## Dataset đã chứng minh được gì?",
        "",
        "- BARTpho và ViT5 học thuộc tập kiểm tra nhỏ 16/16 sau 500 bước; T5Gemma2 "
        "được kiểm tra tokenizer toàn bộ target rồi train trực tiếp để tránh một lượt audit dư thừa.",
        "- Cú pháp test đạt trên 99% ở cả ba model: lỗi chính không còn nằm ở dấu ngoặc hay tokenizer.",
        "- T5Gemma2 đạt điểm validation và test cao nhất, đổi lại dùng nhiều VRAM nhất và sinh chậm nhất.",
        "",
        "### Chi phí trên RTX 4050 6 GB",
        "",
        "| Model | Thời gian train | VRAM train cực đại | Tốc độ test |",
        "|---|---:|---:|---:|",
    ])
    for model in MODELS:
        item = models[model]
        lines.append(
            f"| {model} | {item['training']['seconds']['mean'] / 60:.1f} phút | "
            f"{item['training']['peak_vram_bytes']['mean'] / (1024 ** 3):.2f} GiB | "
            f"{item['inference']['records_per_second']['mean']:.2f} câu/giây |"
        )
    lines.extend([
        "",
        "## Giới hạn được Stage G phát hiện",
        "",
        "| Model | 120 câu target đã thấy | 20 câu target mới |",
        "|---|---:|---:|",
    ])
    for model in MODELS:
        novelty = gen["by_model"][model]["by_target_novelty"]
        lines.append(
            f"| {model} | {novelty['seen_exact_target']['mean_answer_exact_rate']:.2%} | "
            f"{novelty['unseen_exact_target']['mean_answer_exact_rate']:.2%} |"
        )
    failures = gen["persistent_failures_across_all_official_runs"]
    lines.extend([
        "",
        f"- Có {failures['count']}/140 câu sai ở cả ba model; "
        f"{failures['by_register'].get('noisy', 0)} câu thuộc register `noisy`.",
        "- Nhóm yếu nhất là `aggregate`, `multi_column` và câu nói thiếu dấu/viết tắt (`noisy`).",
        "- Khoảng cách lớn ở target mới cho thấy coverage hiện tại chưa đủ mạnh cho ghép cấu trúc mới, "
        "không phải model không sinh được SPARQL.",
        "",
        "## Kết luận",
        "",
        "Dataset v2 **đủ tốt làm baseline nghiên cứu và phiên bản huấn luyện đầu tiên**, nhưng chưa "
        "đủ để coi bài toán tổng quát hóa đã giải quyết. Dataset v2 tiếp tục bị đóng băng vì test đã mở; "
        "mọi bổ sung dựa trên lỗi Stage G phải tạo thành v3 với test mới, tránh học ngược từ test.",
        "",
        "Chi tiết máy đọc được, gồm điểm theo register/query shape, ba run và danh sách lỗi bền vững, "
        "nằm trong `stage_g_audit.json`.",
    ])
    return "\n".join(lines)


def write_stage_g_outputs(artifact_root: Path, learning_root: Path) -> dict[str, Any]:
    audit = build_stage_g_audit(artifact_root, learning_root)
    AUDIT_PATH.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    REPORT_PATH.write_text(render_stage_g_report(audit) + "\n", encoding="utf-8")
    protocol = _read_json(PROTOCOL_PATH)
    protocol["status"] = "complete_test_evaluated_once"
    protocol["stage_g_audit"] = str(AUDIT_PATH.relative_to(PROJECT_ROOT))
    PROTOCOL_PATH.write_text(
        json.dumps(protocol, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return audit
