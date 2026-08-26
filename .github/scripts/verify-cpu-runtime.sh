#!/bin/sh
set -eu
image=${1:?usage: verify-cpu-runtime.sh IMAGE}

docker run --rm --entrypoint /bin/sh "$image" -c '
set -eu
test -z "${CUDA_VERSION:-}"
test ! -e /app/cuda
test ! -d /app/.venv/lib/python3.12/site-packages/nvidia
test ! -e /app/resources/dataset
test ! -e /app/resources/reports
test ! -e /app/resources/provenance
test ! -e /app/resources/end-to-end
test ! -e /app/resources/cases
test -f /app/resources/ontology/ontology.ttl
test -f /app/resources/ontology/catalogue.jsonl
test -f /app/resources/ontology/answer_inventory.json
! command -v uv >/dev/null 2>&1
python - <<"PY"
import sys
from importlib import metadata
from pathlib import Path

assert sys.version_info[:2] == (3, 12)
names = {d.metadata["Name"].lower().replace("_", "-") for d in metadata.distributions()}
assert "onnxruntime" in names
assert "onnxruntime-gpu" not in names
assert not {"fastapi", "pydantic", "openai", "openai-agents"} & names
assert not {name for name in names if name.startswith("nvidia-")}

from ontchatbot.runtime.onnx_classifier import OnnxClassifierGenerator
generator = OnnxClassifierGenerator.load(Path("/app/model"), intra_op_threads=2)
assert generator.providers == ["CPUExecutionProvider"]
assert generator.generate("điều kiện xét học bổng")
PY
'
