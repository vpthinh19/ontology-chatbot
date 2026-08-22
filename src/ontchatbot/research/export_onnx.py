"""Đóng gói bộ phân loại thành một đồ thị ONNX chạy độc lập.

Đường phục vụ không nên mang theo thư viện huấn luyện: riêng chúng và các thư viện
tính toán đi kèm chiếm vài gigabyte trong ảnh triển khai, trong khi lúc chạy chỉ cần
một phép truyền xuôi. Bản xuất gộp cả ba bước - bộ mã hoá kèm bộ điều hợp đã hoà vào
trọng số, phép gộp trung bình theo token, và lớp phân loại - thành một đồ thị nhận
chuỗi token và trả thẳng điểm số của từng nhãn.

Bộ tách từ vẫn dùng tệp ``tokenizer.json`` sẵn có, đọc bằng thư viện tách từ độc lập.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

OPSET = 17


def _wrapper(encoder, head):
    """Bọc bộ mã hoá, phép gộp và lớp phân loại thành một mô-đun xuất được."""
    import torch
    import torch.nn as nn

    class Classifier(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.encoder = encoder
            self.head = head

        def forward(self, input_ids, attention_mask):
            hidden = self.encoder(input_ids=input_ids,
                                  attention_mask=attention_mask).last_hidden_state
            mask = attention_mask.unsqueeze(-1).to(hidden.dtype)
            pooled = (hidden * mask).sum(dim=1) / mask.sum(dim=1).clamp(min=1e-9)
            return self.head(pooled)

    return Classifier().eval()


def export(model_dir: Path, out_dir: Path) -> Path:
    """Xuất model đã huấn luyện ra ONNX và chép kèm bảng nhãn, bộ tách từ."""
    import torch
    import torch.nn as nn
    from peft import PeftModel
    from transformers import AutoModel

    model_dir, out_dir = Path(model_dir), Path(out_dir)
    meta = json.loads((model_dir / "labels.json").read_text(encoding="utf-8"))
    out_dir.mkdir(parents=True, exist_ok=True)

    base = AutoModel.from_pretrained(meta["base_model"])
    # Hoà bộ điều hợp vào trọng số nền: đồ thị xuất ra không còn khái niệm điều
    # hợp, chỉ còn một bộ mã hoá duy nhất.
    encoder = PeftModel.from_pretrained(base, model_dir).merge_and_unload().eval()

    head = nn.Linear(base.config.hidden_size, len(meta["labels"]))
    head.load_state_dict(torch.load(model_dir / "head.pt", map_location="cpu"))
    model = _wrapper(encoder, head.eval())

    dummy_ids = torch.ones(1, 16, dtype=torch.long)
    dummy_mask = torch.ones(1, 16, dtype=torch.long)
    target = out_dir / "classifier.onnx"
    torch.onnx.export(
        model,
        (dummy_ids, dummy_mask),
        target,
        input_names=["input_ids", "attention_mask"],
        output_names=["logits"],
        dynamic_axes={
            "input_ids": {0: "batch", 1: "sequence"},
            "attention_mask": {0: "batch", 1: "sequence"},
            "logits": {0: "batch"},
        },
        opset_version=OPSET,
        do_constant_folding=True,
    )

    (out_dir / "labels.json").write_text(
        json.dumps({"labels": meta["labels"]}, ensure_ascii=False), encoding="utf-8")
    shutil.copy(model_dir / "tokenizer.json", out_dir / "tokenizer.json")

    with torch.no_grad():
        reference = model(dummy_ids, dummy_mask).numpy()
    _check(target, dummy_ids.numpy(), dummy_mask.numpy(), reference)
    return target


def _check(model_path: Path, input_ids, attention_mask, reference) -> None:
    """Đối chiếu đồ thị vừa xuất với bản gốc; lệch quá ngưỡng thì dừng ngay."""
    import numpy as np
    import onnxruntime as ort

    session = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
    produced = session.run(
        ["logits"], {"input_ids": input_ids, "attention_mask": attention_mask})[0]
    gap = float(np.abs(produced - reference).max())
    if gap > 1e-3:
        raise SystemExit(f"đồ thị ONNX lệch bản gốc {gap:.2e}, quá ngưỡng 1e-3")
    print(f"  đối chiếu với bản gốc: lệch tối đa {gap:.2e}")
