from types import SimpleNamespace

from ontchatbot.research.training import (
    MODEL_SPECS,
    _configure_greedy_generation,
    _ensure_eos_token,
)


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
