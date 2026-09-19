"""Nhật ký hội thoại: mỗi lượt hỏi đáp một bản ghi, để người quản trị xem lại và cải thiện ontology.

Các lượt của một cuộc trò chuyện chung một phiên (mã phiên do máy chủ cấp, trang gửi kèm mỗi câu),
nên người xem đọc được cả cuộc trò chuyện. Một bản ghi giữ câu hỏi, câu trả lời, kết cục,
và từng lần tra cứu: từ khoá, công cụ trả ``found`` hay ``not_found``, những mục nào được trả về.
Nhờ đó người xem phân biệt được "ontology thiếu dữ liệu" với "tra sai từ khoá".

Dấu hiệu cần xem xét (``flags``) tính từ chính bản ghi, không đoán:
- ``not_found``: có lần tra cứu không trả về mục nào;
- ``says_missing``: mô hình đánh dấu thiếu dữ liệu (``agent.MARKS``; bản ghi cũ: khớp ``MISSING_PHRASES``);
- ``out_of_scope``: mô hình đánh dấu câu hỏi ngoài phạm vi (có thể là chủ đề nên bổ sung);
- ``no_lookup``: trả lời mà không tra cứu lần nào;
- ``failed``: lượt không xong (quá hạn, lỗi, hàng đầy, người dùng đóng trang).

Mỗi bản ghi là một tệp JSON riêng: ``<ngày bắt đầu phiên>/<mã phiên>/<mã lượt>.json``. Nhiều bản dịch vụ ghi cùng lúc
không đè nhau, và đánh dấu hay xoá một bản ghi chỉ đụng tới đúng tệp đó. Trên Cloud Run tệp nằm
trong Cloud Storage (container không giữ tệp); chạy ở máy thì nằm trong một thư mục.
Việc ghi chạy ở một luồng nền, không làm chậm câu trả lời.
"""

from __future__ import annotations

import json
import logging
import os
import re
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
#: Thời điểm tạo tới phần triệu giây (để các lượt của một phiên sắp đúng thứ tự theo tên tệp) cộng sáu ký tự
#: ngẫu nhiên. Mã tạo trước 19/09/2026 chỉ có tới giây, vẫn hợp lệ.
_ID = re.compile(r"\d{8}T\d{6}(?:\d{6})?-[0-9a-f]{6}")


def new_id(now: datetime) -> str:
    return f"{now:%Y%m%dT%H%M%S%f}-{secrets.token_hex(3)}"


def valid_id(value: object) -> bool:
    """Mã lượt và mã phiên có cùng dạng (``_ID``)."""

    return isinstance(value, str) and _ID.fullmatch(value) is not None


def _day(record_id: str) -> str:
    return f"{record_id[:4]}-{record_id[4:6]}-{record_id[6:8]}"


def flags(record: dict) -> list[str]:
    found = []
    if any(lookup.get("status") == "not_found" for lookup in record.get("lookups", [])):
        found.append("not_found")
    if "marks" in record:  # mô hình tự đánh dấu (từ 19/09/2026)
        missing = "missing" in record["marks"]
        outside = "out_of_scope" in record["marks"]
    else:  # bản ghi cũ: đoán qua câu chữ
        answer = (record.get("answer") or "").casefold()
        missing = any(phrase in answer for phrase in MISSING_PHRASES)
        outside = any(phrase in answer for phrase in OUT_OF_SCOPE_PHRASES)
    if missing:
        found.append("says_missing")
    if outside:
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
    """Lịch sử chat theo phiên. Mỗi lượt vẫn là một tệp riêng (Cloud Storage không ghi nối được, và
    hai bản dịch vụ ghi cùng lúc không đè nhau), nằm trong thư mục của phiên:
    ``<ngày bắt đầu phiên>/<mã phiên>/<mã lượt>.json``. Danh sách gom các lượt thành phiên."""

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

    def list(self, *, days: int = 7, view: str = "all", query: str = "", limit: int = 300) -> list[dict]:
        """Các phiên bắt đầu trong ``days`` ngày có ít nhất một lượt khớp bộ lọc, mới nhất trước."""

        sessions: dict[str, list[dict]] = {}
        for turn in self._turns(days):
            sessions.setdefault(turn["session"], []).append(turn)
        found = []
        for session_id in sorted(sessions, reverse=True):
            turns = sorted(sessions[session_id], key=lambda turn: turn["id"])
            if any(_matches(turn, view, query) for turn in turns):
                found.append(_session_summary(session_id, turns))
                if len(found) >= limit:
                    break
        return found

    @abstractmethod
    def write(self, record: dict) -> None: ...

    @abstractmethod
    def _turns(self, days: int) -> list[dict]:
        """Tóm tắt mọi lượt của các phiên bắt đầu trong ``days`` ngày (có ``session``)."""

    @abstractmethod
    def session(self, session_id: str) -> dict:
        """``{"session": mã, "turns": [bản ghi đầy đủ theo thứ tự]}``."""

    @abstractmethod
    def review(self, session_id: str, turn_id: str, state: str, note: str) -> dict: ...

    @abstractmethod
    def delete(self, session_id: str, turn_id: str | None = None) -> None:
        """Xoá một lượt, hoặc cả phiên khi không nêu lượt."""

    @staticmethod
    def _check_id(value: str) -> None:
        if not valid_id(value):
            raise KeyError(value)

    @staticmethod
    def _summary(record: dict) -> dict:
        return {key: record.get(key) for key in
                ("id", "session", "time", "question", "answer", "outcome", "flags", "review", "admin")}


def _session_summary(session_id: str, turns: list[dict]) -> dict:
    seen: list[str] = []
    for turn in turns:
        seen += [flag for flag in turn["flags"] if flag not in seen]
    return {
        "session": session_id, "time": turns[0]["time"], "last": turns[-1]["time"], "turns": len(turns),
        "question": turns[0]["question"], "flags": seen, "admin": any(turn.get("admin") for turn in turns),
        # Số lượt đã đánh dấu cần bổ sung, và số lượt có dấu hiệu mà chưa ai xem.
        "todo": sum(turn["review"]["state"] == "can-bo-sung" for turn in turns),
        "open": sum(bool(turn["flags"]) and not turn["review"]["state"] for turn in turns),
    }


class LocalChatLog(ChatLog):
    """Bản ghi là tệp trong một thư mục, dùng khi chạy ở máy."""

    def __init__(self, root: Path | str) -> None:
        super().__init__()
        self.root = Path(root)

    def _folder(self, session_id: str) -> Path:
        self._check_id(session_id)
        return self.root / _day(session_id) / session_id

    def _path(self, session_id: str, turn_id: str) -> Path:
        self._check_id(turn_id)
        return self._folder(session_id) / f"{turn_id}.json"

    def write(self, record: dict) -> None:
        path = self._path(record["session"], record["id"])
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(temporary, path)

    def _turns(self, days: int) -> list[dict]:
        since = (datetime.now() - timedelta(days=days - 1)).strftime("%Y-%m-%d")
        if not self.root.exists():
            return []
        return [self._summary(json.loads(path.read_text(encoding="utf-8")))
                for day in self.root.glob("????-??-??") if day.name >= since
                for path in day.glob("*/*.json")]

    def session(self, session_id: str) -> dict:
        folder = self._folder(session_id)
        paths = sorted(folder.glob("*.json")) if folder.exists() else []
        if not paths:
            raise KeyError(session_id)
        return {"session": session_id, "turns": [json.loads(path.read_text(encoding="utf-8")) for path in paths]}

    def review(self, session_id: str, turn_id: str, state: str, note: str) -> dict:
        path = self._path(session_id, turn_id)
        if not path.exists():
            raise KeyError(turn_id)
        record = json.loads(path.read_text(encoding="utf-8"))
        record["review"] = {"state": state, "note": note, "time": datetime.now().astimezone().isoformat(timespec="seconds")}
        self.write(record)
        return record

    def delete(self, session_id: str, turn_id: str | None = None) -> None:
        paths = [self._path(session_id, turn_id)] if turn_id else list(self._folder(session_id).glob("*.json"))
        if not paths or not all(path.exists() for path in paths):
            raise KeyError(turn_id or session_id)
        for path in paths:
            path.unlink()
        folder = self._folder(session_id)
        if folder.exists() and not any(folder.iterdir()):
            folder.rmdir()


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

    def _folder(self, session_id: str) -> str:
        self._check_id(session_id)
        return f"{self.prefix}{_day(session_id)}/{session_id}/"

    def _name(self, session_id: str, turn_id: str) -> str:
        self._check_id(turn_id)
        return f"{self._folder(session_id)}{turn_id}.json"

    def _object_url(self, name: str) -> str:
        return f"{self._api}/storage/v1/b/{quote(self.bucket, safe='')}/o/{quote(name, safe='')}"

    @staticmethod
    def _metadata(record: dict) -> dict[str, str]:
        review = record["review"]
        return {"question": record["question"][:300], "time": record["time"], "outcome": record["outcome"],
                "flags": ",".join(record["flags"]), "review": review["state"], "note": review["note"][:1000],
                "reviewed": review["time"] or "", "admin": "1" if record.get("admin") else ""}

    @staticmethod
    def _check(response, action: str) -> None:
        if response.status_code == 404:
            raise KeyError(action)
        if response.status_code >= 300:
            raise RuntimeError(f"Cloud Storage từ chối {action}: HTTP {response.status_code} {response.text[:300]}")

    def write(self, record: dict) -> None:
        boundary = secrets.token_hex(16)
        head = json.dumps({"name": self._name(record["session"], record["id"]), "contentType": "application/json",
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

    def _objects(self, **params: str) -> list[dict]:
        items, token = [], None
        while True:
            page_params = {"fields": "items(name,metadata),nextPageToken", "maxResults": "1000", **params}
            if token:
                page_params["pageToken"] = token
            response = self.http.get(f"{self._api}/storage/v1/b/{quote(self.bucket, safe='')}/o",
                                     params=page_params, headers=self._headers())
            self._check(response, "liệt kê bản ghi hội thoại")
            page = response.json()
            items += page.get("items", [])
            token = page.get("nextPageToken")
            if not token:
                return items

    def _turns(self, days: int) -> list[dict]:
        since = (datetime.now() - timedelta(days=days - 1)).strftime("%Y-%m-%d")
        turns = []
        for item in self._objects(prefix=self.prefix, startOffset=f"{self.prefix}{since}"):
            parts = item["name"][len(self.prefix):].split("/")
            if len(parts) != 3:  # bản ghi từ trước khi có phiên
                continue
            meta = item.get("metadata", {})
            turns.append({
                "id": parts[2].removesuffix(".json"), "session": parts[1],
                "time": meta.get("time"), "question": meta.get("question", ""), "outcome": meta.get("outcome"),
                "admin": meta.get("admin") == "1",
                "flags": [flag for flag in meta.get("flags", "").split(",") if flag],
                "review": {"state": meta.get("review", ""), "note": meta.get("note", ""),
                           "time": meta.get("reviewed") or None},
            })
        return turns

    def _get(self, name: str) -> dict:
        response = self.http.get(self._object_url(name), params={"alt": "media"}, headers=self._headers())
        self._check(response, "đọc bản ghi hội thoại")
        record = response.json()
        meta = self.http.get(self._object_url(name), params={"fields": "metadata"}, headers=self._headers())
        self._check(meta, "đọc bản ghi hội thoại")
        stored = meta.json().get("metadata", {})
        record["review"] = {"state": stored.get("review", ""), "note": stored.get("note", ""),
                            "time": stored.get("reviewed") or None}
        return record

    def session(self, session_id: str) -> dict:
        names = sorted(item["name"] for item in self._objects(prefix=self._folder(session_id)))
        if not names:
            raise KeyError(session_id)
        return {"session": session_id, "turns": [self._get(name) for name in names]}

    def review(self, session_id: str, turn_id: str, state: str, note: str) -> dict:
        name = self._name(session_id, turn_id)
        reviewed = datetime.now().astimezone().isoformat(timespec="seconds")
        response = self.http.patch(self._object_url(name), headers=self._headers(),
                                   json={"metadata": {"review": state, "note": note[:1000], "reviewed": reviewed}})
        self._check(response, "đánh dấu bản ghi hội thoại")
        return self._get(name)

    def delete(self, session_id: str, turn_id: str | None = None) -> None:
        names = ([self._name(session_id, turn_id)] if turn_id
                 else [item["name"] for item in self._objects(prefix=self._folder(session_id))])
        if not names:
            raise KeyError(session_id)
        for name in names:
            self._check(self.http.delete(self._object_url(name), headers=self._headers()), "xoá bản ghi hội thoại")
