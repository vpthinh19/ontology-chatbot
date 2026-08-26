from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

from ontchatbot.runtime import onnx_classifier


class _Tokenizer:
    @classmethod
    def from_file(cls, _path: str):
        return cls()

    def enable_truncation(self, *, max_length: int) -> None:
        pass

    def token_to_id(self, _token: str) -> int:
        return 1

    def enable_padding(self, *, pad_id: int, pad_token: str) -> None:
        pass


class _SessionOptions:
    def __init__(self) -> None:
        self.intra_op_num_threads = 0
        self.inter_op_num_threads = 0
        self.execution_mode = None
        self.graph_optimization_level = None


def _model_dir(tmp_path):
    (tmp_path / "classifier.onnx").touch()
    (tmp_path / "tokenizer.json").write_text("{}", encoding="utf-8")
    (tmp_path / "labels.json").write_text('{"labels": []}', encoding="utf-8")
    return tmp_path


def _replace_model_dependencies(monkeypatch, ort) -> None:
    monkeypatch.setitem(sys.modules, "onnxruntime", ort)
    monkeypatch.setitem(
        sys.modules, "tokenizers", SimpleNamespace(Tokenizer=_Tokenizer)
    )
    monkeypatch.setattr(
        onnx_classifier,
        "CardLookup",
        lambda *args: SimpleNamespace(query=lambda *label: "unused"),
    )


def _cpu_ort(seen):
    def create_session(path, *, sess_options, providers):
        seen.update(path=path, options=sess_options, providers=providers)
        return SimpleNamespace(get_providers=lambda: providers)

    return SimpleNamespace(
        SessionOptions=_SessionOptions,
        ExecutionMode=SimpleNamespace(ORT_SEQUENTIAL="sequential"),
        GraphOptimizationLevel=SimpleNamespace(ORT_ENABLE_ALL="all"),
        InferenceSession=create_session,
    )


def test_load_pins_the_cpu_provider_and_two_intra_op_threads(monkeypatch, tmp_path):
    seen = {}
    _replace_model_dependencies(monkeypatch, _cpu_ort(seen))

    generator = onnx_classifier.OnnxClassifierGenerator.load(_model_dir(tmp_path))

    assert seen["providers"] == ["CPUExecutionProvider"]
    assert seen["options"].intra_op_num_threads == 2
    assert seen["options"].inter_op_num_threads == 1
    assert seen["options"].execution_mode == "sequential"
    assert seen["options"].graph_optimization_level == "all"
    assert generator.providers == ["CPUExecutionProvider"]


def test_load_accepts_an_explicit_positive_thread_count(monkeypatch, tmp_path):
    seen = {}
    _replace_model_dependencies(monkeypatch, _cpu_ort(seen))

    onnx_classifier.OnnxClassifierGenerator.load(
        _model_dir(tmp_path), intra_op_threads=3
    )

    assert seen["options"].intra_op_num_threads == 3


def test_model_assets_can_load_before_the_ontology_is_available(monkeypatch, tmp_path):
    seen = {}
    _replace_model_dependencies(monkeypatch, _cpu_ort(seen))
    graphs = []
    monkeypatch.setattr(
        onnx_classifier,
        "_cards_for",
        lambda graph: graphs.append(graph) or [],
    )

    assets = onnx_classifier.OnnxClassifierGenerator.load_assets(
        _model_dir(tmp_path), intra_op_threads=1
    )

    assert graphs == []
    generator = onnx_classifier.OnnxClassifierGenerator.from_assets(
        assets, graph="ontology"
    )
    assert graphs == ["ontology"]
    assert generator.providers == ["CPUExecutionProvider"]


@pytest.mark.parametrize("threads", [0, -1])
def test_load_rejects_a_non_positive_thread_count(threads, tmp_path):
    with pytest.raises(ValueError, match="intra_op_threads must be positive"):
        onnx_classifier.OnnxClassifierGenerator.load(
            _model_dir(tmp_path), intra_op_threads=threads
        )
