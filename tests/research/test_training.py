from types import SimpleNamespace

import pytest

import ontchatbot.research.training as training
from ontchatbot.research.training import (
    MODEL_SPECS,
    _configure_greedy_generation,
    _effective_max_steps,
    _ensure_eos_token,
    _generation_cache_config,
    _optimization_arguments,
    _parse_args,
    _optimizer_name,
    _precision_policy,
    _require_training_ready,
)
from ontchatbot.settings import ARTIFACTS_DIR


def test_target_labels_always_end_with_eos() -> None:
    assert _ensure_eos_token([2, 10], 1, 4) == [2, 10, 1]
    assert _ensure_eos_token([2, 10, 1], 1, 4) == [2, 10, 1]
    assert _ensure_eos_token([2, 10, 11, 12], 1, 4) == [2, 10, 11, 1]


def test_all_benchmark_models_share_one_physical_batch_protocol() -> None:
    effective_batches = {
        name: spec["batch_size"] * spec["gradient_accumulation"]
        for name, spec in MODEL_SPECS.items()
    }

    assert effective_batches == {"bartpho": 8, "vit5": 8, "t5gemma2": 8}
    assert all(spec["batch_size"] == 8 for spec in MODEL_SPECS.values())
    assert all(spec["gradient_accumulation"] == 1 for spec in MODEL_SPECS.values())
    # Checkpointing không đổi gradient, chỉ đổi bộ nhớ - nên nó được phép bật.
    # Cái KHÔNG được phép là bật lệch giữa các model: benchmark cuối chỉ so được
    # khi cả ba đi cùng một giao thức. Nếu chỉ một model bật, lượt đó sẽ chậm hơn
    # vì lý do cấu hình chứ không vì bản chất model.
    checkpointing = {
        name: spec.get("gradient_checkpointing", False)
        for name, spec in MODEL_SPECS.items()
    }
    assert len(set(checkpointing.values())) == 1, checkpointing


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


def test_training_rejects_nonempty_model_output_directory(tmp_path) -> None:
    output_dir = tmp_path / "t5gemma2"
    output_dir.mkdir()
    (output_dir / "metrics.json").write_text("{}", encoding="utf-8")

    with pytest.raises(RuntimeError, match="output directory is not empty"):
        training._prepare_output_directory(output_dir)


def test_cli_defaults_match_canonical_training_protocol() -> None:
    """Mặc định phải khớp giao thức ĐÃ ĐO, không phải giao thức lịch sử.

    Bản trước chốt 20 epoch và đánh giá mỗi 2 epoch. Cả hai đã được đo lại:
    mất mát huấn luyện về 0,0000 từ epoch 15 và epoch 16 -> 20 chỉ đổi -0,2%;
    còn mỗi lần đánh giá tốn ~95 giây và từng chiếm 88% thời gian một lượt chạy.
    Để mặc định cũ nghĩa là ai chạy mà quên truyền cờ sẽ mất thêm ~25 phút
    không đổi lại được gì.
    """

    args = _parse_args(["--model", "t5gemma2"])

    assert args.epochs == 16.0
    assert args.eval_every_epochs == 4.0
    assert args.learning_rate == 1e-4
    assert args.seed == 42
    assert args.output_dir == ARTIFACTS_DIR / "models"
    assert not hasattr(args, "keep_dropout")


@pytest.mark.parametrize(
    ("model_name", "names", "expected"),
    [
        (
            "bartpho",
            (
                "model.encoder.layers.0.self_attn.q_proj",
                "model.decoder.layers.0.encoder_attn.out_proj",
                "model.decoder.layers.0.fc2",
                "lm_head",
            ),
            (
                "model.encoder.layers.0.self_attn.q_proj",
                "model.decoder.layers.0.encoder_attn.out_proj",
                "model.decoder.layers.0.fc2",
            ),
        ),
        (
            "vit5",
            (
                "encoder.block.0.layer.0.SelfAttention.q",
                "decoder.block.0.layer.1.EncDecAttention.o",
                "decoder.block.0.layer.2.DenseReluDense.wo",
                "lm_head",
            ),
            (
                "encoder.block.0.layer.0.SelfAttention.q",
                "decoder.block.0.layer.1.EncDecAttention.o",
                "decoder.block.0.layer.2.DenseReluDense.wo",
            ),
        ),
        (
            "t5gemma2",
            (
                "model.encoder.text_model.layers.0.self_attn.q_proj",
                "model.encoder.vision_model.encoder.layers.0.self_attn.q_proj",
                "model.decoder.layers.0.mlp.down_proj",
                "model.decoder.layers.0.layer_norm",
            ),
            (
                "model.encoder.text_model.layers.0.self_attn.q_proj",
                "model.decoder.layers.0.mlp.down_proj",
            ),
        ),
    ],
)
def test_lora_targets_match_each_model_without_unrelated_modules(
    model_name: str,
    names: tuple[str, ...],
    expected: tuple[str, ...],
) -> None:
    model = SimpleNamespace(
        named_modules=lambda: ((name, object()) for name in names)
    )

    assert training._lora_target_modules(model, model_name) == list(expected)


def test_lora_target_discovery_rejects_incompatible_model() -> None:
    model = SimpleNamespace(
        named_modules=lambda: iter(
            (("model.encoder.vision_model.layers.0.self_attn.q_proj", object()),)
        )
    )

    with pytest.raises(RuntimeError, match="text encoder/decoder"):
        training._lora_target_modules(model, "t5gemma2")


def test_attach_lora_model_uses_the_locked_seq2seq_protocol() -> None:
    target_name = "model.decoder.layers.0.self_attn.q_proj"
    model = SimpleNamespace(
        named_modules=lambda: iter(((target_name, object()),))
    )
    adapted_model = object()
    captured = {}

    class FakeTaskType:
        SEQ_2_SEQ_LM = "seq2seq"

    class FakeLoraConfig:
        def __init__(self, **kwargs) -> None:
            captured.update(kwargs)

    def fake_get_peft_model(received_model, config):
        assert received_model is model
        assert isinstance(config, FakeLoraConfig)
        return adapted_model

    result = training._attach_lora_model(
        model,
        model_name="t5gemma2",
        LoraConfig=FakeLoraConfig,
        TaskType=FakeTaskType,
        get_peft_model=fake_get_peft_model,
    )

    assert result is adapted_model
    assert captured == {
        "task_type": "seq2seq",
        "r": 32,
        "lora_alpha": 64,
        "lora_dropout": 0.0,
        "bias": "none",
        "target_modules": [target_name],
    }


@pytest.mark.parametrize(
    ("accelerator", "bf16_supported", "capability", "expected"),
    [
        (
            "cuda",
            True,
            (8, 9),
            {"dtype": "bfloat16", "bf16": True, "fp16": False, "tf32": True},
        ),
        (
            "cuda",
            False,
            (7, 5),
            {"dtype": "float16", "bf16": False, "fp16": True, "tf32": False},
        ),
        # TPU cores have no float16 path, and bf16 keeps the arithmetic the same
        # as every run measured so far on the laptop.
        (
            "xla",
            False,
            None,
            {"dtype": "bfloat16", "bf16": True, "fp16": False, "tf32": False},
        ),
        (
            "cpu",
            False,
            None,
            {"dtype": "float32", "bf16": False, "fp16": False, "tf32": False},
        ),
    ],
)
def test_precision_policy_follows_the_runtime_environment(
    accelerator: str,
    bf16_supported: bool,
    capability: tuple[int, int] | None,
    expected: dict[str, str | bool],
) -> None:
    assert _precision_policy(
        accelerator=accelerator,
        bf16_supported=bf16_supported,
        compute_capability=capability,
    ) == expected


@pytest.mark.parametrize(
    ("accelerator", "expected"),
    [
        ("cuda", "adamw_8bit"),
        # adamw_8bit is the bitsandbytes optimizer and needs CUDA; asking for it
        # on a TPU fails at the first step.
        ("xla", "adamw_torch_xla"),
        ("cpu", "adamw_torch"),
    ],
)
def test_optimizer_matches_what_the_accelerator_can_run(
    accelerator: str,
    expected: str,
) -> None:
    assert _optimizer_name(accelerator) == expected


def test_optimizer_arguments_use_cosine_warmup_without_compile() -> None:
    precision = {
        "dtype": "bfloat16",
        "bf16": True,
        "fp16": False,
        "tf32": True,
    }

    assert _optimization_arguments(precision, optimizer="adamw_8bit") == {
        "lr_scheduler_type": "cosine",
        "warmup_steps": 0.1,
        "weight_decay": 0.005,
        "optim": "adamw_8bit",
        "bf16": True,
        "fp16": False,
        "tf32": True,
        "torch_compile": False,
    }
