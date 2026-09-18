from __future__ import annotations

import asyncio
import logging
import re
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from ontchatbot.cli.serve import _build_agent, _configure_logging, _parse_args
from ontchatbot.settings import ONTOLOGY_PATH


def _flags(*extra: str) -> list[str]:
    return ["--llm", "mo-hinh-lon", *extra]


def test_importing_the_server_does_not_import_the_search_libraries() -> None:
    """Máy chủ nhập nhanh; ontology và chỉ mục chỉ nạp khi dựng trợ lý."""

    script = (
        "import sys; import ontchatbot.cli.serve; "
        "print(*(int(name in sys.modules) for name in ('numpy', 'pyoxigraph', 'bm25s', 'pyshacl')))"
    )

    result = subprocess.run([sys.executable, "-c", script], check=True, capture_output=True, text=True)

    assert result.stdout.strip() == "0 0 0 0"


def test_lookup_is_built_from_the_configured_ontology(monkeypatch, tmp_path) -> None:
    import ontchatbot.cli.serve as serve

    ontology = tmp_path / "ontology.trig"
    args = _parse_args(_flags("--ontology", str(ontology), "--search-workers", "3", "--top-k", "5"))
    opened = {}

    def open_engine(source, *, top_k):
        opened.update(path=source.path, top_k=top_k)
        return "engine"

    monkeypatch.setattr("ontchatbot.search.SearchEngine.open", open_engine)
    monkeypatch.setattr(
        "ontchatbot.runtime.lookup.OntologyLookup",
        lambda engine, *, workers: ("lookup", engine, workers),
    )

    assert serve._build_lookup(args) == ("lookup", "engine", 3)
    assert opened == {"path": ontology, "top_k": 5}


def test_building_the_agent_eagerly_loads_lookup_before_health(monkeypatch) -> None:
    """A health-ready agent must already be able to run its lookup tool."""

    import ontchatbot.cli.serve as serve

    built = []

    class Lookup:
        async def __call__(self, keywords):
            return '{"ket_qua":[]}'

        async def aclose(self):
            built.append("closed")

    monkeypatch.setenv("ONTCHATBOT_LLM_API_KEY", "khoa-thu")
    monkeypatch.setattr(serve, "_build_lookup", lambda _args: built.append("lookup") or Lookup())
    monkeypatch.setattr(serve, "_build_instructions", lambda _lookup: "loi-nhac")

    agent = _build_agent(_parse_args(_flags()))
    assert built == ["lookup"]
    asyncio.run(agent.aclose())
    assert built == ["lookup", "closed"]


def test_defaults_are_bounded_and_point_at_the_packaged_ontology(monkeypatch) -> None:
    for name in ("ONTCHATBOT_SEARCH_WORKERS", "ONTCHATBOT_SEARCH_TOP_K", "ONTCHATBOT_TURN_SLOTS",
                 "ONTCHATBOT_TURN_QUEUE", "ONTCHATBOT_ONTOLOGY_PATH"):
        monkeypatch.delenv(name, raising=False)

    args = _parse_args(_flags())

    assert (args.search_workers, args.top_k) == (4, 5)
    assert (args.turn_slots, args.turn_queue) == (16, 64)
    assert Path(args.ontology) == ONTOLOGY_PATH


def test_cloud_run_port_comes_from_the_environment(monkeypatch) -> None:
    monkeypatch.setenv("PORT", "8080")

    assert _parse_args(_flags()).port == 8080


def test_limits_and_ontology_path_can_come_from_the_environment(monkeypatch) -> None:
    monkeypatch.setenv("ONTCHATBOT_SEARCH_WORKERS", "2")
    monkeypatch.setenv("ONTCHATBOT_SEARCH_TOP_K", "3")
    monkeypatch.setenv("ONTCHATBOT_TURN_SLOTS", "4")
    monkeypatch.setenv("ONTCHATBOT_TURN_QUEUE", "6")
    monkeypatch.setenv("ONTCHATBOT_ONTOLOGY_PATH", "/data/ontology.trig")

    args = _parse_args(_flags())

    assert (args.search_workers, args.top_k) == (2, 3)
    assert (args.turn_slots, args.turn_queue) == (4, 6)
    assert Path(args.ontology) == Path("/data/ontology.trig")


@pytest.mark.parametrize(
    ("flag", "environment"),
    [
        ("--search-workers", "ONTCHATBOT_SEARCH_WORKERS"),
        ("--top-k", "ONTCHATBOT_SEARCH_TOP_K"),
        ("--turn-slots", "ONTCHATBOT_TURN_SLOTS"),
        ("--turn-queue", "ONTCHATBOT_TURN_QUEUE"),
    ],
)
@pytest.mark.parametrize("value", ["0", "-1", "abc"])
def test_limits_reject_invalid_values(monkeypatch, flag, environment, value) -> None:
    with pytest.raises(SystemExit):
        _parse_args(_flags(flag, value))
    monkeypatch.setenv(environment, value)
    with pytest.raises(SystemExit):
        _parse_args(_flags())


def test_serve_stops_when_it_cannot_reach_a_language_model(monkeypatch) -> None:
    """Thiếu một trong hai thứ thì dừng ngay lúc khởi động.

    Nếu không, máy chủ lên bình thường rồi mọi câu hỏi mới hỏng, và triệu chứng
    hiện ra ở phía người dùng chứ không phải ở nhật ký khởi động.
    """

    monkeypatch.delenv("ONTCHATBOT_LLM_API_KEY", raising=False)
    monkeypatch.delenv("ONTCHATBOT_LLM_MODEL", raising=False)

    with pytest.raises(SystemExit):
        _build_agent(_parse_args([]))

    monkeypatch.setenv("ONTCHATBOT_LLM_MODEL", "mo-hinh-lon")
    with pytest.raises(SystemExit):
        _build_agent(_parse_args([]))


def test_server_rejects_missing_llm_credentials_before_loading_the_ontology(monkeypatch) -> None:
    import ontchatbot.cli.serve as serve

    monkeypatch.setenv("ONTCHATBOT_BACKEND_TOKEN", "server-secret")
    monkeypatch.delenv("ONTCHATBOT_LLM_API_KEY", raising=False)
    monkeypatch.setattr(serve, "_parse_args", lambda: _parse_args(_flags()))
    monkeypatch.setattr(serve, "_build_lookup", lambda _args: pytest.fail("ontology must not load"))
    monkeypatch.setitem(
        sys.modules, "uvicorn", SimpleNamespace(run=lambda *_args, **_kwargs: pytest.fail("server must not start"))
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


def test_the_web_server_logs_through_the_same_format(monkeypatch) -> None:
    """Máy chủ web không được dựng khuôn nhật ký riêng.

    Khuôn mặc định của nó không có mốc thời gian. Để nguyên thì nhật ký trộn hai
    kiểu dòng, và các dòng ghi lượt truy cập mất giờ.
    """

    import ontchatbot.cli.serve as serve

    seen = {}
    configured = {}
    monkeypatch.setitem(sys.modules, "uvicorn", SimpleNamespace(run=lambda app, **kwargs: seen.update(kwargs)))
    monkeypatch.setenv("ONTCHATBOT_BACKEND_TOKEN", "server-secret")
    monkeypatch.setenv("ONTCHATBOT_LLM_API_KEY", "provider-secret")
    monkeypatch.setattr(serve, "_build_agent", lambda args: object())
    monkeypatch.setattr(serve, "_parse_args", lambda: _parse_args(_flags()))
    monkeypatch.setattr(
        serve,
        "create_app",
        lambda agent, *, gate, backend_token=None, **_options: configured.update(gate=gate, backend_token=backend_token)
        or object(),
    )

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
    monkeypatch.setattr(serve, "_build_agent", lambda args: built.append(args) or "tro-ly")
    monkeypatch.setattr(serve, "create_app", lambda runtime, **_kwargs: configured.update(runtime=runtime) or object())
    monkeypatch.setitem(sys.modules, "uvicorn", SimpleNamespace(run=lambda *_args, **_kwargs: None))

    serve.main()

    assert built == [_parse_args(_flags())]
    assert configured["runtime"] == "tro-ly"


def test_the_web_server_refuses_to_start_without_a_backend_token(monkeypatch) -> None:
    import ontchatbot.cli.serve as serve

    monkeypatch.delenv("ONTCHATBOT_BACKEND_TOKEN", raising=False)
    monkeypatch.setitem(sys.modules, "uvicorn", SimpleNamespace(run=lambda *_args, **_kwargs: None))
    monkeypatch.setattr(serve, "_build_agent", lambda _args: object())
    monkeypatch.setattr(serve, "_parse_args", lambda: _parse_args(_flags()))
    with pytest.raises(SystemExit, match="ONTCHATBOT_BACKEND_TOKEN"):
        serve.main()


def test_the_stored_ontology_is_fetched_before_the_search_index_is_built(monkeypatch) -> None:
    """Trên Cloud Run, bản trong ảnh có thể đã cũ: engine phải dựng từ bản vừa tải về."""

    import ontchatbot.cli.serve as serve

    order = []
    monkeypatch.setenv("ONTCHATBOT_BACKEND_TOKEN", "server-secret")
    monkeypatch.setenv("ONTCHATBOT_LLM_API_KEY", "provider-secret")
    monkeypatch.setattr(serve, "_parse_args", lambda: _parse_args(_flags()))
    monkeypatch.setattr(serve, "_open_remote", lambda args: order.append("tai") or "kho")
    monkeypatch.setattr(serve, "_build_agent", lambda args: order.append("engine") or "tro-ly")
    monkeypatch.setattr(serve, "_build_admin", lambda args, agent, remote: (None, None))
    monkeypatch.setattr(serve, "_watch_remote", lambda args, agent, remote, admin: order.append(("theo doi", remote)))
    monkeypatch.setattr(serve, "create_app", lambda runtime, **_kwargs: object())
    monkeypatch.setitem(sys.modules, "uvicorn", SimpleNamespace(run=lambda *_args, **_kwargs: None))

    serve.main()

    assert order == ["tai", "engine", ("theo doi", "kho")]


def test_without_a_cloud_storage_address_the_ontology_file_is_used_as_is(monkeypatch) -> None:
    import ontchatbot.cli.serve as serve

    monkeypatch.delenv("ONTCHATBOT_ONTOLOGY_GCS_URI", raising=False)

    assert serve._open_remote(_parse_args(_flags())) is None
    assert _parse_args(_flags()).refresh_seconds == 60


def test_chat_history_is_kept_beside_the_ontology_in_cloud_storage(monkeypatch, tmp_path) -> None:
    import ontchatbot.cli.serve as serve
    from ontchatbot.runtime.chatlog import GcsChatLog, LocalChatLog

    monkeypatch.delenv("ONTCHATBOT_CHATLOG", raising=False)
    monkeypatch.setenv("ONTCHATBOT_ONTOLOGY_GCS_URI", "gs://kho/du-lieu/ontology.trig")
    monkeypatch.setenv("ONTCHATBOT_GCS_ACCESS_TOKEN", "khoa")
    remote = serve._build_chat_log()
    assert isinstance(remote, GcsChatLog) and (remote.bucket, remote.prefix) == ("kho", "du-lieu/chat-logs/")

    monkeypatch.delenv("ONTCHATBOT_ONTOLOGY_GCS_URI")
    monkeypatch.setenv("ONTCHATBOT_CHATLOG_DIR", str(tmp_path))
    assert isinstance(serve._build_chat_log(), LocalChatLog)

    monkeypatch.setenv("ONTCHATBOT_CHATLOG", "off")
    assert serve._build_chat_log() is None
