"""Chấm LLM và seq2seq trên cùng bộ benchmark.

Ví dụ nhắc kèm lấy từ train, câu chấm lấy từ val - không rò rỉ. Dùng cùng hàm
đánh giá với các lượt seq2seq nên con số đặt cạnh nhau được.

"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Sequence

import torch
from transformers import (
    AutoConfig,
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
)

from ontchatbot.research.evaluation import evaluate_predictions
from ontchatbot.research.llm_lora_training import (
    MODEL_ID,
    MODEL_REVISION,
    SYSTEM_PROMPT,
    _is_cuda_oom,
)
from ontchatbot.runtime.llm import (
    FineTunedQueryGenerator,
    LLMQueryGenerator,
    load_examples,
)
from ontchatbot.runtime.sparql import load_ontology
from ontchatbot.settings import ARTIFACTS_DIR, DATASET_DIR



def _pinned_revision(model_id: str) -> str | None:
    """Bản model đã ghim cho ``model_id``, hoặc ``None`` nếu không ghim."""

    return MODEL_REVISION if model_id == MODEL_ID else None


def base_precision_for_adapter(adapter, requested: str) -> str:
    """Chọn độ chính xác của trọng số gốc, mặc định theo adapter.

    Adapter phải được chấm trên cùng cấu hình trọng số với lúc huấn luyện.
    """

    if requested != "match-adapter":
        return requested
    if adapter is None:
        return "bf16"
    metrics = Path(adapter) / "training_metrics.json"
    if not metrics.exists():
        raise RuntimeError(
            f"{metrics} không có, nên không biết adapter đã học trên nền trọng "
            "số nào. Đoán bừa là chấm một model khác với model đã huấn luyện. "
            "Chỉ rõ bằng --base-precision 4bit hoặc --base-precision bf16."
        )
    quantization = json.loads(metrics.read_text(encoding="utf-8")).get("quantization")
    return "4bit" if quantization and "4-bit" in quantization else "bf16"


def fine_tuned_prompt(tokenizer, question: str) -> str:
    """Bọc câu hỏi theo khuôn huấn luyện.

    ``question`` phải được chuẩn hóa trước khi gọi hàm này.
    """

    return tokenizer.apply_chat_template(
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ],
        add_generation_prompt=True,
        tokenize=False,
        enable_thinking=False,
    )



class _Seq2SeqGenerator:
    """Cho checkpoint seq2seq đi qua cùng bộ chấm với LLM.

    Dùng lại đường sinh của huấn luyện để giữ nhất quán chuẩn hóa, đệm và cắt chuỗi.
    """

    def __init__(self, model, tokenizer, batch_size: int) -> None:
        self._model = model
        self._tokenizer = tokenizer
        self._batch_size = max(1, batch_size)

    def generate_many(self, texts):
        from ontchatbot.research.training import _generate_rows

        return _generate_rows(
            self._model,
            self._tokenizer,
            [{"input": text} for text in texts],
            torch,
            batch_size=self._batch_size,
        )

    def generate(self, text: str) -> str:
        return self.generate_many([text])[0]


def _seq2seq_generator(model_dir, batch_size: int) -> _Seq2SeqGenerator:
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(model_dir, local_files_only=True)
    model = AutoModelForSeq2SeqLM.from_pretrained(model_dir, local_files_only=True)
    if torch.cuda.is_available():
        model = model.to("cuda")
    return _Seq2SeqGenerator(model, tokenizer, batch_size)


def _seq2seq_adapter_generator(adapter_dir, batch_size: int) -> _Seq2SeqGenerator:
    """Nạp và gộp adapter LoRA seq2seq trên model gốc đã ghim.

    Cấu hình sinh phải tất định và model gốc phải cùng bản với lúc huấn luyện.
    """
    from huggingface_hub import snapshot_download
    from peft import PeftModel
    from transformers import AutoModelForSeq2SeqLM

    from ontchatbot.research.training import (
        MODEL_SPECS,
        _configure_greedy_generation,
    )

    adapter_dir = Path(adapter_dir)
    config = json.loads((adapter_dir / "adapter_config.json").read_text("utf-8"))
    trained_on = str(config.get("base_model_name_or_path", ""))
    family = next(
        (
            name
            for name, spec in MODEL_SPECS.items()
            if spec["model_id"] in trained_on
            or spec["model_id"].replace("/", "--") in trained_on
        ),
        None,
    )
    if family is None:
        raise SystemExit(
            f"không nhận ra model gốc của adapter này: {trained_on!r}\n"
            f"biết các họ: {', '.join(MODEL_SPECS)}"
        )
    spec = MODEL_SPECS[family]
    if spec["revision"] not in trained_on:
        print(
            f"CẢNH BÁO: adapter học trên {trained_on!r}, mà bản đã ghim là "
            f"{spec['revision']}. Số đo sẽ không so được.",
            flush=True,
        )

    snapshot = snapshot_download(
        spec["model_id"], revision=spec["revision"], local_files_only=True
    )
    tokenizer = AutoTokenizer.from_pretrained(adapter_dir, local_files_only=True)
    dtype = torch.bfloat16 if torch.cuda.is_available() else torch.float32
    base = AutoModelForSeq2SeqLM.from_pretrained(
        snapshot,
        local_files_only=True,
        attn_implementation=spec["attention"],
        dtype=dtype,
    )
    model = PeftModel.from_pretrained(base, adapter_dir, is_trainable=False)
    model = model.merge_and_unload()
    _configure_greedy_generation(model.generation_config)
    if torch.cuda.is_available():
        model = model.to("cuda")
    print(f"nền: {family} @ {spec['revision'][:12]} · LoRA: {adapter_dir}", flush=True)
    return _Seq2SeqGenerator(model, tokenizer, batch_size)


def build_complete(
    model_id: str,
    max_new_tokens: int,
    gpu_memory: str = "",
    load_4bit: bool = False,
    allow_download: bool = False,
    adapter=None,
    batch_size: int = 1,
):
    # ``batch_size`` có thể giảm khi thiếu bộ nhớ GPU.
    batch_size = max(1, batch_size)
    # Ghim bản model để adapter luôn dùng cùng nền trọng số với lúc huấn luyện.
    revision = _pinned_revision(model_id)
    tokenizer = AutoTokenizer.from_pretrained(
        model_id, revision=revision, local_files_only=not allow_download
    )
    # Sinh tự hồi quy từ đuôi chuỗi nên lô suy luận phải đệm bên trái.
    tokenizer.padding_side = "left"
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    # Không ép ``dtype`` cho model đã lượng tử hóa. Chỉ dùng bfloat16 trên GPU
    # có năng lực tính toán từ 8 trở lên.
    compute_dtype = (
        torch.bfloat16 if torch.cuda.get_device_capability()[0] >= 8 else torch.float16
    )
    config = AutoConfig.from_pretrained(
        model_id, revision=revision, local_files_only=not allow_download
    )
    quantized = getattr(config, "quantization_config", None) is not None
    load_kwargs: dict = {"local_files_only": not allow_download, "revision": revision}
    if load_4bit and not quantized:
        # Lượng tử hóa khi nạp để dùng cấu hình 4-bit thống nhất.
        load_kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=compute_dtype,
            # ``lm_head`` dùng chung trọng số với lớp nhúng và không thể lượng tử
            # hóa độc lập bằng bitsandbytes.
            llm_int8_skip_modules=["lm_head"],
        )
    elif not quantized:
        load_kwargs["dtype"] = compute_dtype
    if gpu_memory:
        # Model đa phương thức mang theo tháp thị giác và âm thanh mà bài toán
        # này không dùng tới. Giới hạn phần trên GPU để chúng nằm lại RAM.
        load_kwargs["device_map"] = "auto"
        load_kwargs["max_memory"] = {0: gpu_memory, "cpu": "32GiB"}
    else:
        load_kwargs["device_map"] = "cuda"
    model = AutoModelForCausalLM.from_pretrained(model_id, **load_kwargs)
    if adapter:
        # Nạp adapter để chấm model đã tinh chỉnh.
        from peft import PeftModel

        model = PeftModel.from_pretrained(model, str(adapter))
    model = model.eval()

    def _as_chat(prompt: str) -> str:
        # Model đã tinh chỉnh dùng khuôn huấn luyện; model gốc dùng khuôn nhắc ví dụ.
        if adapter is not None:
            return fine_tuned_prompt(tokenizer, prompt)
        return tokenizer.apply_chat_template(
            [{"role": "user", "content": prompt}],
            add_generation_prompt=True,
            tokenize=False,
        )

    def _generate(prompts: Sequence[str]) -> list[str]:
        encoded = tokenizer(
            [_as_chat(prompt) for prompt in prompts],
            return_tensors="pt",
            padding=True,
        ).to(model.device)
        with torch.no_grad():
            output = model.generate(
                **encoded,
                max_new_tokens=max_new_tokens,
                do_sample=False,
                pad_token_id=tokenizer.pad_token_id,
            )
        # Đệm bên trái làm mọi prompt trong lô có cùng độ dài.
        prompt_length = encoded["input_ids"].shape[-1]
        return tokenizer.batch_decode(
            output[:, prompt_length:], skip_special_tokens=True
        )

    def complete(prompt: str) -> str:
        return _generate([prompt])[0]

    def complete_batch(prompts: Sequence[str]) -> list[str]:
        """Sinh theo lô và giảm cỡ lô khi thiếu bộ nhớ GPU.

        Cỡ lô đã giảm được giữ cho các lần gọi sau của cùng lượt chấm.
        """

        nonlocal batch_size
        outputs: list[str] = []
        index = 0
        while index < len(prompts):
            window = prompts[index : index + batch_size]
            try:
                outputs.extend(_generate(window))
            except (torch.cuda.OutOfMemoryError, RuntimeError) as exc:
                if not _is_cuda_oom(exc) or batch_size == 1:
                    raise
                batch_size = max(1, batch_size // 2)
                complete_batch.batch_size = batch_size
                print(f"  tràn VRAM - hạ lô xuống {batch_size}", flush=True)
                torch.cuda.empty_cache()
                continue
            index += len(window)
        return outputs

    # Báo cáo ghi cỡ lô thực tế sau khi đã điều chỉnh theo bộ nhớ GPU.
    complete_batch.batch_size = batch_size

    return complete, complete_batch


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=MODEL_ID)
    parser.add_argument(
        "--seq2seq-model",
        type=Path,
        default=None,
        help="thư mục checkpoint seq2seq; chấm bằng CÙNG thước với LLM",
    )
    parser.add_argument("--allow-download", action="store_true", help="cho phép tải model")
    parser.add_argument("--shots", type=int, default=12)
    parser.add_argument("--split", default="val")
    parser.add_argument("--limit", type=int, default=0, help="0 = chấm hết")
    parser.add_argument("--max-new-tokens", type=int, default=200)
    parser.add_argument("--gpu-memory", default="", help="vd 4GiB - phần thừa đẩy sang RAM")
    parser.add_argument(
        "--base-precision",
        choices=("match-adapter", "4bit", "bf16"),
        default="match-adapter",
        help="độ chính xác trọng số GỐC; mặc định theo đúng lượt đã huấn luyện adapter",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=16,
        help="số câu sinh cùng lúc; tự hạ khi tràn VRAM",
    )
    parser.add_argument(
        "--adapter",
        type=Path,
        default=None,
        help="thư mục adapter LoRA; bỏ trống thì chấm model gốc bằng nhắc ví dụ",
    )
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    rows = [
        json.loads(line)
        for line in (DATASET_DIR / f"{args.split}.jsonl").read_text("utf-8").splitlines()
        if line.strip()
    ]
    if args.limit:
        rows = rows[: args.limit]

    # Seq2seq và LLM dùng cùng dữ liệu và chỉ số benchmark.
    if args.seq2seq_model:
        print(f"seq2seq: {args.seq2seq_model}", flush=True)
        generator = _seq2seq_generator(args.seq2seq_model, args.batch_size)
        base_precision = "fp32"
    else:
        base_precision = base_precision_for_adapter(args.adapter, args.base_precision)
        print(f"trọng số gốc: {base_precision} · lô sinh: {args.batch_size}", flush=True)
        complete, complete_batch = build_complete(
            args.model,
            args.max_new_tokens,
            args.gpu_memory,
            base_precision == "4bit",
            args.allow_download,
            args.adapter,
            args.batch_size,
        )
        if args.adapter:
            # Model đã tinh chỉnh dùng khuôn huấn luyện, không kèm ví dụ nhắc.
            generator = FineTunedQueryGenerator(complete, complete_batch=complete_batch)
        else:
            generator = LLMQueryGenerator(
                complete,
                load_examples(DATASET_DIR / "train.jsonl"),
                shots=args.shots,
                complete_batch=complete_batch,
            )

    started = time.monotonic()
    predictions: list[str] = []
    for index in range(0, len(rows), args.batch_size):
        window = rows[index : index + args.batch_size]
        predictions.extend(generator.generate_many([row["input"] for row in window]))
        rate = (time.monotonic() - started) / len(predictions)
        print(
            f"  {len(predictions)}/{len(rows)} · {rate:.2f}s mỗi câu",
            flush=True,
        )
    elapsed = time.monotonic() - started

    # Câu hỏi thực tế được đánh giá riêng bằng ``ontchatbot.cli.internal_eval``.
    report = evaluate_predictions(rows, predictions, load_ontology(), include_cases=True)
    report["run"] = {
        "model": str(args.seq2seq_model) if args.seq2seq_model else args.model,
        "shots": None if (args.adapter or args.seq2seq_model) else args.shots,
        "split": args.split,
        "records": len(rows),
        "seconds_per_question": round(elapsed / len(rows), 2),
        # Sự hiện diện của adapter xác định model đã tinh chỉnh.
        "fine_tuned": args.adapter is not None or args.seq2seq_model is not None,
        "family": "seq2seq" if args.seq2seq_model else "causal-lm",
        "adapter": str(args.adapter) if args.adapter else None,
        # Ghi nền trọng số và cỡ lô để tái lập điều kiện benchmark.
        "base_precision": base_precision,
        "generation_batch_size_requested": args.batch_size,
        # Đường seq2seq không có bộ tự hạ lô, nên cỡ lô thực tế bằng cỡ yêu cầu.
        # Đường LLM hạ dần khi thiếu bộ nhớ nên phải hỏi lại giá trị đã dùng.
        "generation_batch_size_effective": (
            args.batch_size if args.seq2seq_model else complete_batch.batch_size
        ),
    }

    primary = report["primary_metrics"]
    print(
        "\n".join(
            [
                "",
                # Nhãn phải lấy từ report["run"], là nơi ghi model thật sự chạy.
                # Đọc thẳng args.model thì lượt seq2seq vẫn in tên model LLM.
                f"model            {report['run']['model']}"
                + (
                    " (seq2seq)"
                    if args.seq2seq_model
                    else f" (nhắc {args.shots} ví dụ, "
                    + ("adapter " + str(args.adapter) if args.adapter else "KHÔNG tinh chỉnh")
                    + ")"
                ),
                f"đúng node        {primary['node_selection']['correct']}/{primary['node_selection']['count']} ({primary['node_selection']['rate']:.1%})",
                f"đúng dạng        {primary['query_shape']['correct']}/{primary['query_shape']['count']} ({primary['query_shape']['rate']:.1%})",
                f"từ chối đúng     {primary['rejection_decision']['correct']}/{primary['rejection_decision']['count']} ({primary['rejection_decision']['rate']:.1%})",
                f"tốc độ           {elapsed / len(rows):.1f}s mỗi câu",
            ]
        )
    )

    destination = args.output or (
        ARTIFACTS_DIR / "llm-benchmark" / f"{args.model.replace('/', '_')}-{args.shots}shot.json"
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print("kết quả:", destination)


if __name__ == "__main__":
    main()
