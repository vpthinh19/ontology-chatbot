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
import tempfile
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


def export(model_dir: Path, out_dir: Path, *, precision: str = "fp16") -> Path:
    """Xuất model đã huấn luyện ra ONNX và chép kèm bảng nhãn, bộ tách từ."""
    import torch
    import torch.nn as nn
    from peft import PeftModel
    from transformers import AutoModel

    model_dir, out_dir = Path(model_dir), Path(out_dir)
    if precision not in {"fp16", "fp32"}:
        raise ValueError(f"precision không hợp lệ: {precision}")
    meta = json.loads((model_dir / "labels.json").read_text(encoding="utf-8"))
    out_dir.mkdir(parents=True, exist_ok=True)

    base = AutoModel.from_pretrained(meta["base_model"])
    # Hoà bộ điều hợp vào trọng số nền: đồ thị xuất ra không còn khái niệm điều
    # hợp, chỉ còn một bộ mã hoá duy nhất.
    encoder = PeftModel.from_pretrained(base, model_dir).merge_and_unload().eval()

    head = nn.Linear(base.config.hidden_size, len(meta["labels"]))
    head.load_state_dict(torch.load(model_dir / "head.pt", map_location="cpu"))
    model = _wrapper(encoder, head.eval())

    # Hai chuỗi khác nhau cùng một batch vừa giữ phép xuất gọn, vừa kiểm tra
    # lượng tử hoá trên token lẫn padding thay vì chỉ trên một hàng toàn số 1.
    dummy_ids = torch.arange(1, 33, dtype=torch.long).reshape(2, 16)
    dummy_mask = torch.ones_like(dummy_ids)
    dummy_mask[1, 12:] = 0
    target = out_dir / "classifier.onnx"
    with tempfile.TemporaryDirectory(prefix=".export-", dir=out_dir) as temp:
        temp_dir = Path(temp)
        fp32_target = temp_dir / "fp32" / "classifier.onnx"
        fp32_target.parent.mkdir()
        torch.onnx.export(
            model,
            (dummy_ids, dummy_mask),
            fp32_target,
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

        with torch.no_grad():
            reference = model(dummy_ids, dummy_mask).numpy()
        _check(fp32_target, dummy_ids.numpy(), dummy_mask.numpy(), reference)

        release_target = fp32_target
        if precision == "fp16":
            release_target = temp_dir / "release" / "classifier.onnx"
            release_target.parent.mkdir()
            _convert_to_float16(fp32_target, release_target)
            _check(
                release_target,
                dummy_ids.numpy(),
                dummy_mask.numpy(),
                reference,
                tolerance=5e-2,
                require_same_top_label=True,
            )

        shutil.copy2(release_target, target)
        shutil.copy2(
            release_target.with_suffix(".onnx.data"),
            target.with_suffix(".onnx.data"),
        )

    (out_dir / "labels.json").write_text(
        json.dumps({"labels": meta["labels"]}, ensure_ascii=False), encoding="utf-8")
    shutil.copy(model_dir / "tokenizer.json", out_dir / "tokenizer.json")

    return target


def _convert_to_float16(source: Path, target: Path) -> None:
    """Đổi trọng số sang FP16, giữ kiểu I/O và kiểm tra graph đã lưu."""
    import onnx
    from onnxruntime.transformers.onnx_model import OnnxModel

    model = OnnxModel(onnx.load(source, load_external_data=True))
    model.convert_float_to_float16(
        use_symbolic_shape_infer=False,
        keep_io_types=True,
    )
    model.save_model_to_file(str(target), use_external_data_format=True)
    onnx.checker.check_model(
        onnx.load(target, load_external_data=True), full_check=True
    )


def _check(
    model_path: Path,
    input_ids,
    attention_mask,
    reference,
    *,
    tolerance: float = 1e-3,
    require_same_top_label: bool = False,
) -> None:
    """Đối chiếu đồ thị vừa xuất với bản gốc; lệch quá ngưỡng thì dừng ngay."""
    import numpy as np
    import onnxruntime as ort

    session = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
    produced = session.run(
        ["logits"], {"input_ids": input_ids, "attention_mask": attention_mask})[0]
    if not np.isfinite(reference).all() or not np.isfinite(produced).all():
        raise SystemExit("đồ thị ONNX sinh giá trị không hữu hạn")
    gap = float(np.abs(produced - reference).max())
    if gap > tolerance:
        raise SystemExit(
            f"đồ thị ONNX lệch bản gốc {gap:.2e}, quá ngưỡng {tolerance:.2e}"
        )
    if require_same_top_label:
        expected = np.argmax(reference, axis=-1)
        actual = np.argmax(produced, axis=-1)
        changed = int(np.count_nonzero(actual != expected))
        if changed:
            raise SystemExit(
                f"đồ thị ONNX đổi nhãn dự đoán cho {changed}/{expected.size} mẫu"
            )
    print(f"  đối chiếu với bản gốc: lệch tối đa {gap:.2e}")
