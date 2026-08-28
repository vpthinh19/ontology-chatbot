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


def test_local_chat_does_not_accept_a_device_flag() -> None:
    from ontchatbot.cli.chat import _parse_args

    with pytest.raises(SystemExit):
        _parse_args(["--device", "cuda"])


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


def _fake_ort(state):
    """Bộ chạy ONNX giả, đủ để canh phần đấu dây của bước nướng đồ thị."""

    class Options:
        def __init__(self) -> None:
            self.graph_optimization_level = None
            self.optimized_model_filepath = None

    def session(path, *, sess_options, providers):
        state.opened.append((Path(path), sess_options.graph_optimization_level))
        # Bộ chạy thật ghi đồ thị đã hợp nhất ra tệp khi được chỉ chỗ.
        if sess_options.optimized_model_filepath is not None:
            Path(sess_options.optimized_model_filepath).write_bytes("đồ thị đã nướng".encode("utf-8"))
            state.baked_to = Path(sess_options.optimized_model_filepath)
        return SimpleNamespace(
            run=lambda names, feed: [state.logits.pop(0)],
            providers=providers,
        )

    return ModuleType("onnxruntime"), session, Options


def _install_fake_ort(monkeypatch, state):
    module, session, options = _fake_ort(state)
    module.SessionOptions = options
    module.InferenceSession = session
    module.GraphOptimizationLevel = SimpleNamespace(
        ORT_ENABLE_EXTENDED="extended",
        ORT_ENABLE_ALL="all",
        ORT_DISABLE_ALL="none",
    )
    monkeypatch.setitem(sys.modules, "onnxruntime", module)


def test_baking_writes_the_graph_next_to_the_weights(monkeypatch, tmp_path) -> None:
    """Đồ thị nướng phải nằm cùng thư mục: trọng số ngoài tìm theo thư mục đó."""
    logits = np.array([[0.25, 0.75]], dtype=np.float32)
    state = SimpleNamespace(opened=[], baked_to=None, logits=[logits, logits.copy()])
    _install_fake_ort(monkeypatch, state)
    model = tmp_path / "classifier.onnx"
    model.touch()

    baked = export_onnx._bake_optimized_graph(
        model, np.zeros((1, 4), dtype=np.int64), np.ones((1, 4), dtype=np.int64)
    )

    assert baked == tmp_path / export_onnx.OPTIMIZED_NAME
    assert state.baked_to == baked
    # Nướng ở mức EXTENDED; mức ALL gắn tối ưu theo phần cứng máy dựng và nội
    # tuyến trọng số vào tệp đồ thị. Đọc lại thì tắt hẳn phần hợp nhất.
    assert [level for _path, level in state.opened] == ["extended", "none"]
    assert [path for path, _level in state.opened] == [model, baked]


def test_baking_refuses_a_graph_that_does_not_read_back_identically(
    monkeypatch, tmp_path
) -> None:
    """Ghi ra rồi đọc lại phải giống TỪNG BIT - đó là việc bước này chịu trách nhiệm."""
    state = SimpleNamespace(
        opened=[],
        baked_to=None,
        logits=[
            np.array([[0.25, 0.75]], dtype=np.float32),
            np.array([[0.25, 0.7500001]], dtype=np.float32),
        ],
    )
    _install_fake_ort(monkeypatch, state)
    model = tmp_path / "classifier.onnx"
    model.touch()

    with pytest.raises(SystemExit, match="không đọc lại đúng bản đã ghi"):
        export_onnx._bake_optimized_graph(
            model, np.zeros((1, 4), dtype=np.int64), np.ones((1, 4), dtype=np.int64)
        )


def test_publishing_blocks_a_model_without_the_baked_graph(tmp_path) -> None:
    """Thiếu đồ thị nướng thì dịch vụ vẫn chạy, chỉ chậm - nên phải chặn ở đây.

    Đó là kiểu hỏng không ai nhìn thấy: không có lỗi, không có cảnh báo, chỉ là
    mỗi lần khởi động nguội tốn thêm chừng một giây.
    """
    for name in ("classifier.onnx", "classifier.onnx.data", "labels.json", "tokenizer.json"):
        (tmp_path / name).touch()

    with pytest.raises(SystemExit, match=export_onnx.OPTIMIZED_NAME):
        publish_classifier.validate_model_directory(tmp_path)

    (tmp_path / export_onnx.OPTIMIZED_NAME).touch()
    assert len(publish_classifier.validate_model_directory(tmp_path)) == len(
        publish_classifier.REQUIRED
    )
