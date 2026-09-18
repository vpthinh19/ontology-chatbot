"""Bản gốc của ontology trên Google Cloud Storage, cho dịch vụ chạy trên Cloud Run.

Container của Cloud Run không giữ tệp qua các lần khởi động lại và có thể chạy nhiều bản cùng lúc,
nên sửa ở trang quản trị mà chỉ ghi tệp trong container thì mất. Bản gốc vì thế là một đối tượng
Cloud Storage; mỗi bản dịch vụ giữ một bản sao trên đĩa để engine và trang quản trị đọc.

- Khởi động: tải đối tượng về đè lên bản sao. Chưa có đối tượng thì đưa tệp trong ảnh lên làm bản đầu.
- Lưu ở trang quản trị: ghi lên kèm điều kiện số thế hệ (generation) chưa đổi. Có người vừa lưu trước
  thì Cloud Storage từ chối (412) thay vì để hai lần sửa đè nhau.
- Các bản dịch vụ khác định kỳ hỏi số thế hệ và tải lại khi nó đổi.

Gọi thẳng JSON API bằng httpx, thư viện dịch vụ đã có, thay vì thêm google-cloud-storage vào ảnh.
Khoá truy cập lấy từ máy chủ metadata của Cloud Run, hoặc từ ONTCHATBOT_GCS_ACCESS_TOKEN khi chạy ngoài
Google Cloud (ví dụ khoá của ``gcloud auth print-access-token``).
"""

from __future__ import annotations

import logging
import os
import threading
import time
from collections.abc import Callable
from pathlib import Path
from urllib.parse import quote

from .trig import write_bytes

logger = logging.getLogger(__name__)

API = "https://storage.googleapis.com"
METADATA_TOKEN_URL = "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token"
CONTENT_TYPE = "application/trig"


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


class GcsObject:
    """Một đối tượng Cloud Storage, đọc và ghi qua JSON API."""

    def __init__(self, bucket: str, name: str, *, http=None, token: Callable[[], str] | None = None) -> None:
        if http is None:
            import httpx

            http = httpx.Client(timeout=30.0)
        self.bucket = bucket
        self.name = name
        self.http = http
        fixed = os.environ.get("ONTCHATBOT_GCS_ACCESS_TOKEN", "").strip()
        self.token = token or ((lambda: fixed) if fixed else MetadataToken(http))

    @classmethod
    def from_uri(cls, uri: str, **options) -> GcsObject:
        """``gs://bucket/đường/dẫn/ontology.trig``."""

        if not uri.startswith("gs://") or "/" not in uri[5:]:
            raise ValueError(f"địa chỉ Cloud Storage phải có dạng gs://bucket/đối-tượng: {uri!r}")
        bucket, name = uri[5:].split("/", 1)
        if not bucket or not name:
            raise ValueError(f"địa chỉ Cloud Storage phải có dạng gs://bucket/đối-tượng: {uri!r}")
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
            headers={**self._headers(), "Content-Type": CONTENT_TYPE},
            content=data,
        )
        if response.status_code == 412:
            raise StaleCopy(self.name)
        if response.status_code != 200:
            self._fail(response, "ghi đối tượng")
        return str(response.json()["generation"])


class RemoteOntology:
    """Giữ bản sao trên đĩa khớp với đối tượng trên Cloud Storage."""

    def __init__(self, remote: GcsObject, path: Path | str) -> None:
        self.remote = remote
        self.path = Path(path)
        self.generation: str | None = None
        self._lock = threading.Lock()

    def start(self) -> None:
        """Gọi một lần trước khi nạp engine."""

        with self._lock:
            if self.remote.generation() is None:
                try:
                    self.generation = self.remote.upload(self.path.read_bytes(), "0")
                    logger.info("ontology seeded to Cloud Storage object=%s generation=%s",
                                self.remote.name, self.generation)
                    return
                except StaleCopy:  # một bản dịch vụ khởi động cùng lúc vừa đưa lên trước
                    pass
            self._download()
            logger.info("ontology loaded from Cloud Storage object=%s generation=%s",
                        self.remote.name, self.generation)

    def refresh(self) -> bool:
        """Tải bản mới nếu số thế hệ đã đổi; trả ``True`` khi bản sao trên đĩa vừa được thay."""

        with self._lock:
            current = self.remote.generation()
            if current is None or current == self.generation:
                return False
            self._download()
            logger.info("ontology refreshed from Cloud Storage generation=%s", self.generation)
            return True

    def push(self, data: bytes) -> None:
        """Ghi một lần sửa; ``StaleCopy`` khi bản đang giữ đã cũ."""

        with self._lock:
            self.generation = self.remote.upload(data, self.generation or "0")

    def _download(self) -> None:
        data, generation = self.remote.download()
        write_bytes(data, self.path)
        self.generation = generation


def watch(poll: Callable[[], None], every: float, stop: threading.Event) -> threading.Thread:
    """Luồng nền gọi ``poll`` mỗi ``every`` giây cho tới khi ``stop`` được bật."""

    def run() -> None:
        while not stop.wait(every):
            try:
                poll()
            except Exception:  # noqa: BLE001 - một lần hỏi hỏng không được làm dừng dịch vụ
                logger.warning("could not check the ontology in Cloud Storage", exc_info=True)

    thread = threading.Thread(target=run, name="ontology-watch", daemon=True)
    thread.start()
    return thread
