#!/usr/bin/env bash
#
# Một lệnh duy nhất cho lượt huấn luyện trên server: train, chấm, gói log lại.
#
# Vì sao cần script này thay vì gõ tay ba lệnh: máy train là máy thuê, người chạy
# không ngồi đọc màn hình suốt buổi, và thứ mang về phải đủ để phân tích NGUỘI -
# tức là phải biết được đã train trên đúng dữ liệu nào, máy nào, cấu hình nào.
# Gõ tay thì ba mẩu log nằm ba chỗ và thiếu đúng phần bối cảnh.
#
# Dùng:
#     bash scripts/train-and-report.sh                 # đủ ba epoch
#     bash scripts/train-and-report.sh --smoke-test    # thử một bước, xem có vừa VRAM
#
# Xong sẽ có MỘT tệp .tar.gz ở artifacts/. Mang tệp đó về là đủ.

set -euo pipefail

cd "$(dirname "$0")/.."

STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="artifacts/run-${STAMP}"
LOG="${OUT}/train.log"
ADAPTER="${OUT}/adapter"
mkdir -p "${OUT}"

PY="${PY:-.venv/bin/python}"
if [ ! -x "${PY}" ]; then
    PY="python3"
fi

# Ghi cả stdout lẫn stderr vào log VÀ ra màn hình. Người chạy vẫn thấy tiến độ,
# còn tệp log giữ nguyên mọi thứ kể cả cảnh báo của CUDA - mấy dòng cảnh báo đó
# chính là chỗ đọc ra được vì sao batch bị lùi.
exec > >(tee -a "${LOG}") 2>&1

echo "=== BỐI CẢNH LƯỢT CHẠY ${STAMP} ==="
echo "--- máy ---"
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv 2>/dev/null || echo "không có GPU"
echo "--- mã nguồn ---"
git rev-parse HEAD 2>/dev/null || echo "không phải kho git"
git status --porcelain 2>/dev/null | head -20 || true
echo "--- thư viện ---"
"${PY}" - <<'PYEOF'
import platform
print("python", platform.python_version())
for name in ("torch", "transformers", "peft", "bitsandbytes", "trl"):
    try:
        module = __import__(name)
        print(name, getattr(module, "__version__", "?"))
    except ImportError:
        print(name, "CHƯA CÀI")
try:
    import torch
    print("cuda", torch.version.cuda, "· khả dụng:", torch.cuda.is_available())
except ImportError:
    pass
PYEOF

# Vân tay dữ liệu. Đây là phần hay bị quên nhất, và thiếu nó thì mọi con số về
# sau đều vô nghĩa: không ai chứng minh được model đã học trên bản dataset nào.
echo "--- dữ liệu đã train ---"
"${PY}" - <<'PYEOF'
import hashlib
import json
from pathlib import Path

for name in ("train", "val", "test"):
    path = Path("resources/dataset") / f"{name}.jsonl"
    raw = path.read_bytes()
    rows = [line for line in raw.decode("utf-8").splitlines() if line.strip()]
    print(f"{name}: {len(rows)} dòng · sha256 {hashlib.sha256(raw).hexdigest()[:16]}")
ontology = Path("resources/ontology/ontology.ttl").read_bytes()
print(f"ontology.ttl: sha256 {hashlib.sha256(ontology).hexdigest()[:16]}")
written = Path("resources/dataset/written-questions.jsonl")
if written.is_file():
    lines = [x for x in written.read_text(encoding="utf-8").splitlines() if x.strip()]
    print(f"câu do LLM viết: {len(lines)}")
PYEOF

echo
echo "=== HUẤN LUYỆN ==="
# Lượt thật PHẢI lưu adapter: không có nó thì không chấm được và cả buổi chạy
# thành công cốc. Nhưng lượt thử thì bộ huấn luyện từ chối lưu ("smoke test never
# saves a model") - nó đúng, một bước huấn luyện không ra model nào đáng giữ - nên
# chỉ thêm cờ đó khi chạy thật.
SMOKE=0
for ARG in "$@"; do
    if [ "${ARG}" = "--smoke-test" ]; then SMOKE=1; fi
done

if [ "${SMOKE}" = "1" ]; then
    echo "(chế độ THỬ: một bước, không lưu adapter, không chấm - chỉ để xem có vừa VRAM)"
    "${PY}" -m ontchatbot.cli.train_llm_lora "$@"
else
    "${PY}" -m ontchatbot.cli.train_llm_lora \
        --save-adapter \
        --output-dir "${ADAPTER}" \
        "$@"
fi

if [ ! -d "${ADAPTER}" ]; then
    echo "KHÔNG có adapter - bỏ qua phần chấm."
else
    # Chấm CẢ val LẪN test. Val để chọn cấu hình, test để báo cáo - trộn hai
    # việc đó là tự lừa mình. Mỗi lượt chấm tự kèm 15 câu người thật.
    for SPLIT in val test; do
        echo
        echo "=== CHẤM ${SPLIT} ==="
        "${PY}" -m ontchatbot.cli.benchmark_llm \
            --model Qwen/Qwen3.5-2B \
            --adapter "${ADAPTER}" \
            --split "${SPLIT}" \
            --load-4bit \
            --output "${OUT}/benchmark-${SPLIT}.json" \
            || echo "chấm ${SPLIT} THẤT BẠI - xem log phía trên"
    done
fi

echo
echo "=== GÓI LẠI ==="
# Không gói adapter: nó nặng và không dùng để phân tích. Thứ cần mang về là log
# và mấy tệp JSON.
BUNDLE="artifacts/ket-qua-${STAMP}.tar.gz"
tar -czf "${BUNDLE}" \
    -C "${OUT}" \
    $(cd "${OUT}" && ls | grep -v '^adapter$')
echo "MANG TỆP NÀY VỀ: ${BUNDLE}"
ls -lh "${BUNDLE}"
