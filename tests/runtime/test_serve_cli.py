from __future__ import annotations

import asyncio
import logging
import re
import subprocess
import sys
import threading
import time
from types import SimpleNamespace

import pytest

from ontchatbot.cli.serve import (
    _build_agent,
    _configure_logging,
    _log_cpu_budget,
    _parse_args,
)


def _flags(*extra: str) -> list[str]:
    return ["--model-dir", "generator", "--llm", "mo-hinh-lon", *extra]


def test_importing_the_server_does_not_import_native_inference_libraries() -> None:
    script = (
        "import sys; import ontchatbot.cli.serve; "
        "print(int('numpy' in sys.modules), int('rdflib' in sys.modules))"
    )

    result = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout.strip() == "0 0"


def test_eager_lookup_loads_model_assets_and_ontology_in_parallel(
    monkeypatch,
) -> None:
    import ontchatbot.cli.serve as serve

    args = _parse_args(
        _flags(
            "--onnx-threads",
            "2",
            "--lookup-workers",
            "3",
            "--classification-cache-entries",
            "4",
            "--sparql-cache-mib",
            "5",
        )
    )
    started = threading.Barrier(2, timeout=1)
    graph, assets, generator, pool = object(), object(), object(), object()

    def load_ontology():
        started.wait()
        return graph

    def load_assets(path, **kwargs):
        assert str(path) == "generator"
        assert kwargs == {"intra_op_threads": 2}
        started.wait()
        return assets

    monkeypatch.setattr("ontchatbot.runtime.sparql.load_ontology", load_ontology)
    monkeypatch.setattr(
        "ontchatbot.runtime.onnx_classifier.OnnxClassifierGenerator.load_assets",
        load_assets,
    )
    monkeypatch.setattr(
        "ontchatbot.runtime.onnx_classifier.OnnxClassifierGenerator.from_assets",
        lambda candidate, *, graph: generator,
    )
    monkeypatch.setattr(
        "ontchatbot.runtime.lookup_pool.AsyncLookupPool",
        lambda chatbot, **kwargs: (
            pool
            if chatbot.generator is generator
            and chatbot.graph is graph
            and kwargs
            == {
                "workers": 3,
                "classification_cache_entries": 4,
                "sparql_cache_bytes": 5 * 1024 * 1024,
            }
            else pytest.fail("lookup pool received the wrong runtime configuration")
        ),
    )

    assert serve._build_lookup_pool(args) is pool


def test_eager_lookup_waits_for_both_loaders_when_one_fails(monkeypatch) -> None:
    import ontchatbot.cli.serve as serve

    args = _parse_args(_flags())
    started = threading.Barrier(2, timeout=1)
    onnx_finished = threading.Event()

    def fail_ontology():
        started.wait()
        raise RuntimeError("ontology failed")

    def load_onnx(_path, **_kwargs):
        started.wait()
        onnx_finished.set()
        return object()

    monkeypatch.setattr("ontchatbot.runtime.sparql.load_ontology", fail_ontology)
    monkeypatch.setattr(
        "ontchatbot.runtime.onnx_classifier.OnnxClassifierGenerator.load_assets",
        load_onnx,
    )

    with pytest.raises(RuntimeError, match="ontology failed"):
        serve._build_lookup_pool(args)
    assert onnx_finished.is_set()


def test_building_the_agent_eagerly_loads_lookup_before_health(monkeypatch) -> None:
    """A health-ready agent must already be able to run its lookup tool."""

    import ontchatbot.cli.serve as serve

    built = []

    class Pool:
        async def __call__(self, keywords):
            return '{"du_lieu":[]}'

        async def aclose(self):
            pass

    def build_pool(_args):
        built.append("lookup")
        return Pool()

    monkeypatch.setenv("ONTCHATBOT_LLM_API_KEY", "khoa-thu")
    monkeypatch.setattr(serve, "_build_lookup_pool", build_pool)

    agent = _build_agent(_parse_args(_flags()))
    assert built == ["lookup"]
    asyncio.run(agent.aclose())


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


def test_eager_server_rejects_missing_llm_credentials_before_loading_assets(
    monkeypatch,
) -> None:
    import ontchatbot.cli.serve as serve

    monkeypatch.setenv("ONTCHATBOT_BACKEND_TOKEN", "server-secret")
    monkeypatch.delenv("ONTCHATBOT_LLM_API_KEY", raising=False)
    monkeypatch.setattr(serve, "_parse_args", lambda: _parse_args(_flags()))
    monkeypatch.setitem(
        __import__("sys").modules,
        "uvicorn",
        SimpleNamespace(
            run=lambda *_args, **_kwargs: pytest.fail("server must not start")
        ),
    )

    with pytest.raises(SystemExit, match="ONTCHATBOT_LLM_API_KEY"):
        serve.main()


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
    monkeypatch.setenv("ONTCHATBOT_BACKEND_TOKEN", "server-secret")
    monkeypatch.setenv("ONTCHATBOT_LLM_API_KEY", "provider-secret")
    monkeypatch.setattr(serve, "_build_agent", lambda args: object())
    monkeypatch.setattr(serve, "_parse_args", lambda: _parse_args(_flags()))
    configured = {}
    monkeypatch.setattr(
        serve,
        "create_app",
        lambda agent, *, gate, backend_token=None: configured.update(
            agent=agent, gate=gate, backend_token=backend_token
        ) or object(),
    )
    with caplog.at_level(logging.INFO, logger="ontchatbot.cli.serve"):
        serve.main()

    assert seen["log_config"] is None
    assert configured["backend_token"] == "server-secret"
    gate = configured["gate"]
    assert (gate._slots._value, gate._queue_size) == (16, 64)


def test_the_web_server_builds_the_complete_runtime_before_listening(monkeypatch) -> None:
    import ontchatbot.cli.serve as serve

    built = []
    configured = {}
    monkeypatch.setenv("ONTCHATBOT_BACKEND_TOKEN", "server-secret")
    monkeypatch.setenv("ONTCHATBOT_LLM_API_KEY", "provider-secret")
    monkeypatch.setattr(serve, "_parse_args", lambda: _parse_args(_flags()))
    monkeypatch.setattr(
        serve, "_build_agent", lambda args: built.append(args) or "tro-ly"
    )
    monkeypatch.setattr(
        serve,
        "create_app",
        lambda runtime, **_kwargs: configured.update(runtime=runtime) or object(),
    )
    monkeypatch.setitem(
        __import__("sys").modules,
        "uvicorn",
        SimpleNamespace(run=lambda *_args, **_kwargs: None),
    )

    serve.main()

    assert built == [_parse_args(_flags())]
    assert configured["runtime"] == "tro-ly"


def test_the_web_server_refuses_to_start_without_a_backend_token(monkeypatch) -> None:
    import ontchatbot.cli.serve as serve

    monkeypatch.delenv("ONTCHATBOT_BACKEND_TOKEN", raising=False)
    monkeypatch.setitem(
        __import__("sys").modules,
        "uvicorn",
        SimpleNamespace(run=lambda *_args, **_kwargs: None),
    )
    monkeypatch.setattr(serve, "_build_agent", lambda _args: object())
    monkeypatch.setattr(serve, "_parse_args", lambda: _parse_args(_flags()))
    with pytest.raises(SystemExit, match="ONTCHATBOT_BACKEND_TOKEN"):
        serve.main()
