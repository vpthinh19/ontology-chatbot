"""Fine-tune a supported encoder-decoder model to generate direct SPARQL."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from .benchmark import (
    evaluate_benchmark,
    load_benchmark,
    validate_benchmark,
)
from ..settings import ARTIFACTS_DIR, DATASET_DIR
from .dataset import load_release
from .evaluation import evaluate_predictions
from .reporting import build_dataset_report, sha256_file
from ..runtime.text import normalize_model_input
from ..tools.tokenizer import (
    BARTPHO_MODEL_ID,
    BARTPHO_REVISION,
    DEFAULT_VIT5_TOKENIZER_DIR,
    T5GEMMA_MODEL_ID,
    T5GEMMA_REVISION,
    VIT5_MODEL_ID,
    VIT5_REVISION,
    audit_target_roundtrip,
    prepare_vit5_tokenizer,
    unrepresentable_targets,
)
from ..runtime.sparql import load_ontology

#: Ba model dùng CÙNG một giao thức lô, vì benchmark cuối chỉ so được khi chúng
#: chịu cùng điều kiện.
#:
#: ``eval_batch_size`` phải khai tường minh: mặc định của thư viện là 1, và với
#: ``predict_with_generate`` thì mỗi lần đánh giá sinh tuần tự từng câu.
#:
#: ĐỪNG nâng nó lên vì thấy card còn trống. Đã thử 32 rồi 16 trên L4 24 GB và
#: tràn cả hai lần: khâu huấn luyện (checkpointing tắt) đã giữ ~21 GB khi chạm
#: mốc đánh giá đầu tiên, còn đánh giá thì đòi thêm một khối logits
#: ``lô × 320 × 262.144``. Chỗ trống nhìn thấy lúc epoch 0,3 không phải chỗ
#: trống lúc epoch 2.
#:
#: ``batch_size`` 4 với tích luỹ 2 - lô HIỆU DỤNG vẫn là 8, khớp với đường LLM.
#:
#: Trước đây là lô 8 tích luỹ 1, con số đó là trần đo trên card 6 GB KHI CÒN BẬT
#: checkpointing. Tắt checkpointing trên card 24 GB rồi giữ nguyên lô 8 thì tràn
#: - và tràn không phải vì model to. Bộ nhớ ở đây do ``lô × độ dài × từ điển``
#: quyết định, tức khối logits:
#:
#:     LLM  : lô 4 × 266 token × 248.320  = 264 triệu phần tử  (~2,5 GiB)
#:     T5   : lô 8 × 320 token × 262.144  = 671 triệu phần tử  (~6,2 GiB)
#:
#: Model 540 triệu tham số mà khối logits gấp 2,5 lần model 1,88 tỉ, chỉ vì lô
#: gấp đôi, chuỗi dài hơn và từ điển to hơn. Hạ lô vật lý về 4 đưa nó về ~3,1
#: GiB, ngang đường LLM, mà lô hiệu dụng không đổi nên số đo vẫn so được.
#:
#: ``gradient_checkpointing`` tính lại activation thay vì giữ; nó không đụng tới
#: phép tính, chỉ chậm hơn khoảng một phần tư.
#:
#: Hai giới hạn của thư viện: ``group_by_length`` không còn trong transformers
#: 5.x, và FlashAttention-2 chưa hỗ trợ t5gemma2.
MODEL_SPECS = {
    "bartpho": {
        "model_id": BARTPHO_MODEL_ID,
        "revision": BARTPHO_REVISION,
        "batch_size": 8,
        "eval_batch_size": 6,
        "gradient_accumulation": 1,
        "attention": "sdpa",
        "gradient_checkpointing": False,
    },
    "vit5": {
        "model_id": VIT5_MODEL_ID,
        "revision": VIT5_REVISION,
        "batch_size": 8,
        "eval_batch_size": 6,
        "gradient_accumulation": 1,
        "attention": "eager",
        "gradient_checkpointing": False,
    },
    "t5gemma2": {
        "model_id": T5GEMMA_MODEL_ID,
        "revision": T5GEMMA_REVISION,
        "batch_size": 8,
        "eval_batch_size": 6,
        "gradient_accumulation": 1,
        "attention": "sdpa",
        "gradient_checkpointing": False,
    },
}
MAX_SOURCE_LENGTH = 128
#: Trần CẮT, không phải độ dài đệm: model dừng ở EOS nên nới trần gần như không
#: tốn gì, còn vượt trần thì đích bị cắt giữa chừng và luôn sai - hỏng âm thầm.
#: ViT5 sinh đích dài nhất trong ba model nên nó chạm trần trước. Dataset hiện
#: tại đạt 307 token ViT5 (không tính special token), vì vậy 320 chừa chỗ cho
#: EOS mà không cắt một đích canonical nào.
#:
#: Họ truy vấn trả càng nhiều thông tin thì đích càng dài, nên **sau mỗi lần gộp
#: họ phải đo lại độ dài đích trên cả ba tokenizer**.
MAX_TARGET_LENGTH = 320
LORA_R = 32
LORA_ALPHA = 64
LORA_DROPOUT = 0.0
_LORA_TARGET_SPECS = {
    "bartpho": {
        "prefixes": ("model.encoder.layers.", "model.decoder.layers."),
        "leaves": frozenset(
            {"q_proj", "k_proj", "v_proj", "out_proj", "fc1", "fc2"}
        ),
    },
    "vit5": {
        "prefixes": ("encoder.block.", "decoder.block."),
        "leaves": frozenset({"q", "k", "v", "o", "wi", "wo"}),
    },
    "t5gemma2": {
        "prefixes": (
            "model.encoder.text_model.layers.",
            "model.decoder.layers.",
        ),
        "leaves": frozenset(
            {
                "q_proj",
                "k_proj",
                "v_proj",
                "o_proj",
                "gate_proj",
                "up_proj",
                "down_proj",
            }
        ),
    },
}


def _lora_target_modules(model, model_name: str) -> list[str]:
    """Return equivalent attention/FFN modules for a supported seq2seq model."""

    target_spec = _LORA_TARGET_SPECS[model_name]
    targets = [
        name
        for name, _ in model.named_modules()
        if name.startswith(target_spec["prefixes"])
        and name.rsplit(".", 1)[-1] in target_spec["leaves"]
    ]
    if not targets:
        raise RuntimeError("model does not expose compatible text encoder/decoder modules")
    return targets


def _attach_lora_model(
    model,
    *,
    model_name: str,
    LoraConfig,
    TaskType,
    get_peft_model,
):
    """Freeze the base model and attach the locked seq2seq LoRA adapter."""

    config = LoraConfig(
        task_type=TaskType.SEQ_2_SEQ_LM,
        r=LORA_R,
        lora_alpha=LORA_ALPHA,
        lora_dropout=LORA_DROPOUT,
        bias="none",
        target_modules=_lora_target_modules(model, model_name),
    )
    return get_peft_model(model, config)


#: Lớp KHÔNG được nén.
#:
#: ``lm_head`` buộc chung trọng số với lớp nhúng, nên nén nó là nén luôn bảng
#: nhúng - đúng chỗ đã làm đường chấm 4-bit không bao giờ chạy nổi. Lớp nhúng
#: cũng không phải phép nhân ma trận nên nén nó chẳng nhanh thêm được gì.
_TORCHAO_SKIP = ("lm_head", "embed_tokens", "shared")


def _apply_torchao(model, mode: str) -> int:
    """Nén trọng số NỀN bằng torchao, trả về số lớp đã nén.

    Gọi TRƯỚC khi gắn LoRA: nền bị đóng băng nên nén nó không đụng tới thứ đang
    học, còn adapter thì ở lại bf16 và vẫn nhận gradient bình thường.

    Vì sao torchao chứ không phải bitsandbytes: torchao gói trọng số thành
    tensor subclass mà ``torch.compile`` truy được vào trong, nên phép giải nén
    được fuse thẳng vào matmul. bitsandbytes giải nén thành một lượt riêng ở mỗi
    lượt truyền xuôi - đó là lý do bản 4-bit đo được CHẬM hơn bf16 28% ở khâu
    sinh chữ. Hai thư viện nén cùng một thứ nhưng trả giá ở hai chỗ khác nhau.
    """

    if mode == "off":
        return 0
    from torchao.quantization import (
        Int4WeightOnlyConfig,
        Int8WeightOnlyConfig,
        quantize_,
    )

    config = Int8WeightOnlyConfig() if mode == "int8" else Int4WeightOnlyConfig()
    skipped: list[str] = []
    quantized: list[str] = []

    def keep(module, fully_qualified_name: str) -> bool:
        import torch.nn as nn

        if not isinstance(module, nn.Linear):
            return False
        leaf = fully_qualified_name.rsplit(".", 1)[-1]
        if leaf in _TORCHAO_SKIP or any(part in fully_qualified_name for part in _TORCHAO_SKIP):
            skipped.append(fully_qualified_name)
            return False
        quantized.append(fully_qualified_name)
        return True

    quantize_(model, config, filter_fn=keep)
    print(
        f"torchao {mode}: nén {len(quantized)} lớp, bỏ qua {len(skipped)} "
        f"({', '.join(sorted({n.rsplit('.', 1)[-1] for n in skipped})) or 'không có'})",
        flush=True,
    )
    return len(quantized)


def _stable_gradient_buffers(TrainerCallback, torch):
    """Callback giữ bộ đệm ``.grad`` cố định qua các bước.

    CUDA graph ghi nhớ địa chỉ của mọi tensor nó chạm tới. PyTorch mặc định đặt
    ``.grad`` về ``None`` sau mỗi bước, nên bước sau cấp tensor ở địa chỉ khác
    và graph đọc phải vùng nhớ đã bị ghi đè. Cấp sẵn bộ đệm rồi chỉ ghi số 0 vào
    chúng thì địa chỉ giữ nguyên, nhờ đó tích luỹ gradient dùng chung được với
    CUDA graphs.
    """

    class _Callback(TrainerCallback):
        def on_train_begin(self, args, state, control, model=None, optimizer=None, **kwargs):
            if optimizer is None or model is None:
                return control
            for parameter in model.parameters():
                if parameter.requires_grad and parameter.grad is None:
                    parameter.grad = torch.zeros_like(parameter)
            original = optimizer.zero_grad

            def zero_grad_in_place(set_to_none: bool = True) -> None:
                original(set_to_none=False)

            optimizer.zero_grad = zero_grad_in_place
            return control

    return _Callback()


def _prepare_output_directory(path: Path) -> None:
    if path.exists() and (not path.is_dir() or any(path.iterdir())):
        raise RuntimeError(f"model output directory is not empty: {path}")
    path.mkdir(parents=True, exist_ok=True)


def train(args: argparse.Namespace) -> dict:
    try:
        import numpy as np
        import torch
        import transformers
        from datasets import Dataset
        from huggingface_hub import snapshot_download
        from peft import (
            LoraConfig,
            PeftModel,
            TaskType,
            get_peft_model,
        )
        from transformers import (
            AutoModelForSeq2SeqLM,
            AutoTokenizer,
            DataCollatorForSeq2Seq,
            EarlyStoppingCallback,
            TrainerCallback,
            Seq2SeqTrainer,
            Seq2SeqTrainingArguments,
        )
    except ImportError as exc:  # pragma: no cover - CLI requires train extra.
        raise RuntimeError("install the train extra to fine-tune models") from exc

    spec = dict(MODEL_SPECS[args.model])
    if args.batch_size:
        effective = spec["batch_size"] * spec["gradient_accumulation"]
        spec["batch_size"] = args.batch_size
        # Giữ NGUYÊN lô hiệu dụng: lùi lô vật lý mà không bù thì đổi luôn phép
        # thử, và số đo hết so được với lượt trước.
        spec["gradient_accumulation"] = max(1, effective // args.batch_size)
        spec["eval_batch_size"] = min(spec.get("eval_batch_size", 1), args.batch_size)
    # Chốt MỘT LẦN rồi dùng chung. Ba chỗ cùng đọc cờ này - bật trên model, đưa
    # vào TrainingArguments, và ghi vào metrics - nên để mỗi chỗ tự suy lại là
    # mở đường cho việc sửa một chỗ rồi tưởng đã xong.
    checkpoint_gradients = _should_checkpoint_gradients(
        spec.get("gradient_checkpointing", False), args.gradient_checkpointing
    )
    output_dir = Path(args.output_dir) / args.model
    _prepare_output_directory(output_dir)
    snapshot = Path(
        snapshot_download(
            spec["model_id"],
            revision=spec["revision"],
            local_files_only=args.local_files_only,
        )
    )
    if args.model == "vit5":
        if not (DEFAULT_VIT5_TOKENIZER_DIR / "manifest.json").is_file():
            prepare_vit5_tokenizer(snapshot, DEFAULT_VIT5_TOKENIZER_DIR)
        tokenizer = AutoTokenizer.from_pretrained(
            DEFAULT_VIT5_TOKENIZER_DIR,
            local_files_only=True,
        )
    else:
        tokenizer_kwargs = (
            {"fix_mistral_regex": False} if args.model == "t5gemma2" else {}
        )
        tokenizer = AutoTokenizer.from_pretrained(
            snapshot,
            revision=spec["revision"],
            local_files_only=True,
            trust_remote_code=True,
            **tokenizer_kwargs,
        )

    release = load_release(args.dataset_dir)
    graph = load_ontology()
    dataset_report = build_dataset_report(
        release,
        graph,
        dataset_dir=args.dataset_dir,
    )
    _require_training_ready(
        dataset_report["training_readiness"],
        smoke_test=args.smoke_test,
    )
    rows = release["train"] + release["val"]
    targets = tuple(dict.fromkeys(row["target"] for row in rows))
    audit = audit_target_roundtrip(
        tokenizer, targets, strict=not args.allow_lossy_targets
    )
    lossy = unrepresentable_targets(audit)
    if lossy:
        print(
            f"CẢNH BÁO: tokenizer không tái tạo được {len(lossy)}/{len(targets)} đích "
            f"({len(lossy) / len(targets):.1%}). Model KHÔNG THỂ sinh đúng chúng, "
            "nên mọi con số của lượt này phải nêu kèm giới hạn đó."
        )

    train_rows = release["train"]
    validation_rows = release["val"]
    if args.smoke_test:
        train_rows = _smoke_subset(train_rows, 16)
        validation_rows = _smoke_subset(validation_rows, 8)

    cuda_available = torch.cuda.is_available()
    precision = _precision_policy(
        cuda_available=cuda_available,
        bf16_supported=torch.cuda.is_bf16_supported() if cuda_available else False,
        compute_capability=(
            torch.cuda.get_device_capability() if cuda_available else None
        ),
    )
    model_dtype = getattr(torch, str(precision["dtype"]))
    model = AutoModelForSeq2SeqLM.from_pretrained(
        snapshot,
        local_files_only=True,
        attn_implementation=spec["attention"],
        dtype=model_dtype,
    )
    base_parameter_count = sum(parameter.numel() for parameter in model.parameters())
    quantized_layers = _apply_torchao(model, args.torchao)
    model = _attach_lora_model(
        model,
        model_name=args.model,
        LoraConfig=LoraConfig,
        TaskType=TaskType,
        get_peft_model=get_peft_model,
    )
    trainable_parameter_count = sum(
        parameter.numel() for parameter in model.parameters() if parameter.requires_grad
    )
    cache_config = _generation_cache_config(model.config)
    cache_config.use_cache = False
    _configure_greedy_generation(model.generation_config)
    if checkpoint_gradients:
        model.gradient_checkpointing_enable(
            gradient_checkpointing_kwargs={"use_reentrant": False}
        )
    train_dataset = _tokenized_dataset(Dataset, train_rows, tokenizer)
    validation_dataset = _tokenized_dataset(Dataset, validation_rows, tokenizer)
    steps_per_epoch = math.ceil(
        len(train_rows) / (spec["batch_size"] * spec["gradient_accumulation"])
    )
    eval_steps = max(1, round(steps_per_epoch * args.eval_every_epochs))
    short_run = args.smoke_test

    keep_checkpoints = args.save_model and not short_run
    effective_max_steps = _effective_max_steps(
        smoke_test=args.smoke_test,
        requested_steps=args.max_steps,
        train_records=len(train_rows),
        batch_size=spec["batch_size"],
        gradient_accumulation=spec["gradient_accumulation"],
    )
    training_args = Seq2SeqTrainingArguments(
        output_dir=str(output_dir),
        num_train_epochs=args.epochs,
        max_steps=effective_max_steps,
        per_device_train_batch_size=spec["batch_size"],
        per_device_eval_batch_size=spec.get("eval_batch_size", 1),
        gradient_accumulation_steps=spec["gradient_accumulation"],
        learning_rate=args.learning_rate,
        **_optimization_arguments(precision),
        gradient_checkpointing=checkpoint_gradients,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        eval_strategy="no" if short_run else "steps",
        eval_steps=eval_steps,
        save_strategy="steps" if keep_checkpoints else "no",
        save_steps=eval_steps,
        save_total_limit=1 if keep_checkpoints else None,
        save_only_model=True,
        load_best_model_at_end=keep_checkpoints,
        # Chọn checkpoint bằng MẤT MÁT trên tập held-out, không bằng
        # ``answer_exact_rate``. Hai lý do, cái nào cũng đủ:
        #
        # Một, giá. Sinh chữ cho cả 400 câu val mất 15,6 phút mỗi lượt trên L4 -
        # 47 trong 76 phút của lượt chạy là khâu đánh giá. Một lượt truyền xuôi
        # tính mất mát thì rẻ hơn hàng chục lần vì nó không giải mã tuần tự.
        #
        # Hai, nhất quán. ``docs/EVALUATION.md`` ghi rõ ``answer_exact_rate``
        # chỉ là chỉ số CHẨN ĐOÁN, không phải chỉ số chính - mà nó lại đang là
        # thứ quyết định giữ checkpoint nào.
        #
        # Đo trên lượt t5gemma2 17/8, ba mốc, ``eval_loss`` xếp hạng đúng như
        # chất lượng thật: 0,0319→0,6225 · 0,0171→0,7925 · 0,0105→0,8175. Điểm
        # sinh chữ vẫn được đo MỘT LẦN sau khi train xong, ngay bên dưới.
        metric_for_best_model="eval_loss",
        greater_is_better=False,
        logging_strategy="steps",
        logging_steps=1 if args.smoke_test else 50,
        disable_tqdm=True,
        report_to="none",
        seed=args.seed,
        data_seed=args.seed,
        predict_with_generate=False,
        # BẮT BUỘC đi kèm ``predict_with_generate=False``. Thiếu nó thì Trainer
        # gom logits của cả tập val để đưa cho ``compute_metrics``: 400 câu ×
        # 192 vị trí × 262.144 token từ điển, tức hàng chục GB - tràn ngay, mà
        # lại tràn ở lượt đánh giá đầu tiên chứ không phải lúc khởi động.
        prediction_loss_only=True,
        generation_max_length=MAX_TARGET_LENGTH,
        generation_num_beams=1,
        torch_compile=args.compile,
        # ``max-autotune`` KHÔNG dùng được ở đây: nó kéo theo CUDA graphs, mà
        # CUDA graphs xung khắc với tích luỹ gradient - bộ đệm ``.grad`` bị bắt
        # vào graph rồi ghi đè ở micro-batch sau, và lượt chạy chết giữa chừng
        # với "accessing gradient tensor output of CUDAGraphs that has been
        # overwritten". Đã đo: chết ở ngay lượt truyền ngược đầu tiên.
        #
        # Bản ``-no-cudagraphs`` giữ phần tự dò kernel của Inductor mà bỏ phần
        # graph. Trên card này phần tự dò GEMM cũng bị bỏ qua ("Not enough SMs
        # to use max_autotune_gemm"), nên thứ còn lại chủ yếu là fuse kernel.
        torch_compile_mode=args.compile_mode if args.compile else None,
    )
    source_pad, target_pad = _fixed_pad_lengths(train_dataset, validation_dataset)

    class _FixedShapeCollator(DataCollatorForSeq2Seq):
        """Đệm MỌI lô về cùng một hình dạng, nguồn và đích đệm riêng.

        Bộ gom lô sẵn có đệm theo câu dài nhất TRONG LÔ, nên mỗi lô một hình
        dạng. Lớp này đệm nhãn tới ``target_pad`` trước rồi để lớp cha đệm nguồn
        tới ``source_pad`` - hai độ dài khác nhau, vì dùng chung một độ dài thì
        nguồn (dài nhất 43 token) bị kéo lên bằng đích (186).
        """

        def __call__(self, features, return_tensors=None):
            for feature in features:
                labels = list(feature["labels"])
                feature["labels"] = labels + [self.label_pad_token_id] * (
                    target_pad - len(labels)
                )
            return super().__call__(features, return_tensors)

    collator = _FixedShapeCollator(
        tokenizer,
        model=model,
        padding="max_length",
        max_length=source_pad,
        pad_to_multiple_of=None,
        label_pad_token_id=-100,
    )
    trainer = Seq2SeqTrainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=validation_dataset,
        data_collator=collator,
        processing_class=tokenizer,
        callbacks=(
            [EarlyStoppingCallback(early_stopping_patience=3)]
            if keep_checkpoints
            else None
        ),
    )
    if args.compile and spec["gradient_accumulation"] > 1:
        trainer.add_callback(_stable_gradient_buffers(TrainerCallback, torch))

    if torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()
    try:
        train_result = trainer.train()
    except (torch.OutOfMemoryError, RuntimeError) as exc:
        # HẾT BỘ NHỚ THÌ NÓI RÕ PHẢI LÀM GÌ, đừng để người chạy tự đoán.
        #
        # Đường LLM tự lùi lô rồi bù bằng tích luỹ gradient; đường này chưa làm
        # được vậy vì Trainer đã dựng xong trạng thái trước khi bước đầu chạy.
        # Nhưng ít nhất nó phải chỉ đúng hai cần gạt, thay vì ném ra một vệt
        # traceback của torch rồi để người chạy mò.
        if "out of memory" not in str(exc).casefold():
            raise
        raise RuntimeError(
            "CUDA hết bộ nhớ khi huấn luyện "
            f"({args.model}, lô {spec['batch_size']}, "
            f"checkpointing {checkpoint_gradients}, "
            f"lô đánh giá {spec.get('eval_batch_size')}).\n"
            "Thử theo thứ tự:\n"
            "  --gradient-checkpointing on   (đổi ~1/4 tốc độ lấy bộ nhớ, "
            "KHÔNG đổi kết quả)\n"
            "  --batch-size 4                (lô hiệu dụng vẫn giữ 8 nhờ "
            "tích luỹ gradient)"
        ) from None
    inference_model = trainer.model
    adapter_source = trainer.state.best_model_checkpoint
    if adapter_source is None and args.torchao != "off":
        # Gộp LoRA vào một nền ĐÃ NÉN thì PEFT dừng lại: nó không biết nén lại
        # lớp nền sau khi cộng adapter vào ("TorchaoLoraLinear was instantiated
        # without get_apply_tensor_subclass"). Lối ra là dựng lại trên nền bf16
        # sạch - cũng chính là thứ nên đem đi phục vụ, vì bản gộp lúc đó không
        # đòi torchao có mặt ở máy chạy thật.
        #
        # Adapter học trên nền đã nén rồi gộp vào nền bf16 là ĐỔI nền một chút,
        # đúng như QLoRA vẫn làm. Bản ghi khai rõ ``torchao`` của lượt train nên
        # người đọc số biết điều đó.
        adapter_source = str(output_dir / "adapter-final")
        inference_model.save_pretrained(adapter_source)
    if adapter_source:
        # Rebuild the accepted adapter on a clean pretrained base. The final artifact
        # is merged below, so runtime never needs to load PEFT separately.
        trainer.model = None
        trainer.model_wrapped = None
        del inference_model
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        inference_base = AutoModelForSeq2SeqLM.from_pretrained(
            snapshot,
            local_files_only=True,
            attn_implementation=spec["attention"],
            dtype=model_dtype,
            trust_remote_code=True,
        )
        inference_model = PeftModel.from_pretrained(
            inference_base,
            adapter_source,
            is_trainable=False,
        ).to(training_args.device)
    inference_model = inference_model.merge_and_unload()
    _configure_greedy_generation(inference_model.generation_config)
    decoded = _generate_rows(
        inference_model,
        tokenizer,
        validation_rows,
        torch,
        batch_size=spec.get("eval_batch_size", 1),
    )
    report = evaluate_predictions(validation_rows, decoded, graph, include_cases=True)
    report["training"] = {
        "model": args.model,
        "model_id": spec["model_id"],
        "revision": spec["revision"],
        "seed": args.seed,
        "epochs": args.epochs,
        "max_steps": effective_max_steps,
        "train_records": len(train_rows),
        "validation_records": len(validation_rows),
        "dataset_records": dataset_report["dataset"]["records"],
        "dataset_manifest_sha256": sha256_file(args.dataset_dir / "manifest.json"),
        "batch_size": spec["batch_size"],
        "gradient_accumulation": spec["gradient_accumulation"],
        "source_pad_length": source_pad,
        "target_pad_length": target_pad,
        "dtype": precision["dtype"],
        "bf16": precision["bf16"],
        "fp16": precision["fp16"],
        "tf32": precision["tf32"],
        "torch_compile": bool(training_args.torch_compile),
        "torchao": args.torchao,
        "torchao_quantized_layers": quantized_layers,
        "torch_compile_mode": training_args.torch_compile_mode,
        "checkpoint_selection_metric": training_args.metric_for_best_model,
        "eval_generates_text": bool(training_args.predict_with_generate),
        "eval_batch_size": spec.get("eval_batch_size", 1),
        "gradient_checkpointing_spec": spec.get("gradient_checkpointing", False),
        "gradient_checkpointing": checkpoint_gradients,
        "generation_do_sample": False,
        "dropout_policy": "checkpoint_default",
        "fine_tuning_method": "peft_lora",
        "lora_rank": LORA_R,
        "lora_alpha": LORA_ALPHA,
        "lora_dropout": LORA_DROPOUT,
        "lora_target_modules": len(
            _lora_target_modules(inference_model, args.model)
        ),
        "trainable_parameters": trainable_parameter_count,
        "base_parameters": base_parameter_count,
        "merged_artifact": True,
        # Đọc THẲNG từ cấu hình đã đưa vào Trainer. Chép tay vào đây là cách
        # bản ghi nói dối: optimizer đã đổi sang fused mà ô này vẫn ghi 8-bit,
        # và người đọc log không có cách nào biết. Cùng lỗi với cờ
        # checkpointing, lần thứ ba trong một phiên.
        **{
            key: value
            for key, value in _optimization_arguments(precision).items()
            if key in ("optim", "lr_scheduler_type", "warmup_steps", "weight_decay")
        },
        "learning_rate": args.learning_rate,
        "evaluation_every_epochs": args.eval_every_epochs,
        "early_stopping_patience": 3 if keep_checkpoints else None,
        "train_runtime_seconds": round(train_result.metrics.get("train_runtime", 0.0), 3),
        "train_loss": round(train_result.metrics.get("train_loss", 0.0), 6),
        "peak_vram_bytes": torch.cuda.max_memory_allocated() if torch.cuda.is_available() else None,
        "peak_vram_reserved_bytes": torch.cuda.max_memory_reserved() if torch.cuda.is_available() else None,
        "best_checkpoint": trainer.state.best_model_checkpoint,
        "smoke_test": args.smoke_test,
        "unrepresentable_targets": len(lossy),
        "distinct_targets": len(targets),
        "torch_version": torch.__version__,
        "transformers_version": transformers.__version__,
        "gpu": torch.cuda.get_device_name() if torch.cuda.is_available() else None,
    }
    report["training_log"] = trainer.state.log_history
    metrics_path = output_dir / "metrics.json"
    metrics_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.save_model:
        inference_model.save_pretrained(output_dir / "model")
        tokenizer.save_pretrained(output_dir / "model")
    if args.benchmark_after_training:
        benchmark_rows = load_benchmark()
        benchmark_validation = validate_benchmark(
            benchmark_rows,
            graph,
            training_rows=release["train"],
        )
        benchmark_decoded = _generate_rows(
            inference_model,
            tokenizer,
            benchmark_rows,
            torch,
            batch_size=spec.get("eval_batch_size", 1),
        )
        benchmark_predictions = dict(
            zip(
                (row["id"] for row in benchmark_rows),
                benchmark_decoded,
                strict=True,
            )
        )
        benchmark_report = evaluate_benchmark(
            benchmark_rows,
            benchmark_predictions,
            graph,
            include_cases=True,
        )
        benchmark_report["benchmark"] = benchmark_validation
        (output_dir / "benchmark_metrics.json").write_text(
            json.dumps(benchmark_report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (output_dir / "benchmark_predictions.jsonl").write_text(
            "".join(
                json.dumps(
                    {"id": row["id"], "prediction": prediction},
                    ensure_ascii=False,
                )
                + "\n"
                for row, prediction in zip(
                    benchmark_rows,
                    benchmark_decoded,
                    strict=True,
                )
            ),
            encoding="utf-8",
        )
        print(
            json.dumps(
                {"benchmark_overall": benchmark_report["overall"]},
                ensure_ascii=False,
                indent=2,
            )
        )
    print(json.dumps({"overall": report["overall"], "training": report["training"], "metrics": str(metrics_path)}, ensure_ascii=False, indent=2))
    return report


def _tokenized_dataset(Dataset, rows, tokenizer):
    dataset = Dataset.from_dict(
        {
            "source": [normalize_model_input(row["input"]) for row in rows],
            "target": [row["target"] for row in rows],
        }
    )

    def tokenize(batch):
        encoded = tokenizer(
            batch["source"],
            max_length=MAX_SOURCE_LENGTH,
            truncation=True,
        )
        labels = tokenizer(
            text_target=batch["target"],
            max_length=MAX_TARGET_LENGTH,
            truncation=True,
        )["input_ids"]
        encoded["labels"] = [
            _ensure_eos_token(ids, tokenizer.eos_token_id, MAX_TARGET_LENGTH)
            for ids in labels
        ]
        return encoded

    return dataset.map(tokenize, batched=True, remove_columns=["source", "target"])


#: Bội số để làm tròn độ dài đệm cố định.
#:
#: Hình dạng cố định là điều kiện để ``torch.compile`` có ích: đệm động làm mỗi
#: lô một hình dạng khác, và bản biên dịch bị vứt đi rồi dựng lại liên tục - đó
#: chính là lý do lần thử compile trước trên đường LLM không xong nổi 60 bước
#: trong thời gian bản thường chạy hết.
PAD_MULTIPLE = 64


def _fixed_pad_lengths(*datasets) -> tuple[int, int]:
    """Độ dài đệm cố định, đo TỪ DỮ LIỆU chứ không đặt tay.

    Đệm tới TRẦN CẮT (128 · 320) là phình nguồn chín lần và đích hai lần - phần
    tính thêm đó lớn hơn mọi thứ compile tiết kiệm được. Đệm tới độ dài thật lớn
    nhất, làm tròn lên bội số 64, thì gần như miễn phí mà hình dạng vẫn cố định.

    Đo từ dữ liệu chứ không ghim hằng số vì hằng số sẽ mục: thêm một câu dài hơn
    là đích bị cắt cụt, và câu bị cắt thì luôn sai mà không có lỗi nào báo.
    """

    longest_source = 0
    longest_target = 0
    for dataset in datasets:
        for row in dataset:
            longest_source = max(longest_source, len(row["input_ids"]))
            longest_target = max(longest_target, len(row["labels"]))
    return (
        min(MAX_SOURCE_LENGTH, math.ceil(longest_source / PAD_MULTIPLE) * PAD_MULTIPLE),
        min(MAX_TARGET_LENGTH, math.ceil(longest_target / PAD_MULTIPLE) * PAD_MULTIPLE),
    )


def _ensure_eos_token(
    ids: list[int], eos_token_id: int | None, max_length: int
) -> list[int]:
    """Terminate target labels even when a tokenizer only inserts BOS."""

    if eos_token_id is None:
        raise ValueError("a seq2seq target tokenizer must define eos_token_id")
    output = list(ids)
    if output and output[-1] == eos_token_id:
        return output
    if len(output) >= max_length:
        output[-1] = eos_token_id
    else:
        output.append(eos_token_id)
    return output


def _configure_greedy_generation(config) -> None:
    """Remove inherited sampling settings from structured generation."""

    config.do_sample = False
    config.top_p = None
    config.top_k = None


def _generation_cache_config(config):
    """Return the config object that owns ``use_cache``.

    Conventional seq2seq models expose it on the top-level config, whereas
    T5Gemma2 keeps it on its decoder config.
    """

    if hasattr(config, "use_cache"):
        return config
    decoder = getattr(config, "decoder", None)
    if decoder is None or not hasattr(decoder, "use_cache"):
        raise AttributeError("seq2seq model config does not expose use_cache")
    return decoder


def _generate_rows(model, tokenizer, rows, torch, *, batch_size: int) -> list[str]:
    """Generate from a normally reloaded checkpoint, independent of Trainer state."""

    model.eval()
    cache_config = _generation_cache_config(model.config)
    use_cache = cache_config.use_cache
    cache_config.use_cache = True
    predictions = []
    try:
        # ``no_grad`` chứ không phải ``inference_mode``: tensor của chế độ suy
        # luận không mang bộ đếm phiên bản, thứ mà model đã gộp LoRA cần khi sinh.
        with torch.no_grad():
            for offset in range(0, len(rows), batch_size):
                batch = rows[offset : offset + batch_size]
                encoded = tokenizer(
                    [normalize_model_input(row["input"]) for row in batch],
                    max_length=MAX_SOURCE_LENGTH,
                    truncation=True,
                    padding=True,
                    pad_to_multiple_of=8,
                    return_tensors="pt",
                ).to(model.device)
                output = model.generate(
                    **encoded,
                    max_length=MAX_TARGET_LENGTH,
                    num_beams=1,
                    do_sample=False,
                )
                predictions.extend(
                    text.strip()
                    for text in tokenizer.batch_decode(output, skip_special_tokens=True)
                )
    finally:
        cache_config.use_cache = use_cache
    return predictions


def _smoke_subset(rows: list[dict[str, str]], limit: int) -> list[dict[str, str]]:
    selected = []
    seen_targets = set()
    for row in sorted(rows, key=lambda item: len(item["target"]), reverse=True):
        if row["target"] in seen_targets:
            continue
        selected.append(row)
        seen_targets.add(row["target"])
        if len(selected) == limit:
            break
    return selected


def _effective_max_steps(
    *,
    smoke_test: bool,
    requested_steps: int,
    train_records: int,
    batch_size: int,
    gradient_accumulation: int,
) -> int:
    if not smoke_test:
        return requested_steps
    return math.ceil(train_records / (batch_size * gradient_accumulation))


def _require_training_ready(
    readiness: dict,
    *,
    smoke_test: bool,
) -> None:
    if readiness.get("ready") or smoke_test:
        return
    codes = [gap.get("code", "unknown") for gap in readiness.get("gaps", [])]
    raise RuntimeError(
        "dataset is not ready for full training: " + ", ".join(codes)
    )


def _should_checkpoint_gradients(spec_default: bool, choice: str = "auto") -> bool:
    """Bỏ activation để tính lại, hay giữ - hỏi theo VRAM của máy đang chạy.

    ``MODEL_SPECS`` bật sẵn cho MỌI model vì lúc soạn chỉ có card 6 GB, và chính
    ghi chú ở đó nói nó "chậm hơn khoảng một phần tư". Trên card 24 GB thì đó là
    trả một phần tư tốc độ để mua bộ nhớ đang thừa. Đường LLM đã tự tắt theo
    VRAM từ trước; đường này thì chưa, nên cùng một dự án chạy hai kiểu.

    Kết quả huấn luyện không đổi: checkpointing chỉ tính lại activation, không
    đụng tới phép tính.
    """

    if choice == "on":
        return True
    if choice == "off":
        return False
    try:
        import torch
    except ImportError:
        return spec_default
    if not torch.cuda.is_available():
        return spec_default
    return torch.cuda.get_device_properties(0).total_memory < 16 * 1024**3


def _precision_policy(
    *,
    cuda_available: bool,
    bf16_supported: bool,
    compute_capability: tuple[int, int] | None,
) -> dict[str, str | bool]:
    bf16 = cuda_available and bf16_supported
    return {
        "dtype": "bfloat16" if bf16 else "float16" if cuda_available else "float32",
        "bf16": bf16,
        "fp16": cuda_available and not bf16,
        "tf32": cuda_available
        and compute_capability is not None
        and compute_capability[0] >= 8,
    }


def _optimization_arguments(
    precision: dict[str, str | bool],
) -> dict[str, object]:
    return {
        "lr_scheduler_type": "cosine",
        "warmup_steps": 0.1,
        "weight_decay": 0.005,
        # Đo trên đường LLM, 60 bước: adamw_torch 4,902 · fused 4,914 · 8-bit
        # 4,940 giây/bước - chênh 0,8%, tức nhiễu. LoRA chỉ chỉnh vài triệu tham
        # số nên trạng thái optimizer quá nhỏ để việc nén nó đổi được gì, và
        # bản 8-bit kéo theo bitsandbytes vào một đường vốn không cần.
        "optim": "adamw_torch_fused",
        "bf16": precision["bf16"],
        "fp16": precision["fp16"],
        "tf32": precision["tf32"],
    }


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=sorted(MODEL_SPECS), required=True)
    parser.add_argument("--dataset-dir", type=Path, default=DATASET_DIR)
    parser.add_argument("--output-dir", type=Path, default=ARTIFACTS_DIR / "models")
    # Mất mát về 0 từ khoảng epoch 15; thêm epoch không đổi kết quả.
    parser.add_argument("--epochs", type=float, default=16.0)
    parser.add_argument("--max-steps", type=int, default=-1)
    # Lô của seq2seq trước đây ghim cứng trong MODEL_SPECS, không có đường lùi.
    # Card 6 GB tràn ngay ở lô 8 và chết hẳn - trong khi đường LLM tự lùi lô rồi
    # bù bằng tích luỹ gradient. Cùng một dự án mà hai đường xử lý hết bộ nhớ
    # theo hai kiểu là chỗ để người chạy mất một lượt máy thuê.
    parser.add_argument(
        "--gradient-checkpointing",
        choices=("auto", "on", "off"),
        default="auto",
        help="auto: bật khi VRAM dưới 16 GiB. Bật thì chậm hơn ~1/4 mà tốn ít bộ nhớ hơn hẳn",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=None,
        help="ép lô vật lý; bỏ trống thì lấy theo model và tự lùi khi tràn",
    )
    parser.add_argument("--learning-rate", type=float, default=1e-4)
    # Mỗi lần đánh giá phải sinh lại toàn tập val, nên nhịp thưa mà vẫn đủ mốc.
    parser.add_argument("--eval-every-epochs", type=float, default=4.0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--torchao",
        choices=("off", "int8", "int4"),
        default="int8",
        help=(
            "nén trọng số NỀN bằng torchao. Đi cặp với --compile: tensor "
            "subclass của torchao cho compile fuse phép giải nén vào matmul"
        ),
    )
    parser.add_argument(
        "--compile",
        action="store_true",
        help=(
            "biên dịch model bằng torch.compile(max-autotune). Chỉ có ích khi "
            "hình dạng lô cố định, và bản biên dịch tốn vài phút hâm nóng - "
            "PHẢI đo mới biết nó lãi hay lỗ trên card của bạn"
        ),
    )
    parser.add_argument(
        "--compile-mode",
        default="max-autotune",
        help="chế độ torch.compile; mặc định bỏ CUDA graphs vì chúng xung khắc với tích luỹ gradient",
    )
    parser.add_argument("--smoke-test", action="store_true")
    parser.add_argument("--save-model", action="store_true")
    parser.add_argument("--benchmark-after-training", action="store_true")
    parser.add_argument("--local-files-only", action="store_true")
    # Cho phép huấn luyện một model KHÔNG biểu diễn nổi mọi đích. Mặc định tắt:
    # trần trên của nó bị chặn trước khi học, nên con số thu được không so thẳng
    # với model biểu diễn được đủ. Số đích hỏng được ghi vào metrics.
    parser.add_argument("--allow-lossy-targets", action="store_true")
    args = parser.parse_args(argv)
    if args.benchmark_after_training and not args.save_model:
        parser.error("--benchmark-after-training requires --save-model")
    if args.benchmark_after_training and args.smoke_test:
        parser.error("benchmark is only available after a full training run")
    return args


def main() -> None:
    train(_parse_args())


if __name__ == "__main__":
    main()
