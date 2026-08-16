#!/usr/bin/env bash
#
# Huấn luyện seq2seq, chuyển sang CTranslate2, chấm bằng ĐÚNG bộ chấm của LLM,
# rồi gói kết quả mang về. Chạy thẳng, không cần tham số:
#
#     bash scripts/train-seq2seq-and-report.sh
#
# Muốn model khác thì đưa tên vào: t5gemma2 (mặc định), vit5, bartpho.
#
#     bash scripts/train-seq2seq-and-report.sh vit5
#
# Vì sao mặc định là t5gemma2: BARTpho KHÔNG sinh nổi ``:summaryText`` (từ điển
# không có token "summary", nó phát ra <unk>), còn ViT5 phải vá từ điển trước.
# t5gemma2 chạy thẳng.
#
# Vì sao chấm bằng bộ chấm của LLM chứ không phải bộ chấm gắn trong đường
# huấn luyện: bộ chấm kia chỉ chấm val và bỏ 15 câu người thật, nên số của nó
# KHÔNG đặt cạnh số của LLM được - mà đặt cạnh nhau chính là lý do chạy lượt
# này.
#
# Model seq2seq nhỏ (t5gemma2 là 270M), chạy được ngay trên máy local để thử.

set -euo pipefail

cd "$(dirname "$0")/.."

MODEL="${1:-t5gemma2}"
STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="artifacts/seq2seq-${STAMP}"
LOG="${OUT}/train.log"
mkdir -p "${OUT}"

PY="${PY:-.venv/bin/python}"
if [ ! -x "${PY}" ]; then
    PY="python3"
fi

exec > >(tee -a "${LOG}") 2>&1

echo "=== BỐI CẢNH LƯỢT CHẠY ${STAMP} (seq2seq: ${MODEL}) ==="
echo "--- máy ---"
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv 2>/dev/null || echo "không có GPU"
. /etc/os-release 2>/dev/null && echo "${PRETTY_NAME}"
uname -srm
echo "--- mã nguồn ---"
git rev-parse HEAD
git status --porcelain
echo "--- thư viện ---"
"${PY}" - <<'PYEOF'
import importlib
for name in ("torch", "transformers", "peft", "ctranslate2"):
    try:
        print(name, importlib.import_module(name).__version__)
    except Exception:
        print(name, "CHƯA CÀI")
PYEOF

# Vân tay dữ liệu: thiếu nó thì vài tuần sau không ai chứng minh được model học
# trên bản dataset nào. Giống hệt đường LLM, và PHẢI khớp để hai bên so được.
echo "--- dữ liệu đã train ---"
"${PY}" - <<'PYEOF'
import hashlib
from pathlib import Path

for name in ("train", "val", "test"):
    path = Path("resources/dataset") / f"{name}.jsonl"
    raw = path.read_bytes()
    rows = [line for line in raw.decode("utf-8").splitlines() if line.strip()]
    print(f"{name}: {len(rows)} dòng · sha256 {hashlib.sha256(raw).hexdigest()[:16]}")
ontology = Path("resources/ontology/ontology.ttl").read_bytes()
print(f"ontology.ttl: sha256 {hashlib.sha256(ontology).hexdigest()[:16]}")
PYEOF

echo
echo "=== HUẤN LUYỆN ${MODEL} ==="
"${PY}" -m ontchatbot.cli.train \
    --model "${MODEL}" \
    --save-model \
    --output-dir "${OUT}/model"

CHECKPOINT="${OUT}/model/${MODEL}/model"
if [ ! -d "${CHECKPOINT}" ]; then
    CHECKPOINT="$(find "${OUT}/model" -maxdepth 3 -type d -name model | head -1)"
fi
echo "checkpoint: ${CHECKPOINT}"

echo
for SPLIT in val test; do
    echo
    echo "=== CHẤM ${SPLIT} ==="
    # Chấm bằng ĐÚNG bộ chấm của LLM, trên ĐÚNG val/test của dataset hiện tại.
    # Không có tập benchmark riêng, không có bước chuyển sang CTranslate2 -
    # mỗi thước thêm vào là một cách nữa để hai họ model hết so được với nhau.
    "${PY}" -m ontchatbot.cli.benchmark_llm \
        --seq2seq-model "${CHECKPOINT}" \
        --split "${SPLIT}" \
        --output "${OUT}/benchmark-${SPLIT}.json" \
        || echo "chấm ${SPLIT} THẤT BẠI - xem log phía trên"
done

echo
echo "=== GÓI LẠI ==="
BUNDLE="artifacts/ket-qua-seq2seq-${STAMP}.tar.gz"
tar -czf "${BUNDLE}" \
    -C "${OUT}" \
    $(cd "${OUT}" && ls | grep -v '^model$')
echo "MANG TỆP NÀY VỀ: ${BUNDLE}"
ls -lh "${BUNDLE}"
