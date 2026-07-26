"""Audit a dataset release without modifying it."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..research.audit import (
    audit_release,
    load_validation_reports,
    sha256_file,
)
from ..research.audit_report import write_audit_outputs
from ..research.dataset import REQUIRED_SPLITS, load_release
from ..runtime.sparql import load_ontology
from ..settings import DATASET_DIR, ONTOLOGY_PATH, PROJECT_ROOT


def _load_tokenizer(path: Path, *, trust_remote_code: bool):
    try:
        from transformers import AutoTokenizer
    except ImportError as exc:  # pragma: no cover - optional research dependency.
        raise RuntimeError("install the train extra to include tokenizer metrics") from exc
    return AutoTokenizer.from_pretrained(
        path,
        local_files_only=True,
        trust_remote_code=trust_remote_code,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-dir", type=Path, default=DATASET_DIR)
    parser.add_argument("--ontology", type=Path, default=ONTOLOGY_PATH)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "reports/dataset_audit_v1",
    )
    parser.add_argument("--near-duplicate-threshold", type=float, default=0.84)
    parser.add_argument("--validation-metrics-root", type=Path)
    parser.add_argument("--bartpho-tokenizer", type=Path)
    parser.add_argument("--vit5-tokenizer", type=Path)
    args = parser.parse_args()
    if not 0.0 < args.near_duplicate_threshold <= 1.0:
        parser.error("--near-duplicate-threshold must be in (0, 1]")
    return args


def main() -> None:
    args = _parse_args()
    release = load_release(args.dataset_dir)
    checksums = {
        f"dataset/{split}.jsonl": sha256_file(args.dataset_dir / f"{split}.jsonl")
        for split in REQUIRED_SPLITS
    }
    checksums["ontology"] = sha256_file(args.ontology)

    tokenizers = {}
    if args.bartpho_tokenizer:
        tokenizers["bartpho"] = _load_tokenizer(
            args.bartpho_tokenizer,
            trust_remote_code=True,
        )
    if args.vit5_tokenizer:
        tokenizers["vit5"] = _load_tokenizer(
            args.vit5_tokenizer,
            trust_remote_code=False,
        )
    validation_reports = (
        load_validation_reports(args.validation_metrics_root)
        if args.validation_metrics_root
        else []
    )

    report, worksheet = audit_release(
        release,
        load_ontology(args.ontology),
        checksums=checksums,
        near_duplicate_threshold=args.near_duplicate_threshold,
        tokenizers=tokenizers,
        validation_reports=validation_reports,
    )
    report["audit_inputs"] = {
        "dataset_dir": str(args.dataset_dir),
        "ontology": str(args.ontology),
        "near_duplicate_threshold": args.near_duplicate_threshold,
        "validation_metrics_root": (
            str(args.validation_metrics_root) if args.validation_metrics_root else None
        ),
        "bartpho_tokenizer": (
            str(args.bartpho_tokenizer) if args.bartpho_tokenizer else None
        ),
        "vit5_tokenizer": str(args.vit5_tokenizer) if args.vit5_tokenizer else None,
    }
    write_audit_outputs(args.output_dir, report, worksheet)
    print(
        json.dumps(
            {
                "output_dir": str(args.output_dir),
                "records": report["baseline"]["records"],
                "families": report["review"]["families"],
                "review_priority": report["review"]["priority_counts"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
