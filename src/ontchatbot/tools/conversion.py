"""Convert a saved Transformers checkpoint to a CTranslate2 artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


TOKENIZER_FILES = (
    "tokenizer.json",
    "tokenizer_config.json",
    "special_tokens_map.json",
    "sentencepiece.bpe.model",
    "spiece.model",
    "dict.txt",
    "generation_config.json",
)


def convert_model(
    model_dir: Path,
    output_dir: Path,
    *,
    quantization: str = "int8_float16",
    force: bool = False,
) -> dict:
    try:
        import ctranslate2
        from ctranslate2.converters import TransformersConverter
    except ImportError as exc:  # pragma: no cover - dependency is required by CLI.
        raise RuntimeError("CTranslate2 is required to convert models") from exc

    model_dir = Path(model_dir)
    output_dir = Path(output_dir)
    if not (model_dir / "config.json").is_file():
        raise FileNotFoundError(f"Transformers checkpoint not found: {model_dir}")
    copy_files = [name for name in TOKENIZER_FILES if (model_dir / name).is_file()]
    if "tokenizer_config.json" not in copy_files:
        raise ValueError("checkpoint does not contain tokenizer_config.json")

    source_config = json.loads((model_dir / "config.json").read_text(encoding="utf-8"))
    needs_mbart_compat = (
        source_config.get("model_type") == "mbart"
        and "normalize_before" not in source_config
    )

    class CompatibleTransformersConverter(TransformersConverter):
        def load_model(self, model_class, model_name_or_path, **kwargs):
            model = super().load_model(model_class, model_name_or_path, **kwargs)
            if needs_mbart_compat:
                # CTranslate2 4.8 reads this legacy BART flag, while recent
                # Transformers omits it. MBART normalizes before each block.
                model.config.normalize_before = True
            return model

    converter = CompatibleTransformersConverter(
        str(model_dir),
        copy_files=copy_files,
        trust_remote_code=True,
        low_cpu_mem_usage=True,
    )
    converter.convert(
        str(output_dir),
        quantization=quantization,
        force=force,
    )
    manifest = {
        "format": "ctranslate2",
        "ctranslate2_version": ctranslate2.__version__,
        "quantization": quantization,
        "source": str(model_dir),
        "compatibility": (
            {"mbart_normalize_before": True} if needs_mbart_compat else {}
        ),
        "files": {
            path.name: _sha256(path)
            for path in sorted(output_dir.iterdir())
            if path.is_file() and path.name != "manifest.json"
        },
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--quantization",
        choices=(
            "int8",
            "int8_float32",
            "int8_float16",
            "int8_bfloat16",
            "int16",
            "float16",
            "bfloat16",
            "float32",
        ),
        default="int8_float16",
    )
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    manifest = convert_model(
        args.model_dir,
        args.output_dir,
        quantization=args.quantization,
        force=args.force,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
