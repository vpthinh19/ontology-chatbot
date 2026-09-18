"""Lịch sử chat: mỗi lượt một bản ghi, dấu hiệu cần xem xét, đọc và đánh dấu ở trang quản trị."""

from __future__ import annotations

import asyncio
import json
import shutil
from datetime import datetime

import httpx
import pytest

from ontchatbot.admin import AdminStore, Schema
from ontchatbot.runtime import api
from ontchatbot.runtime.agent import AgentEvent
from ontchatbot.runtime.chatlog import GcsChatLog, LocalChatLog, flags, new_id, summarize_lookup
from ontchatbot.settings import ONTOLOGY_PATH

FOUND = json.dumps({"status": "found", "results": [{"label": "Thủ tục nghỉ học tạm thời"}]})
NOT_FOUND = json.dumps({"status": "not_found", "results": [], "unmatched": ["ký túc xá"]})


def record(**extra) -> dict:
    now = datetime(2026, 9, 18, 17, 19, 39).astimezone()
    return {"id": new_id(now), "time": now.isoformat(), "question": "Hỏi thử", "context": [], "answer": "Đáp thử",
            "outcome": "ok", "error": "", "lookups": [summarize_lookup(["thử"], FOUND)], "duration_ms": 10, **extra}


def test_turns_that_need_a_look_are_flagged_from_the_record_itself() -> None:
    assert flags(record()) == []
    assert flags(record(lookups=[summarize_lookup(["ký túc xá"], NOT_FOUND)])) == ["not_found"]
    assert flags(record(answer="Dữ liệu hiện có không chứa mức phí này.")) == ["says_missing"]
    assert flags(record(answer="Giá phòng không được đề cập trong dữ liệu.")) == ["says_missing"]
    assert flags(record(answer="Câu hỏi này nằm ngoài phạm vi hỗ trợ học vụ.")) == ["out_of_scope"]
    assert flags(record(lookups=[])) == ["no_lookup"]
    assert flags(record(outcome="timeout", answer="")) == ["failed"]


def test_a_lookup_keeps_its_keywords_status_and_the_labels_it_returned() -> None:
    assert summarize_lookup(("ký túc xá",), NOT_FOUND) == {
        "keywords": ["ký túc xá"], "status": "not_found", "results": [], "unmatched": ["ký túc xá"]}
    assert summarize_lookup(("x",), "không phải JSON")["status"] is None


def test_a_local_log_lists_filters_reviews_and_deletes(tmp_path) -> None:
    log = LocalChatLog(tmp_path)
    today = datetime.now().astimezone()
    plain = record(id=new_id(today), time=today.isoformat())
    missing = record(id=new_id(today), time=today.isoformat(), question="Ký túc xá ở đâu?",
                     lookups=[summarize_lookup(["ký túc xá"], NOT_FOUND)], answer="Không tìm thấy thông tin.")
    log.submit(plain)
    log.submit(missing)
    log.flush()

    assert {item["id"] for item in log.list()} == {plain["id"], missing["id"]}
    assert [item["id"] for item in log.list(view="review")] == [missing["id"]]
    assert [item["id"] for item in log.list(query="ký túc")] == [missing["id"]]

    reviewed = log.review(missing["id"], "can-bo-sung", "thêm thực thể ký túc xá")
    assert reviewed["review"]["state"] == "can-bo-sung"
    assert log.list(view="review") == []
    assert [item["id"] for item in log.list(view="todo")] == [missing["id"]]

    log.delete(plain["id"])
    with pytest.raises(KeyError):
        log.get(plain["id"])


def test_a_record_id_cannot_reach_outside_the_log_folder(tmp_path) -> None:
    log = LocalChatLog(tmp_path / "chat")
    for bad in ("../../etc/passwd", "20260918T171939-../../x", "x" * 22):
        with pytest.raises(KeyError):
            log.get(bad)


def test_a_cloud_log_keeps_the_summary_in_object_metadata() -> None:
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.method == "GET":
            return httpx.Response(200, json={"items": [{
                "name": "du-lieu/chat-logs/2026-09-18/20260918T171939-abcdef.json",
                "metadata": {"question": "Ký túc xá?", "time": "t", "outcome": "ok", "flags": "not_found",
                             "review": "", "note": "", "reviewed": ""}}]})
        return httpx.Response(200, json={})

    log = GcsChatLog("kho", "du-lieu/chat-logs/", http=httpx.Client(transport=httpx.MockTransport(handler)),
                     token=lambda: "khoa")
    log.write({**record(), "flags": ["not_found"], "review": {"state": "", "note": "", "time": None}})
    items = log.list(days=3650)

    upload = seen[0]
    assert upload.url.params["uploadType"] == "multipart"
    assert b'"name": "du-lieu/chat-logs/2026-09-18/' in upload.content
    assert b'"flags": "not_found"' in upload.content
    assert items[0]["flags"] == ["not_found"] and items[0]["question"] == "Ký túc xá?"
    assert seen[1].url.params["startOffset"].startswith("du-lieu/chat-logs/")


def test_each_chat_turn_is_recorded_with_its_lookups(tmp_path) -> None:
    class Agent:
        async def stream(self, messages):
            yield AgentEvent("lookup_started", keywords=("ký túc xá",))
            yield AgentEvent("lookup_finished", content=NOT_FOUND)
            yield AgentEvent("text_delta", content="Không tìm thấy thông tin về ký túc xá.")
            yield AgentEvent("completed", content="Không tìm thấy thông tin về ký túc xá.")

    log = LocalChatLog(tmp_path)

    async def run():
        return [chunk async for chunk in api._stream(Agent(), "Ký túc xá ở đâu?",
                                                     [{"role": "user", "content": "Chào"},
                                                      {"role": "assistant", "content": "Chào bạn"}],
                                                     api.TurnGate(), log)]

    asyncio.run(run())
    log.flush()

    [item] = log.list()
    saved = log.get(item["id"])
    assert saved["question"] == "Ký túc xá ở đâu?"
    assert [m["content"] for m in saved["context"]] == ["Chào", "Chào bạn"]
    assert saved["lookups"] == [{"keywords": ["ký túc xá"], "status": "not_found", "results": [],
                                 "unmatched": ["ký túc xá"]}]
    assert saved["flags"] == ["not_found", "says_missing"]


# --- đăng nhập quản trị --------------------------------------------------------------


def _app(tmp_path, chat_log=None):
    shutil.copy(ONTOLOGY_PATH, tmp_path / "ontology.trig")
    shutil.copy(ONTOLOGY_PATH.with_name("shapes.ttl"), tmp_path / "shapes.ttl")
    store = AdminStore(tmp_path / "ontology.trig", Schema.from_file(tmp_path / "shapes.ttl"))
    return api.create_app(object(), admin=store, admin_token="khoa-quan-tri", chat_log=chat_log)


def _client(app):
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://test")


def test_signing_in_gives_a_cookie_that_opens_the_admin_routes(tmp_path) -> None:
    async def run():
        async with _client(_app(tmp_path)) as client:
            wrong = await client.post("/admin/login", json={"key": "sai"})
            before = await client.get("/admin/session")
            right = await client.post("/admin/login", json={"key": "khoa-quan-tri"})
            # Cookie đặt cho đường trình duyệt thấy (/api/admin); ở đây gửi thẳng tới dịch vụ.
            cookie = {"Cookie": f"ontchatbot_admin={client.cookies.get('ontchatbot_admin')}"}
            after = await client.get("/admin/session", headers=cookie)
            await client.post("/admin/logout")
            return wrong, before, right, after

    wrong, before, right, after = asyncio.run(run())
    assert (wrong.status_code, before.status_code, right.status_code, after.status_code) == (401, 401, 200, 200)
    set_cookie = right.headers["set-cookie"].lower()
    assert "httponly" in set_cookie and "secure" in set_cookie and "samesite=strict" in set_cookie
    assert "path=/api/admin" in set_cookie


def test_repeated_wrong_keys_are_blocked_for_a_minute(tmp_path) -> None:
    async def run():
        async with _client(_app(tmp_path)) as client:
            answers = [(await client.post("/admin/login", json={"key": f"sai-{i}"})).status_code for i in range(11)]
            answers.append((await client.post("/admin/login", json={"key": "khoa-quan-tri"})).status_code)
            return answers

    assert asyncio.run(run()) == [401] * 10 + [429, 429]


def test_the_admin_reads_and_marks_chat_history(tmp_path) -> None:
    log = LocalChatLog(tmp_path / "chat")
    today = datetime.now().astimezone()
    turn = record(id=new_id(today), time=today.isoformat(), answer="Không có thông tin.")
    log.submit(turn)
    log.flush()
    key = {"X-Admin-Token": "khoa-quan-tri"}

    async def run():
        async with _client(_app(tmp_path, log)) as client:
            listed = (await client.get("/admin/chats?view=review", headers=key)).json()
            marked = await client.put(f"/admin/chats/{turn['id']}", headers=key,
                                      json={"state": "can-bo-sung", "note": "thêm dữ liệu"})
            bad = await client.put(f"/admin/chats/{turn['id']}", headers=key, json={"state": "lung-tung"})
            missing = await client.get("/admin/chats/20990101T000000-abcdef", headers=key)
            return listed, marked, bad, missing

    listed, marked, bad, missing = asyncio.run(run())
    assert [item["id"] for item in listed["items"]] == [turn["id"]]
    assert marked.json()["review"]["note"] == "thêm dữ liệu"
    assert (bad.status_code, missing.status_code) == (400, 404)
