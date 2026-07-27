"""Run Stage F gates and freeze dataset v2 using local tokenizers."""

from __future__ import annotations

import argparse
from pathlib import Path

from ..research.stage_f import freeze_release
from ..settings import ARTIFACTS_DIR
from ..tools.tokenizer import BARTPHO_REVISION


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--bartpho-tokenizer",
        type=Path,
        default=(
            Path.home()
            / ".cache/huggingface/hub/models--vinai--bartpho-syllable/snapshots"
            / BARTPHO_REVISION
        ),
    )
    parser.add_argument(
        "--vit5-tokenizer",
        type=Path,
        default=ARTIFACTS_DIR / "tokenizers/vit5",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    try:
        from transformers import AutoTokenizer
    except ImportError as exc:  # pragma: no cover - optional train dependency.
        raise RuntimeError("install the train extra to run the Stage F tokenizer gate") from exc

    bartpho = AutoTokenizer.from_pretrained(
        args.bartpho_tokenizer,
        local_files_only=True,
        trust_remote_code=True,
    )
    vit5 = AutoTokenizer.from_pretrained(
        args.vit5_tokenizer,
        local_files_only=True,
    )
    audit = freeze_release(bartpho, vit5)
    print(
        f"Stage F: {audit['status']}; "
        f"structural={audit['gate_checks']['structural_contract']}, "
        f"tokenizers={audit['gate_checks']['tokenizer_contract']}"
    )


if __name__ == "__main__":
    main()
