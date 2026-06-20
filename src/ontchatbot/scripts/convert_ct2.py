"""Convert fine-tuned BARTpho (HF) → CTranslate2 int8 cho deploy CPU (DESIGN.md, Phase 6).

    uv run --extra train python -m ontchatbot.scripts.convert_ct2 \
        [--model-dir artifacts/models/bartpho_tree] [--out artifacts/models/bartpho_ct2] [--no-check]

2 bước (theo pattern ĐÃ VERIFY ở ``custom_test/convert_ct2_test.py``):
  ① vá ``model.config.normalize_before = True`` — pretrained BARTpho THIẾU/đặt sai field này; CT2
     sinh rác nếu bỏ qua. Lưu HF model + tokenizer ra thư mục trung gian (converter đọc từ đĩa).
  ② ``TransformersConverter(quantization="int8")`` → ``CT2_MODEL_DIR``; rồi lưu tokenizer VÀO đó để
     thư mục CT2 self-contained (deploy chỉ cần 1 thư mục: model.bin + vocab + tokenizer).

⚠️ ĐÃ KIỂM THỰC NGHIỆM (2026-06-19, đừng làm lại): BARTpho config có ``normalize_before=None`` (+
``add_final_layer_norm``/``normalize_embedding`` None). CT2 converter cho ``model_type=mbart`` **BẮT
BUỘC** ``normalize_before=True`` — đặt False ném ``AttributeError: ...has no attribute 'layer_norm'``.
Nên vá True là ĐÚNG & BẮT BUỘC. Lưu ý: gán ``model.config`` SAU khi dựng model KHÔNG đổi hành vi
model in-memory (layer chốt giá trị lúc init) — chỉ đổi config GHI ĐĨA → ảnh hưởng CT2; nên HF generate
luôn phản ánh lúc train, CT2 là đường deploy, parity nối hai cái.

PARITY CHECK (mặc định bật, ``--no-check`` để tắt): chạy HF generate trên model **NGUYÊN BẢN** (đúng
đường ``evaluate.py`` đo) rồi so với CT2 (đã vá+int8). Trên base-model thấy ~ khớp cao, vài câu mơ hồ
lệch do **nhiễu int8** (không phải lỗi kiến trúc); model fine-tuned (tự tin trên JSON hẹp) kỳ vọng
~100%. Nếu khớp THẤP trên model fine-tuned → mới cần điều tra. Chạy CPU (không tranh GPU với train).
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

from ..config import CT2_MODEL_DIR, MAX_SOURCE_LENGTH, MAX_TARGET_LENGTH, MODEL_DIR, TEST_PATH

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

_BEAM = 4                       # khớp evaluate.py (parity phải so cùng chế độ decode)


def _resolve_model_dir(raw: str) -> str:
    """Local model dir → đường TUYỆT ĐỐI (transformers nhận chắc); chỉ có ``checkpoint-*`` → bước
    cao nhất (train chưa lưu model cuối); không phải local dir → trả nguyên (có thể là HF repo id)."""
    p = Path(raw)
    if (p / "config.json").exists():
        return str(p.resolve())
    ckpts = sorted([d for d in p.glob("checkpoint-*") if (d / "config.json").exists()],
                   key=lambda d: int(d.name.split("-")[-1]) if d.name.split("-")[-1].isdigit() else -1)
    if ckpts:
        print(f"[convert] ⚠️ {raw} chưa có model cuối — dùng {ckpts[-1].name}")
        return str(ckpts[-1].resolve())
    if p.exists():
        print(f"[convert] ⚠️ {raw} tồn tại nhưng không có config.json/checkpoint-* — để from_pretrained xử lý")
    return raw                  # HF repo id (vd vinai/bartpho-syllable) hoặc để from_pretrained báo lỗi rõ


def _sample(n: int) -> tuple[list[dict], list[str]]:
    """``n`` câu rải đều test.jsonl (đã ``clean``) cho parity."""
    from ..preprocess import clean

    rows = [json.loads(l) for l in TEST_PATH.read_text(encoding="utf-8").splitlines() if l.strip()]
    step = max(1, len(rows) // n)
    sample = rows[::step][:n]
    return sample, [clean(r["text"]) for r in sample]


def _hf_generate(model, tokenizer, texts: list[str]) -> list[str]:
    """HF torch generate (CPU) → chuỗi JSON, giống evaluate.py (beam=_BEAM)."""
    import torch

    out: list[str] = []
    for t in texts:
        enc = tokenizer(t, return_tensors="pt", truncation=True, max_length=MAX_SOURCE_LENGTH)
        with torch.no_grad():
            ids = model.generate(**enc, num_beams=_BEAM, max_length=MAX_TARGET_LENGTH)
        out.append(tokenizer.batch_decode(ids, skip_special_tokens=True)[0])
    return out


def _ct2_generate(out_dir: str, tokenizer, texts: list[str]) -> list[str]:
    """CT2 Translator (CPU int8) → chuỗi JSON, theo pattern custom_test/using_ct2_test.py."""
    import ctranslate2

    tr = ctranslate2.Translator(out_dir, device="cpu", compute_type="int8")
    res: list[str] = []
    for t in texts:
        src = tokenizer.convert_ids_to_tokens(
            tokenizer.encode(t, truncation=True, max_length=MAX_SOURCE_LENGTH))
        hyp = tr.translate_batch([src], beam_size=_BEAM, max_decoding_length=MAX_TARGET_LENGTH)
        res.append(tokenizer.decode(
            tokenizer.convert_tokens_to_ids(hyp[0].hypotheses[0]), skip_special_tokens=True))
    return res


def _compare(sample, hf: list[str], ct2: list[str], orig_nb) -> None:
    """So HF(nguyên bản) vs CT2(đã vá). So cây-parse (dict) — bỏ khác whitespace."""
    str_match = tree_match = 0
    print(f"\n[convert] PARITY HF(nguyên bản, normalize_before={orig_nb}) ↔ CT2(vá=True), "
          f"{len(sample)} câu, beam={_BEAM}:")
    for r, h, c in zip(sample, hf, ct2):
        try:
            same_tree = json.loads(h) == json.loads(c)
        except (json.JSONDecodeError, TypeError):
            same_tree = (h == c)
        str_match += (h == c)
        tree_match += same_tree
        if not same_tree:
            print(f"    ✗ {r['text']!r}\n        HF : {h}\n        CT2: {c}")
    n = len(sample)
    rate = tree_match / n if n else 1.0
    print(f"[convert] khớp chuỗi {str_match}/{n}, khớp cây {tree_match}/{n} → "
          + ("✅ OK — CT2 trung thành với HF/eval" if rate == 1.0 else
             f"{'≈ OK (lệch ít, hợp lý int8)' if rate >= 0.9 else '⚠️ LỆCH NHIỀU — điều tra'}: "
             "vài câu lệch thường là nhiễu lượng-tử-hoá int8 trên sinh-văn kém-tự-tin; "
             "model fine-tuned tốt nên gần 100% — nếu thấp thật sự thì xem lại quantization/decode."))


def convert(args: argparse.Namespace) -> int:
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
    import ctranslate2

    model_dir = _resolve_model_dir(args.model_dir)
    out_dir = str(args.out)
    print(f"[convert] nạp HF model {model_dir} (CPU)")
    tokenizer = AutoTokenizer.from_pretrained(model_dir)
    model = AutoModelForSeq2SeqLM.from_pretrained(model_dir)        # mặc định CPU — không tranh GPU train
    orig_nb = getattr(model.config, "normalize_before", None)
    print(f"[convert] normalize_before (gốc) = {orig_nb}")

    sample = hf_outputs = texts = None
    if not args.no_check:                                          # HF generate TRƯỚC khi vá (đường eval)
        sample, texts = _sample(args.check_n)
        print(f"[convert] HF generate {len(texts)} câu (nguyên bản, beam={_BEAM}) ...")
        hf_outputs = _hf_generate(model, tokenizer, texts)

    with tempfile.TemporaryDirectory() as td:
        model.config.normalize_before = True                       # vá BẮT BUỘC cho CT2
        tokenizer.save_pretrained(td)
        model.save_pretrained(td)
        ctranslate2.converters.TransformersConverter(model_name_or_path=td).convert(
            output_dir=out_dir, quantization="int8", force=True)
    tokenizer.save_pretrained(out_dir)                             # self-contained cho deploy
    print(f"[convert] ✅ CT2 int8 → {out_dir} (kèm tokenizer)")

    if not args.no_check:
        _compare(sample, hf_outputs, _ct2_generate(out_dir, tokenizer, texts), orig_nb)
    return 0


def main() -> None:
    p = argparse.ArgumentParser(description="Convert BARTpho HF → CTranslate2 int8 (deploy CPU)")
    p.add_argument("--model-dir", default=str(MODEL_DIR),
                   help="thư mục model HF fine-tuned / HF repo id (tự lùi checkpoint-* nếu chưa có model cuối)")
    p.add_argument("--out", default=str(CT2_MODEL_DIR), help="thư mục CT2 xuất ra")
    p.add_argument("--no-check", action="store_true", help="bỏ parity check HF↔CT2")
    p.add_argument("--check-n", type=int, default=12, help="số câu parity check")
    sys.exit(convert(p.parse_args()))


if __name__ == "__main__":
    main()
