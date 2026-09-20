"""Bản gốc của ontology trên Google Cloud Storage, cho dịch vụ chạy trên Cloud Run.

Container không giữ tệp và có thể chạy nhiều bản, nên bản gốc là đối tượng Cloud Storage; mỗi bản
dịch vụ giữ một bản sao trên đĩa cho engine và trang quản trị.

- Khởi động: tải ontology.trig và shapes.ttl về đè lên bản sao; kho chưa có thì đưa tệp trong ảnh lên.
- Lưu: ghi kèm điều kiện số thế hệ (generation) chưa đổi; phiên khác vừa lưu thì kho từ chối (412).
- Các bản dịch vụ khác định kỳ hỏi số thế hệ và tải lại khi nó đổi.

Gọi thẳng JSON API bằng httpx (không thêm google-cloud-storage vào ảnh).
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from pathlib import Path
from urllib.parse import quote

from .trig import write_bytes

logger = logging.getLogger(__name__)

API = "https://storage.googleapis.com"
METADATA_TOKEN_URL = "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token"
CONTENT_TYPES = {".trig": "application/trig", ".ttl": "text/turtle"}


class StaleCopy(Exception):
    """Đối tượng trên Cloud Storage đã được ghi bởi một phiên khác từ lần đọc gần nhất."""


class MetadataToken:
    """Khoá truy cập của tài khoản dịch vụ Cloud Run, giữ lại tới gần lúc hết hạn."""

    def __init__(self, http, clock: Callable[[], float] = time.monotonic) -> None:
        self.http = http
        self.clock = clock
        self._token = ""
        self._until = 0.0

    def __call__(self) -> str:
        if self.clock() >= self._until:
            response = self.http.get(METADATA_TOKEN_URL, headers={"Metadata-Flavor": "Google"})
            response.raise_for_status()
            body = response.json()
            self._token = body["access_token"]
            self._until = self.clock() + max(int(body.get("expires_in", 0)) - 60, 0)
        return self._token


def default_token(http, fixed: str = "") -> Callable[[], str]:
    """Khoá cố định nếu có (chạy ngoài Google Cloud), không thì khoá từ máy chủ metadata của Cloud Run."""

    return (lambda: fixed) if fixed else MetadataToken(http)


class GcsObject:
    """Một đối tượng Cloud Storage, đọc và ghi qua JSON API."""

    def __init__(self, bucket: str, name: str, *, http=None, token: Callable[[], str] | None = None) -> None:
        if http is None:
            import httpx

            http = httpx.Client(timeout=30.0)
        self.bucket = bucket
        self.name = name
        self.http = http
        self.token = token or default_token(http)

    #: Tên tệp mặc định khi địa chỉ chỉ nêu bucket hoặc thư mục.
    MAC_DINH = "ontology.trig"

    @classmethod
    def from_uri(cls, uri: str, **options) -> GcsObject:
        """``gs://bucket``, ``gs://bucket/thư-mục`` hay ``gs://bucket/thư-mục/ontology.trig``.

        Không nêu tên tệp thì lấy ``ontology.trig``; shapes.ttl và chat-logs/ nằm cùng thư mục với nó.
        """

        if not uri.startswith("gs://"):
            raise ValueError(f"địa chỉ Cloud Storage phải bắt đầu bằng gs://: {uri!r}")
        bucket, _, name = uri[5:].partition("/")
        name = name.strip("/")
        if not bucket:
            raise ValueError(f"địa chỉ Cloud Storage phải nêu bucket: {uri!r}")
        if "." not in name.rsplit("/", 1)[-1]:      # trống hoặc là thư mục
            name = f"{name}/{cls.MAC_DINH}" if name else cls.MAC_DINH
        return cls(bucket, name, **options)

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token()}"}

    def _object_url(self) -> str:
        return f"{API}/storage/v1/b/{quote(self.bucket, safe='')}/o/{quote(self.name, safe='')}"

    @staticmethod
    def _fail(response, action: str) -> None:
        raise RuntimeError(f"Cloud Storage từ chối {action}: HTTP {response.status_code} {response.text[:300]}")

    def generation(self) -> str | None:
        """Số thế hệ hiện tại; ``None`` khi đối tượng chưa tồn tại."""

        response = self.http.get(self._object_url(), params={"fields": "generation"}, headers=self._headers())
        if response.status_code == 404:
            return None
        if response.status_code != 200:
            self._fail(response, "đọc thông tin đối tượng")
        return str(response.json()["generation"])

    def download(self) -> tuple[bytes, str]:
        """Nội dung và số thế hệ của đúng nội dung đó."""

        response = self.http.get(self._object_url(), params={"alt": "media"}, headers=self._headers())
        if response.status_code != 200:
            self._fail(response, "tải đối tượng")
        return response.content, response.headers["x-goog-generation"]

    def upload(self, data: bytes, if_generation: str) -> str:
        """Ghi nếu số thế hệ trên kho vẫn là ``if_generation`` ("0": chỉ khi chưa có đối tượng)."""

        response = self.http.post(
            f"{API}/upload/storage/v1/b/{quote(self.bucket, safe='')}/o",
            params={"uploadType": "media", "name": self.name, "ifGenerationMatch": if_generation},
            headers={**self._headers(), "Content-Type": CONTENT_TYPES.get(Path(self.name).suffix, "text/plain")},
            content=data,
        )
        if response.status_code == 412:
            raise StaleCopy(self.name)
        if response.status_code != 200:
            self._fail(response, "ghi đối tượng")
        return str(response.json()["generation"])


class RemoteOntology:
    """Giữ các tệp trên đĩa (ontology.trig, shapes.ttl) khớp với các đối tượng trên Cloud Storage."""

    def __init__(self, files: dict[Path | str, GcsObject]) -> None:
        self.files = {Path(path): remote for path, remote in files.items()}
        self.generations: dict[Path, str | None] = dict.fromkeys(self.files)
        self._lock = threading.Lock()

    @classmethod
    def beside(cls, remote: GcsObject, ontology: Path | str) -> RemoteOntology:
        """``remote`` giữ ontology.trig; lược đồ là đối tượng shapes.ttl cùng thư mục trên kho."""

        folder = remote.name.rsplit("/", 1)[0] + "/" if "/" in remote.name else ""
        shapes = GcsObject(remote.bucket, folder + "shapes.ttl", http=remote.http, token=remote.token)
        return cls({ontology: remote, Path(ontology).with_name("shapes.ttl"): shapes})

    def start(self) -> None:
        """Gọi một lần trước khi nạp engine."""

        with self._lock:
            for path, remote in self.files.items():
                if remote.generation() is None:
                    try:
                        self.generations[path] = remote.upload(path.read_bytes(), "0")
                        logger.info("ontology seeded to Cloud Storage object=%s generation=%s",
                                    remote.name, self.generations[path])
                        continue
                    except StaleCopy:  # một bản dịch vụ khởi động cùng lúc vừa đưa lên trước
                        pass
                self._download(path)
                logger.info("ontology loaded from Cloud Storage object=%s generation=%s",
                            remote.name, self.generations[path])

    def refresh(self) -> bool:
        """Tải những tệp có số thế hệ đã đổi; trả ``True`` khi có tệp trên đĩa vừa được thay."""

        with self._lock:
            changed = False
            for path, remote in self.files.items():
                current = remote.generation()
                if current is not None and current != self.generations[path]:
                    self._download(path)
                    logger.info("ontology refreshed from Cloud Storage object=%s generation=%s",
                                remote.name, self.generations[path])
                    changed = True
            return changed

    def push(self, files: dict[Path, bytes]) -> None:
        """Ghi một lần sửa; ``StaleCopy`` khi bản đang giữ đã cũ.

        Mọi tệp phải còn đúng bản đang giữ, kể cả tệp lần này không đổi: một lần sửa mục dựng trên
        lược đồ cũ không được ghi đè lên dữ liệu đã khớp với lược đồ mới của phiên khác.
        """

        with self._lock:
            for path, remote in self.files.items():
                if remote.generation() != self.generations[path]:
                    raise StaleCopy(remote.name)
            written = []
            try:
                for path, data in files.items():
                    self.generations[path] = self.files[path].upload(data, self.generations[path] or "0")
                    written.append(path)
            except BaseException:
                # Tệp đã lên kho nhưng lần sửa bị huỷ: quên số thế hệ để lần hỏi sau tải lại đúng bản trên kho.
                for path in written:
                    self.generations[path] = None
                raise

    def _download(self, path: Path) -> None:
        data, generation = self.files[path].download()
        write_bytes(data, path)
        self.generations[path] = generation


def watch(poll: Callable[[], None], every: float, stop: threading.Event) -> threading.Thread:
    """Luồng nền gọi ``poll`` mỗi ``every`` giây cho tới khi ``stop`` được bật."""

    def run() -> None:
        while not stop.wait(every):
            try:
                poll()
            except Exception:  # một lần hỏi hỏng không được làm dừng dịch vụ
                logger.warning("could not check the ontology in Cloud Storage", exc_info=True)

    thread = threading.Thread(target=run, name="ontology-watch", daemon=True)
    thread.start()
    return thread
