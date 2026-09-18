"""Bản gốc trên Cloud Storage: tải về lúc khởi động, ghi có điều kiện, hai phiên sửa không đè nhau."""

from __future__ import annotations

import shutil
import threading
from types import SimpleNamespace

import httpx
import pytest

from ontchatbot.admin import AdminError, AdminStore, Conflict, Schema
from ontchatbot.admin.remote import GcsObject, MetadataToken, RemoteOntology, StaleCopy, watch
from ontchatbot.settings import ONTOLOGY_PATH

SHAPES_PATH = ONTOLOGY_PATH.with_name("shapes.ttl")


def concept(label: str) -> dict:
    return {
        "class": "KhaiNiem",
        "label": label,
        "statements": [
            {"property": "loaiKhaiNiem", "value": "KhaiNiemHocVu"},
            {"property": "noiDung", "value": "Nội dung thử.", "source": "Nguon1052", "coordinate": "khoản 9 Điều 99"},
        ],
    }


class FakeObject:
    """Một đối tượng Cloud Storage trong bộ nhớ, cùng quy tắc số thế hệ với kho thật."""

    name = "ontology.trig"

    def __init__(self) -> None:
        self.data: bytes | None = None
        self.number = 0

    def generation(self) -> str | None:
        return None if self.data is None else str(self.number)

    def download(self) -> tuple[bytes, str]:
        return self.data, str(self.number)

    def upload(self, data: bytes, if_generation: str) -> str:
        if if_generation != (self.generation() or "0"):
            raise StaleCopy(self.name)
        self.data, self.number = data, self.number + 1
        return str(self.number)


# --- gọi JSON API ---------------------------------------------------------------


def gcs(handler) -> GcsObject:
    return GcsObject("kho-ntu", "du lieu/ontology.trig", http=httpx.Client(transport=httpx.MockTransport(handler)),
                     token=lambda: "khoa")


def test_an_address_names_the_bucket_and_the_object() -> None:
    remote = GcsObject.from_uri("gs://kho-ntu/du-lieu/ontology.trig", http=object(), token=str)

    assert (remote.bucket, remote.name) == ("kho-ntu", "du-lieu/ontology.trig")
    for wrong in ("kho-ntu/ontology.trig", "gs://kho-ntu", "gs://kho-ntu/", "gs:///ontology.trig"):
        with pytest.raises(ValueError):
            GcsObject.from_uri(wrong, http=object(), token=str)


def test_reading_sends_the_token_and_escapes_the_object_name() -> None:
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.params.get("alt") == "media":
            return httpx.Response(200, content=b"noi dung", headers={"x-goog-generation": "17"})
        return httpx.Response(200, json={"generation": "17"})

    remote = gcs(handler)

    assert remote.generation() == "17"
    assert remote.download() == (b"noi dung", "17")
    assert all(r.headers["Authorization"] == "Bearer khoa" for r in seen)
    assert seen[0].url.raw_path.startswith(b"/storage/v1/b/kho-ntu/o/du%20lieu%2Fontology.trig?")


def test_a_missing_object_has_no_generation() -> None:
    assert gcs(lambda request: httpx.Response(404)).generation() is None


def test_a_write_is_conditional_on_the_generation_it_was_built_on() -> None:
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.params["ifGenerationMatch"] != "17":
            return httpx.Response(412)
        return httpx.Response(200, json={"generation": "18"})

    remote = gcs(handler)

    assert remote.upload(b"ban moi", "17") == "18"
    with pytest.raises(StaleCopy):
        remote.upload(b"ban moi", "16")
    assert seen[0].url.path == "/upload/storage/v1/b/kho-ntu/o"
    assert dict(seen[0].url.params) == {"uploadType": "media", "name": "du lieu/ontology.trig", "ifGenerationMatch": "17"}
    assert seen[0].content == b"ban moi"


def test_other_refusals_are_reported_not_mistaken_for_a_missing_object() -> None:
    with pytest.raises(RuntimeError, match="HTTP 403"):
        gcs(lambda request: httpx.Response(403, text="khong co quyen")).generation()


def test_the_service_account_token_is_kept_until_shortly_before_it_expires() -> None:
    now = [0.0]
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.headers["Metadata-Flavor"])
        return httpx.Response(200, json={"access_token": f"khoa-{len(calls)}", "expires_in": 3600})

    token = MetadataToken(httpx.Client(transport=httpx.MockTransport(handler)), clock=lambda: now[0])

    assert token() == token() == "khoa-1"
    now[0] = 3600 - 59
    assert token() == "khoa-2"
    assert calls == ["Google", "Google"]


# --- bản sao trên đĩa -----------------------------------------------------------


def test_the_first_start_uploads_the_packaged_ontology(tmp_path) -> None:
    path = tmp_path / "ontology.trig"
    path.write_bytes(b"ban trong anh")
    bucket = FakeObject()

    RemoteOntology({path: bucket}).start()

    assert bucket.data == b"ban trong anh"


def test_an_instance_starting_at_the_same_moment_takes_the_copy_seeded_first(tmp_path) -> None:
    path = tmp_path / "ontology.trig"
    path.write_bytes(b"ban trong anh")
    bucket = FakeObject()
    empty_then_seeded = iter([None])
    original = bucket.generation
    bucket.generation = lambda: next(empty_then_seeded, None) or original()
    bucket.upload(b"ban cua ban kia", "0")
    remote = RemoteOntology({path: bucket})

    remote.start()

    assert path.read_bytes() == b"ban cua ban kia"
    assert remote.generations[path] == "1"


def test_a_later_start_replaces_the_packaged_ontology_with_the_stored_one(tmp_path) -> None:
    path = tmp_path / "ontology.trig"
    path.write_bytes(b"ban trong anh")
    bucket = FakeObject()
    bucket.upload(b"ban da sua", "0")
    remote = RemoteOntology({path: bucket})

    remote.start()

    assert path.read_bytes() == b"ban da sua"
    assert remote.refresh() is False


def test_a_refresh_fetches_only_a_newer_version(tmp_path) -> None:
    bucket = FakeObject()
    bucket.upload(b"ban 1", "0")
    path = tmp_path / "ontology.trig"
    remote = RemoteOntology({path: bucket})
    remote.start()

    bucket.upload(b"ban 2", "1")

    assert remote.refresh() is True
    assert path.read_bytes() == b"ban 2"
    assert remote.refresh() is False


def test_the_watcher_keeps_polling_after_a_failed_check() -> None:
    calls = []
    done = threading.Event()
    stop = threading.Event()

    def poll() -> None:
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("mat mang")
        done.set()

    thread = watch(poll, 0.01, stop)
    assert done.wait(5)
    stop.set()
    thread.join(5)
    assert len(calls) >= 2


# --- trang quản trị ghi lên kho bền ---------------------------------------------


def test_a_failed_persist_leaves_the_file_and_the_memory_unchanged(tmp_path) -> None:
    path = tmp_path / "ontology.trig"
    shutil.copy(ONTOLOGY_PATH, path)
    before = path.read_bytes()

    def persist(files) -> None:
        raise Conflict("kho bền từ chối")

    store = AdminStore(path, Schema.from_file(SHAPES_PATH), shapes_path=SHAPES_PATH, persist=persist)
    with pytest.raises(Conflict):
        store.create(concept("Mục thử không được lưu"))

    assert path.read_bytes() == before
    assert all(item["label"] != "Mục thử không được lưu" for item in store.list("KhaiNiem"))


def instance(tmp_path, name: str, bucket: FakeObject) -> tuple[AdminStore, RemoteOntology, SimpleNamespace]:
    """Một bản dịch vụ như trên Cloud Run: bản sao riêng trên đĩa, chung một đối tượng Cloud Storage."""

    import ontchatbot.cli.serve as serve

    folder = tmp_path / name
    folder.mkdir()
    shutil.copy(ONTOLOGY_PATH, folder / "ontology.trig")
    shutil.copy(SHAPES_PATH, folder / "shapes.ttl")
    args = serve._parse_args(["--llm", "mo-hinh", "--ontology", str(folder / "ontology.trig")])
    agent = SimpleNamespace(lookup=SimpleNamespace(engine=None))
    remote = RemoteOntology({args.ontology: bucket})
    remote.start()
    store, _token = serve._build_admin(args, agent, remote)
    return store, remote, agent


def test_two_instances_editing_at_once_never_overwrite_each_other(tmp_path, monkeypatch) -> None:
    import ontchatbot.cli.serve as serve

    reloads = []
    monkeypatch.setattr(serve, "_reload_engine", lambda _args, runtime, why: reloads.append((runtime, why)))
    monkeypatch.setenv("ONTCHATBOT_ADMIN_TOKEN", "quan-tri")
    bucket = FakeObject()
    first, first_remote, _ = instance(tmp_path, "a", bucket)
    second, _, second_agent = instance(tmp_path, "b", bucket)

    created = first.create(concept("Mục do phiên thứ nhất thêm"))
    assert bucket.data == first.path.read_bytes()

    with pytest.raises(AdminError) as refused:
        second.create(concept("Mục do phiên thứ hai thêm"))
    assert refused.value.status == 409
    assert second.get(created)["label"] == "Mục do phiên thứ nhất thêm", "bản mới đã được tải về"
    assert second.path.read_bytes() == bucket.data
    assert (second_agent, "from Cloud Storage after a conflicting edit") in reloads, "engine của phiên thứ hai nạp lại"

    added = second.create(concept("Mục do phiên thứ hai thêm"))

    assert first.reload(first_remote.refresh) is True
    assert first.get(added)["label"] == "Mục do phiên thứ hai thêm"
    assert first.get(created)["label"] == "Mục do phiên thứ nhất thêm"


def test_when_cloud_storage_cannot_be_reached_the_editor_is_told_nothing_was_saved(tmp_path, monkeypatch) -> None:
    import ontchatbot.cli.serve as serve

    monkeypatch.setattr(serve, "_reload_engine", lambda *_args: None)
    monkeypatch.setenv("ONTCHATBOT_ADMIN_TOKEN", "quan-tri")
    bucket = FakeObject()
    store, _, _ = instance(tmp_path, "a", bucket)
    before = store.path.read_bytes()

    def unreachable(data: bytes, if_generation: str) -> str:
        raise httpx.ConnectError("mat mang")

    monkeypatch.setattr(bucket, "upload", unreachable)
    with pytest.raises(AdminError) as refused:
        store.create(concept("Mục thử không được lưu"))

    assert refused.value.status == 503
    assert store.path.read_bytes() == before == bucket.data


def test_a_data_edit_is_refused_when_the_schema_changed_elsewhere(tmp_path) -> None:
    """Sửa mục dựng trên lược đồ cũ không được đè lên dữ liệu đã khớp lược đồ mới của phiên khác."""

    data, shapes = tmp_path / "ontology.trig", tmp_path / "shapes.ttl"
    data.write_bytes(b"du lieu")
    shapes.write_bytes(b"luoc do")
    data_object, shapes_object = FakeObject(), FakeObject()
    remote = RemoteOntology({data: data_object, shapes: shapes_object})
    remote.start()
    shapes_object.upload(b"luoc do moi", "1")

    with pytest.raises(StaleCopy):
        remote.push({data: b"du lieu da sua"})

    assert data_object.data == b"du lieu"
    assert remote.refresh() is True
    assert shapes.read_bytes() == b"luoc do moi"


def test_the_schema_object_sits_beside_the_ontology_object() -> None:
    remote = RemoteOntology.beside(GcsObject("kho", "du-lieu/ontology.trig", http=object(), token=str),
                                   ONTOLOGY_PATH)

    assert sorted(obj.name for obj in remote.files.values()) == ["du-lieu/ontology.trig", "du-lieu/shapes.ttl"]
