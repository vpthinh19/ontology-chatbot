"""Đường HTTP của trang quản trị: khoá, lược đồ cho form, và lý do khi từ chối."""

from __future__ import annotations

import asyncio
import shutil

import pytest

pytest.importorskip("starlette")
httpx = pytest.importorskip("httpx")

from ontchatbot.admin import AdminStore, Schema
from ontchatbot.runtime.api import create_app
from ontchatbot.settings import ONTOLOGY_PATH

KEY = {"X-Admin-Token": "khoa-quan-tri"}


def _call(app, method: str, path: str, **kwargs):
    async def run():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.request(method, path, **kwargs)

    return asyncio.run(run())


@pytest.fixture
def app(tmp_path):
    path, shapes = tmp_path / "ontology.trig", tmp_path / "shapes.ttl"
    shutil.copy(ONTOLOGY_PATH, path)
    shutil.copy(ONTOLOGY_PATH.with_name("shapes.ttl"), shapes)  # sửa loại ghi cả shapes.ttl: không đụng bản thật
    store = AdminStore(path, Schema.from_file(shapes), shapes_path=shapes)
    return create_app(object(), admin=store, admin_token="khoa-quan-tri")


def test_admin_routes_do_not_exist_when_no_admin_key_is_configured() -> None:
    assert _call(create_app(object()), "GET", "/admin/schema").status_code == 404


def test_admin_routes_refuse_a_request_without_the_admin_key(app) -> None:
    assert _call(app, "GET", "/admin/schema").status_code == 401


def test_the_schema_route_describes_the_form_of_each_class(app) -> None:
    classes = {item["name"]: item for item in _call(app, "GET", "/admin/schema", headers=KEY).json()["classes"]}

    fields = {field["property"]: field for field in classes["ThuTucHocVu"]["fields"]}
    assert fields["noiDung"]["sourced"] is True
    assert {"id": "QuyChe", "label": "Quy chế"} in {
        f["property"]: f for f in classes["Nguon"]["fields"]}["loaiNguon"]["choices"]


def test_an_invalid_save_answers_with_the_reasons(app) -> None:
    response = _call(app, "POST", "/admin/entities", headers=KEY, json={
        "class": "KhaiNiem", "label": "Mục thiếu nội dung",
        "statements": [{"property": "loaiKhaiNiem", "value": "KhaiNiemHocVu"}],
    })

    assert response.status_code == 400
    assert response.json()["errors"] == ["Mục thiếu nội dung · nội dung: thiếu giá trị bắt buộc"]


def test_a_class_can_be_created_and_deleted_over_http(app) -> None:
    created = _call(app, "POST", "/admin/classes", headers=KEY, json={
        "name": "LoaiThu", "label": "Loại thử", "altLabels": False,
        "fields": [{"property": "noiDung", "name": "nội dung", "kind": "text", "required": True, "single": False,
                    "sourced": True}],
    })
    assert created.status_code == 201
    classes = {c["name"]: c for c in _call(app, "GET", "/admin/schema", headers=KEY).json()["classes"]}
    assert classes["LoaiThu"]["count"] == 0

    deleted = _call(app, "DELETE", f"/admin/classes/LoaiThu?version={classes['LoaiThu']['version']}", headers=KEY)

    assert deleted.status_code == 200


def test_an_invalid_class_answers_with_where_each_problem_is(app) -> None:
    response = _call(app, "POST", "/admin/classes", headers=KEY, json={"name": "x", "label": "", "fields": []})

    assert response.status_code == 400
    assert {d.get("where") for d in response.json()["details"]} == {"label", "name"}


def test_deleting_with_an_outdated_version_is_refused(app) -> None:
    response = _call(app, "DELETE", "/admin/entities/HocKyHe?version=cu", headers=KEY)

    assert response.status_code == 409
