from __future__ import annotations

import logging
import re
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from ontchatbot.cli.serve import (
    _build_agent,
    _configure_logging,
    _log_cpu_budget,
    _parse_args,
    _runtime_revisions,
)


def _flags(*extra: str) -> list[str]:
    return ["--model-dir", "generator", "--llm", "mo-hinh-lon", *extra]


def test_serve_passes_cpu_limits_to_the_classifier_and_agent(monkeypatch) -> None:
    """Máy chủ dựng đúng một bộ chọn truy vấn và đưa nó cho trợ lý."""
    args = _parse_args(
        _flags(
            "--onnx-threads",
            "3",
            "--lookup-workers",
            "5",
            "--classification-cache-entries",
            "6",
            "--sparql-cache-mib",
            "7",
        )
    )
    loaded, built = [], []
    generator = SimpleNamespace()
    monkeypatch.setenv("ONTCHATBOT_LLM_API_KEY", "khoa-thu")
    monkeypatch.setattr(
        "ontchatbot.cli.serve.OnnxClassifierGenerator.load",
        lambda path, **kwargs: loaded.append((path, kwargs)) or generator,
    )
    monkeypatch.setattr(
        "ontchatbot.cli.serve.build_agent",
        lambda chatbot, **kwargs: built.append((chatbot, kwargs)) or "tro-ly",
    )

    assert _build_agent(args) == "tro-ly"
    assert loaded == [(Path("generator"), {"intra_op_threads": 3})]
    chatbot, kwargs = built[0]
    assert chatbot.generator is generator
    assert kwargs["model"] == "mo-hinh-lon"
    assert kwargs["lookup_workers"] == 5
    assert kwargs["classification_cache_entries"] == 6
    assert kwargs["sparql_cache_bytes"] == 7 * 1024 * 1024


def test_throughput_defaults_are_bounded(monkeypatch) -> None:
    monkeypatch.delenv("ONTCHATBOT_ONNX_THREADS", raising=False)
    monkeypatch.delenv("ONTCHATBOT_LOOKUP_WORKERS", raising=False)
    monkeypatch.delenv("ONTCHATBOT_TURN_SLOTS", raising=False)
    monkeypatch.delenv("ONTCHATBOT_TURN_QUEUE", raising=False)
    monkeypatch.delenv("ONTCHATBOT_CLASSIFICATION_CACHE_ENTRIES", raising=False)
    monkeypatch.delenv("ONTCHATBOT_SPARQL_CACHE_MIB", raising=False)

    args = _parse_args(_flags())

    assert (args.onnx_threads, args.lookup_workers) == (1, 8)
    assert (args.turn_slots, args.turn_queue) == (16, 64)
    assert args.classification_cache_entries == 4096
    assert args.sparql_cache_mib == 64


def test_cloud_run_port_comes_from_the_environment(monkeypatch) -> None:
    monkeypatch.setenv("PORT", "8080")

    args = _parse_args(_flags())

    assert args.port == 8080


def test_cpu_limits_can_come_from_the_environment(monkeypatch) -> None:
    monkeypatch.setenv("ONTCHATBOT_ONNX_THREADS", "3")
    monkeypatch.setenv("ONTCHATBOT_LOOKUP_WORKERS", "2")
    monkeypatch.setenv("ONTCHATBOT_TURN_SLOTS", "4")
    monkeypatch.setenv("ONTCHATBOT_TURN_QUEUE", "6")
    monkeypatch.setenv("ONTCHATBOT_CLASSIFICATION_CACHE_ENTRIES", "8")
    monkeypatch.setenv("ONTCHATBOT_SPARQL_CACHE_MIB", "10")

    args = _parse_args(_flags())

    assert (args.onnx_threads, args.lookup_workers) == (3, 2)
    assert (args.turn_slots, args.turn_queue) == (4, 6)
    assert (args.classification_cache_entries, args.sparql_cache_mib) == (8, 10)


@pytest.mark.parametrize(
    ("flag", "environment"),
    [
        ("--onnx-threads", "ONTCHATBOT_ONNX_THREADS"),
        ("--lookup-workers", "ONTCHATBOT_LOOKUP_WORKERS"),
        ("--turn-slots", "ONTCHATBOT_TURN_SLOTS"),
        ("--turn-queue", "ONTCHATBOT_TURN_QUEUE"),
    ],
)
@pytest.mark.parametrize("value", ["0", "-1", "abc"])
def test_cpu_limits_reject_invalid_values(monkeypatch, flag, environment, value) -> None:
    with pytest.raises(SystemExit):
        _parse_args(_flags(flag, value))
    monkeypatch.setenv(environment, value)
    with pytest.raises(SystemExit):
        _parse_args(_flags())


@pytest.mark.parametrize(
    ("flag", "environment"),
    [
        ("--classification-cache-entries", "ONTCHATBOT_CLASSIFICATION_CACHE_ENTRIES"),
        ("--sparql-cache-mib", "ONTCHATBOT_SPARQL_CACHE_MIB"),
    ],
)
@pytest.mark.parametrize("value", ["-1", "abc"])
def test_cache_budgets_reject_negative_or_non_integer_values(
    monkeypatch, flag, environment, value
) -> None:
    with pytest.raises(SystemExit):
        _parse_args(_flags(flag, value))
    monkeypatch.setenv(environment, value)
    with pytest.raises(SystemExit):
        _parse_args(_flags())


def test_zero_disables_completed_caches() -> None:
    args = _parse_args(
        _flags("--classification-cache-entries", "0", "--sparql-cache-mib", "0")
    )

    assert (args.classification_cache_entries, args.sparql_cache_mib) == (0, 0)


def test_runtime_revisions_hash_only_the_ontology_and_catalogue(
    monkeypatch, tmp_path
) -> None:
    import ontchatbot.cli.serve as serve

    ontology = tmp_path / "ontology.ttl"
    catalogue = tmp_path / "catalogue.jsonl"
    classifier = tmp_path / "classifier.onnx"
    ontology.write_text("ontology", encoding="utf-8")
    catalogue.write_text("catalogue", encoding="utf-8")
    classifier.write_text("model contents must not be read", encoding="utf-8")
    monkeypatch.setattr(serve, "ONTOLOGY_PATH", ontology)
    monkeypatch.setattr(serve, "QUERY_CATALOGUE_PATH", catalogue)
    monkeypatch.setenv("ONTCHATBOT_MODEL_REVISION", "release-7")

    opened = []
    original_open = Path.open

    def track_open(path, *args, **kwargs):
        opened.append(path)
        if path == classifier:
            raise AssertionError("the model file must never be hashed at startup")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(serve.Path, "open", track_open)

    revisions = _runtime_revisions()

    assert revisions["model"] == "release-7"
    assert len(revisions["ontology"]) == len(revisions["catalogue"]) == 64
    assert opened == [ontology, catalogue]


def test_oversubscribed_cpu_budget_is_logged(monkeypatch, caplog) -> None:
    monkeypatch.setattr("ontchatbot.cli.serve._visible_cpu_count", lambda: 4)

    with caplog.at_level(logging.WARNING, logger="ontchatbot.cli.serve"):
        _log_cpu_budget(onnx_threads=2, lookup_workers=4)

    assert "8 native threads" in caplog.text
    assert "4 visible CPUs" in caplog.text


def test_default_cpu_budget_does_not_warn_with_exactly_eight_visible_cpus(
    monkeypatch, caplog
) -> None:
    """A budget equal to CPU affinity is not oversubscription."""
    monkeypatch.delenv("ONTCHATBOT_ONNX_THREADS", raising=False)
    monkeypatch.delenv("ONTCHATBOT_LOOKUP_WORKERS", raising=False)
    monkeypatch.setattr("ontchatbot.cli.serve._visible_cpu_count", lambda: 8)
    args = _parse_args(_flags())

    with caplog.at_level(logging.WARNING, logger="ontchatbot.cli.serve"):
        _log_cpu_budget(
            onnx_threads=args.onnx_threads, lookup_workers=args.lookup_workers
        )

    assert (args.onnx_threads, args.lookup_workers) == (1, 8)
    assert not caplog.records


def test_serve_stops_when_it_cannot_reach_a_language_model(monkeypatch) -> None:
    """Thiếu một trong hai thứ thì dừng ngay lúc khởi động.

    Nếu không, máy chủ lên bình thường rồi mọi câu hỏi mới hỏng, và triệu chứng
    hiện ra ở phía người dùng chứ không phải ở nhật ký khởi động.
    """

    monkeypatch.delenv("ONTCHATBOT_LLM_API_KEY", raising=False)
    monkeypatch.delenv("ONTCHATBOT_LLM_MODEL", raising=False)

    with pytest.raises(SystemExit):
        _build_agent(_parse_args(["--model-dir", "generator"]))

    monkeypatch.setenv("ONTCHATBOT_LLM_MODEL", "mo-hinh-lon")
    with pytest.raises(SystemExit):
        _build_agent(_parse_args(["--model-dir", "generator"]))


def test_serve_log_level_defaults_to_info_and_accepts_debug() -> None:
    assert _parse_args(_flags()).log_level == "info"
    assert _parse_args(_flags("--log-level", "debug")).log_level == "debug"


def test_configure_logging_uses_requested_level_and_trace_fields(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(logging, "basicConfig", lambda **kwargs: calls.append(kwargs))

    _configure_logging("warning")

    assert calls == [
        {
            "level": logging.WARNING,
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S%z",
        }
    ]


def test_the_log_timestamp_carries_its_time_zone(monkeypatch) -> None:
    """Mốc thời gian phải tự nói nó thuộc múi giờ nào.

    Máy chủ và người đọc nhật ký thường ở hai múi giờ khác nhau. Thiếu độ lệch
    thì cùng một dòng được hai bên đọc ra hai thời điểm cách nhau nhiều tiếng,
    và không có gì trên màn hình để lộ chuyện đó.
    """

    calls = []
    monkeypatch.setattr(logging, "basicConfig", lambda **kwargs: calls.append(kwargs))

    _configure_logging("info")

    stamped = time.strftime(calls[0]["datefmt"], time.localtime())
    assert re.fullmatch(r"\d{4}-\d\d-\d\d \d\d:\d\d:\d\d[+-]\d{4}", stamped)


def test_serve_no_longer_takes_the_flags_of_the_replaced_runtime() -> None:
    """Các cờ của bộ chạy cũ phải biến mất, không im lặng bị bỏ qua.

    Một cờ bị gỡ mà vẫn nhận vào sẽ khiến lệnh triển khai cũ chạy được nhưng
    không còn tác dụng, và không ai biết.
    """
    for flag in ("--compute-type", "--inter-threads", "--compiled-dir", "--device"):
        with pytest.raises(SystemExit):
            _parse_args(_flags(flag, "gi-do"))


def test_the_web_server_logs_through_the_same_format(monkeypatch, caplog) -> None:
    """Máy chủ web không được dựng khuôn nhật ký riêng.

    Khuôn mặc định của nó không có mốc thời gian. Để nguyên thì nhật ký trộn hai
    kiểu dòng, và các dòng ghi lượt truy cập mất giờ.
    """

    import ontchatbot.cli.serve as serve

    seen = {}

    def run(app, **kwargs):
        seen["app"] = app
        seen.update(kwargs)

    fake = SimpleNamespace(run=run)
    monkeypatch.setitem(__import__("sys").modules, "uvicorn", fake)
    monkeypatch.setattr(serve, "_build_agent", lambda args: object())
    monkeypatch.setattr(serve, "_parse_args", lambda: _parse_args(_flags()))
    configured = {}
    monkeypatch.setattr(
        serve,
        "create_app",
        lambda agent, *, gate: configured.update(agent=agent, gate=gate) or object(),
    )
    monkeypatch.setattr(serve, "_runtime_revisions", lambda: {
        "model": "release-7",
        "ontology": "a" * 64,
        "catalogue": "b" * 64,
    })

    with caplog.at_level(logging.INFO, logger="ontchatbot.cli.serve"):
        serve.main()

    assert seen["log_config"] is None
    gate = configured["gate"]
    assert (gate._slots._value, gate._queue_size) == (16, 64)
    startup = "\n".join(record.getMessage() for record in caplog.records)
    assert "turn slots=16" in startup
    assert "queue=64" in startup
    assert "classification cache entries=4096" in startup
    assert "SPARQL cache=64 MiB" in startup
    assert "release-7" in startup
    assert "a" * 64 in startup
    assert "b" * 64 in startup
