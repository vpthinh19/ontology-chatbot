"""Convert fine-tuned BARTpho (HF) → CTranslate2 int8 cho deploy CPU.

    uv run --extra train python -m ontchatbot.scripts.convert_ct2 \
        [--model-dir artifacts/models/bartpho_tree] [--out artifacts/models/bartpho_ct2]

2 bước (theo pattern đã verify):
  ① vá ``model.config.normalize_before = True`` — pretrained BARTpho THIẾU/đặt sai field này; CT2
     sinh rác nếu bỏ qua. Lưu HF model + tokenizer ra thư mục trung gian (converter đọc từ đĩa).
  ② ``TransformersConverter(quantization="int8")`` → ``CT2_MODEL_DIR``; rồi lưu tokenizer VÀO đó để
     thư mục CT2 self-contained (deploy chỉ cần 1 thư mục: model.bin + vocab + tokenizer).

⚠️ ĐÃ KIỂM THỰC NGHIỆM (đừng làm lại): BARTpho config có ``normalize_before=None``. CT2 converter cho
``model_type=mbart`` **BẮT BUỘC** ``normalize_before=True`` — đặt False ném ``AttributeError:
...has no attribute 'layer_norm'``. Gán ``model.config`` SAU khi dựng model KHÔNG đổi model in-memory
(layer chốt giá trị lúc init) — chỉ đổi config GHI ĐĨA → ảnh hưởng CT2.

Script này CHỈ làm một việc: chuyển đổi. Việc đánh giá chất lượng model (kể cả đối chiếu đường HF
với đường deploy) thuộc về ``scripts.evaluate``.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

from ..config import CT2_MODEL_DIR, MODEL_DIR

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


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


def convert(args: argparse.Namespace) -> int:
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
    import ctranslate2

    model_dir = _resolve_model_dir(args.model_dir)
    out_dir = str(args.out)
    print(f"[convert] nạp HF model {model_dir} (CPU)")
    tokenizer = AutoTokenizer.from_pretrained(model_dir)
    model = AutoModelForSeq2SeqLM.from_pretrained(model_dir)        # mặc định CPU — không tranh GPU train
    print(f"[convert] normalize_before (gốc) = {getattr(model.config, 'normalize_before', None)}")

    with tempfile.TemporaryDirectory() as td:
        model.config.normalize_before = True                       # vá BẮT BUỘC cho CT2
        tokenizer.save_pretrained(td)
        model.save_pretrained(td)
        ctranslate2.converters.TransformersConverter(model_name_or_path=td).convert(
            output_dir=out_dir, quantization="int8", force=True)
    tokenizer.save_pretrained(out_dir)                             # self-contained cho deploy
    print(f"[convert] ✅ CT2 int8 → {out_dir} (kèm tokenizer)")
    return 0


def main() -> None:
    p = argparse.ArgumentParser(description="Convert BARTpho HF → CTranslate2 int8 (deploy CPU)")
    p.add_argument("--model-dir", default=str(MODEL_DIR),
                   help="thư mục model HF fine-tuned / HF repo id (tự lùi checkpoint-* nếu chưa có model cuối)")
    p.add_argument("--out", default=str(CT2_MODEL_DIR), help="thư mục CT2 xuất ra")
    sys.exit(convert(p.parse_args()))


if __name__ == "__main__":
    main()
