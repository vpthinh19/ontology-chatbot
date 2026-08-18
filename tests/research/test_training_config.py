"""Ghim cấu hình huấn luyện vào đúng những giá trị đã đo.

Mỗi con số dưới đây đến từ một phép đo, không từ một lựa chọn mặc định của thư
viện. Đổi bất kỳ giá trị nào là đổi phép thử, nên số của lượt chạy sau không còn
đặt cạnh lượt trước được - phép kiểm này bắt việc đó xảy ra âm thầm.
"""

from __future__ import annotations

from ontchatbot.research.training import (
    COMPILE_MODE,
    EVAL_EVERY_EPOCHS,
    MAX_SOURCE_LENGTH,
    MAX_TARGET_LENGTH,
    MODEL_SPECS,
    PAD_MULTIPLE,
    _optimization_arguments,
    _parse_args,
)

#: Lô hiệu dụng phải như nhau ở mọi model, nếu không benchmark so bốn model với
#: nhau là so ba phép thử khác nhau.
EFFECTIVE_BATCH = 8

#: Cỡ lô bộ chấm dùng; khâu đánh giá phải khớp để hai đường cùng điều kiện.
SCORER_BATCH = 16


def test_every_model_trains_at_the_same_effective_batch() -> None:
    for name, spec in MODEL_SPECS.items():
        effective = spec["batch_size"] * spec["gradient_accumulation"]
        assert effective == EFFECTIVE_BATCH, name


def test_evaluation_batch_matches_the_scorer() -> None:
    """Lô đánh giá chi phối cả các lượt đánh giá lẫn lượt sinh chữ cuối lượt
    chạy. Để nó nhỏ hơn lô của bộ chấm là đo cùng một việc bằng hai điều kiện."""

    for name, spec in MODEL_SPECS.items():
        assert spec["eval_batch_size"] == SCORER_BATCH, name


def test_settled_configuration_is_not_a_command_line_choice() -> None:
    """Quyết định đã đo xong thì là hằng số, không phải cờ.

    Một cờ cho quyết định đã chốt là một cách để vô tình chạy cấu hình chưa ai
    đo, và để hai lượt chạy khác nhau mà không ai nhận ra.
    """

    args = _parse_args(["--model", "t5gemma2"])
    settled = {"torchao", "compile_mode", "eval_every_epochs", "gradient_checkpointing"}

    assert settled.isdisjoint(vars(args))


def test_defaults_match_the_measured_run() -> None:
    args = _parse_args(["--model", "t5gemma2"])

    # Trần chứ không phải đích: chất lượng còn lên ở epoch 3 của lượt đo, và
    # dừng sớm mới là thứ quyết định lượt chạy kết thúc ở đâu.
    assert args.epochs == 8.0
    assert args.learning_rate == 1e-4
    assert args.seed == 42
    # Biên dịch bật sẵn; tắt được vì có model không biên dịch nổi, và mất tốc độ
    # vẫn hơn mất cả một model trong lượt chạy.
    assert args.compile is True
    assert _parse_args(["--model", "t5gemma2", "--no-compile"]).compile is False


def test_compilation_and_evaluation_are_pinned() -> None:
    # ``max-autotune`` cần nhiều SM hơn các card đang dùng có, nên phần đắt nhất
    # của nó không chạy và chỉ còn lại thời gian biên dịch.
    assert COMPILE_MODE == "reduce-overhead"
    # Nhịp thưa hơn số epoch của một lượt chạy nghĩa là không có mốc nào giữa
    # chừng, và việc chọn checkpoint mất hết ý nghĩa.
    assert EVAL_EVERY_EPOCHS <= _parse_args(["--model", "t5gemma2"]).epochs


def test_checkpoint_is_chosen_without_generating_text() -> None:
    """Sinh chữ để chọn checkpoint tốn gấp hàng chục lần một lượt truyền xuôi."""

    from ontchatbot.research import training

    source = training.train.__code__.co_consts
    flattened = " ".join(str(c) for c in source)

    assert "eval_loss" in flattened


def test_padding_is_fixed_and_rounded() -> None:
    """Hình dạng cố định là điều kiện để biên dịch có ích: đệm động làm mỗi lô
    một hình dạng, và bản biên dịch bị dựng lại liên tục."""

    assert PAD_MULTIPLE == 64
    assert MAX_SOURCE_LENGTH % PAD_MULTIPLE == 0
    assert MAX_TARGET_LENGTH % PAD_MULTIPLE == 0


def test_optimizer_choice_stays_fused() -> None:
    precision = {"bf16": True, "fp16": False, "tf32": True, "dtype": "bfloat16"}

    arguments = _optimization_arguments(precision)

    assert arguments["optim"] == "adamw_torch_fused"
    assert arguments["lr_scheduler_type"] == "cosine"


def test_only_the_lossy_tokenizers_are_allowed_to_skip_the_round_trip() -> None:
    """Model nào tái tạo được mọi đích thì phép kiểm phải còn chặt: đó là thứ
    duy nhất bắt được một đích hỏng âm thầm khi dataset đổi."""

    lossy = {n for n, s in MODEL_SPECS.items() if s.get("allow_lossy_targets")}

    assert lossy == {"vit5", "bartpho"}
