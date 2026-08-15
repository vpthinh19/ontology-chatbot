"""Chấm một LLM có nhắc ví dụ trên ĐÚNG tập mà seq2seq đã chấm.

Ví dụ nhắc kèm lấy từ train, câu chấm lấy từ val - không rò rỉ. Dùng cùng hàm
đánh giá với các lượt seq2seq nên con số đặt cạnh nhau được.

    uv run python .claude/notes/tools/llm_benchmark.py --model Qwen/Qwen3.5-2B --shots 12
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import torch
from transformers import (
    AutoConfig,
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
)

from ontchatbot.research.benchmark import load_user_query_expectations
from ontchatbot.research.evaluation import (
    evaluate_predictions,
    evaluate_query_id_expectations,
)
from ontchatbot.runtime.llm import LLMQueryGenerator, load_examples
from ontchatbot.runtime.sparql import load_ontology
from ontchatbot.settings import ARTIFACTS_DIR, DATASET_DIR



def _pinned_revision(model_id: str) -> str | None:
    """Bản model đã ghim cho ``model_id``, hoặc None nếu không ghim bản nào.

    Đường huấn luyện ghim cứng một commit. Đường chấm phải hỏi đúng commit ấy,
    nếu không thì adapter và model gốc có thể lệch nhau mà không báo gì.
    """

    from ..research.llm_lora_training import MODEL_ID, MODEL_REVISION

    return MODEL_REVISION if model_id == MODEL_ID else None


def build_complete(
    model_id: str,
    max_new_tokens: int,
    gpu_memory: str = "",
    load_4bit: bool = False,
    allow_download: bool = False,
    adapter=None,
):
    # GHIM ĐÚNG BẢN MODEL MÀ ADAPTER ĐÃ HỌC TRÊN ĐÓ.
    #
    # Không ghim thì thư viện hỏi nhánh ``main``, và nó phải gọi mạng chỉ để biết
    # ``main`` đang trỏ vào đâu - nên máy offline chết ngay dù model đã nằm sẵn
    # trong cache. Đó là triệu chứng; bệnh nặng hơn nằm ở chỗ khác: nếu máy CÓ
    # mạng và ``main`` đã nhích sang bản mới, ta sẽ lặng lẽ chấm adapter trên một
    # model KHÁC với model nó được huấn luyện, và con số thu được vô nghĩa mà
    # không ai thấy sai ở đâu.
    revision = _pinned_revision(model_id)
    tokenizer = AutoTokenizer.from_pretrained(
        model_id, revision=revision, local_files_only=not allow_download
    )
    # Model đã lượng tử hoá thì ĐỪNG ép dtype: ép là trọng số 4-bit bị giải nén
    # ngược về 16-bit ngay lúc nạp, và card 6 GB tràn ngay.
    # Hỏi ĐỜI KIẾN TRÚC, đừng hỏi ``is_bf16_supported``: trên T4 hàm đó trả về
    # True vì nó tính cả trường hợp giả lập bằng phần mềm, mà giả lập thì chậm
    # hơn hẳn float16 vốn có nhân tính chuyên dụng. bfloat16 chỉ có thật từ
    # Ampere (đời 8) trở đi.
    compute_dtype = (
        torch.bfloat16 if torch.cuda.get_device_capability()[0] >= 8 else torch.float16
    )
    config = AutoConfig.from_pretrained(
        model_id, revision=revision, local_files_only=not allow_download
    )
    quantized = getattr(config, "quantization_config", None) is not None
    load_kwargs: dict = {"local_files_only": not allow_download, "revision": revision}
    if load_4bit and not quantized:
        # Tự nén lúc nạp. Nhanh hơn bản nén sẵn theo compressed-tensors vì
        # không phải giải nén lại khi tính, và nén được nhiều phần hơn.
        load_kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=compute_dtype,
            # KHÔNG nén lớp đầu ra, dù nó là phần nặng nhất còn lại.
            #
            # Ghi chú cũ ở đây nói nén nó để tiết kiệm 0,8 GB trên card 6 GB.
            # Điều đó không thực hiện được với model này: ``lm_head`` BUỘC CHUNG
            # trọng số với lớp nhúng, mà bitsandbytes đòi trọng số 4-bit đã đóng
            # gói nên trọng số buộc chung không đóng gói được - nó vấp thẳng
            # ``assert module.weight.shape[1] == 1`` ở lượt truyền xuôi đầu tiên.
            # Đường huấn luyện đã loại nó ra từ đầu vì đúng lý do này; đường chấm
            # thì chưa, nên chấm bằng model 4-bit chưa bao giờ chạy nổi.
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
        # Chấm model ĐÃ TINH CHỈNH. Không có cờ này thì bộ chấm chỉ đo cách
        # nhắc ví dụ, và hai phép đo đó không so được với nhau.
        from peft import PeftModel

        model = PeftModel.from_pretrained(model, str(adapter))
    model = model.eval()

    def complete(prompt: str) -> str:
        text = tokenizer.apply_chat_template(
            [{"role": "user", "content": prompt}],
            add_generation_prompt=True,
            tokenize=False,
        )
        encoded = tokenizer(text, return_tensors="pt").to(model.device)
        with torch.no_grad():
            output = model.generate(
                **encoded,
                max_new_tokens=max_new_tokens,
                do_sample=False,
                pad_token_id=tokenizer.eos_token_id,
            )
        return tokenizer.decode(
            output[0][encoded["input_ids"].shape[-1] :], skip_special_tokens=True
        )

    return complete


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--allow-download", action="store_true", help="cho phép tải model")
    parser.add_argument("--shots", type=int, default=12)
    parser.add_argument("--split", default="val")
    parser.add_argument("--limit", type=int, default=0, help="0 = chấm hết")
    parser.add_argument("--max-new-tokens", type=int, default=200)
    parser.add_argument("--gpu-memory", default="", help="vd 4GiB - phần thừa đẩy sang RAM")
    parser.add_argument("--load-4bit", action="store_true", help="tự nén 4-bit lúc nạp")
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

    generator = LLMQueryGenerator(
        build_complete(
            args.model,
            args.max_new_tokens,
            args.gpu_memory,
            args.load_4bit,
            args.allow_download,
            args.adapter,
        ),
        load_examples(DATASET_DIR / "train.jsonl"),
        shots=args.shots,
    )

    started = time.monotonic()
    predictions = []
    for index, row in enumerate(rows, start=1):
        predictions.append(generator.generate(row["input"]))
        if index % 25 == 0:
            rate = (time.monotonic() - started) / index
            print(f"  {index}/{len(rows)} · {rate:.1f}s mỗi câu", flush=True)
    elapsed = time.monotonic() - started

    report = evaluate_predictions(rows, predictions, load_ontology(), include_cases=True)
    real_user_expectations = load_user_query_expectations()
    real_user_started = time.monotonic()
    real_user_predictions = [
        generator.generate(item["question"]) for item in real_user_expectations
    ]
    real_user_elapsed = time.monotonic() - real_user_started
    report["real_user_cases"] = evaluate_query_id_expectations(
        real_user_expectations,
        real_user_predictions,
        include_cases=True,
    )
    report["real_user_cases"]["inference"] = {
        "records": len(real_user_expectations),
        "seconds": round(real_user_elapsed, 3),
        "seconds_per_question": round(
            real_user_elapsed / len(real_user_expectations),
            3,
        ),
    }
    report["run"] = {
        "model": args.model,
        "shots": args.shots,
        "split": args.split,
        "records": len(rows),
        "seconds_per_question": round(elapsed / len(rows), 2),
        "fine_tuned": False,
    }

    primary = report["primary_metrics"]
    real_user = report["real_user_cases"]
    print(
        "\n".join(
            [
                "",
                f"model            {args.model} (nhắc {args.shots} ví dụ, KHÔNG tinh chỉnh)",
                f"đúng node        {primary['node_selection']['correct']}/{primary['node_selection']['count']} ({primary['node_selection']['rate']:.1%})",
                f"đúng dạng        {primary['query_shape']['correct']}/{primary['query_shape']['count']} ({primary['query_shape']['rate']:.1%})",
                f"từ chối đúng     {primary['rejection_decision']['correct']}/{primary['rejection_decision']['count']} ({primary['rejection_decision']['rate']:.1%})",
                f"câu người thật {real_user['correct']}/{real_user['count']} ({real_user['query_id_accuracy']:.1%}) — báo riêng",
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
