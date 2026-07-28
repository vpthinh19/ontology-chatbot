from __future__ import annotations

from ontchatbot.research.gate_training import (
    PHOBERT_MODEL_ID,
    PHOBERT_REVISION,
    _tokenize_batch,
    _training_argument_values,
)


class _Tokenizer:
    def __init__(self) -> None:
        self.call = None

    def __call__(self, texts, **kwargs):
        self.call = (texts, kwargs)
        return {"input_ids": [[1, 2], [3, 4]]}


def test_gate_tokenization_normalizes_without_word_segmentation() -> None:
    tokenizer = _Tokenizer()

    encoded = _tokenize_batch(
        tokenizer,
        {
            "input": ["  tui đi NVQS, mún bảo lưu  ", "sv dh qg hcm"],
            "label": ["in_scope", "out_of_scope"],
        },
    )

    assert tokenizer.call == (
        ["tui đi nghĩa vụ quân sự, muốn bảo lưu", "sinh viên dh qg hcm"],
        {"max_length": 128, "truncation": True},
    )
    assert encoded == {"input_ids": [[1, 2], [3, 4]], "labels": [1, 0]}


def test_gate_training_configuration_is_fixed_and_environment_aware(tmp_path) -> None:
    values = _training_argument_values(
        tmp_path,
        precision={"bf16": True, "fp16": False, "tf32": True},
        smoke_test=False,
    )

    assert PHOBERT_MODEL_ID == "vinai/phobert-base-v2"
    assert len(PHOBERT_REVISION) == 40
    assert values["num_train_epochs"] == 5
    assert values["learning_rate"] == 2e-5
    assert values["lr_scheduler_type"] == "cosine"
    assert values["warmup_steps"] == 0.1
    assert values["seed"] == 42
    assert values["data_seed"] == 42
    assert values["bf16"] is True
    assert values["fp16"] is False
    assert values["tf32"] is True
    assert values["load_best_model_at_end"] is True
    assert values["metric_for_best_model"] == "macro_f1"
