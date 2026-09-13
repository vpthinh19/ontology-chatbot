#!/bin/sh
set -eu
image=${1:?usage: verify-cpu-runtime.sh IMAGE}

docker run --rm --entrypoint /bin/sh "$image" -c '
set -eu
test -z "${CUDA_VERSION:-}"
test ! -d /app/.venv/lib/python3.12/site-packages/nvidia
test ! -e /app/resources/end-to-end
test -f /app/resources/ontology/ontology.trig
test -f /app/resources/ontology/shapes.ttl
! command -v uv >/dev/null 2>&1
python - <<"PY"
import sys
from importlib import metadata
from pathlib import Path

assert sys.version_info[:2] == (3, 12)
names = {d.metadata["Name"].lower().replace("_", "-") for d in metadata.distributions()}
assert {"pyoxigraph", "bm25s", "pyshacl", "starlette", "uvicorn"} <= names
assert not {name for name in names if name.startswith("nvidia-")}

from ontchatbot.search import SearchEngine, TriGFileSource
engine = SearchEngine.open(TriGFileSource(Path("/app/resources/ontology/ontology.trig")))
assert engine.search(["điều kiện xét học bổng"]).results
PY
'
