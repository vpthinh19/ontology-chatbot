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
    """Bản model đã ghim cho ``model_id``, hoặc None nếu không ghim bản nào.

    Đường huấn luyện ghim cứng một commit. Đường chấm phải hỏi đúng commit ấy,
    nếu không thì adapter và model gốc có thể lệch nhau mà không báo gì.
    """

    return MODEL_REVISION if model_id == MODEL_ID else None


def base_precision_for_adapter(adapter, requested: str) -> str:
    """Chọn độ chính xác của trọng số GỐC, mặc định theo đúng lượt huấn luyện.

    Cùng một họ lỗi với việc ghim bản model ở trên. Adapter học cách bù cho một
    nền trọng số CỤ THỂ; chấm nó trên nền khác là chấm một model khác, mà triệu
    chứng thì không có - chỉ là con số hơi lệch, không ai biết vì sao.

    Nén 4-bit sinh ra cho card 6 GB. Trên card lớn nó chỉ làm CHẬM: bitsandbytes
    giải nén trọng số ở mỗi lượt truyền xuôi, mà giải mã tuần tự từng token thì
    phần đó lấn át (đo trên card 6 GB: 6,9 giây/câu so với 5,0 ở bf16). Nên đây
    không phải cờ để bật cho vui - nó phải theo lượt huấn luyện, không theo máy.
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
    """Bọc câu hỏi ĐÚNG như lúc huấn luyện đã bọc nó.

    Nằm ở cấp mô-đun chứ không nấp trong ``build_complete`` để phép kiểm gọi
    được mà không phải nạp model - phép kiểm ấy đối chiếu thẳng với đường huấn
    luyện, và nếu có nó từ đầu thì lượt chấm 16/8 đã không đo nhầm.

    ``question`` phải là câu ĐÃ chuẩn hoá; bên gọi lo bước đó, y như bên huấn
    luyện.
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
    """Cho checkpoint seq2seq đi qua ĐÚNG bộ chấm của LLM.

    Dùng lại thẳng ``_generate_rows`` của đường huấn luyện thay vì viết vòng
    sinh thứ hai: hai vòng sinh là hai cách chuẩn hoá, hai cách đệm, hai cách
    cắt chuỗi - và khi chúng trôi ra thì con số của hai họ model không còn so
    được, mà so được chính là lý do tồn tại của phép đo này.
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


def build_complete(
    model_id: str,
    max_new_tokens: int,
    gpu_memory: str = "",
    load_4bit: bool = False,
    allow_download: bool = False,
    adapter=None,
    batch_size: int = 1,
):
    # ``batch_size`` bị hạ dần khi tràn VRAM, xem ``complete_batch`` bên dưới.
    batch_size = max(1, batch_size)
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
    # ĐỆM BÊN TRÁI, và đây không phải chuyện gọn gàng - nó là chuyện đúng/sai.
    #
    # Model kiểu này sinh tiếp vào ĐUÔI chuỗi. Đệm bên phải thì đuôi là một dãy
    # token rỗng, model sinh tiếp vào đó và câu trả lời hỏng - mà hỏng lặng lẽ:
    # vẫn ra chữ, vẫn chấm được, chỉ là điểm thấp không rõ nguyên nhân. Câu dài
    # nhất trong lô không đệm gì nên vẫn đúng, và đó chính là lý do lỗi này khó
    # thấy: lô nào cũng có vài câu đúng.
    #
    # Huấn luyện thì ngược lại, đệm bên phải, vì ở đó không sinh tiếp mà chỉ
    # tính mất mát trên nhãn.
    tokenizer.padding_side = "left"
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
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

    def _as_chat(prompt: str) -> str:
        # HỎI MODEL ĐÃ TINH CHỈNH BẰNG ĐÚNG KHUÔN NÓ ĐƯỢC DẠY.
        #
        # Khuôn huấn luyện là lời hệ thống + câu hỏi trần, và phần trả lời bắt
        # đầu ngay sau khối ``<think>`` rỗng. Khuôn nhắc ví dụ thì không có lời
        # hệ thống, không có khối đó, và dài gấp mấy chục lần vì cõng theo 12 ví
        # dụ. Suốt hơn hai nghìn bước huấn luyện, model chưa gặp khuôn ấy lần
        # nào.
        #
        # Hỏi sai khuôn KHÔNG làm model câm - nó vẫn trả lời gần đúng, chỉ trượt
        # một token ở cùng một chỗ, và một token đó đủ để truy vấn rơi khỏi danh
        # mục. Đo được trên lượt chấm ngày 16/8: 150 trong 399 câu sai đúng một
        # token, kéo cả ba chỉ số xuống cùng lúc.
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
        # Đệm bên trái nên mọi chuỗi vào đều dài bằng nhau: cắt một chỗ là xong.
        prompt_length = encoded["input_ids"].shape[-1]
        return tokenizer.batch_decode(
            output[:, prompt_length:], skip_special_tokens=True
        )

    def complete(prompt: str) -> str:
        return _generate([prompt])[0]

    def complete_batch(prompts: Sequence[str]) -> list[str]:
        """Sinh theo lô, tự thu nhỏ lô khi tràn VRAM.

        Gom lô ở đây không phải tối ưu vụn vặt. Sinh chữ bị chặn bởi băng thông
        bộ nhớ: mỗi bước giải mã phải đọc TOÀN BỘ trọng số dù đang xử lý một câu
        hay ba mươi hai câu. Sinh từng câu một là để card chạy không tải - 788
        câu val+test từng mất hơn ba tiếng, lâu hơn cả lượt huấn luyện.

        Không xếp câu theo độ dài trước khi chia lô: phần lâu là số BƯỚC GIẢI MÃ,
        mà số đó do câu trả lời dài nhất trong lô quyết định, không phải câu hỏi.
        Xếp theo độ dài câu hỏi chỉ bớt được phần đệm lúc đọc prompt, vốn đã rẻ.

        Cỡ lô đã hạ thì GIỮ NGUYÊN cho những lần gọi sau. Đặt lại về cỡ ban đầu
        mỗi lần gọi nghĩa là card nhỏ phải tràn đi tràn lại suốt cả lượt chấm,
        mỗi lần tràn tốn một lượt sinh hỏng.
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

    # Cỡ lô THỰC SỰ đã chạy, cho báo cáo đọc. Ghi cỡ yêu cầu là ghi sai khi card
    # phải hạ lô, mà cỡ lô lại là thứ quyết định cả tốc độ lẫn mấy chỗ lật token.
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

    # SEQ2SEQ ĐI QUA ĐÚNG BỘ CHẤM NÀY, không có thước riêng.
    #
    # Trước đây mỗi họ model có một đường chấm: LLM chấm val+test kèm 15 câu
    # người thật, bộ chấm gắn trong seq2seq chỉ chấm val và bỏ câu người thật,
    # bộ chấm CTranslate2 lại dùng một tập benchmark khác hẳn. Ba thước khác
    # nhau thì con số của hai họ không đặt cạnh nhau được - mà đặt cạnh nhau
    # chính là lý do tồn tại của cả phép so.
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
            # Model đã tinh chỉnh KHÔNG được nhắc ví dụ: xem ghi chú ở ``_as_chat``.
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

    # 15 CÂU NGƯỜI THẬT KHÔNG NẰM Ở ĐÂY NỮA.
    #
    # Chúng là dữ liệu nội bộ để chủ dự án và tôi đánh giá model, không thuộc
    # train/val/test và không đưa ra ngoài. Đo bằng ``scripts/danh-gia-noi-bo.py``.
    report = evaluate_predictions(rows, predictions, load_ontology(), include_cases=True)
    report["run"] = {
        "model": str(args.seq2seq_model) if args.seq2seq_model else args.model,
        "shots": None if (args.adapter or args.seq2seq_model) else args.shots,
        "split": args.split,
        "records": len(rows),
        "seconds_per_question": round(elapsed / len(rows), 2),
        # Có adapter là ĐÃ tinh chỉnh. Trước đây ô này ghi cứng False, nên đúng
        # lượt chấm adapter - lý do tồn tại của cả bộ chấm - lại tự khai là chưa
        # tinh chỉnh, và báo cáo nói ngược với thứ nó vừa đo.
        "fine_tuned": args.adapter is not None or args.seq2seq_model is not None,
        "family": "seq2seq" if args.seq2seq_model else "causal-lm",
        "adapter": str(args.adapter) if args.adapter else None,
        # Ghi CẢ nền trọng số lẫn cỡ lô. Thiếu nền thì vài tuần sau không ai
        # chứng minh được con số này đo trên đúng model mà adapter đã học; thiếu
        # cỡ lô thì không so được tốc độ giữa hai lượt chạy.
        "base_precision": base_precision,
        "generation_batch_size_requested": args.batch_size,
        "generation_batch_size_effective": complete_batch.batch_size,
    }

    primary = report["primary_metrics"]
    print(
        "\n".join(
            [
                "",
                f"model            {args.model} (nhắc {args.shots} ví dụ, "
                + ("adapter " + str(args.adapter) if args.adapter else "KHÔNG tinh chỉnh")
                + ")",
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
