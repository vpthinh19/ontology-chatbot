#!/bin/sh
set -eu
image=${1:?usage: verify-cpu-runtime.sh IMAGE}

docker run --rm --entrypoint /bin/sh "$image" -c '
set -eu
test -z "${CUDA_VERSION:-}"
test ! -e /app/cuda
test ! -e /app/model
test ! -d /app/.venv/lib/python3.12/site-packages/nvidia
test ! -e /app/resources/dataset
test ! -e /app/resources/reports
test ! -e /app/resources/provenance
test ! -e /app/resources/end-to-end
test ! -e /app/resources/cases
test -f /app/resources/ontology/ontology.ttl
! command -v uv >/dev/null 2>&1
python - <<"PY"
import sys
from importlib import metadata
from pathlib import Path

assert sys.version_info[:2] == (3, 12)
names = {d.metadata["Name"].lower().replace("_", "-") for d in metadata.distributions()}
assert {"rdflib", "bm25s"} <= names
assert not {"onnxruntime", "tokenizers", "torch", "transformers"} & names
assert not {"fastapi", "pydantic", "openai", "openai-agents"} & names
assert not {name for name in names if name.startswith("nvidia-")}

from ontchatbot.search import SearchEngine, TurtleFileSource
engine = SearchEngine.open(TurtleFileSource(Path("/app/resources/ontology/ontology.ttl")))
assert engine.search(["điều kiện xét học bổng"]).results
PY
'
