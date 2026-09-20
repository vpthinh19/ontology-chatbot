"""Khởi động dịch vụ: đọc cấu hình, dựng đủ thành phần trước khi mở cổng, đóng chúng khi tắt."""

from __future__ import annotations

import asyncio
import logging
import re
import subprocess
import sys
import time
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

import ontchatbot.cli.serve as serve
from ontchatbot.settings import DEFAULT_LLM_BASE_URL, GEMINI_BASE_URL
from ontchatbot.cli.serve import _config, _configure_logging, _parse_args
from ontchatbot.runtime.service import Config, Service
from ontchatbot.settings import ONTOLOGY_PATH


def _flags(*extra: str) -> list[str]:
    return ["--llm", "mo-hinh-lon", *extra]


@pytest.fixture
def secrets(monkeypatch):
    monkeypatch.setenv("ONTCHATBOT_BACKEND_TOKEN", "server-secret")
    monkeypatch.setenv("ONTCHATBOT_LLM_API_KEY", "provider-secret")
    for name in ("ONTCHATBOT_ADMIN_TOKEN", "ONTCHATBOT_ONTOLOGY_GCS_URI", "ONTCHATBOT_CHATLOG"):
        monkeypatch.delenv(name, raising=False)


def _no_server(monkeypatch, run=lambda *_args, **_kwargs: None) -> None:
    monkeypatch.setitem(sys.modules, "uvicorn", SimpleNamespace(run=run))


def test_importing_the_server_does_not_import_the_search_libraries() -> None:
    """Thư viện tìm kiếm và trang quản trị chỉ nạp trong ``Service.start``."""

    script = (
        "import sys; import ontchatbot.cli.serve; "
        "print(*(int(name in sys.modules) for name in ('numpy', 'pyoxigraph', 'bm25s', 'pyshacl')))"
    )

    result = subprocess.run([sys.executable, "-c", script], check=True, capture_output=True, text=True)

    assert result.stdout.strip() == "0 0 0 0"


# --- cấu hình ---------------------------------------------------------------------


def test_defaults_are_bounded_and_point_at_the_packaged_ontology(monkeypatch) -> None:
    for name in ("ONTCHATBOT_SEARCH_WORKERS", "ONTCHATBOT_SEARCH_TOP_K", "ONTCHATBOT_TURN_SLOTS",
                 "ONTCHATBOT_TURN_QUEUE", "ONTCHATBOT_ONTOLOGY_PATH", "ONTCHATBOT_ONTOLOGY_REFRESH_SECONDS"):
        monkeypatch.delenv(name, raising=False)

    config = _config(_parse_args(_flags()))

    assert (config.search_workers, config.top_k) == (4, 5)
    assert (config.turn_slots, config.turn_queue) == (16, 64)
    assert config.refresh_seconds == 60
    assert config.ontology == ONTOLOGY_PATH


def test_cloud_run_port_comes_from_the_environment(monkeypatch) -> None:
    monkeypatch.setenv("PORT", "8080")

    assert _parse_args(_flags()).port == 8080


def test_limits_and_ontology_path_can_come_from_the_environment(monkeypatch) -> None:
    monkeypatch.setenv("ONTCHATBOT_SEARCH_WORKERS", "2")
    monkeypatch.setenv("ONTCHATBOT_SEARCH_TOP_K", "3")
    monkeypatch.setenv("ONTCHATBOT_TURN_SLOTS", "4")
    monkeypatch.setenv("ONTCHATBOT_TURN_QUEUE", "6")
    monkeypatch.setenv("ONTCHATBOT_ONTOLOGY_PATH", "/data/ontology.trig")

    config = _config(_parse_args(_flags()))

    assert (config.search_workers, config.top_k) == (2, 3)
    assert (config.turn_slots, config.turn_queue) == (4, 6)
    assert config.ontology == Path("/data/ontology.trig")


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


def test_secrets_and_storage_come_from_the_environment() -> None:
    config = Config.from_env({
        "ONTCHATBOT_LLM_API_KEY": "k", "ONTCHATBOT_BACKEND_TOKEN": "b", "ONTCHATBOT_ADMIN_TOKEN": " a ",
        "ONTCHATBOT_ONTOLOGY_GCS_URI": "gs://kho/o.trig", "ONTCHATBOT_CHATLOG": "OFF",
        "ONTCHATBOT_CORS_ORIGINS": "https://a.example/, https://b.example",
    })

    assert (config.llm_api_key, config.backend_token, config.admin_token) == ("k", "b", "a")
    assert config.gcs_uri == "gs://kho/o.trig"
    assert config.chat_log is False
    assert config.cors_origins == ("https://a.example", "https://b.example")
    assert Config.from_env({}).chat_log is True


def test_the_service_stops_when_it_cannot_reach_a_language_model() -> None:
    """Thiếu mô hình hoặc khoá thì dừng ngay lúc khởi động, không để mọi câu hỏi hỏng về sau."""

    with pytest.raises(SystemExit, match="ONTCHATBOT_LLM_MODEL"):
        Config(llm_api_key="k").check_llm()
    with pytest.raises(SystemExit, match="ONTCHATBOT_LLM_API_KEY"):
        Config(llm_model="m").check_llm()


def test_the_endpoints_run_from_the_chosen_model_to_the_spare_provider() -> None:
    """Mô hình chính trước, rồi mô hình dự phòng cùng nhà, cuối cùng mới sang nhà cung cấp khác."""

    khong_gemini = Config(llm_model="chinh", llm_api_key="k", llm_fallback_models=("du-phong", "chinh"))
    assert [(e.model, e.base_url) for e in khong_gemini.endpoints()] == [
        ("chinh", DEFAULT_LLM_BASE_URL), ("du-phong", DEFAULT_LLM_BASE_URL)]

    co_gemini = Config(llm_model="chinh", llm_api_key="k", llm_fallback_models=("du-phong",),
                       gemini_api_key="kg", gemini_model="gemini-x")
    assert [e.model for e in co_gemini.endpoints()] == ["chinh", "du-phong", "gemini-x"]
    assert co_gemini.endpoints()[-1].base_url == GEMINI_BASE_URL


# --- khởi động và tắt ----------------------------------------------------------------


def test_start_builds_a_ready_agent_and_aclose_releases_it() -> None:
    service = Service(Config(llm_model="m", llm_api_key="k", chat_log=False, search_workers=3, top_k=4)).start()

    assert service.lookup.engine.top_k == 4
    assert service.lookup._executor._max_workers == 3
    assert "lookup_academic_information" in service.agent._instructions
    assert service.admin is None and service.remote is None

    asyncio.run(service.aclose())
    assert service._llm._clients == {}
    assert service.lookup._executor._shutdown


def test_the_stored_ontology_is_fetched_before_the_search_index_is_built(monkeypatch) -> None:
    """Trên Cloud Run, bản trong ảnh có thể đã cũ: engine phải dựng từ bản vừa tải về."""

    order = []
    monkeypatch.setattr(Service, "_open_remote", lambda self: order.append("tai") or "kho")
    monkeypatch.setattr(Service, "_open_engine", lambda self: order.append("engine") or "engine")
    monkeypatch.setattr(Service, "_build_agent", lambda self: order.append("tro ly") or "tro-ly")
    monkeypatch.setattr(Service, "_watch_remote", lambda self: order.append(("theo doi", self.remote)))

    Service(Config(llm_model="m", llm_api_key="k", gcs_uri="gs://kho/o.trig", chat_log=False)).start()

    assert order == ["tai", "engine", "tro ly", ("theo doi", "kho")]


def test_without_a_cloud_storage_address_the_ontology_file_is_used_as_is(monkeypatch) -> None:
    monkeypatch.setattr(Service, "_open_remote", lambda self: pytest.fail("không có kho thì không tải"))
    monkeypatch.setattr(Service, "_open_engine", lambda self: "engine")
    monkeypatch.setattr(Service, "_build_agent", lambda self: "tro-ly")

    service = Service(Config(llm_model="m", llm_api_key="k", chat_log=False)).start()

    assert service.remote is None


def test_chat_history_is_kept_beside_the_ontology_in_cloud_storage(tmp_path) -> None:
    from ontchatbot.runtime.chatlog import GcsChatLog, LocalChatLog

    remote = Service(Config(gcs_uri="gs://kho/du-lieu/ontology.trig", gcs_access_token="khoa"))._open_chat_log()
    assert isinstance(remote, GcsChatLog) and (remote.bucket, remote.prefix) == ("kho", "du-lieu/chat-logs/")
    assert remote.token() == "khoa"

    local = Service(Config(chat_log_dir=tmp_path))._open_chat_log()
    assert isinstance(local, LocalChatLog) and local.root == tmp_path


def test_aclose_stops_watching_cloud_storage(monkeypatch) -> None:
    service = Service(Config())
    watched = []
    monkeypatch.setattr("ontchatbot.admin.remote.watch", lambda poll, every, stop: watched.append(stop))
    service.remote = SimpleNamespace(refresh=lambda: False)

    service._watch_remote()
    asyncio.run(service.aclose())

    assert watched == [service._stop] and service._stop.is_set()


# --- dòng lệnh -------------------------------------------------------------------


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
    calls = []
    monkeypatch.setattr(logging, "basicConfig", lambda **kwargs: calls.append(kwargs))

    _configure_logging("info")

    stamped = time.strftime(calls[0]["datefmt"], time.localtime())
    assert re.fullmatch(r"\d{4}-\d\d-\d\d \d\d:\d\d:\d\d[+-]\d{4}", stamped)


def test_the_server_starts_the_whole_service_before_listening(monkeypatch, secrets) -> None:
    order, seen, configured = [], {}, {}
    monkeypatch.setattr(serve, "_parse_args", lambda: _parse_args(_flags()))
    monkeypatch.setattr(Service, "start", lambda self: order.append("start") or self)
    monkeypatch.setattr(
        "ontchatbot.runtime.service.create_app",
        lambda agent, gate, **options: configured.update(gate=gate, **options) or "ung-dung",
    )
    _no_server(monkeypatch, lambda app, **kwargs: order.append(app) or seen.update(kwargs))

    serve.main()

    assert order == ["start", "ung-dung"]
    # Máy chủ web không dựng khuôn nhật ký riêng (khuôn mặc định của nó không có mốc thời gian).
    assert seen["log_config"] is None
    assert configured["backend_token"] == "server-secret"
    assert (configured["gate"]._slots._value, configured["gate"]._queue_size) == (16, 64)
    assert configured["on_close"].__self__.__class__ is Service


def test_the_server_refuses_to_start_without_a_backend_token(monkeypatch, secrets) -> None:
    monkeypatch.delenv("ONTCHATBOT_BACKEND_TOKEN")
    monkeypatch.setattr(serve, "_parse_args", lambda: _parse_args(_flags()))
    monkeypatch.setattr(Service, "start", lambda self: pytest.fail("không được khởi động"))
    _no_server(monkeypatch)

    with pytest.raises(SystemExit, match="ONTCHATBOT_BACKEND_TOKEN"):
        serve.main()


def test_the_server_rejects_missing_llm_credentials_before_loading_the_ontology(monkeypatch, secrets) -> None:
    monkeypatch.delenv("ONTCHATBOT_LLM_API_KEY")
    monkeypatch.setattr(serve, "_parse_args", lambda: _parse_args(_flags()))
    monkeypatch.setattr(Service, "_open_engine", lambda self: pytest.fail("ontology must not load"))
    _no_server(monkeypatch, lambda *_args, **_kwargs: pytest.fail("server must not start"))

    with pytest.raises(SystemExit, match="ONTCHATBOT_LLM_API_KEY"):
        serve.main()


def test_an_admin_key_opens_the_admin_store(tmp_path) -> None:
    import shutil

    shutil.copy(ONTOLOGY_PATH, tmp_path / "ontology.trig")
    shutil.copy(ONTOLOGY_PATH.with_name("shapes.ttl"), tmp_path / "shapes.ttl")
    config = replace(Config(llm_model="m", llm_api_key="k", chat_log=False), ontology=tmp_path / "ontology.trig",
                     admin_token="quan-tri")

    service = Service(config).start()

    assert service.admin is not None and service.admin.path == tmp_path / "ontology.trig"
    asyncio.run(service.aclose())
