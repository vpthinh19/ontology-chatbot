#!/usr/bin/env bash
#
# MỘT script huấn luyện cho cả hai họ model. Chạy thẳng, không cần tham số:
#
#     bash scripts/train.sh              # LLM (Qwen3.5-2B + LoRA) - mặc định
#     bash scripts/train.sh t5gemma2     # seq2seq
#     bash scripts/train.sh vit5
#
# Cả hai nhánh ghi cùng một bối cảnh máy, cùng vân tay dữ liệu, và chấm bằng
# CÙNG một bộ chấm trên cùng val/test - nếu không thì hai con số không đặt cạnh
# nhau được, mà đặt cạnh nhau chính là lý do chạy chúng.
#
# Chấm lại một model đã có, khỏi huấn luyện lại:
#
#     ADAPTER=artifacts/run-<mốc>/adapter bash scripts/train.sh --skip-train

set -euo pipefail

cd "$(dirname "$0")/.."

FAMILY=llm
SEQ2SEQ_MODEL=""
ARGS=()
SKIP_TRAIN=0
for ARG in "$@"; do
    case "${ARG}" in
        t5gemma2|vit5|bartpho) FAMILY=seq2seq; SEQ2SEQ_MODEL="${ARG}" ;;
        --skip-train) SKIP_TRAIN=1 ;;
        *) ARGS+=("${ARG}") ;;
    esac
done
set -- ${ARGS+"${ARGS[@]}"}

STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="artifacts/run-${STAMP}"
LOG="${OUT}/train.log"
ADAPTER="${ADAPTER:-${OUT}/adapter}"
# Số câu sinh cùng lúc lúc chấm. Bộ chấm tự hạ khi tràn nên đặt cao là an toàn.
BENCH_BATCH="${BENCH_BATCH:-16}"
mkdir -p "${OUT}"

PY="${PY:-.venv/bin/python}"
if [ ! -x "${PY}" ]; then
    PY="python3"
fi

exec > >(tee -a "${LOG}") 2>&1

echo "=== BỐI CẢNH LƯỢT CHẠY ${STAMP} (${FAMILY}${SEQ2SEQ_MODEL:+: ${SEQ2SEQ_MODEL}}) ==="
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
for name in ("torch", "transformers", "peft", "bitsandbytes"):
    try:
        print(name, importlib.import_module(name).__version__)
    except Exception:
        print(name, "CHƯA CÀI")
PYEOF

# Vân tay dữ liệu: thiếu nó thì vài tuần sau không ai chứng minh được model học
# trên bản dataset nào, và hai lượt chấm hết so được với nhau.
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
echo "=== HUẤN LUYỆN ==="
if [ "${FAMILY}" = "seq2seq" ]; then
    "${PY}" -m ontchatbot.cli.train \
        --model "${SEQ2SEQ_MODEL}" \
        --save-model \
        --output-dir "${OUT}/model"
    TARGET="$(find "${OUT}/model" -maxdepth 3 -type d -name model | head -1)"
    SCORE_FLAG=(--seq2seq-model "${TARGET}")
elif [ "${SKIP_TRAIN}" = "1" ]; then
    echo "(BỎ QUA huấn luyện; chấm lại adapter có sẵn: ${ADAPTER})"
    SCORE_FLAG=(--adapter "${ADAPTER}" --batch-size "${BENCH_BATCH}")
else
    "${PY}" -m ontchatbot.cli.train_llm_lora \
        --save-adapter \
        --output-dir "${ADAPTER}" \
        "$@"
    SCORE_FLAG=(--adapter "${ADAPTER}" --batch-size "${BENCH_BATCH}")
fi

for SPLIT in val test; do
    echo
    echo "=== CHẤM ${SPLIT} ==="
    "${PY}" -m ontchatbot.cli.benchmark_llm \
        "${SCORE_FLAG[@]}" \
        --split "${SPLIT}" \
        --output "${OUT}/benchmark-${SPLIT}.json" \
        || echo "chấm ${SPLIT} THẤT BẠI - xem log phía trên"
done

echo
echo "=== GÓI LẠI ==="
BUNDLE="artifacts/ket-qua-${STAMP}.tar.gz"
tar -czf "${BUNDLE}" -C "${OUT}" $(cd "${OUT}" && ls | grep -vE '^(adapter|model)$')
echo "MANG TỆP NÀY VỀ: ${BUNDLE}"
ls -lh "${BUNDLE}"
