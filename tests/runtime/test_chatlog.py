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
from ontchatbot.runtime.chatlog import GcsChatLog, LocalChatLog, flags, new_id, summarize_lookup, valid_id
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


def test_the_model_marks_decide_the_missing_and_out_of_scope_flags() -> None:
    # Câu dặn "không cung cấp số tài khoản" từng bị đoán nhầm là báo thiếu; có dấu thì chỉ tin dấu.
    warning = "Tuyệt đối không cung cấp số tài khoản của Trường cho ngân hàng."
    assert flags(record(answer=warning, marks=[])) == []
    assert flags(record(answer="Đủ.", marks=["missing"])) == ["says_missing"]
    assert flags(record(answer="Đủ.", marks=["out_of_scope"])) == ["out_of_scope"]


def test_a_lookup_keeps_its_keywords_status_and_the_labels_it_returned() -> None:
    assert summarize_lookup(("ký túc xá",), NOT_FOUND) == {
        "keywords": ["ký túc xá"], "status": "not_found", "results": [], "unmatched": ["ký túc xá"]}
    assert summarize_lookup(("x",), "không phải JSON")["status"] is None


def test_a_local_log_groups_turns_into_sessions_filters_reviews_and_deletes(tmp_path) -> None:
    log = LocalChatLog(tmp_path)
    today = datetime.now().astimezone()
    day = f"{today:%Y%m%d}"
    first, other = f"{day}T100000-000001", f"{day}T110000-000002"
    plain = record(id=f"{day}T100001-00000a", session=first, time=today.isoformat())
    missing = record(id=f"{day}T100002-00000b", session=first, time=today.isoformat(), question="Ký túc xá ở đâu?",
                     lookups=[summarize_lookup(["ký túc xá"], NOT_FOUND)], answer="Không tìm thấy thông tin.")
    alone = record(id=f"{day}T110001-00000c", session=other, time=today.isoformat(), question="Học phí?")
    for turn in (plain, missing, alone):
        log.submit(turn)
    log.flush()

    listed = log.list()
    assert [item["session"] for item in listed] == [other, first]
    assert {key: listed[1][key] for key in ("turns", "question", "flags", "open", "todo")} == {
        "turns": 2, "question": "Hỏi thử", "flags": ["not_found", "says_missing"], "open": 1, "todo": 0}
    assert [item["session"] for item in log.list(view="review")] == [first]
    assert [item["session"] for item in log.list(query="ký túc")] == [first]
    assert [turn["id"] for turn in log.session(first)["turns"]] == [plain["id"], missing["id"]]

    reviewed = log.review(first, missing["id"], "can-bo-sung", "thêm thực thể ký túc xá")
    assert reviewed["review"]["state"] == "can-bo-sung"
    assert log.list(view="review") == []
    assert [(item["session"], item["todo"]) for item in log.list(view="todo")] == [(first, 1)]

    log.delete(first, plain["id"])
    assert [turn["id"] for turn in log.session(first)["turns"]] == [missing["id"]]
    log.delete(other)
    with pytest.raises(KeyError):
        log.session(other)


def test_an_id_cannot_reach_outside_the_log_folder(tmp_path) -> None:
    log = LocalChatLog(tmp_path / "chat")
    for bad in ("../../etc/passwd", "20260918T171939-../../x", "x" * 22, "20260918T171939-ABCDEF"):
        with pytest.raises(KeyError):
            log.session(bad)
        with pytest.raises(KeyError):
            log.delete("20260918T171939-abcdef", bad)


def test_a_cloud_log_keeps_the_summary_in_object_metadata() -> None:
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.method == "GET":
            return httpx.Response(200, json={"items": [{
                "name": "du-lieu/chat-logs/2026-09-18/20260918T171900-aaaaaa/20260918T171939-abcdef.json",
                "metadata": {"question": "Ký túc xá?", "time": "t", "outcome": "ok", "flags": "not_found",
                             "review": "", "note": "", "reviewed": "", "admin": "1"}}]})
        return httpx.Response(200, json={})

    log = GcsChatLog("kho", "du-lieu/chat-logs/", http=httpx.Client(transport=httpx.MockTransport(handler)),
                     token=lambda: "khoa")
    log.write({**record(session="20260918T171900-aaaaaa"), "flags": ["not_found"],
               "review": {"state": "", "note": "", "time": None}, "admin": True})
    items = log.list(days=3650)

    upload = seen[0]
    assert upload.url.params["uploadType"] == "multipart"
    assert b'"name": "du-lieu/chat-logs/2026-09-18/20260918T171900-aaaaaa/' in upload.content
    assert b'"flags": "not_found"' in upload.content
    assert b'"admin": "1"' in upload.content
    assert items[0]["session"] == "20260918T171900-aaaaaa"
    assert items[0]["flags"] == ["not_found"] and items[0]["question"] == "Ký túc xá?"
    assert items[0]["admin"] is True
    assert seen[1].url.params["startOffset"].startswith("du-lieu/chat-logs/")


def test_each_chat_turn_is_recorded_with_its_lookups(tmp_path) -> None:
    class Agent:
        async def stream(self, messages):
            yield AgentEvent("lookup_started", keywords=("ký túc xá",))
            yield AgentEvent("lookup_finished", content=NOT_FOUND)
            yield AgentEvent("text_delta", content="Không tìm thấy thông tin về ký túc xá.")
            yield AgentEvent("completed", content="Không tìm thấy thông tin về ký túc xá.", marks=("missing",))

    log = LocalChatLog(tmp_path)

    async def run():
        return [chunk async for chunk in api._stream(Agent(), "Ký túc xá ở đâu?",
                                                     [{"role": "user", "content": "Chào"},
                                                      {"role": "assistant", "content": "Chào bạn"}],
                                                     api.TurnGate(), log)]

    asyncio.run(run())
    log.flush()

    [item] = log.list()
    [saved] = log.session(item["session"])["turns"]
    assert saved["question"] == "Ký túc xá ở đâu?" and saved["session"] == item["session"]
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
            # Cookie đặt cho đường trình duyệt thấy (/api); ở đây gửi thẳng tới dịch vụ.
            cookie = {"Cookie": f"ontchatbot_admin={client.cookies.get('ontchatbot_admin')}"}
            after = await client.get("/admin/session", headers=cookie)
            await client.post("/admin/logout")
            return wrong, before, right, after

    wrong, before, right, after = asyncio.run(run())
    assert (wrong.status_code, before.status_code, right.status_code, after.status_code) == (401, 401, 200, 200)
    set_cookie = right.headers["set-cookie"].lower()
    assert "httponly" in set_cookie and "secure" in set_cookie and "samesite=strict" in set_cookie
    assert "path=/api;" in set_cookie or set_cookie.endswith("path=/api")


def test_a_question_asked_while_signed_in_as_admin_is_labelled(tmp_path) -> None:
    class Agent:
        async def stream(self, messages):
            yield AgentEvent("completed", content="Có.")

    shutil.copy(ONTOLOGY_PATH, tmp_path / "ontology.trig")
    shutil.copy(ONTOLOGY_PATH.with_name("shapes.ttl"), tmp_path / "shapes.ttl")
    store = AdminStore(tmp_path / "ontology.trig", Schema.from_file(tmp_path / "shapes.ttl"))
    log = LocalChatLog(tmp_path / "logs")
    app = api.create_app(Agent(), admin=store, admin_token="khoa-quan-tri", chat_log=log)

    async def run():
        async with _client(app) as client:
            await client.post("/chat", json={"message": "câu của sinh viên"})
            await client.post("/admin/login", json={"key": "khoa-quan-tri"})
            cookie = {"Cookie": f"ontchatbot_admin={client.cookies.get('ontchatbot_admin')}"}
            await client.post("/chat", json={"message": "câu quản trị thử"}, headers=cookie)
            await client.post("/chat", json={"message": "cookie giả"}, headers={"Cookie": "ontchatbot_admin=v1.9999999999.x"})

    asyncio.run(run())
    log.flush()
    labelled = {item["question"]: item["admin"] for item in log.list()}
    assert labelled == {"câu của sinh viên": False, "câu quản trị thử": True, "cookie giả": False}


def test_repeated_wrong_keys_are_blocked_for_a_minute(tmp_path) -> None:
    async def run():
        async with _client(_app(tmp_path)) as client:
            answers = [(await client.post("/admin/login", json={"key": f"sai-{i}"})).status_code for i in range(11)]
            answers.append((await client.post("/admin/login", json={"key": "khoa-quan-tri"})).status_code)
            return answers

    assert asyncio.run(run()) == [401] * 10 + [429, 429]


def test_the_admin_reads_marks_and_deletes_chat_sessions(tmp_path) -> None:
    log = LocalChatLog(tmp_path / "chat")
    today = datetime.now().astimezone()
    session = new_id(today)
    turn = record(id=new_id(today), session=session, time=today.isoformat(), answer="Không có thông tin.")
    log.submit(turn)
    log.flush()
    key = {"X-Admin-Token": "khoa-quan-tri"}

    async def run():
        async with _client(_app(tmp_path, log)) as client:
            listed = (await client.get("/admin/chats?view=review", headers=key)).json()
            opened = (await client.get(f"/admin/chats/{session}", headers=key)).json()
            marked = await client.put(f"/admin/chats/{session}/{turn['id']}", headers=key,
                                      json={"state": "can-bo-sung", "note": "thêm dữ liệu"})
            bad = await client.put(f"/admin/chats/{session}/{turn['id']}", headers=key, json={"state": "lung-tung"})
            missing = await client.get("/admin/chats/20990101T000000-abcdef", headers=key)
            deleted = await client.delete(f"/admin/chats/{session}", headers=key)
            gone = await client.get(f"/admin/chats/{session}", headers=key)
            return listed, opened, marked, bad, missing, deleted, gone

    listed, opened, marked, bad, missing, deleted, gone = asyncio.run(run())
    assert [item["session"] for item in listed["items"]] == [session]
    assert [t["id"] for t in opened["turns"]] == [turn["id"]]
    assert marked.json()["review"]["note"] == "thêm dữ liệu"
    assert (bad.status_code, missing.status_code, deleted.status_code, gone.status_code) == (400, 404, 200, 404)


def test_the_chat_route_issues_a_session_and_keeps_the_one_it_is_given(tmp_path) -> None:
    class Agent:
        async def stream(self, messages):
            yield AgentEvent("completed", content="Có.")

    log = LocalChatLog(tmp_path / "logs")
    app = api.create_app(Agent(), chat_log=log)

    async def run():
        async with _client(app) as client:
            first = await client.post("/chat", json={"message": "một"})
            session = first.headers["x-chat-session"]
            again = await client.post("/chat", json={"message": "hai", "session": session})
            forged = await client.post("/chat", json={"message": "ba", "session": "../../x"})
            return session, again.headers["x-chat-session"], forged.headers["x-chat-session"]

    session, again, forged = asyncio.run(run())
    log.flush()
    assert again == session and forged != session and valid_id(forged)
    assert [turn["question"] for turn in log.session(session)["turns"]] == ["một", "hai"]


def test_ids_sort_in_creation_order_and_old_ids_stay_valid() -> None:
    ids = [new_id(datetime.now().astimezone()) for _ in range(50)]

    assert ids == sorted(ids) and all(valid_id(value) for value in ids)
    assert valid_id("20260918T171939-abcdef")
