#!/usr/bin/env bash
#
# Huấn luyện và chấm lần lượt cả ba model seq2seq trên máy từ xa, rồi đóng gói
# đúng phần cần mang về.
#
#     bash train-server.sh                       # cả ba model, 3 epoch
#     bash train-server.sh --epochs 4            # cờ nào cũng chuyển xuống lệnh train
#     MODELS="t5gemma2" bash train-server.sh     # chỉ một model
#
# Gói mang về chỉ chứa chỉ số và log, không chứa trọng số: trọng số nằm lại trên
# máy chạy, và bảng biểu chỉ cần các tệp JSON.
#
# Huấn luyện và chấm chạy ở hai tiến trình riêng để giải phóng bộ nhớ GPU giữa
# hai giai đoạn.

set -uo pipefail

cd "$(dirname "$0")"

MODELS="${MODELS:-t5gemma2 vit5 bartpho}"
EPOCHS_DEFAULT=3
STAMP="$(date +%Y%m%d-%H%M%S)"
ROOT="artifacts/runs/${STAMP}"
BENCH_BATCH="${BENCH_BATCH:-16}"
# 0 = chấm hết. Đặt số nhỏ để thử trọn đường mà không chờ cả tập.
BENCH_LIMIT="${BENCH_LIMIT:-0}"
mkdir -p "${ROOT}"

PY="${PY:-.venv/bin/python}"
[ -x "${PY}" ] || PY="python3"

exec > >(tee -a "${ROOT}/chay.log") 2>&1

echo "=== BỐI CẢNH ${STAMP} ==="
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv 2>/dev/null || echo "không có GPU"
. /etc/os-release 2>/dev/null && echo "${PRETTY_NAME}"
uname -srm
git rev-parse HEAD
git status --porcelain
"${PY}" - <<'PYEOF'
import hashlib
import importlib
from pathlib import Path

for name in ("torch", "transformers", "peft", "torchao"):
    try:
        print(name, importlib.import_module(name).__version__)
    except Exception:
        print(name, "CHƯA CÀI")

# Dấu vân tay dữ liệu để định danh đầu vào của lượt chạy.
for name in ("train", "val", "test"):
    raw = (Path("resources/dataset") / f"{name}.jsonl").read_bytes()
    rows = [line for line in raw.decode("utf-8").splitlines() if line.strip()]
    print(f"{name}: {len(rows)} dòng · sha256 {hashlib.sha256(raw).hexdigest()[:16]}")
ontology = Path("resources/ontology/ontology.ttl").read_bytes()
print(f"ontology.ttl: sha256 {hashlib.sha256(ontology).hexdigest()[:16]}")
PYEOF

# ViT5 phát hành tokenizer thiếu vài token điều khiển; bản đã chuẩn hoá phải có
# trước khi lượt huấn luyện của nó bắt đầu, nếu không mọi đích sinh ra đều lệch.
case " ${MODELS} " in
    *" vit5 "*)
        echo
        echo "=== CHUẨN HOÁ TOKENIZER ViT5 ==="
        if ! "${PY}" -m ontchatbot.cli.prepare_tokenizer; then
            echo "CHUẨN HOÁ TOKENIZER ViT5 THẤT BẠI - bỏ vit5 khỏi lượt chạy"
            MODELS="$(echo "${MODELS}" | sed 's/vit5//')"
        fi
        ;;
esac

FAILED=()
for MODEL in ${MODELS}; do
    OUT="${ROOT}/${MODEL}"
    mkdir -p "${OUT}"
    echo
    echo "############ ${MODEL} ############"
    echo "=== HUẤN LUYỆN ${MODEL} ==="
    # torch.compile chưa chạy được trên mọi tổ hợp card và model. Hỏng thì chạy
    # lại không compile, vì mất tốc độ vẫn hơn mất cả một model trong lượt chạy.
    if ! "${PY}" -m ontchatbot.cli.train \
        --model "${MODEL}" \
        --epochs "${EPOCHS_DEFAULT}" \
        --compile \
        --save-model \
        --output-dir "${OUT}/model" \
        "$@"; then
        echo "HUẤN LUYỆN ${MODEL} VỚI COMPILE THẤT BẠI - chạy lại không compile"
        rm -rf "${OUT}/model"
        if ! "${PY}" -m ontchatbot.cli.train \
            --model "${MODEL}" \
            --epochs "${EPOCHS_DEFAULT}" \
            --save-model \
            --output-dir "${OUT}/model" \
            "$@"; then
            echo "HUẤN LUYỆN ${MODEL} THẤT BẠI"
            FAILED+=("${MODEL}:train")
            continue
        fi
        FAILED+=("${MODEL}:compile-bỏ-qua")
    fi

    # Thư mục model đã lưu nằm bên trong --output-dir; bỏ thư mục xuất phát vì
    # nó trùng tên.
    TARGET="$(find "${OUT}/model" -mindepth 1 -maxdepth 3 -type d -name model | head -1)"
    if [ -z "${TARGET}" ]; then
        echo "KHÔNG tìm thấy thư mục model đã lưu của ${MODEL}"
        FAILED+=("${MODEL}:không-thấy-model")
        continue
    fi

    for SPLIT in val test; do
        echo "=== CHẤM ${MODEL} ${SPLIT} ==="
        if ! "${PY}" -m ontchatbot.cli.benchmark_model \
            --seq2seq-model "${TARGET}" \
            --batch-size "${BENCH_BATCH}" \
            --limit "${BENCH_LIMIT}" \
            --split "${SPLIT}" \
            --output "${OUT}/benchmark-${SPLIT}.json"; then
            echo "CHẤM ${MODEL} ${SPLIT} THẤT BẠI"
            FAILED+=("${MODEL}:${SPLIT}")
        fi
    done

    # Kéo chỉ số và adapter ra khỏi thư mục model, để gói mang về không phải
    # đụng tới trọng số đã gộp (1,5 GB) hay tokenizer (33 MB).
    find "${OUT}/model" -name metrics.json -exec cp {} "${OUT}/training-metrics.json" \; 2>/dev/null
    mkdir -p "${OUT}/adapter"
    find "${OUT}/model" \( -name 'adapter_model.safetensors' -o -name 'adapter_config.json' \) \
        -exec cp {} "${OUT}/adapter/" \; 2>/dev/null
done

echo
echo "=== GÓI LẠI ==="
BUNDLE="artifacts/ket-qua-${STAMP}.tar.gz"
tar -czf "${BUNDLE}" -C "${ROOT}" \
    $(cd "${ROOT}" && find . -maxdepth 3 \
        \( -name '*.log' -o -name 'benchmark-*.json' -o -name 'training-metrics.json' \
           -o -path './*/adapter/*' \) | sed 's|^\./||')
echo "MANG TỆP NÀY VỀ: ${BUNDLE}"
ls -lh "${BUNDLE}"

if [ ${#FAILED[@]} -gt 0 ]; then
    echo "THẤT BẠI: ${FAILED[*]}"
    exit 1
fi
echo "cả ${MODELS} đều xong"
