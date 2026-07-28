from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import numpy as np
import pytest

from ontchatbot.tools.gate_conversion import convert_gate


class _Tensor:
    def __init__(self, values: list | np.ndarray) -> None:
        self._values = np.asarray(values, dtype=np.float32)

    def detach(self) -> _Tensor:
        return self

    def float(self) -> _Tensor:
        return self

    def cpu(self) -> _Tensor:
        return self

    def numpy(self) -> np.ndarray:
        return self._values


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source(tmp_path: Path) -> Path:
    source = tmp_path / "source"
    model = source / "model"
    model.mkdir(parents=True)
    (source / "manifest.json").write_text(
        json.dumps(
            {
                "model_id": "vinai/phobert-base-v2",
                "revision": "test-revision",
                "threshold": 0.75,
                "label_to_id": {"out_of_scope": 0, "in_scope": 1},
            }
        ),
        encoding="utf-8",
    )
    (model / "config.json").write_text("{}", encoding="utf-8")
    (model / "tokenizer_config.json").write_text("{}", encoding="utf-8")
    (model / "vocab.txt").write_text("<s>\n</s>\n", encoding="utf-8")
    (model / "bpe.codes").write_text("#version: 0.2\n", encoding="utf-8")
    return source


def _install_fake_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeConverter:
        def __init__(self, model_dir: str, **kwargs) -> None:
            assert Path(model_dir).name == "model"
            assert kwargs["low_cpu_mem_usage"] is True

        def convert(self, output_dir: str, *, quantization: str, force: bool) -> None:
            assert quantization == "int8"
            assert force is False
            output = Path(output_dir)
            output.mkdir(parents=True, exist_ok=True)
            (output / "model.bin").write_bytes(b"ct2-encoder")
            (output / "config.json").write_text("{}", encoding="utf-8")

    class FakeModel:
        def state_dict(self) -> dict[str, _Tensor]:
            return {
                "classifier.dense.weight": _Tensor([[1, 2], [3, 4]]),
                "classifier.dense.bias": _Tensor([5, 6]),
                "classifier.out_proj.weight": _Tensor([[7, 8], [9, 10]]),
                "classifier.out_proj.bias": _Tensor([11, 12]),
            }

    class FakeAutoModel:
        @classmethod
        def from_pretrained(cls, model_dir: Path, **kwargs) -> FakeModel:
            assert Path(model_dir).name == "model"
            assert kwargs == {"local_files_only": True}
            return FakeModel()

    ctranslate2 = ModuleType("ctranslate2")
    ctranslate2.__version__ = "test-ct2"
    converters = ModuleType("ctranslate2.converters")
    converters.TransformersConverter = FakeConverter
    transformers = ModuleType("transformers")
    transformers.AutoModelForSequenceClassification = FakeAutoModel
    monkeypatch.setitem(sys.modules, "ctranslate2", ctranslate2)
    monkeypatch.setitem(sys.modules, "ctranslate2.converters", converters)
    monkeypatch.setitem(sys.modules, "transformers", transformers)


def test_convert_gate_exports_complete_checksummed_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _source(tmp_path)
    output = tmp_path / "deployment"
    _install_fake_dependencies(monkeypatch)

    manifest = convert_gate(source, output)

    with np.load(output / "classifier.npz") as classifier:
        assert classifier.files == [
            "dense_weight",
            "dense_bias",
            "out_proj_weight",
            "out_proj_bias",
        ]
        np.testing.assert_array_equal(
            classifier["dense_weight"], np.asarray([[1, 2], [3, 4]], dtype=np.float32)
        )
        np.testing.assert_array_equal(
            classifier["out_proj_bias"], np.asarray([11, 12], dtype=np.float32)
        )
    assert (output / "vocab.txt").read_text(encoding="utf-8") == "<s>\n</s>\n"
    assert (output / "bpe.codes").is_file()
    assert manifest["format"] == "ctranslate2-domain-gate"
    assert manifest["threshold"] == 0.75
    assert manifest["label_to_id"] == {"out_of_scope": 0, "in_scope": 1}
    assert manifest["classifier"] == {
        "file": "classifier.npz",
        "input": "cls",
        "activation": "tanh",
    }
    assert manifest["files"] == {
        path.name: _sha256(path)
        for path in sorted(output.iterdir())
        if path.is_file() and path.name != "manifest.json"
    }
    assert json.loads((output / "manifest.json").read_text(encoding="utf-8")) == manifest


def test_convert_gate_refuses_non_empty_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _source(tmp_path)
    output = tmp_path / "deployment"
    output.mkdir()
    (output / "keep.txt").write_text("user data", encoding="utf-8")
    _install_fake_dependencies(monkeypatch)

    with pytest.raises(RuntimeError, match="not empty"):
        convert_gate(source, output)

    assert (output / "keep.txt").read_text(encoding="utf-8") == "user data"


@pytest.mark.parametrize(
    ("manifest", "message"),
    [
        ({"threshold": 0.5}, "label_to_id"),
        (
            {
                "threshold": 1.5,
                "label_to_id": {"out_of_scope": 0, "in_scope": 1},
            },
            "threshold",
        ),
    ],
)
def test_convert_gate_rejects_invalid_source_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    manifest: dict,
    message: str,
) -> None:
    source = _source(tmp_path)
    (source / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    _install_fake_dependencies(monkeypatch)

    with pytest.raises(ValueError, match=message):
        convert_gate(source, tmp_path / "deployment")
