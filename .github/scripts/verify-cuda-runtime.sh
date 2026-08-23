#!/bin/sh
set -eu

image=${1:?usage: verify-cuda-runtime.sh IMAGE}

docker run --rm --entrypoint /bin/sh "$image" -c '
set -eu

test "${CUDA_VERSION:-}" = "13.0.2"
test -n "${NV_CUDNN_PACKAGE:-}"
test ! -e /app/cuda
test ! -d /app/.venv/lib/python3.12/site-packages/nvidia

python - <<"PY"
import sys
import onnxruntime as ort

assert sys.version_info[:2] == (3, 12), sys.version
assert "CUDAExecutionProvider" in ort.get_available_providers()
PY

provider=/app/.venv/lib/python3.12/site-packages/onnxruntime/capi/libonnxruntime_providers_cuda.so
unexpected=$(ldd "$provider" | awk '\''$3 == "not" && $4 == "found" && $1 != "libcuda.so.1" { print $1 }'\'')
test -z "$unexpected" || {
    echo "unresolved CUDA runtime libraries: $unexpected" >&2
    exit 1
}
'
