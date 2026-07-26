"""Reproducible tokenizer contract for BARTpho and ViT5."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

from .config import ARTIFACTS_DIR

BARTPHO_MODEL_ID = "vinai/bartpho-syllable"
BARTPHO_REVISION = "36eee8b4d648dd99da56462edcda3c5c97f7f3de"
VIT5_MODEL_ID = "VietAI/vit5-base"
VIT5_REVISION = "2209a38d735ede63e88f5aa52bcdc11a05a37b85"
VIT5_VOCAB_SIZE = 36096
VIT5_SENTINEL_MAPPING = {
    "<extra_id_0>": ("{", 36095),
    "<extra_id_1>": ("}", 36094),
    "<extra_id_2>": ("|", 36093),
    "<extra_id_3>": ("=", 36092),
}

DEFAULT_VIT5_TOKENIZER_DIR = ARTIFACTS_DIR / "tokenizers/vit5"
_REQUIRED_SOURCE_FILES = (
    "tokenizer.json",
    "tokenizer_config.json",
    "special_tokens_map.json",
)
_INPUT_PROBES = (
    "đóng tiền học sao",
    "tui rớt môn rồi, học lại sao giờ",
    "làm sao bảo lưu kết quả hiện tại, tui sắp đi nghĩa vụ quân sự",
    "học phí K63 ngành Công nghệ sinh học bao nhiêu một tín chỉ",
)
TOKENIZER_TARGET_PROBES = (
    "SELECT ?answer WHERE { :AcademicLeaveProcedure :content ?answer . }",
    "SELECT ?answer WHERE { :AcademicLeaveProcedure :condition ?answer . }",
    "SELECT ?answer WHERE { :AcademicLeaveProcedure :handledBy ?office . ?office :email ?answer . }",
    "SELECT (COUNT(DISTINCT ?method) AS ?answer) WHERE { :TuitionPaymentProcedure :supportsPaymentMethod ?method . }",
    'SELECT ?answer WHERE { ?rate :cohortCode ?cohort ; :tuitionPerCredit ?answer . FILTER ( STR ( ?cohort ) = "K63" ) }',
)


class TokenizerContractError(ValueError):
    """A tokenizer does not preserve the shared structured-output contract."""


def patch_vit5_tokenizer_data(source_data: dict[str, Any]) -> dict[str, Any]:
    """Rename four BPE vocabulary entries while preserving IDs and size."""

    data = copy.deepcopy(source_data)
    model = data.get("model")
    if not isinstance(model, dict) or model.get("type") != "BPE":
        raise TokenizerContractError("ViT5 tokenizer model must be BPE")

    vocab = model.get("vocab")
    if not isinstance(vocab, dict) or len(vocab) != VIT5_VOCAB_SIZE:
        raise TokenizerContractError(
            f"ViT5 vocabulary must contain {VIT5_VOCAB_SIZE} entries"
        )

    for old_token, (new_token, expected_id) in VIT5_SENTINEL_MAPPING.items():
        if vocab.get(old_token) != expected_id:
            raise TokenizerContractError(
                f"expected {old_token} at ID {expected_id}, got {vocab.get(old_token)}"
            )
        if new_token in vocab:
            raise TokenizerContractError(f"target token already exists: {new_token}")
        del vocab[old_token]
        vocab[new_token] = expected_id

    if len(vocab) != VIT5_VOCAB_SIZE or len(set(vocab.values())) != VIT5_VOCAB_SIZE:
        raise TokenizerContractError("ViT5 vocabulary IDs changed during repair")
    return data


def prepare_vit5_tokenizer(
    source_dir: Path,
    output_dir: Path = DEFAULT_VIT5_TOKENIZER_DIR,
) -> dict[str, Any]:
    """Create, validate and save the fixed tokenizer plus an audit manifest."""

    try:
        import transformers
        from transformers import AutoTokenizer, PreTrainedTokenizerFast
    except ImportError as exc:  # pragma: no cover - exercised without train extra.
        raise RuntimeError("install the train extra to prepare the ViT5 tokenizer") from exc

    source_dir = Path(source_dir)
    output_dir = Path(output_dir)
    missing = [name for name in _REQUIRED_SOURCE_FILES if not (source_dir / name).is_file()]
    if missing:
        raise FileNotFoundError(f"ViT5 source tokenizer is missing: {', '.join(missing)}")

    source_data = _read_json(source_dir / "tokenizer.json")
    fixed_data = patch_vit5_tokenizer_data(source_data)
    source_config = _read_json(source_dir / "tokenizer_config.json")
    special_tokens = source_config.get("additional_special_tokens")
    if not isinstance(special_tokens, list):
        raise TokenizerContractError("ViT5 additional_special_tokens must be a list")
    repaired_sentinels = set(VIT5_SENTINEL_MAPPING)
    remaining_special_tokens = [
        token for token in special_tokens if token not in repaired_sentinels
    ]
    if len(remaining_special_tokens) != len(special_tokens) - len(repaired_sentinels):
        raise TokenizerContractError("the four repaired sentinels must be special tokens")

    output_dir.mkdir(parents=True, exist_ok=True)
    tokenizer_json = output_dir / "tokenizer.json"
    tokenizer_json.write_text(
        json.dumps(fixed_data, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )

    original = PreTrainedTokenizerFast(
        tokenizer_file=str(source_dir / "tokenizer.json"),
        pad_token="<pad>",
        eos_token="</s>",
        unk_token="<unk>",
        additional_special_tokens=special_tokens,
    )
    fixed = PreTrainedTokenizerFast(
        tokenizer_file=str(tokenizer_json),
        pad_token="<pad>",
        eos_token="</s>",
        unk_token="<unk>",
        additional_special_tokens=remaining_special_tokens,
    )
    fixed.save_pretrained(output_dir)
    reloaded = AutoTokenizer.from_pretrained(output_dir, local_files_only=True)

    if len(reloaded) != VIT5_VOCAB_SIZE or reloaded.vocab_size != VIT5_VOCAB_SIZE:
        raise TokenizerContractError("ViT5 repair changed tokenizer size")
    for _, (token, expected_id) in VIT5_SENTINEL_MAPPING.items():
        if reloaded.convert_tokens_to_ids(token) != expected_id:
            raise TokenizerContractError(f"{token} was not preserved at ID {expected_id}")

    for text in _INPUT_PROBES:
        original_ids = original(text, add_special_tokens=False)["input_ids"]
        fixed_ids = reloaded(text, add_special_tokens=False)["input_ids"]
        if original_ids != fixed_ids:
            raise TokenizerContractError(f"Vietnamese tokenization changed for: {text}")
    target_report = audit_target_roundtrip(reloaded, TOKENIZER_TARGET_PROBES)

    output_files = sorted(
        path.name for path in output_dir.iterdir() if path.is_file() and path.name != "manifest.json"
    )
    manifest = {
        "format_version": 1,
        "source_model": VIT5_MODEL_ID,
        "source_revision": VIT5_REVISION,
        "transformers_version": transformers.__version__,
        "vocab_size": VIT5_VOCAB_SIZE,
        "mapping": {
            old: {"new": new, "id": token_id}
            for old, (new, token_id) in VIT5_SENTINEL_MAPPING.items()
        },
        "input_probe_count": len(_INPUT_PROBES),
        "target_probe_count": len(target_report),
        "source_sha256": {
            name: _sha256(source_dir / name) for name in _REQUIRED_SOURCE_FILES
        },
        "output_sha256": {name: _sha256(output_dir / name) for name in output_files},
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def audit_target_roundtrip(tokenizer: Any, targets: Iterable[str]) -> list[dict[str, Any]]:
    """Require every canonical target to survive encode/decode without UNK."""

    report = []
    for target in targets:
        ids = tokenizer(target, add_special_tokens=False)["input_ids"]
        unknown_count = ids.count(tokenizer.unk_token_id) if tokenizer.unk_token_id is not None else 0
        decoded = tokenizer.decode(ids, skip_special_tokens=True)
        exact = decoded.strip() == target.strip()
        row = {
            "target": target,
            "tokens": len(ids),
            "unknown_tokens": unknown_count,
            "roundtrip_exact": exact,
        }
        report.append(row)
        if unknown_count or not exact:
            raise TokenizerContractError(f"target does not round-trip: {row}")
    return report


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TokenizerContractError(f"expected a JSON object: {path}")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
