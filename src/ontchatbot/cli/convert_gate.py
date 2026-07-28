"""Convert a trained domain gate for CTranslate2 deployment."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..tools.gate_conversion import convert_gate


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--quantization", default="int8")
    args = parser.parse_args()
    manifest = convert_gate(
        args.source_dir,
        args.output_dir,
        quantization=args.quantization,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
