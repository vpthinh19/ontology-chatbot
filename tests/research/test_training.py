from types import SimpleNamespace

import pytest

from ontchatbot.research.training import (
    MODEL_SPECS,
    _configure_greedy_generation,
    _effective_max_steps,
    _ensure_eos_token,
    _generation_cache_config,
    _optimization_arguments,
    _parse_args,
    _precision_policy,
    _require_training_ready,
)
from ontchatbot.settings import ARTIFACTS_DIR


def test_target_labels_always_end_with_eos() -> None:
    assert _ensure_eos_token([2, 10], 1, 4) == [2, 10, 1]
    assert _ensure_eos_token([2, 10, 1], 1, 4) == [2, 10, 1]
    assert _ensure_eos_token([2, 10, 11, 12], 1, 4) == [2, 10, 11, 1]


def test_t5gemma_keeps_the_same_effective_batch_as_baselines() -> None:
    effective_batches = {
        name: spec["batch_size"] * spec["gradient_accumulation"]
        for name, spec in MODEL_SPECS.items()
    }

    assert effective_batches == {"bartpho": 8, "vit5": 8, "t5gemma2": 8}
    assert MODEL_SPECS["t5gemma2"]["gradient_checkpointing"] is True


def test_structured_generation_disables_inherited_sampling_settings() -> None:
    config = SimpleNamespace(do_sample=True, top_p=0.95, top_k=64)

    _configure_greedy_generation(config)

    assert config.do_sample is False
    assert config.top_p is None
    assert config.top_k is None


def test_generation_cache_supports_flat_and_nested_model_configs() -> None:
    flat = SimpleNamespace(use_cache=False)
    nested_decoder = SimpleNamespace(use_cache=True)
    nested = SimpleNamespace(decoder=nested_decoder)

    assert _generation_cache_config(flat) is flat
    assert _generation_cache_config(nested) is nested_decoder


def test_full_training_rejects_dataset_with_coverage_gaps() -> None:
    readiness = {"ready": False, "gaps": [{"code": "missing_validation_features"}]}

    with pytest.raises(RuntimeError, match="dataset is not ready for full training"):
        _require_training_ready(readiness, smoke_test=False)


def test_smoke_training_can_check_pipeline_before_curation_finishes() -> None:
    readiness = {"ready": False, "gaps": [{"code": "missing_validation_features"}]}

    _require_training_ready(readiness, smoke_test=True)


def test_cli_defaults_match_canonical_training_protocol() -> None:
    args = _parse_args(["--model", "bartpho"])

    assert args.epochs == 20.0
    assert args.eval_every_epochs == 2.0
    assert args.learning_rate == 3e-5
    assert args.seed == 42
    assert args.output_dir == ARTIFACTS_DIR / "models"
    assert not hasattr(args, "keep_dropout")


@pytest.mark.parametrize(
    ("cuda_available", "bf16_supported", "capability", "expected"),
    [
        (
            True,
            True,
            (8, 9),
            {"dtype": "bfloat16", "bf16": True, "fp16": False, "tf32": True},
        ),
        (
            True,
            False,
            (7, 5),
            {"dtype": "float16", "bf16": False, "fp16": True, "tf32": False},
        ),
        (
            False,
            False,
            None,
            {"dtype": "float32", "bf16": False, "fp16": False, "tf32": False},
        ),
    ],
)
def test_precision_policy_follows_the_runtime_environment(
    cuda_available: bool,
    bf16_supported: bool,
    capability: tuple[int, int] | None,
    expected: dict[str, str | bool],
) -> None:
    assert _precision_policy(
        cuda_available=cuda_available,
        bf16_supported=bf16_supported,
        compute_capability=capability,
    ) == expected


def test_optimizer_arguments_use_cosine_warmup_without_compile() -> None:
    precision = {
        "dtype": "bfloat16",
        "bf16": True,
        "fp16": False,
        "tf32": True,
    }

    assert _optimization_arguments(precision) == {
        "lr_scheduler_type": "cosine",
        "warmup_steps": 0.1,
        "weight_decay": 0.005,
        "optim": "adamw_8bit",
        "bf16": True,
        "fp16": False,
        "tf32": True,
        "torch_compile": False,
    }


def test_smoke_run_covers_its_complete_training_subset() -> None:
    assert _effective_max_steps(
        smoke_test=True,
        requested_steps=-1,
        train_records=16,
        batch_size=4,
        gradient_accumulation=2,
    ) == 2
    assert _effective_max_steps(
        smoke_test=False,
        requested_steps=-1,
        train_records=1084,
        batch_size=4,
        gradient_accumulation=2,
    ) == -1
