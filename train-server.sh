#!/usr/bin/env bash
#
# Huấn luyện và chấm model seq2seq trên máy từ xa, rồi đóng gói đúng phần cần
# mang về.
#
# Bộ câu hỏi vừa được sửa lại nên cả bốn model phải chạy lại trên cùng dữ liệu
# mới; gói mang về chứa đủ bốn, không cần ghép với kết quả cũ.
#
# Trần lượt học đặt rộng và để phép dừng sớm quyết định chỗ kết thúc: lượt chạy
# trước chạm đúng trần nên không ai biết các model còn khá lên tới đâu.
#
#     bash train-server.sh              # cả bốn model, trần 16 lượt
#     EPOCHS=8 bash train-server.sh     # hạ trần khi chỉ muốn thử nhanh
#     MODELS="t5gemma2" bash train-server.sh      # chạy riêng một model
#
# Gói mang về chỉ chứa chỉ số và log, không chứa trọng số: trọng số nằm lại trên
# máy chạy, và bảng biểu chỉ cần các tệp JSON.
#
# Huấn luyện và chấm chạy ở hai tiến trình riêng để giải phóng bộ nhớ GPU giữa
# hai giai đoạn.

set -uo pipefail

cd "$(dirname "$0")"

MODELS="${MODELS:-t5gemma2 mbart bartpho vit5}"
EPOCHS_DEFAULT="${EPOCHS:-16}"
STAMP="$(date +%Y%m%d-%H%M%S)"
ROOT="artifacts/runs/${STAMP}"
BENCH_BATCH="${BENCH_BATCH:-16}"
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

# Điểm của bốn model chỉ đặt cạnh nhau được khi cả bốn học trên cùng một bộ dữ
# liệu. Vân tay dưới đây là bộ mà ba model đã chấm xong dùng, nên lệch vân tay
# nghĩa là lượt này không so được với chúng.
EXPECTED_DATASET="e170f014d514061882d8a30460fe6c187759328cc7fc3c7159d6c4ab1c0b4ddf"
ACTUAL_DATASET="$("${PY}" -c 'import hashlib, pathlib; print(hashlib.sha256(pathlib.Path("resources/dataset/manifest.json").read_bytes()).hexdigest())')"
if [ "${ACTUAL_DATASET}" != "${EXPECTED_DATASET}" ]; then
    echo
    echo "DỮ LIỆU ĐÃ ĐỔI KỂ TỪ LƯỢT BA MODEL"
    echo "  chờ:  ${EXPECTED_DATASET}"
    echo "  thấy: ${ACTUAL_DATASET}"
    if [ -z "${SKIP_DATASET_CHECK:-}" ]; then
        echo "Chạy tiếp thì điểm không so được với ba model kia. Vẫn muốn chạy:"
        echo "  SKIP_DATASET_CHECK=1 bash train-server.sh"
        exit 1
    fi
    echo "SKIP_DATASET_CHECK đang bật - chạy tiếp, số của lượt này đứng riêng."
fi

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

# Hỏng thật thì lượt chạy thoát bằng mã lỗi; những chuyện chỉ cần ghi nhận,
# như bỏ compile, không được làm một lượt chạy tốt trông như đã hỏng.
FAILED=()
NOTES=()
for MODEL in ${MODELS}; do
    OUT="${ROOT}/${MODEL}"
    mkdir -p "${OUT}"
    echo
    echo "############ ${MODEL} ############"
    echo "=== HUẤN LUYỆN ${MODEL} ==="
    # Biên dịch hỏng thì chạy lại không biên dịch: mất tốc độ vẫn hơn mất cả một
    # model trong lượt chạy.
    if ! "${PY}" -m ontchatbot.cli.train \
        --model "${MODEL}" \
        --epochs "${EPOCHS_DEFAULT}" \
        --save-model \
        --output-dir "${OUT}/model" \
        "$@"; then
        echo "HUẤN LUYỆN ${MODEL} VỚI COMPILE THẤT BẠI - chạy lại không compile"
        rm -rf "${OUT}/model"
        if ! "${PY}" -m ontchatbot.cli.train \
            --model "${MODEL}" \
            --epochs "${EPOCHS_DEFAULT}" \
            --no-compile \
            --save-model \
            --output-dir "${OUT}/model" \
            "$@"; then
            echo "HUẤN LUYỆN ${MODEL} THẤT BẠI"
            FAILED+=("${MODEL}:train")
            continue
        fi
        NOTES+=("${MODEL}:không-compile")
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
echo "Giải nén cạnh kết quả của ba model kia; mỗi model một thư mục cùng cấp."

if [ ${#NOTES[@]} -gt 0 ]; then
    echo "GHI NHẬN: ${NOTES[*]}"
fi
if [ ${#FAILED[@]} -gt 0 ]; then
    echo "THẤT BẠI: ${FAILED[*]}"
    exit 1
fi
echo "xong: ${MODELS}"
