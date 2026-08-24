from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import numpy as np
import pytest

from ontchatbot.cli import export_classifier, publish_classifier
from ontchatbot.research import export_onnx


def test_export_cli_defaults_to_fp16() -> None:
    args = export_classifier._parse_args(
        ["--model-dir", "trained", "--out", "released"]
    )

    assert args.precision == "fp16"


def test_export_cli_can_still_request_fp32() -> None:
    args = export_classifier._parse_args(
        [
            "--model-dir",
            "trained",
            "--out",
            "released",
            "--precision",
            "fp32",
        ]
    )

    assert args.precision == "fp32"


def test_fp16_conversion_keeps_io_types_and_checks_the_saved_graph(
    monkeypatch, tmp_path
) -> None:
    source = tmp_path / "source.onnx"
    source.touch()
    target = tmp_path / "classifier.onnx"
    state = SimpleNamespace(converted=None, saved=None, checked=None)

    onnx = ModuleType("onnx")
    onnx.load = lambda path, *, load_external_data=True: (
        "saved" if Path(path) == target else "source"
    )
    onnx.checker = SimpleNamespace(
        check_model=lambda model, *, full_check: setattr(
            state, "checked", (model, full_check)
        )
    )

    class FakeOnnxModel:
        def __init__(self, model) -> None:
            assert model == "source"

        def convert_float_to_float16(self, **kwargs) -> None:
            state.converted = kwargs

        def save_model_to_file(self, path, **kwargs) -> None:
            assert isinstance(path, str)
            Path(path).touch()
            state.saved = (path, kwargs)

    onnx_model = ModuleType("onnxruntime.transformers.onnx_model")
    onnx_model.OnnxModel = FakeOnnxModel
    monkeypatch.setitem(sys.modules, "onnx", onnx)
    monkeypatch.setitem(sys.modules, "onnxruntime.transformers.onnx_model", onnx_model)

    export_onnx._convert_to_float16(source, target)

    assert state.converted == {
        "use_symbolic_shape_infer": False,
        "keep_io_types": True,
    }
    assert state.saved == (
        str(target),
        {"use_external_data_format": True},
    )
    assert state.checked == ("saved", True)


def test_publish_cli_keeps_the_stable_release_path_for_fp16() -> None:
    args = publish_classifier._parse_args(["--repo", "owner/model"])

    assert args.model_dir == Path("artifacts/entity-linking/onnx-xlmr")
    assert args.path_in_repo == "onnx-xlmr"


def test_publish_cli_does_not_accept_a_provider_selection() -> None:
    with pytest.raises(SystemExit):
        publish_classifier._parse_args(["--repo", "owner/model", "--device", "cuda"])


def test_fp16_check_allows_rounding_without_allowing_the_top_label_to_change(
    monkeypatch, tmp_path
) -> None:
    model_path = tmp_path / "classifier.onnx"
    model_path.touch()
    output = SimpleNamespace(
        logits=np.array([[0.48, 0.52]], dtype=np.float32)
    )

    class FakeSession:
        def __init__(self, path, *, providers) -> None:
            assert path == str(model_path)
            assert providers == ["CPUExecutionProvider"]

        def run(self, names, inputs):
            assert names == ["logits"]
            assert set(inputs) == {"input_ids", "attention_mask"}
            return [output.logits]

    ort = ModuleType("onnxruntime")
    ort.InferenceSession = FakeSession
    monkeypatch.setitem(sys.modules, "onnxruntime", ort)
    input_ids = np.ones((1, 4), dtype=np.int64)
    attention_mask = np.ones((1, 4), dtype=np.int64)
    reference = np.array([[0.49, 0.51]], dtype=np.float32)

    export_onnx._check(
        model_path,
        input_ids,
        attention_mask,
        reference,
        tolerance=5e-2,
        require_same_top_label=True,
    )

    output.logits = np.array([[0.51, 0.49]], dtype=np.float32)
    with pytest.raises(SystemExit, match="đổi nhãn dự đoán"):
        export_onnx._check(
            model_path,
            input_ids,
            attention_mask,
            reference,
            tolerance=5e-2,
            require_same_top_label=True,
        )


def test_check_rejects_non_finite_logits(monkeypatch, tmp_path) -> None:
    model_path = tmp_path / "classifier.onnx"
    model_path.touch()

    class FakeSession:
        def __init__(self, path, *, providers) -> None:
            assert path == str(model_path)
            assert providers == ["CPUExecutionProvider"]

        def run(self, names, inputs):
            return [np.array([[0.49, np.nan]], dtype=np.float32)]

    ort = ModuleType("onnxruntime")
    ort.InferenceSession = FakeSession
    monkeypatch.setitem(sys.modules, "onnxruntime", ort)
    values = np.ones((1, 4), dtype=np.int64)
    reference = np.array([[0.49, 0.51]], dtype=np.float32)

    with pytest.raises(SystemExit, match="giá trị không hữu hạn"):
        export_onnx._check(
            model_path,
            values,
            values,
            reference,
            tolerance=5e-2,
            require_same_top_label=True,
        )
