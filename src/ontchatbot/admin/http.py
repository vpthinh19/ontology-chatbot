"""Đường HTTP của trang quản trị: thực thể (``/admin/entities``), lớp (``/admin/classes``) và lịch sử
chat (``/admin/chats``).

Mọi đường đòi hai lớp khoá: khoá dịch vụ như đường hỏi đáp, cộng quyền quản trị. Quyền quản trị là
khoá quản trị gửi trong header ``X-Admin-Token`` (cho script), hoặc phiên đăng nhập: gửi khoá một
lần tới ``/admin/login``, nhận lại cookie HttpOnly ký bằng chính khoá đó, sống 8 giờ. Trình duyệt
không phải giữ khoá, mã trong trang không đọc được cookie, và đổi khoá thì mọi phiên cũ mất hiệu lực.
Đăng nhập sai quá ``MAX_FAILED_LOGINS`` lần trong một phút thì bị chặn tới hết phút đó.
Không đặt khoá quản trị thì dịch vụ không mở các đường này. Việc ghi chạy ở luồng riêng vì bước
kiểm SHACL mất cỡ một hai giây.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import secrets
import time
from collections import deque

from .store import CODE_NAMES, AdminError, AdminStore

#: Đủ cho một thực thể có bảng nguyên văn dài, vẫn chặn được yêu cầu vô lý.
MAX_ADMIN_BODY_BYTES = 1024 * 1024
SESSION_COOKIE = "ontchatbot_admin"
SESSION_SECONDS = 8 * 3600
#: Cookie chỉ đi kèm các yêu cầu tới đường quản trị (trình duyệt gọi chúng qua /api/admin).
SESSION_PATH = "/api/admin"
MAX_FAILED_LOGINS = 10


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


def admin_routes(store: AdminStore, admin_token: str, authorize, chat_log=None) -> list:
    from starlette.responses import JSONResponse
    from starlette.routing import Route

    from ..runtime.chatlog import REVIEW_STATES

    failed_logins: deque[float] = deque()

    def is_admin(request) -> bool:
        candidate = request.headers.get("x-admin-token", "")
        if candidate and secrets.compare_digest(candidate.encode("utf-8"), admin_token.encode("utf-8")):
            return True
        return valid_session(admin_token, request.cookies.get(SESSION_COOKIE, ""))

    def refuse(request):
        denied = authorize(request)
        if denied is not None:
            return denied
        if is_admin(request):
            return None
        return JSONResponse({"detail": "Cần đăng nhập quản trị."}, status_code=401)

    def failure(exc: AdminError):
        return JSONResponse({"detail": str(exc), "errors": exc.errors, "details": exc.details,
                             "confirm": exc.confirm}, status_code=exc.status)

    async def read_body(request) -> dict:
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

    def describe() -> dict:
        counts = store.counts()
        classes = store.schema.classes
        properties: dict[str, dict] = {}
        for spec in classes.values():
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
                for spec in classes.values()
            ],
            "properties": sorted(properties.values(), key=lambda entry: entry["property"]),
        }

    async def schema(request):
        return refuse(request) or JSONResponse(describe())

    async def entities(request):
        denied = refuse(request)
        if denied is not None:
            return denied
        try:
            if request.method == "GET":
                return JSONResponse({"items": store.list(request.query_params.get("class", ""))})
            local = await asyncio.to_thread(store.create, await read_body(request))
            return JSONResponse({"id": local}, status_code=201)
        except AdminError as exc:
            return failure(exc)

    async def entity(request):
        denied = refuse(request)
        if denied is not None:
            return denied
        local = request.path_params["id"]
        try:
            if request.method == "GET":
                return JSONResponse(store.get(local))
            if request.method == "PUT":
                renamed = await asyncio.to_thread(store.update, local, await read_body(request))
                return JSONResponse({"id": renamed})
            await asyncio.to_thread(store.delete, local, request.query_params.get("version"))
            return JSONResponse({"deleted": local})
        except AdminError as exc:
            return failure(exc)

    async def classes(request):
        denied = refuse(request)
        if denied is not None:
            return denied
        try:
            name = await asyncio.to_thread(store.save_class, None, await read_body(request))
            return JSONResponse({"name": name}, status_code=201)
        except AdminError as exc:
            return failure(exc)

    async def one_class(request):
        denied = refuse(request)
        if denied is not None:
            return denied
        name = request.path_params["name"]
        try:
            if request.method == "PUT":
                renamed = await asyncio.to_thread(store.save_class, name, await read_body(request))
                return JSONResponse({"name": renamed})
            await asyncio.to_thread(store.delete_class, name, request.query_params.get("version"))
            return JSONResponse({"deleted": name})
        except AdminError as exc:
            return failure(exc)

    async def login(request):
        denied = authorize(request)
        if denied is not None:
            return denied
        now = time.monotonic()
        while failed_logins and now - failed_logins[0] > 60:
            failed_logins.popleft()
        if len(failed_logins) >= MAX_FAILED_LOGINS:
            return JSONResponse({"detail": "Đăng nhập sai quá nhiều lần; hãy đợi một phút."}, status_code=429)
        try:
            key = str((await read_body(request)).get("key") or "")
        except AdminError as exc:
            return failure(exc)
        if not secrets.compare_digest(key.encode("utf-8"), admin_token.encode("utf-8")):
            failed_logins.append(now)
            return JSONResponse({"detail": "Mật khẩu quản trị không đúng."}, status_code=401)
        response = JSONResponse({"ok": True})
        response.set_cookie(SESSION_COOKIE, session_value(admin_token), max_age=SESSION_SECONDS, path=SESSION_PATH,
                            httponly=True, secure=True, samesite="strict")
        return response

    async def logout(request):
        denied = authorize(request)
        if denied is not None:
            return denied
        response = JSONResponse({"ok": True})
        response.delete_cookie(SESSION_COOKIE, path=SESSION_PATH, httponly=True, secure=True, samesite="strict")
        return response

    async def session(request):
        return refuse(request) or JSONResponse({"ok": True, "chatLog": chat_log is not None})

    async def chats(request):
        denied = refuse(request)
        if denied is not None:
            return denied
        if chat_log is None:
            return JSONResponse({"detail": "Dịch vụ chưa bật lưu lịch sử chat."}, status_code=404)
        query = request.query_params
        try:
            days = min(max(int(query.get("days", "7")), 1), 366)
        except ValueError:
            days = 7
        items = await asyncio.to_thread(chat_log.list, days=days, view=query.get("view", "all"),
                                        query=query.get("q", "").strip(), limit=500)
        return JSONResponse({"items": items})

    async def chat_record(request):
        denied = refuse(request)
        if denied is not None:
            return denied
        if chat_log is None:
            return JSONResponse({"detail": "Dịch vụ chưa bật lưu lịch sử chat."}, status_code=404)
        record_id = request.path_params["id"]
        try:
            if request.method == "GET":
                return JSONResponse(await asyncio.to_thread(chat_log.get, record_id))
            if request.method == "DELETE":
                await asyncio.to_thread(chat_log.delete, record_id)
                return JSONResponse({"deleted": record_id})
            body = await read_body(request)
            state, note = body.get("state", ""), str(body.get("note") or "")[:1000]
            if state not in REVIEW_STATES:
                raise AdminError("Trạng thái xem xét không hợp lệ.")
            return JSONResponse(await asyncio.to_thread(chat_log.review, record_id, state, note))
        except KeyError:
            return JSONResponse({"detail": "Không có bản ghi này."}, status_code=404)
        except AdminError as exc:
            return failure(exc)

    return [
        Route("/admin/login", login, methods=["POST"]),
        Route("/admin/logout", logout, methods=["POST"]),
        Route("/admin/session", session, methods=["GET"]),
        Route("/admin/chats", chats, methods=["GET"]),
        Route("/admin/chats/{id}", chat_record, methods=["GET", "PUT", "DELETE"]),
        Route("/admin/schema", schema, methods=["GET"]),
        Route("/admin/entities", entities, methods=["GET", "POST"]),
        Route("/admin/entities/{id}", entity, methods=["GET", "PUT", "DELETE"]),
        Route("/admin/classes", classes, methods=["POST"]),
        Route("/admin/classes/{name}", one_class, methods=["PUT", "DELETE"]),
    ]
