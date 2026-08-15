import os
import subprocess
import sys

import pytest
import torch

from ontchatbot.research.llm_lora_training import (
    ATTENTION_LORA_TARGET_MODULES,
    EFFECTIVE_BATCH_SIZE,
    TargetOnlyDataCollator,
    _batch_plans,
    _cast_tied_weight_to_dtype,
    _cuda_memory_record,
    _lora_spec,
    _parse_args,
    encode_training_example,
)


class FakeTokenizer:
    eos_token_id = 99
    pad_token_id = 0

    def apply_chat_template(self, *args, **kwargs):
        assert kwargs == {
            "tokenize": True,
            "add_generation_prompt": True,
            "enable_thinking": False,
        }
        return {"input_ids": [10, 11, 12]}

    def __call__(self, text, *, add_special_tokens):
        assert text == "SELECT ?x WHERE { ?x ?p ?o }"
        assert add_special_tokens is False
        return {"input_ids": [20, 21]}


def test_causal_labels_exclude_every_prompt_token_from_loss() -> None:
    encoded = encode_training_example(
        FakeTokenizer(),
        {"id": "q-1", "input": "câu hỏi", "target": "SELECT ?x WHERE { ?x ?p ?o }"},
    )

    assert encoded["input_ids"] == [10, 11, 12, 20, 21, 99]
    assert encoded["labels"] == [-100, -100, -100, 20, 21, 99]
    assert encoded["attention_mask"] == [1] * 6


def test_collator_excludes_padding_from_loss() -> None:
    collator = TargetOnlyDataCollator(pad_token_id=0, pad_to_multiple_of=8)
    batch = collator(
        [
            {"input_ids": [1, 2], "attention_mask": [1, 1], "labels": [-100, 2]},
            {
                "input_ids": [3, 4, 5],
                "attention_mask": [1, 1, 1],
                "labels": [-100, 4, 5],
            },
        ]
    )

    assert batch["input_ids"].shape == (2, 8)
    assert batch["labels"][0].tolist() == [-100, 2, -100, -100, -100, -100, -100, -100]
    assert batch["labels"][1].tolist() == [-100, 4, 5, -100, -100, -100, -100, -100]
    assert batch["attention_mask"][0].tolist() == [1, 1, 0, 0, 0, 0, 0, 0]


def test_encoder_refuses_to_silently_truncate_a_target() -> None:
    with pytest.raises(ValueError, match="refusing to truncate the target"):
        encode_training_example(
            FakeTokenizer(),
            {"id": "q-1", "input": "câu hỏi", "target": "SELECT ?x WHERE { ?x ?p ?o }"},
            max_length=5,
        )


def test_oom_fallback_preserves_effective_batch_size() -> None:
    plans = _batch_plans(None)

    assert [plan.per_device_batch_size for plan in plans] == [8, 4, 2, 1]
    assert {
        plan.per_device_batch_size * plan.gradient_accumulation_steps
        for plan in plans
    } == {EFFECTIVE_BATCH_SIZE}


def test_explicit_batch_disables_fallback() -> None:
    assert _batch_plans(2) == (_batch_plans(None)[2],)


def test_smoke_test_cannot_save_an_adapter() -> None:
    with pytest.raises(SystemExit):
        _parse_args(["--smoke-test", "--save-adapter"])


def test_import_enables_expandable_cuda_allocator_by_default() -> None:
    env = os.environ.copy()
    env.pop("PYTORCH_CUDA_ALLOC_CONF", None)

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import os; import ontchatbot.research.llm_lora_training; "
                "print(os.environ['PYTORCH_CUDA_ALLOC_CONF'])"
            ),
        ],
        check=True,
        capture_output=True,
        env=env,
        text=True,
    )

    assert result.stdout.strip() == "expandable_segments:True"


def test_default_lora_profile_is_attention_only_rank_8() -> None:
    args = _parse_args(["--smoke-test", "--batch-size", "1"])
    spec = _lora_spec(args.lora_profile)

    assert args.lora_profile == "attention-r8"
    assert spec.rank == 8
    assert spec.alpha == 16
    assert spec.target_modules == ATTENTION_LORA_TARGET_MODULES
    assert not {"gate_proj", "up_proj", "down_proj"} & set(spec.target_modules)
    assert args.model_profile == "text-only"
    assert args.keep_tied_weight_fp32 is False


def test_legacy_lora_profile_remains_available_for_memory_comparison() -> None:
    args = _parse_args(
        ["--smoke-test", "--batch-size", "1", "--lora-profile", "full-r16"]
    )
    spec = _lora_spec(args.lora_profile)

    assert spec.rank == 16
    assert spec.alpha == 32
    assert {"gate_proj", "up_proj", "down_proj"} <= set(spec.target_modules)


class ToyTiedModel(torch.nn.Module):
    def __init__(self, *, tied: bool) -> None:
        super().__init__()
        self.embedding = torch.nn.Embedding(32, 8, dtype=torch.float32)
        self.lm_head = torch.nn.Linear(8, 32, bias=False, dtype=torch.float32)
        if tied:
            self.lm_head.weight = self.embedding.weight
        for parameter in self.parameters():
            parameter.requires_grad = False

    def get_input_embeddings(self):
        return self.embedding

    def get_output_embeddings(self):
        return self.lm_head


def test_tied_embedding_and_lm_head_can_return_to_compute_dtype() -> None:
    model = ToyTiedModel(tied=True)

    result = _cast_tied_weight_to_dtype(model, torch.bfloat16)

    assert model.embedding.weight is model.lm_head.weight
    assert model.embedding.weight.dtype is torch.bfloat16
    assert result["before_bytes"] == 32 * 8 * 4
    assert result["after_bytes"] == 32 * 8 * 2


def test_tied_weight_cast_refuses_an_untied_lm_head() -> None:
    model = ToyTiedModel(tied=False)

    with pytest.raises(RuntimeError, match="not tied"):
        _cast_tied_weight_to_dtype(model, torch.bfloat16)


class FakeCudaMemory:
    @staticmethod
    def memory_allocated() -> int:
        return 100

    @staticmethod
    def memory_reserved() -> int:
        return 180

    @staticmethod
    def max_memory_allocated() -> int:
        return 150

    @staticmethod
    def max_memory_reserved() -> int:
        return 220

    @staticmethod
    def mem_get_info() -> tuple[int, int]:
        return 900, 1_000

    @staticmethod
    def memory_stats() -> dict[str, int]:
        return {
            "inactive_split_bytes.all.current": 30,
            "inactive_split_bytes.all.peak": 40,
        }


class FakeTorchMemory:
    cuda = FakeCudaMemory()


def test_cuda_memory_record_exposes_allocator_and_physical_memory() -> None:
    record = _cuda_memory_record(FakeTorchMemory(), "after_adapter")

    assert record == {
        "stage": "after_adapter",
        "allocated_bytes": 100,
        "reserved_bytes": 180,
        "reserved_unallocated_bytes": 80,
        "physical_free_bytes": 900,
        "physical_total_bytes": 1_000,
        "peak_allocated_bytes": 150,
        "peak_reserved_bytes": 220,
        "inactive_split_bytes": 30,
        "peak_inactive_split_bytes": 40,
    }
