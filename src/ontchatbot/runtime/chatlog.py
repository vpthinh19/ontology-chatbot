"""Nhật ký hội thoại: mỗi lượt hỏi đáp một bản ghi, để người quản trị xem lại và cải thiện ontology.

Một bản ghi giữ câu hỏi, vài tin nhắn trước đó (để hiểu câu hỏi nối tiếp), câu trả lời, kết cục,
và từng lần tra cứu: từ khoá, công cụ trả ``found`` hay ``not_found``, những mục nào được trả về.
Nhờ đó người xem phân biệt được "ontology thiếu dữ liệu" với "tra sai từ khoá".

Dấu hiệu cần xem xét (``flags``) tính từ chính bản ghi, không đoán:
- ``not_found``: có lần tra cứu không trả về mục nào;
- ``says_missing``: câu trả lời nói dữ liệu không có (khớp một trong các cụm ``MISSING_PHRASES``);
- ``out_of_scope``: câu trả lời nói câu hỏi nằm ngoài phạm vi (có thể là chủ đề nên bổ sung);
- ``no_lookup``: trả lời mà không tra cứu lần nào;
- ``failed``: lượt không xong (quá hạn, lỗi, hàng đầy, người dùng đóng trang).

Mỗi bản ghi là một tệp JSON riêng: ``<ngày>/<định danh>.json``. Nhiều bản dịch vụ ghi cùng lúc
không đè nhau, và đánh dấu hay xoá một bản ghi chỉ đụng tới đúng tệp đó. Trên Cloud Run tệp nằm
trong Cloud Storage (container không giữ tệp); chạy ở máy thì nằm trong một thư mục.
Việc ghi chạy ở một luồng nền, không làm chậm câu trả lời.
"""

from __future__ import annotations

import json
import logging
import os
import secrets
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote

logger = logging.getLogger(__name__)

#: Cách mô hình nói "dữ liệu không có". Đo trên 210 câu trả lời đã chấm của bộ 70 câu: bắt 106/111
#: câu từ chối đúng, 21/21 câu từ chối nhầm, 9/14 câu đúng một phần; chỉ gắn nhầm 4/64 câu đúng hẳn
#: (các câu này cũng nói rõ một vế không có dữ liệu).
MISSING_PHRASES = (
    "không tìm thấy", "không thấy thông tin", "không có thông tin", "chưa có thông tin", "không chứa",
    "chưa có dữ liệu", "không có dữ liệu", "không có trong dữ liệu", "chưa có trong dữ liệu",
    "không cung cấp", "chưa cung cấp", "không đề cập", "chưa đề cập", "không được đề cập", "chưa được đề cập",
    "không nêu", "chưa nêu", "không được nêu", "chưa được nêu", "không ghi", "chưa ghi", "không được ghi",
    "chưa được ghi", "không có quy định", "chưa có quy định", "không được quy định", "không có nội dung",
    "không bao gồm thông tin",
)
OUT_OF_SCOPE_PHRASES = ("ngoài phạm vi",)
#: Trạng thái xem xét: chưa xem · cần bổ sung dữ liệu hay sửa hệ thống · đã xử lý · không cần xử lý.
REVIEW_STATES = ("", "can-bo-sung", "da-xu-ly", "bo-qua")
_ID_LENGTH = len("20260918T171939-abcdef")


def new_id(now: datetime) -> str:
    return f"{now:%Y%m%dT%H%M%S}-{secrets.token_hex(3)}"


def _day(record_id: str) -> str:
    return f"{record_id[:4]}-{record_id[4:6]}-{record_id[6:8]}"


def flags(record: dict) -> list[str]:
    found = []
    if any(lookup.get("status") == "not_found" for lookup in record.get("lookups", [])):
        found.append("not_found")
    answer = (record.get("answer") or "").casefold()
    if any(phrase in answer for phrase in MISSING_PHRASES):
        found.append("says_missing")
    if any(phrase in answer for phrase in OUT_OF_SCOPE_PHRASES):
        found.append("out_of_scope")
    if record.get("outcome") == "ok" and not record.get("lookups"):
        found.append("no_lookup")
    if record.get("outcome") != "ok":
        found.append("failed")
    return found


def summarize_lookup(keywords, result: str) -> dict:
    """Phần đáng giữ của một lần tra cứu: từ khoá, kết cục, tên các mục được trả về."""

    summary = {"keywords": list(keywords), "status": None, "results": [], "unmatched": []}
    try:
        payload = json.loads(result) if result else {}
    except json.JSONDecodeError:
        return summary
    summary["status"] = payload.get("status")
    summary["results"] = [item.get("label") for item in payload.get("results", []) if isinstance(item, dict)]
    summary["unmatched"] = list(payload.get("unmatched") or [])
    return summary


def _matches(record: dict, view: str, query: str) -> bool:
    if view == "review" and not (record["flags"] and not record["review"]["state"]):
        return False
    if view == "flagged" and not record["flags"]:
        return False
    if view == "todo" and record["review"]["state"] != "can-bo-sung":
        return False
    if view == "failed" and "failed" not in record["flags"]:
        return False
    return not query or query.casefold() in f"{record['question']} {record.get('answer', '')}".casefold()


class ChatLog(ABC):
    def __init__(self) -> None:
        self._writer = ThreadPoolExecutor(max_workers=1, thread_name_prefix="chatlog")

    def submit(self, record: dict) -> None:
        """Ghi ở luồng nền; lỗi chỉ ghi vào nhật ký dịch vụ, không làm hỏng lượt hỏi."""

        record = {**record, "flags": flags(record), "review": {"state": "", "note": "", "time": None}}

        def write() -> None:
            try:
                self.write(record)
            except Exception:  # noqa: BLE001 - mất một bản ghi còn hơn làm hỏng câu trả lời
                logger.warning("could not record chat turn id=%s", record.get("id"), exc_info=True)

        self._writer.submit(write)

    def flush(self) -> None:
        """Chờ các bản ghi đang xếp hàng ghi xong (dùng khi tắt dịch vụ và trong kiểm thử)."""

        self._writer.submit(lambda: None).result()

    @abstractmethod
    def write(self, record: dict) -> None: ...

    @abstractmethod
    def list(self, *, days: int = 7, view: str = "all", query: str = "", limit: int = 300) -> list[dict]: ...

    @abstractmethod
    def get(self, record_id: str) -> dict: ...

    @abstractmethod
    def review(self, record_id: str, state: str, note: str) -> dict: ...

    @abstractmethod
    def delete(self, record_id: str) -> None: ...

    @staticmethod
    def _check_id(record_id: str) -> None:
        if len(record_id) != _ID_LENGTH or not record_id[:8].isdigit() or "/" in record_id or ".." in record_id:
            raise KeyError(record_id)

    @staticmethod
    def _summary(record: dict) -> dict:
        return {key: record.get(key) for key in ("id", "time", "question", "outcome", "flags", "review")}


class LocalChatLog(ChatLog):
    """Bản ghi là tệp trong một thư mục, dùng khi chạy ở máy."""

    def __init__(self, root: Path | str) -> None:
        super().__init__()
        self.root = Path(root)

    def _path(self, record_id: str) -> Path:
        self._check_id(record_id)
        return self.root / _day(record_id) / f"{record_id}.json"

    def write(self, record: dict) -> None:
        path = self._path(record["id"])
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(temporary, path)

    def list(self, *, days: int = 7, view: str = "all", query: str = "", limit: int = 300) -> list[dict]:
        since = (datetime.now() - timedelta(days=days - 1)).strftime("%Y-%m-%d")
        found = []
        folders = sorted((p for p in self.root.glob("????-??-??") if p.name >= since), reverse=True) \
            if self.root.exists() else []
        for folder in folders:
            for path in sorted(folder.glob("*.json"), reverse=True):
                record = json.loads(path.read_text(encoding="utf-8"))
                if _matches(record, view, query):
                    found.append(self._summary(record))
                    if len(found) >= limit:
                        return found
        return found

    def get(self, record_id: str) -> dict:
        path = self._path(record_id)
        if not path.exists():
            raise KeyError(record_id)
        return json.loads(path.read_text(encoding="utf-8"))

    def review(self, record_id: str, state: str, note: str) -> dict:
        record = self.get(record_id)
        record["review"] = {"state": state, "note": note, "time": datetime.now().astimezone().isoformat(timespec="seconds")}
        self.write(record)
        return record

    def delete(self, record_id: str) -> None:
        path = self._path(record_id)
        if not path.exists():
            raise KeyError(record_id)
        path.unlink()


class GcsChatLog(ChatLog):
    """Bản ghi là đối tượng Cloud Storage. Tóm tắt (câu hỏi, dấu hiệu, trạng thái xem xét) nằm trong
    metadata của đối tượng, nên danh sách chỉ cần một lần liệt kê chứ không tải từng tệp."""

    def __init__(self, bucket: str, prefix: str, *, http=None, token=None) -> None:
        super().__init__()
        from ..admin.remote import API, default_token

        if http is None:
            import httpx

            http = httpx.Client(timeout=30.0)
        self.bucket, self.prefix, self.http = bucket, prefix, http
        self.token = token or default_token(http)
        self._api = API

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token()}"}

    def _name(self, record_id: str) -> str:
        self._check_id(record_id)
        return f"{self.prefix}{_day(record_id)}/{record_id}.json"

    def _object_url(self, record_id: str) -> str:
        return f"{self._api}/storage/v1/b/{quote(self.bucket, safe='')}/o/{quote(self._name(record_id), safe='')}"

    @staticmethod
    def _metadata(record: dict) -> dict[str, str]:
        review = record["review"]
        return {"question": record["question"][:300], "time": record["time"], "outcome": record["outcome"],
                "flags": ",".join(record["flags"]), "review": review["state"], "note": review["note"][:1000],
                "reviewed": review["time"] or ""}

    @staticmethod
    def _check(response, action: str) -> None:
        if response.status_code == 404:
            raise KeyError(action)
        if response.status_code >= 300:
            raise RuntimeError(f"Cloud Storage từ chối {action}: HTTP {response.status_code} {response.text[:300]}")

    def write(self, record: dict) -> None:
        boundary = secrets.token_hex(16)
        head = json.dumps({"name": self._name(record["id"]), "contentType": "application/json",
                           "metadata": self._metadata(record)}, ensure_ascii=False)
        body = json.dumps(record, ensure_ascii=False)
        content = (f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n{head}\r\n"
                   f"--{boundary}\r\nContent-Type: application/json\r\n\r\n{body}\r\n--{boundary}--\r\n").encode("utf-8")
        response = self.http.post(
            f"{self._api}/upload/storage/v1/b/{quote(self.bucket, safe='')}/o",
            params={"uploadType": "multipart"},
            headers={**self._headers(), "Content-Type": f"multipart/related; boundary={boundary}"},
            content=content,
        )
        self._check(response, "ghi bản ghi hội thoại")

    def list(self, *, days: int = 7, view: str = "all", query: str = "", limit: int = 300) -> list[dict]:
        since = (datetime.now() - timedelta(days=days - 1)).strftime("%Y-%m-%d")
        records, token = [], None
        while True:
            params = {"prefix": self.prefix, "startOffset": f"{self.prefix}{since}",
                      "fields": "items(name,metadata),nextPageToken", "maxResults": "1000"}
            if token:
                params["pageToken"] = token
            response = self.http.get(f"{self._api}/storage/v1/b/{quote(self.bucket, safe='')}/o",
                                     params=params, headers=self._headers())
            self._check(response, "liệt kê bản ghi hội thoại")
            page = response.json()
            for item in page.get("items", []):
                meta = item.get("metadata", {})
                records.append({
                    "id": item["name"].rsplit("/", 1)[-1].removesuffix(".json"),
                    "time": meta.get("time"), "question": meta.get("question", ""), "outcome": meta.get("outcome"),
                    "flags": [flag for flag in meta.get("flags", "").split(",") if flag],
                    "review": {"state": meta.get("review", ""), "note": meta.get("note", ""),
                               "time": meta.get("reviewed") or None},
                })
            token = page.get("nextPageToken")
            if not token:
                break
        records.sort(key=lambda record: record["id"], reverse=True)
        return [record for record in records if _matches(record, view, query)][:limit]

    def get(self, record_id: str) -> dict:
        response = self.http.get(self._object_url(record_id), params={"alt": "media"}, headers=self._headers())
        self._check(response, "đọc bản ghi hội thoại")
        record = response.json()
        meta = self.http.get(self._object_url(record_id), params={"fields": "metadata"}, headers=self._headers())
        self._check(meta, "đọc bản ghi hội thoại")
        stored = meta.json().get("metadata", {})
        record["review"] = {"state": stored.get("review", ""), "note": stored.get("note", ""),
                            "time": stored.get("reviewed") or None}
        return record

    def review(self, record_id: str, state: str, note: str) -> dict:
        reviewed = datetime.now().astimezone().isoformat(timespec="seconds")
        response = self.http.patch(self._object_url(record_id), headers=self._headers(),
                                   json={"metadata": {"review": state, "note": note[:1000], "reviewed": reviewed}})
        self._check(response, "đánh dấu bản ghi hội thoại")
        return self.get(record_id)

    def delete(self, record_id: str) -> None:
        self._check(self.http.delete(self._object_url(record_id), headers=self._headers()), "xoá bản ghi hội thoại")
