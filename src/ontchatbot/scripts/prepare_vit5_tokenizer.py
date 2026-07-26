"""CLI for the deterministic ViT5 sentinel-token repair."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..model_tokenizers import (
    DEFAULT_VIT5_TOKENIZER_DIR,
    VIT5_MODEL_ID,
    VIT5_REVISION,
    prepare_vit5_tokenizer,
)


def main() -> None:
    try:
        from huggingface_hub import snapshot_download
    except ImportError as exc:
        raise RuntimeError("install the train extra to download the ViT5 tokenizer") from exc

    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_VIT5_TOKENIZER_DIR)
    parser.add_argument("--local-files-only", action="store_true")
    args = parser.parse_args()

    source = args.source
    if source is None:
        source = Path(
            snapshot_download(
                VIT5_MODEL_ID,
                revision=VIT5_REVISION,
                local_files_only=args.local_files_only,
                allow_patterns=(
                    "tokenizer.json",
                    "tokenizer_config.json",
                    "special_tokens_map.json",
                ),
            )
        )

    manifest = prepare_vit5_tokenizer(source, args.output)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
