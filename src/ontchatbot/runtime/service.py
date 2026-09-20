"""Dịch vụ hỏi đáp: cấu hình, các thành phần và vòng đời của chúng.

    start():  (Cloud Storage → đĩa) → engine tìm kiếm → trợ lý → trang quản trị → lịch sử chat → theo dõi kho
    reload(): dựng lại engine từ tệp trên đĩa (sau lần sửa ở trang quản trị, hoặc khi kho có bản mới)
    aclose(): dừng theo dõi kho, chờ ghi xong lịch sử chat, đóng kết nối

Mọi thứ dựng xong trước khi máy chủ mở cổng, nên request đầu tiên không phải chờ nạp.
Thư viện tìm kiếm và trang quản trị chỉ được nạp trong ``start``.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import httpx

from ..settings import (
    DEFAULT_GEMINI_MODEL,
    DEFAULT_LLM_BASE_URL,
    DEFAULT_LLM_FALLBACK_MODELS,
    GEMINI_BASE_URL,
    ONTOLOGY_PATH,
)
from .agent import (
    MODEL_REQUEST_TIMEOUT_SECONDS,
    AgentLoop,
    build_instructions,
    read_vocabulary,
)
from .api import (
    MAX_CONCURRENT_TURNS,
    MAX_MODEL_STEPS,
    MAX_QUEUED_TURNS,
    TurnGate,
    create_app,
)
from .llm import ENDPOINT_READ_TIMEOUT_SECONDS, Endpoint, FallbackClient
from .lookup import OntologyLookup

logger = logging.getLogger(__name__)

_OFF = ("off", "0", "false", "no")


@dataclass(frozen=True)
class Config:
    ontology: Path = ONTOLOGY_PATH
    llm_model: str = ""
    llm_base_url: str = DEFAULT_LLM_BASE_URL
    llm_api_key: str = ""
    #: Mô hình dự phòng cùng nhà cung cấp, thử lần lượt khi mô hình chính không trả lời.
    llm_fallback_models: tuple[str, ...] = DEFAULT_LLM_FALLBACK_MODELS
    #: Nhà cung cấp dự phòng cuối (Google AI Studio); không có khoá thì bỏ qua nấc này.
    gemini_api_key: str = ""
    gemini_model: str = DEFAULT_GEMINI_MODEL
    #: Khoá frontend dùng để gọi API.
    backend_token: str = ""
    #: Có thì mở trang quản trị; cũng là mật khẩu đăng nhập quản trị.
    admin_token: str = ""
    #: ``gs://bucket/thu-muc/ontology.trig``: bản gốc trên Cloud Storage; shapes.ttl và chat-logs/ cùng thư mục.
    gcs_uri: str = ""
    #: Khoá Cloud Storage khi chạy ngoài Google Cloud; trên Cloud Run lấy từ máy chủ metadata.
    gcs_access_token: str = ""
    chat_log: bool = True
    #: Thư mục lịch sử chat khi không dùng Cloud Storage.
    chat_log_dir: Path = Path("logs/chat")
    cors_origins: tuple[str, ...] = ()
    turn_slots: int = MAX_CONCURRENT_TURNS
    turn_queue: int = MAX_QUEUED_TURNS
    search_workers: int = 4
    top_k: int = 5
    #: Chu kỳ hỏi Cloud Storage xem có bản mới.
    refresh_seconds: int = 60

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None, **settings) -> Config:
        """Khoá và các thiết lập chỉ đặt bằng biến môi trường; ``settings`` là phần dòng lệnh đã đọc."""

        env = os.environ if env is None else env

        def value(name: str) -> str:
            return env.get(name, "").strip()

        return cls(
            llm_api_key=value("ONTCHATBOT_LLM_API_KEY"),
            llm_fallback_models=tuple(ten.strip() for ten in value("ONTCHATBOT_LLM_FALLBACK_MODELS").split(",")
                                      if ten.strip()) or DEFAULT_LLM_FALLBACK_MODELS,
            gemini_api_key=value("ONTCHATBOT_LLM_API_KEY_GEMINI"),
            gemini_model=value("ONTCHATBOT_LLM_MODEL_GEMINI") or DEFAULT_GEMINI_MODEL,
            backend_token=value("ONTCHATBOT_BACKEND_TOKEN"),
            admin_token=value("ONTCHATBOT_ADMIN_TOKEN"),
            gcs_uri=value("ONTCHATBOT_ONTOLOGY_GCS_URI"),
            gcs_access_token=value("ONTCHATBOT_GCS_ACCESS_TOKEN"),
            chat_log=value("ONTCHATBOT_CHATLOG").lower() not in _OFF,
            chat_log_dir=Path(value("ONTCHATBOT_CHATLOG_DIR") or "logs/chat"),
            cors_origins=tuple(origin.strip().rstrip("/") for origin in value("ONTCHATBOT_CORS_ORIGINS").split(",")
                               if origin.strip()),
            **settings,
        )

    def check_llm(self) -> None:
        """Dừng ngay khi thiếu mô hình hoặc khoá, trước khi nạp gì."""

        if not self.llm_model:
            raise SystemExit("chưa chỉ định mô hình ngôn ngữ lớn: dùng --llm hoặc đặt ONTCHATBOT_LLM_MODEL")
        if not self.llm_api_key:
            raise SystemExit("chưa đặt ONTCHATBOT_LLM_API_KEY")

    def endpoints(self) -> list[Endpoint]:
        """Mô hình chính trước, rồi các mô hình dự phòng cùng nhà, cuối cùng là nhà cung cấp khác."""

        base = self.llm_base_url.rstrip("/") + "/"
        ra = [Endpoint(base, self.llm_api_key, self.llm_model)]
        ra += [Endpoint(base, self.llm_api_key, ten) for ten in self.llm_fallback_models if ten != self.llm_model]
        if self.gemini_api_key:
            ra.append(Endpoint(GEMINI_BASE_URL, self.gemini_api_key, self.gemini_model))
        return ra


class Service:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.remote = None
        self.lookup: OntologyLookup | None = None
        self.agent: AgentLoop | None = None
        self.admin = None
        self.chat_log = None
        self._llm: FallbackClient | None = None
        self._gcs_object = None
        self._stop = threading.Event()

    # --- khởi động -------------------------------------------------------------

    def start(self) -> Service:
        """Dựng mọi thành phần; ghi lại thời gian từng chặng để còn biết lần khởi động nguội tốn ở đâu."""

        moc, chang = time.perf_counter(), {}

        def xong(ten: str) -> None:
            nonlocal moc
            gio = time.perf_counter()
            chang[ten] = round((gio - moc) * 1000)
            moc = gio

        self.config.check_llm()
        if self.config.gcs_uri:
            # Tải ontology về là chờ mạng, nạp thư viện tìm kiếm là chờ CPU: làm cùng lúc.
            nap = threading.Thread(target=self._import_search, name="nap-thu-vien-tim-kiem", daemon=True)
            nap.start()
            self.remote = self._open_remote()
            xong("cloud storage")
            nap.join()
            xong("chờ nạp thư viện")
        self.lookup = OntologyLookup(self._open_engine(), workers=self.config.search_workers)
        xong("engine")
        self.agent = self._build_agent()
        xong("agent")
        if self.config.admin_token:
            self.open_admin()
            xong("admin")
        if self.config.chat_log:
            self.chat_log = self._open_chat_log()
        if self.remote is not None:
            self._watch_remote()
        xong("phần còn lại")
        logger.info("service started in %d ms (%s)", sum(chang.values()),
                    ", ".join(f"{ten} {ms} ms" for ten, ms in chang.items()))
        return self

    def app(self):
        config = self.config
        return create_app(
            self.agent,
            TurnGate(slots=config.turn_slots, queue_size=config.turn_queue),
            backend_token=config.backend_token or None,
            admin=self.admin,
            admin_token=config.admin_token or None,
            chat_log=self.chat_log,
            cors_origins=config.cors_origins,
            on_close=self.aclose,
        )

    def _gcs(self):
        """Đối tượng ontology.trig trên Cloud Storage. Mọi đối tượng khác dùng chung kết nối và khoá của nó."""

        from ..admin.remote import GcsObject, default_token

        if self._gcs_object is None:
            http = httpx.Client(timeout=30.0)
            self._gcs_object = GcsObject.from_uri(self.config.gcs_uri, http=http,
                                                  token=default_token(http, self.config.gcs_access_token))
        return self._gcs_object

    def _open_remote(self):
        """Tải bản gốc về đè lên tệp trên đĩa; kho chưa có thì đưa tệp trong ảnh lên."""

        from ..admin.remote import RemoteOntology

        remote = RemoteOntology.beside(self._gcs(), self.config.ontology)
        remote.start()
        return remote

    @staticmethod
    def _import_search() -> None:
        """Nạp sẵn gói tìm kiếm (kéo theo numpy, bm25s, pyoxigraph): phần nặng nhất của lần khởi động nguội."""

        from ..search import SearchEngine  # noqa: F401

    def _open_engine(self):
        from ..search import SearchEngine, TriGFileSource

        return SearchEngine.open(TriGFileSource(self.config.ontology), top_k=self.config.top_k)

    def _build_agent(self) -> AgentLoop:
        config = self.config
        diem_cuoi = config.endpoints()
        logger.info("model endpoints: %s", " → ".join(e.label for e in diem_cuoi))
        self._llm = FallbackClient(diem_cuoi, open_client=self._open_llm_http)
        instructions = build_instructions(read_vocabulary(self.lookup.engine.ontology))
        return AgentLoop(self._llm, self.lookup, instructions=instructions, max_steps=MAX_MODEL_STEPS)

    @staticmethod
    def _open_llm_http(endpoint: Endpoint) -> httpx.AsyncClient:
        """Kết nối tới một điểm cuối; chỉ mở khi điểm cuối đó thật sự được dùng tới."""

        return httpx.AsyncClient(
            base_url=endpoint.base_url,
            headers={"Authorization": f"Bearer {endpoint.api_key}", "Content-Type": "application/json"},
            # Chờ mảnh đầu quá ENDPOINT_READ_TIMEOUT_SECONDS thì coi như điểm cuối này im, chuyển nơi khác.
            timeout=httpx.Timeout(MODEL_REQUEST_TIMEOUT_SECONDS, read=ENDPOINT_READ_TIMEOUT_SECONDS),
        )

    def open_admin(self):
        """Kho sửa ontology cho trang quản trị. Mỗi lần ghi xong, engine nạp lại."""

        from ..admin import AdminStore, Schema

        shapes = Path(self.config.ontology).with_name("shapes.ttl")
        self.admin = AdminStore(
            self.config.ontology,
            Schema.from_file(shapes),
            shapes_path=shapes,
            on_change=lambda _path: self.reload("after an admin edit"),
            persist=self._persist if self.remote is not None else None,
        )
        return self.admin

    def _persist(self, files: dict[Path, bytes]) -> None:
        """Ghi lần sửa lên Cloud Storage trước khi ghi đĩa.

        Phiên khác vừa ghi trước thì tải bản mới và từ chối lần sửa (409); lỗi mạng thì báo chưa lưu (503).
        """

        from ..admin import Conflict, Unavailable
        from ..admin.remote import StaleCopy

        try:
            self.remote.push(files)
        except StaleCopy:
            if self.admin.reload(self.remote.refresh):
                self.reload("from Cloud Storage after a conflicting edit")
            raise Conflict(
                "Ontology vừa được sửa ở một phiên khác. Dữ liệu mới đã được tải; hãy mở lại thực thể và sửa lại."
            ) from None
        except Exception as exc:
            logger.exception("could not save the ontology to Cloud Storage")
            raise Unavailable("Chưa lưu được lên kho lưu trữ nên chưa có gì thay đổi; hãy thử lại sau ít phút.") from exc

    def _open_chat_log(self):
        """Lịch sử chat: thư mục chat-logs/ cạnh ontology trên Cloud Storage, không thì thư mục trên đĩa."""

        from .chatlog import GcsChatLog, LocalChatLog

        if not self.config.gcs_uri:
            return LocalChatLog(self.config.chat_log_dir)
        ontology = self._gcs()
        folder = ontology.name.rsplit("/", 1)[0] + "/" if "/" in ontology.name else ""
        return GcsChatLog(ontology.bucket, folder + "chat-logs/", http=ontology.http, token=ontology.token)

    def _watch_remote(self) -> None:
        """Nhiều bản dịch vụ chạy song song: mỗi bản định kỳ tải lần sửa mà bản khác đã ghi lên kho."""

        from ..admin.remote import watch

        def poll() -> None:
            changed = self.admin.reload(self.remote.refresh) if self.admin is not None else self.remote.refresh()
            if changed:
                self.reload("from Cloud Storage")

        watch(poll, self.config.refresh_seconds, self._stop)

    # --- trong lúc chạy và khi tắt ------------------------------------------------

    def reload(self, why: str) -> None:
        self.lookup.engine = self._open_engine()
        logger.info("ontology reloaded %s path=%s", why, self.config.ontology)

    async def aclose(self) -> None:
        self._stop.set()
        if self.chat_log is not None:
            self.chat_log.close()
        if self._llm is not None:
            await self._llm.aclose()
        if self.lookup is not None:
            await self.lookup.aclose()
        if self._gcs_object is not None:
            self._gcs_object.http.close()
