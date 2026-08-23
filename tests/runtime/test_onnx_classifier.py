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


def test_cuda_libraries_are_preloaded_before_the_session_is_created(
    monkeypatch, tmp_path
) -> None:
    state = SimpleNamespace(
        preloaded=False,
        requested_providers=None,
        fallback_disabled=False,
    )

    def preload_dlls(*, directory: str) -> None:
        if directory == "":
            state.preloaded = True

    def create_session(_path: str, *, providers: list[str]):
        if not state.preloaded:
            raise RuntimeError("CUDA libraries were not preloaded")
        state.requested_providers = providers

        def disable_fallback() -> None:
            state.fallback_disabled = True

        return SimpleNamespace(
            get_providers=lambda: providers,
            disable_fallback=disable_fallback,
        )

    ort = SimpleNamespace(
        preload_dlls=preload_dlls,
        get_available_providers=lambda: [
            "CUDAExecutionProvider",
            "CPUExecutionProvider",
        ],
        InferenceSession=create_session,
    )
    _replace_model_dependencies(monkeypatch, ort)

    generator = onnx_classifier.OnnxClassifierGenerator.load(
        _model_dir(tmp_path), device="cuda"
    )

    assert generator.providers[0] == "CUDAExecutionProvider"
    assert state.requested_providers == ["CUDAExecutionProvider"]
    assert state.fallback_disabled is True


def test_legacy_pruned_runtime_flag_cannot_skip_system_cuda_preload(
    monkeypatch, tmp_path
) -> None:
    state = SimpleNamespace(preloaded=False)

    def preload(*, directory: str) -> None:
        assert directory == ""
        state.preloaded = True

    session = SimpleNamespace(
        get_providers=lambda: ["CUDAExecutionProvider"],
        disable_fallback=lambda: None,
    )
    ort = SimpleNamespace(
        preload_dlls=preload,
        InferenceSession=lambda _path, *, providers: session,
    )
    _replace_model_dependencies(monkeypatch, ort)
    monkeypatch.setenv("ONTCHATBOT_PRUNED_CUDA_RUNTIME", "1")
    monkeypatch.setenv("LD_LIBRARY_PATH", "/app/cuda/lib")

    generator = onnx_classifier.OnnxClassifierGenerator.load(
        _model_dir(tmp_path), device="cuda"
    )

    assert generator.providers[0] == "CUDAExecutionProvider"
    assert state.preloaded is True


def test_cuda_load_refuses_to_fall_back_entirely_to_the_cpu(
    monkeypatch, tmp_path
) -> None:
    ort = SimpleNamespace(
        preload_dlls=lambda *, directory: None,
        get_available_providers=lambda: [
            "CUDAExecutionProvider",
            "CPUExecutionProvider",
        ],
        InferenceSession=lambda _path, *, providers: SimpleNamespace(
            get_providers=lambda: ["CPUExecutionProvider"],
            disable_fallback=lambda: None,
        ),
    )
    _replace_model_dependencies(monkeypatch, ort)

    with pytest.raises(RuntimeError, match="CUDAExecutionProvider"):
        onnx_classifier.OnnxClassifierGenerator.load(
            _model_dir(tmp_path), device="cuda"
        )
