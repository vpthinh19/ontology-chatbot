from __future__ import annotations

import json
from pathlib import Path

import pytest

from ontchatbot.research.dataset import load_release
from ontchatbot.research.training import MAX_TARGET_LENGTH
from ontchatbot.runtime.model import MAX_TARGET_LENGTH as RUNTIME_MAX_TARGET_LENGTH
from ontchatbot.settings import ARTIFACTS_DIR
from ontchatbot.tools.tokenizer import (
    BARTPHO_MODEL_ID,
    BARTPHO_REVISION,
    T5GEMMA_MODEL_ID,
    T5GEMMA_REVISION,
    VIT5_MODEL_ID,
    VIT5_REVISION,
    audit_target_roundtrip,
    summarize_target_audit,
)


def _snapshot(cache_name: str, revision: str) -> Path:
    return Path.home() / ".cache/huggingface/hub" / cache_name / "snapshots" / revision


MODEL_TOKENIZERS = {
    "bartpho": {
        "model_id": BARTPHO_MODEL_ID,
        "revision": BARTPHO_REVISION,
        "path": _snapshot("models--vinai--bartpho-syllable", BARTPHO_REVISION),
        "kwargs": {},
    },
    "vit5": {
        "model_id": VIT5_MODEL_ID,
        "revision": VIT5_REVISION,
        "path": ARTIFACTS_DIR / "tokenizers/vit5",
        "kwargs": {},
    },
    "t5gemma2": {
        "model_id": T5GEMMA_MODEL_ID,
        "revision": T5GEMMA_REVISION,
        "path": _snapshot(
            "models--google--t5gemma-2-270m-270m", T5GEMMA_REVISION
        ),
        "kwargs": {"fix_mistral_regex": False},
    },
}


def test_target_measurement_summary_uses_nearest_rank_p95() -> None:
    report = [
        {
            "target": f"target-{index}",
            "tokens": index,
            "unknown_tokens": int(index == 20),
            "roundtrip_exact": index != 20,
        }
        for index in range(1, 21)
    ]

    summary = summarize_target_audit(report, generation_ceiling=19)

    assert summary["token_lengths"] == {
        "min": 1,
        "median": 10.5,
        "p95": 19,
        "max": 20,
    }
    assert summary["unrepresentable_targets"] == 1
    assert summary["targets_over_ceiling"] == 1


def _measure_model(model_name: str) -> dict:
    try:
        from transformers import AutoTokenizer
    except ImportError:
        pytest.skip(
            f"{model_name}: chưa cài transformers; cài project với extra 'train'"
        )

    spec = MODEL_TOKENIZERS[model_name]
    tokenizer_path = Path(spec["path"])
    if not tokenizer_path.is_dir():
        if model_name == "vit5":
            pytest.skip(
                f"{model_name}: thiếu tokenizer ViT5 đã sửa tại {tokenizer_path}; "
                "chạy prepare_vit5_tokenizer trước"
            )
        pytest.skip(
            f"{model_name}: thiếu snapshot cục bộ {spec['model_id']} "
            f"revision {spec['revision']}; tải bằng hf download"
        )

    tokenizer = AutoTokenizer.from_pretrained(
        tokenizer_path,
        local_files_only=True,
        **spec["kwargs"],
    )
    release = load_release()
    targets = sorted(
        {
            row["target"]
            for split in ("train", "val", "test")
            for row in release[split]
        }
    )
    audit = audit_target_roundtrip(tokenizer, targets, strict=False)
    generation_ceiling = min(MAX_TARGET_LENGTH, RUNTIME_MAX_TARGET_LENGTH)
    summary = summarize_target_audit(
        audit,
        generation_ceiling=generation_ceiling,
    )
    print(f"TOKENIZER_METRICS {model_name} {json.dumps(summary, ensure_ascii=False)}")

    assert summary["targets_over_ceiling"] == 0, (
        f"{model_name}: {summary['targets_over_ceiling']} đích vượt trần sinh "
        f"{generation_ceiling}; ví dụ {summary['over_ceiling_examples']}"
    )
    return summary


def test_bartpho_target_measurements() -> None:
    _measure_model("bartpho")


def test_vit5_target_measurements() -> None:
    _measure_model("vit5")


def test_t5gemma2_target_measurements() -> None:
    _measure_model("t5gemma2")
