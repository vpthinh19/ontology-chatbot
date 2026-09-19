"""Đường HTTP của trang quản trị: thực thể, lớp và lịch sử chat.

Mọi đường cần khoá dịch vụ như đường hỏi đáp, cộng quyền quản trị: khoá quản trị trong header
``X-Admin-Token`` (cho script), hoặc cookie phiên. Cookie nhận được khi gửi đúng khoá tới
``/admin/login``: HttpOnly, ký bằng chính khoá đó, sống 8 giờ; đổi khoá thì mọi phiên cũ hết hiệu lực.
Việc ghi chạy ở luồng riêng vì bước kiểm SHACL mất một hai giây.
"""

from __future__ import annotations

import asyncio
import functools
import hashlib
import hmac
import json
import secrets
import time
from collections import deque

from starlette.responses import JSONResponse
from starlette.routing import Route

from ..runtime.chatlog import REVIEW_STATES
from .store import CODE_NAMES, AdminError, AdminStore

#: Đủ cho một thực thể có bảng dài, vẫn chặn được yêu cầu vô lý.
MAX_ADMIN_BODY_BYTES = 1024 * 1024
SESSION_COOKIE = "ontchatbot_admin"
SESSION_SECONDS = 8 * 3600
#: Cookie đi kèm mọi yêu cầu tới /api, kể cả đường hỏi đáp (để gắn nhãn câu quản trị).
SESSION_PATH = "/api"
#: Số lần đăng nhập sai trong một phút trước khi bị chặn tới hết phút đó.
MAX_FAILED_LOGINS = 10
_NO_CHAT_LOG = "Dịch vụ chưa bật lưu lịch sử chat."


def _signature(admin_token: str, expiry: int) -> str:
    return hmac.new(admin_token.encode("utf-8"), f"v1.{expiry}".encode(), hashlib.sha256).hexdigest()


def session_value(admin_token: str, now: float | None = None) -> str:
    expiry = int((now if now is not None else time.time()) + SESSION_SECONDS)
    return f"v1.{expiry}.{_signature(admin_token, expiry)}"


def valid_session(admin_token: str, value: str, now: float | None = None) -> bool:
    try:
        version, expiry, signature = value.split(".")
        expiry_time = int(expiry)
    except ValueError:
        return False
    return (version == "v1" and expiry_time > (now if now is not None else time.time())
            and hmac.compare_digest(signature, _signature(admin_token, expiry_time)))


def _json(payload, status: int = 200) -> JSONResponse:
    return JSONResponse(payload, status_code=status)


def _failure(exc: AdminError) -> JSONResponse:
    return _json({"detail": str(exc), "errors": exc.errors, "details": exc.details, "confirm": exc.confirm},
                 exc.status)


def _admin_only(handler):
    """Đường chỉ dành cho quản trị: kiểm quyền, và đổi ``AdminError`` thành phản hồi JSON."""

    @functools.wraps(handler)
    async def guarded(self: AdminApi, request):
        denied = self.authorize(request)
        if denied is not None:
            return denied
        if not self.is_admin(request):
            return _json({"detail": "Cần đăng nhập quản trị."}, 401)
        try:
            return await handler(self, request)
        except AdminError as exc:
            return _failure(exc)

    return guarded


def _needs_chat_log(handler):
    @functools.wraps(handler)
    async def checked(self: AdminApi, request):
        if self.chat_log is None:
            return _json({"detail": _NO_CHAT_LOG}, 404)
        return await handler(self, request)

    return checked


class AdminApi:
    def __init__(self, store: AdminStore, admin_token: str, authorize, chat_log=None) -> None:
        """``authorize(request)`` kiểm khoá dịch vụ: trả ``None`` khi được phép, không thì phản hồi lỗi."""

        self.store = store
        self.admin_token = admin_token
        self.authorize = authorize
        self.chat_log = chat_log
        self._failed_logins: deque[float] = deque()

    def routes(self) -> list[Route]:
        return [
            Route("/admin/login", self.login, methods=["POST"]),
            Route("/admin/logout", self.logout, methods=["POST"]),
            Route("/admin/session", self.session, methods=["GET"]),
            Route("/admin/chats", self.chats, methods=["GET"]),
            Route("/admin/chats/{session}", self.chat_session, methods=["GET", "DELETE"]),
            Route("/admin/chats/{session}/{id}", self.chat_turn, methods=["PUT", "DELETE"]),
            Route("/admin/schema", self.schema, methods=["GET"]),
            Route("/admin/entities", self.entities, methods=["GET", "POST"]),
            Route("/admin/entities/{id}", self.entity, methods=["GET", "PUT", "DELETE"]),
            Route("/admin/classes", self.classes, methods=["POST"]),
            Route("/admin/classes/{name}", self.one_class, methods=["PUT", "DELETE"]),
        ]

    # --- quyền ----------------------------------------------------------------

    def has_session(self, request) -> bool:
        """Trình duyệt đang có phiên quản trị."""

        return valid_session(self.admin_token, request.cookies.get(SESSION_COOKIE, ""))

    def is_admin(self, request) -> bool:
        candidate = request.headers.get("x-admin-token", "")
        if candidate and secrets.compare_digest(candidate.encode("utf-8"), self.admin_token.encode("utf-8")):
            return True
        return self.has_session(request)

    @staticmethod
    async def _body(request) -> dict:
        raw = await request.body()
        if len(raw) > MAX_ADMIN_BODY_BYTES:
            raise AdminError("Nội dung gửi lên quá lớn.")
        try:
            payload = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise AdminError("Nội dung gửi lên phải là JSON.") from None
        if not isinstance(payload, dict):
            raise AdminError("Nội dung gửi lên phải là một đối tượng JSON.")
        return payload

    async def login(self, request):
        denied = self.authorize(request)
        if denied is not None:
            return denied
        now = time.monotonic()
        while self._failed_logins and now - self._failed_logins[0] > 60:
            self._failed_logins.popleft()
        if len(self._failed_logins) >= MAX_FAILED_LOGINS:
            return _json({"detail": "Đăng nhập sai quá nhiều lần; hãy đợi một phút."}, 429)
        try:
            key = str((await self._body(request)).get("key") or "")
        except AdminError as exc:
            return _failure(exc)
        if not secrets.compare_digest(key.encode("utf-8"), self.admin_token.encode("utf-8")):
            self._failed_logins.append(now)
            return _json({"detail": "Mật khẩu quản trị không đúng."}, 401)
        response = _json({"ok": True})
        response.set_cookie(SESSION_COOKIE, session_value(self.admin_token), max_age=SESSION_SECONDS,
                            path=SESSION_PATH, httponly=True, secure=True, samesite="strict")
        return response

    async def logout(self, request):
        denied = self.authorize(request)
        if denied is not None:
            return denied
        response = _json({"ok": True})
        response.delete_cookie(SESSION_COOKIE, path=SESSION_PATH, httponly=True, secure=True, samesite="strict")
        return response

    @_admin_only
    async def session(self, request):
        return _json({"ok": True, "chatLog": self.chat_log is not None})

    # --- lược đồ, thực thể, lớp -------------------------------------------------

    @_admin_only
    async def schema(self, request):
        return _json(self._describe())

    def _describe(self) -> dict:
        store = self.store
        counts = store.counts()
        properties: dict[str, dict] = {}
        for spec in store.schema.classes.values():
            for field in spec.fields:
                entry = properties.setdefault(field.property, {"property": field.property, "name": field.name,
                                                               "kind": field.kind, "target": field.target,
                                                               "classes": []})
                entry["classes"].append(spec.name)
        return {
            "classes": [
                {
                    "name": spec.name,
                    "label": spec.label,
                    "count": counts.get(spec.name, 0),
                    "altLabels": spec.alt_labels,
                    "version": store.class_version(spec.name),
                    "locked": spec.name in CODE_NAMES,
                    "fields": [
                        {
                            "property": field.property, "name": field.name, "kind": field.kind,
                            "required": field.required, "single": field.single, "target": field.target,
                            "sourced": field.sourced, "locked": field.property in CODE_NAMES,
                            "choices": [{"id": choice, "label": store.label(choice)} for choice in field.choices],
                        }
                        for field in spec.fields
                    ],
                }
                for spec in store.schema.classes.values()
            ],
            "properties": sorted(properties.values(), key=lambda entry: entry["property"]),
        }

    @_admin_only
    async def entities(self, request):
        if request.method == "GET":
            return _json({"items": self.store.list(request.query_params.get("class", ""))})
        local = await asyncio.to_thread(self.store.create, await self._body(request))
        return _json({"id": local}, 201)

    @_admin_only
    async def entity(self, request):
        local = request.path_params["id"]
        if request.method == "GET":
            return _json(self.store.get(local))
        if request.method == "PUT":
            return _json({"id": await asyncio.to_thread(self.store.update, local, await self._body(request))})
        await asyncio.to_thread(self.store.delete, local, request.query_params.get("version"))
        return _json({"deleted": local})

    @_admin_only
    async def classes(self, request):
        name = await asyncio.to_thread(self.store.save_class, None, await self._body(request))
        return _json({"name": name}, 201)

    @_admin_only
    async def one_class(self, request):
        name = request.path_params["name"]
        if request.method == "PUT":
            return _json({"name": await asyncio.to_thread(self.store.save_class, name, await self._body(request))})
        await asyncio.to_thread(self.store.delete_class, name, request.query_params.get("version"))
        return _json({"deleted": name})

    # --- lịch sử chat -----------------------------------------------------------

    @_admin_only
    @_needs_chat_log
    async def chats(self, request):
        query = request.query_params
        try:
            days = min(max(int(query.get("days", "7")), 1), 366)
        except ValueError:
            days = 7
        items = await asyncio.to_thread(self.chat_log.list, days=days, view=query.get("view", "all"),
                                        query=query.get("q", "").strip(), limit=500)
        return _json({"items": items})

    @_admin_only
    @_needs_chat_log
    async def chat_session(self, request):
        session_id = request.path_params["session"]
        try:
            if request.method == "DELETE":
                await asyncio.to_thread(self.chat_log.delete, session_id)
                return _json({"deleted": session_id})
            return _json(await asyncio.to_thread(self.chat_log.session, session_id))
        except KeyError:
            return _json({"detail": "Không có phiên này."}, 404)

    @_admin_only
    @_needs_chat_log
    async def chat_turn(self, request):
        session_id, turn_id = request.path_params["session"], request.path_params["id"]
        try:
            if request.method == "DELETE":
                await asyncio.to_thread(self.chat_log.delete, session_id, turn_id)
                return _json({"deleted": turn_id})
            body = await self._body(request)
            state, note = body.get("state", ""), str(body.get("note") or "")[:1000]
            if state not in REVIEW_STATES:
                raise AdminError("Trạng thái xem xét không hợp lệ.")
            return _json(await asyncio.to_thread(self.chat_log.review, session_id, turn_id, state, note))
        except KeyError:
            return _json({"detail": "Không có lượt này."}, 404)
