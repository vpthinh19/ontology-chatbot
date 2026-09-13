"""Đường HTTP của trang quản trị ontology.

Mọi đường đòi hai lớp khoá: khoá dịch vụ như đường hỏi đáp, cộng khoá quản trị gửi trong
header ``X-Admin-Token``. Không đặt khoá quản trị thì dịch vụ không mở các đường này. Việc
ghi chạy ở luồng riêng vì bước kiểm SHACL mất cỡ một hai giây.
"""

from __future__ import annotations

import asyncio
import json
import secrets

from .store import AdminError, AdminStore

#: Đủ cho một mục có bảng nguyên văn dài, vẫn chặn được yêu cầu vô lý.
MAX_ADMIN_BODY_BYTES = 1024 * 1024


def admin_routes(store: AdminStore, admin_token: str, authorize) -> list:
    from starlette.responses import JSONResponse
    from starlette.routing import Route

    def refuse(request):
        denied = authorize(request)
        if denied is not None:
            return denied
        candidate = request.headers.get("x-admin-token", "")
        if secrets.compare_digest(candidate.encode("utf-8"), admin_token.encode("utf-8")):
            return None
        return JSONResponse({"detail": "Khoá quản trị không đúng."}, status_code=403)

    def failure(exc: AdminError):
        return JSONResponse({"detail": str(exc), "errors": exc.errors}, status_code=exc.status)

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
        return {"classes": [
            {
                "name": spec.name,
                "label": spec.label,
                "count": counts.get(spec.name, 0),
                "altLabels": spec.alt_labels,
                "fields": [
                    {
                        "property": field.property, "name": field.name, "kind": field.kind,
                        "required": field.required, "single": field.single, "target": field.target,
                        "sourced": field.sourced,
                        "choices": [{"id": choice, "label": store.label(choice)} for choice in field.choices],
                    }
                    for field in spec.fields
                ],
            }
            for spec in store.schema.classes.values()
        ]}

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
                await asyncio.to_thread(store.update, local, await read_body(request))
                return JSONResponse({"id": local})
            await asyncio.to_thread(store.delete, local)
            return JSONResponse({"deleted": local})
        except AdminError as exc:
            return failure(exc)

    return [
        Route("/admin/schema", schema, methods=["GET"]),
        Route("/admin/entities", entities, methods=["GET", "POST"]),
        Route("/admin/entities/{id}", entity, methods=["GET", "PUT", "DELETE"]),
    ]
