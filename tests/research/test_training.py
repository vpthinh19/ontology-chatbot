from types import SimpleNamespace

import pytest

import ontchatbot.research.training as training
from ontchatbot.research.training import (
    _configure_greedy_generation,
    _ensure_eos_token,
    _generation_cache_config,
    _require_training_ready,
    configure_decoder_start,
)


def test_target_labels_always_end_with_eos() -> None:
    assert _ensure_eos_token([2, 10], 1, 4) == [2, 10, 1]
    assert _ensure_eos_token([2, 10, 1], 1, 4) == [2, 10, 1]
    assert _ensure_eos_token([2, 10, 11, 12], 1, 4) == [2, 10, 11, 1]


def test_a_language_code_after_the_terminator_counts_as_terminated() -> None:
    """Nhãn của model đa ngữ kết thúc bằng cặp ``</s> <mã ngôn ngữ>``. Thêm
    một dấu kết thúc nữa là đẩy mã ngôn ngữ vào giữa nhãn, mà chính mã đó quyết
    định token mở đầu của bộ giải mã."""

    assert _ensure_eos_token([10, 11, 1, 250024], 1, 8) == [10, 11, 1, 250024]


def test_decoder_start_follows_the_language_code_the_model_declares() -> None:
    tokenizer = SimpleNamespace(
        convert_tokens_to_ids=lambda token: {"vi_VN": 250024}.get(token, 3),
        unk_token_id=3,
    )
    model = SimpleNamespace(
        config=SimpleNamespace(decoder_start_token_id=None),
        generation_config=SimpleNamespace(decoder_start_token_id=None),
    )

    configure_decoder_start(model, tokenizer, {"decoder_start_token": "vi_VN"})

    assert model.config.decoder_start_token_id == 250024
    assert model.generation_config.decoder_start_token_id == 250024


def test_a_model_without_a_language_code_keeps_its_own_start_token() -> None:
    model = SimpleNamespace(
        config=SimpleNamespace(decoder_start_token_id=2),
        generation_config=SimpleNamespace(decoder_start_token_id=2),
    )

    configure_decoder_start(model, SimpleNamespace(), {})

    assert model.config.decoder_start_token_id == 2


def test_a_missing_language_code_stops_the_run() -> None:
    tokenizer = SimpleNamespace(convert_tokens_to_ids=lambda token: 3, unk_token_id=3)
    model = SimpleNamespace(
        config=SimpleNamespace(decoder_start_token_id=None),
        generation_config=SimpleNamespace(decoder_start_token_id=None),
    )

    with pytest.raises(ValueError):
        configure_decoder_start(model, tokenizer, {"decoder_start_token": "xx_XX"})


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
    output_dir = tmp_path / "model"
    output_dir.mkdir()
    (output_dir / "metrics.json").write_text("{}", encoding="utf-8")

    with pytest.raises(RuntimeError, match="output directory is not empty"):
        training._prepare_output_directory(output_dir)
