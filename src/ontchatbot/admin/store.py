"""Thêm, sửa, xoá mục và loại của ontology theo lược đồ.

Mỗi lần ghi đi bốn bước: dựng bản mới trong bộ nhớ, kiểm bản đó bằng lược đồ SHACL, ghi
tệp TriG theo thứ tự cố định, rồi báo để engine tìm kiếm nạp lại. Khi chạy trên Cloud Run,
bản mới được ghi lên Cloud Storage ngay trước khi ghi tệp. Bước nào hỏng thì tệp trên đĩa
giữ nguyên.

"Sửa" là sửa thật: mục được thay bằng đúng những gì người sửa gửi lên, kể cả nguồn của
từng câu, loại và định danh. Địa chỉ trích dẫn được tạo khi người sửa chọn nguồn và ghi vị
trí; địa chỉ không còn câu nào dùng thì bị dọn.

Sửa loại (lớp) ghi cả shapes.ttl lẫn ontology.trig: tên hiển thị của loại, thuộc tính và
giá trị chọn nằm ở cả hai nơi (form đọc shapes.ttl, engine đọc nhãn trong ontology.trig).
Đổi định danh loại hay thuộc tính thì mọi câu đang dùng nó đổi theo. Toàn bộ dữ liệu được
kiểm lại với lược đồ mới trước khi ghi.

Mỗi mục và mỗi loại mang một ``version`` (dấu vân tay nội dung). Form gửi lại dấu đó khi
lưu; mục đã bị sửa ở tab hay phiên khác thì lần lưu bị từ chối thay vì đè lên.
"""

from __future__ import annotations

import hashlib
import json
import re
import threading
from collections.abc import Callable, Iterable
from dataclasses import asdict
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urlparse

import pyoxigraph as oxi

from ..rdf import OUTSIDE, RDF_TYPE, SH, XSD, load_trig, local_id
from ..rdf import RDFS_LABEL as LABEL
from ..rdf import SKOS_ALT_LABEL as ALT_LABEL
from ..rdf import term as _node
from .schema import KINDS, ClassSpec, Field, Schema
from .trig import iri_name, serialize, write_bytes

IDENTITY = (RDF_TYPE, LABEL, ALT_LABEL)
SOURCE_CLASS = "Nguon"
ADDRESS_CLASS = "DiaChiTrichDan"
#: Định danh mà mã nguồn gọi thẳng (tìm kiếm, trích dẫn, khuôn nhắc): đổi hay xoá chúng làm
#: hỏng chatbot âm thầm, nên trang quản trị chỉ cho đổi tên hiển thị.
CODE_NAMES = frozenset({
    "Nguon", "DiaChiTrichDan", "ThuTucHocVu", "MucBieuMauTrenWebsite", "NganhDaoTao", "DonViTrongTruong",
    "thuocNguon", "toaDo", "duongDan", "soHieu", "banHanhNgay", "ngayThuThap", "diaChiTaiVe", "hopThu", "websiteDonVi",
})
_ID = re.compile(r"[A-Za-z][A-Za-z0-9_]*\Z")
_CLASS_ID = re.compile(r"[A-Z][A-Za-z0-9_]*\Z")
_PROPERTY_ID = re.compile(r"[a-z][A-Za-z0-9_]*\Z")
#: Sửa lược đồ có thể làm hàng trăm mục vi phạm; chỉ liệt kê chừng này dòng.
MAX_LISTED = 20
#: Lời giải thích cho từng loại vi phạm SHACL mà lược đồ dùng.
_VIOLATIONS = {
    "MinCountConstraintComponent": "thiếu giá trị bắt buộc",
    "MaxCountConstraintComponent": "chỉ được có một giá trị",
    "DatatypeConstraintComponent": "sai kiểu dữ liệu",
    "LanguageInConstraintComponent": "chữ phải gắn nhãn tiếng Việt",
    "ClassConstraintComponent": "phải trỏ tới một thực thể đúng lớp",
    "InConstraintComponent": "giá trị không nằm trong danh sách cho phép",
    "ClosedConstraintComponent": "thuộc tính này không thuộc lớp của thực thể",
}
_KIND_NAMES = {"integer": "số nguyên", "decimal": "số", "date": "ngày (YYYY-MM-DD)"}
_ID_RULE = "chỉ gồm chữ không dấu, chữ số và dấu gạch dưới, bắt đầu bằng một chữ cái"


class AdminError(Exception):
    """Yêu cầu không thực hiện được.

    ``errors`` là các câu giải thích; ``details`` là cùng các lỗi đó kèm chỗ sai (``row``: dòng
    thứ mấy của form, ``property``, ``where``: "label" · "altLabels" · "id" · "name" · "fields",
    ``field``: ô thứ mấy khi sửa loại) để trang tô đỏ đúng chỗ. ``confirm``: làm được, nhưng sẽ
    xoá dữ liệu, nên cần người sửa đồng ý rồi gửi lại.
    """

    status = 400

    def __init__(self, message: str, errors: Iterable[str | dict] = (), *, confirm: bool = False) -> None:
        super().__init__(message)
        self.details = [dict(error) if isinstance(error, dict) else {"message": str(error)} for error in errors]
        self.errors = [detail["message"] for detail in self.details]
        self.confirm = confirm


class NotFound(AdminError):
    status = 404


class Conflict(AdminError):
    status = 409


class Unavailable(AdminError):
    status = 503


def _problem(message: str, **where) -> dict:
    return {"message": message, **where}


def _any(quads) -> bool:
    return next(iter(quads), None) is not None


def _exists(store: oxi.Store, node: oxi.NamedNode) -> bool:
    return _any(store.quads_for_pattern(node, None, None, None))


def _version(content) -> str:
    return hashlib.sha1(json.dumps(content, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]


def _text(raw) -> str:
    """Chữ một dòng: bỏ khoảng trắng thừa."""

    return " ".join(str(raw or "").split())


def _label(payload: dict) -> str:
    label = payload.get("label")
    if not isinstance(label, str) or not label.strip():
        raise AdminError("Thực thể phải có tên.", [_problem("Thực thể phải có tên.", where="label")])
    return label.strip()


def _value(field: Field, raw, where: str, errors: list[dict], at: dict):
    text = raw if isinstance(raw, str) else ("" if raw is None else str(raw))
    if not text.strip():
        errors.append(_problem(f"{where}: chưa có giá trị.", **at))
        return None
    try:
        if field.kind == "text":
            return oxi.Literal(text, language="vi")
        if field.kind in ("link", "choice"):
            return _node(text.strip())
        if field.kind == "integer":
            return oxi.Literal(str(int(text.strip())), datatype=oxi.NamedNode(XSD + "integer"))
        if field.kind == "decimal":
            return oxi.Literal(str(Decimal(text.strip())), datatype=oxi.NamedNode(XSD + "decimal"))
        if field.kind == "date":
            return oxi.Literal(date.fromisoformat(text.strip()).isoformat(), datatype=oxi.NamedNode(XSD + "date"))
        if field.kind == "uri":
            url = urlparse(text.strip())
            if url.scheme not in ("http", "https") or not url.netloc or " " in text.strip():
                errors.append(_problem(f"{where}: «{text.strip()}» không phải địa chỉ web (bắt đầu bằng http:// "
                                       "hoặc https://).", **at))
                return None
            return oxi.Literal(text.strip(), datatype=oxi.NamedNode(XSD + "anyURI"))
    except (ValueError, InvalidOperation):
        errors.append(_problem(f"{where}: «{text.strip()}» không phải {_KIND_NAMES[field.kind]}.", **at))
        return None
    return oxi.Literal(text)


def _move(store: oxi.Store, pattern: tuple, rebuild: Callable[[oxi.Quad], oxi.Quad]) -> None:
    for quad in list(store.quads_for_pattern(*pattern)):
        store.remove(quad)
        store.add(rebuild(quad))


def _rename_subject(store: oxi.Store, old: str, new: str) -> None:
    _move(store, (_node(old), None, None, None), lambda q: oxi.Quad(_node(new), q.predicate, q.object, q.graph_name))


def _rename_object(store: oxi.Store, old: str, new: str) -> None:
    _move(store, (None, None, _node(old), None), lambda q: oxi.Quad(q.subject, q.predicate, _node(new), q.graph_name))


def _rename_predicate(store: oxi.Store, old: str, new: str) -> None:
    _move(store, (None, _node(old), None, None), lambda q: oxi.Quad(q.subject, _node(new), q.object, q.graph_name))


def _set_label(store: oxi.Store, local: str, text: str) -> None:
    """Nhãn của loại, thuộc tính hay giá trị chọn: engine đọc nhãn này để gọi tên chúng."""

    for quad in list(store.quads_for_pattern(_node(local), LABEL, None, OUTSIDE)):
        store.remove(quad)
    store.add(oxi.Quad(_node(local), LABEL, oxi.Literal(text, language="vi"), OUTSIDE))


def _schema_names(schema: Schema) -> set[str]:
    names = set(schema.all_classes)
    for spec in schema.all_classes.values():
        for field in spec.fields:
            names.add(field.property)
            names.update(field.choices)
    return names


class AdminStore:
    def __init__(
        self,
        path: Path | str,
        schema: Schema,
        *,
        shapes_path: Path | str | None = None,
        on_change: Callable[[Path], None] | None = None,
        persist: Callable[[dict[Path, bytes]], None] | None = None,
    ) -> None:
        """``persist`` nhận đúng nội dung sắp ghi của từng tệp (ontology.trig, và shapes.ttl khi sửa loại),
        trước khi tệp trên đĩa đổi: bản triển khai dùng nó để ghi lên kho bền (Cloud Storage). Nó báo lỗi
        thì lần sửa bị huỷ, tệp và bộ nhớ giữ nguyên."""

        self.path = Path(path)
        self.schema = schema
        self.shapes_path = Path(shapes_path) if shapes_path else self.path.with_name("shapes.ttl")
        self.on_change = on_change
        self.persist = persist
        self._store = load_trig(self.path)
        # RLock: khi kho bền báo có bản mới hơn, việc nạp lại chạy ngay trong lượt ghi đang giữ khoá.
        self._lock = threading.RLock()
        self._shapes = None

    def reload(self, fetch: Callable[[], bool] | None = None) -> bool:
        """Đọc lại tệp trên đĩa; trả ``True`` khi đã đọc.

        ``fetch`` thay tệp bằng bản mới từ kho bền và trả ``False`` khi không có gì mới. Nó chạy trong
        khoá ghi, để không lần sửa nào dựng trên bản cũ trong bộ nhớ trong lúc tệp đã là bản mới.
        """

        with self._lock:
            if fetch is not None and not fetch():
                return False
            self._store = load_trig(self.path)
            if self.shapes_path.exists():
                self.schema = Schema.from_file(self.shapes_path)
                self._shapes = None
            return True

    # --- đọc ------------------------------------------------------------------

    def label(self, local: str, store: oxi.Store | None = None) -> str:
        for quad in (store or self._store).quads_for_pattern(_node(local), LABEL, None, OUTSIDE):
            return quad.object.value
        return local

    def class_of(self, local: str, store: oxi.Store | None = None, schema: Schema | None = None) -> str | None:
        classes = (schema or self.schema).classes
        for quad in (store or self._store).quads_for_pattern(_node(local), RDF_TYPE, None, OUTSIDE):
            name = local_id(quad.object.value)
            if name in classes or name == ADDRESS_CLASS:
                return name
        return None

    def counts(self) -> dict[str, int]:
        return {name: sum(1 for _ in self._store.quads_for_pattern(None, RDF_TYPE, _node(name), OUTSIDE))
                for name in self.schema.classes}

    def list(self, class_name: str) -> list[dict[str, str]]:
        if class_name not in self.schema.classes:
            raise NotFound(f"Không có lớp «{class_name}».")
        items = [{"id": local_id(quad.subject.value), "label": self.label(local_id(quad.subject.value))}
                 for quad in self._store.quads_for_pattern(None, RDF_TYPE, _node(class_name), OUTSIDE)]
        return sorted(items, key=lambda item: item["label"].casefold())

    def get(self, local: str) -> dict:
        with self._lock:
            entity = self._content(local)
            return {**entity, "version": _version(entity),
                    "references": self._references(self._store, _node(local))}

    def _content(self, local: str) -> dict:
        class_name = self.class_of(local)
        if class_name is None or class_name == ADDRESS_CLASS:
            raise NotFound(f"Không có thực thể «{local}».")
        node = _node(local)
        statements = []
        for quad in self._store.quads_for_pattern(node, None, None, None):
            if quad.predicate in IDENTITY:
                continue
            source, coordinate = self._address_parts(self._store, quad.graph_name)
            statements.append({
                "property": local_id(quad.predicate.value),
                "value": local_id(quad.object.value) if isinstance(quad.object, oxi.NamedNode) else quad.object.value,
                "source": source,
                "coordinate": coordinate,
            })
        statements.sort(key=lambda s: (s["property"], s["source"] or "", s["coordinate"] or "", s["value"]))
        return {
            "id": local,
            "class": class_name,
            "label": self.label(local),
            "altLabels": sorted(q.object.value for q in self._store.quads_for_pattern(node, ALT_LABEL, None, OUTSIDE)),
            "statements": statements,
        }

    def _address_parts(self, store: oxi.Store, graph) -> tuple[str | None, str | None]:
        if isinstance(graph, oxi.DefaultGraph):
            return None, None
        source = coordinate = None
        for quad in store.quads_for_pattern(graph, None, None, OUTSIDE):
            name = local_id(quad.predicate.value)
            if name == "thuocNguon":
                source = local_id(quad.object.value)
            elif name == "toaDo":
                coordinate = quad.object.value
        return source, coordinate

    def _references(self, store: oxi.Store, node: oxi.NamedNode) -> list[dict]:
        """Những mục đang trỏ tới mục này: bằng một câu của chúng, hay bằng câu trích dẫn nó (với Nguồn)."""

        found = {}
        for quad in store.quads_for_pattern(None, None, node, None):
            if quad.predicate == RDF_TYPE:
                continue
            subject = local_id(quad.subject.value)
            if self.class_of(subject, store) == ADDRESS_CLASS:
                for cited in store.quads_for_pattern(None, None, None, quad.subject):
                    entity = local_id(cited.subject.value)
                    reference = {"id": entity, "label": self.label(entity, store), "property": "trích dẫn nguồn này"}
                    found[(entity, reference["property"])] = reference
                continue
            spec = self.schema.classes.get(self.class_of(subject, store) or "")
            field = spec.field(local_id(quad.predicate.value)) if spec else None
            reference = {"id": subject, "label": self.label(subject, store),
                         "property": field.name if field else local_id(quad.predicate.value)}
            found[(subject, reference["property"])] = reference
        return sorted(found.values(), key=lambda r: (r["property"], r["label"].casefold()))

    def _taken(self, store: oxi.Store, local: str, schema: Schema | None = None) -> bool:
        """Định danh đã được dùng ở bất cứ đâu: làm mục, thuộc tính, giá trị, túi trích dẫn hay trong lược đồ."""

        node = _node(local)
        return (local in _schema_names(schema or self.schema)
                or _any(store.quads_for_pattern(node, None, None, None))
                or _any(store.quads_for_pattern(None, node, None, None))
                or _any(store.quads_for_pattern(None, None, node, None))
                or _any(store.quads_for_pattern(None, None, None, node)))

    # --- ghi mục ----------------------------------------------------------------

    def create(self, payload: dict) -> str:
        with self._lock:
            spec = self.schema.classes.get(payload.get("class"))
            if spec is None:
                raise AdminError("Chọn lớp cho thực thể mới.")
            label = _label(payload)
            chosen = str(payload.get("id") or "").strip()
            local = chosen or iri_name(label)
            if not local:
                raise AdminError("Tên phải có ít nhất một chữ cái hoặc chữ số.",
                                 [_problem("Tên phải có ít nhất một chữ cái hoặc chữ số.", where="label")])
            if chosen and not _ID.match(chosen):
                raise AdminError(f"Định danh {_ID_RULE}.", [_problem(f"Định danh {_ID_RULE}.", where="id")])
            if self._taken(self._store, local):
                message = (f"Định danh «{local}» đã được dùng; hãy chọn định danh khác." if chosen else
                           f"Định danh «{local}» sinh từ tên này đã được dùng; hãy đặt tên khác.")
                raise Conflict(message, [_problem(message, where="id" if chosen else "label")])
            store = self._copy()
            self._put(store, local, spec, label, payload)
            self._commit(store)
            return local

    def update(self, local: str, payload: dict) -> str:
        """Thay mục bằng nội dung gửi lên; có thể đổi cả loại và định danh. Trả định danh sau khi sửa."""

        with self._lock:
            current = self._content(local)
            self._check_version(payload.get("version"), current)
            spec = self.schema.classes.get(payload.get("class") or current["class"])
            if spec is None:
                raise AdminError(f"Không có lớp «{payload.get('class')}».")
            label = _label(payload)
            new_local = str(payload.get("id") or local).strip()
            if new_local != local:
                if not _ID.match(new_local):
                    raise AdminError(f"Định danh {_ID_RULE}.", [_problem(f"Định danh {_ID_RULE}.", where="id")])
                if self._taken(self._store, new_local):
                    message = f"Định danh «{new_local}» đã được dùng; hãy chọn định danh khác."
                    raise Conflict(message, [_problem(message, where="id")])
            store = self._copy()
            for quad in list(store.quads_for_pattern(_node(local), None, None, None)):
                store.remove(quad)
            self._put(store, new_local, spec, label, payload)
            if new_local != local:
                _rename_object(store, local, new_local)
            self._commit(store)
            return new_local

    def delete(self, local: str, version: str | None = None) -> None:
        with self._lock:
            self._check_version(version, self._content(local))
            store = self._copy()
            node = _node(local)
            for quad in list(store.quads_for_pattern(node, None, None, None)):
                store.remove(quad)
            self._drop_unused_addresses(store)
            references = self._references(store, node)
            if references:
                raise Conflict("Còn thực thể khác trỏ tới thực thể này; sửa hoặc xoá chúng trước.",
                               [f"{r['label']} · {r['property']}" for r in references])
            self._commit(store)

    @staticmethod
    def _check_version(version, content: dict) -> None:
        if version and version != _version(content):
            raise Conflict("Thực thể này vừa được sửa ở nơi khác (tab khác hoặc người khác) nên chưa lưu, để khỏi đè "
                           "lên thay đổi đó. Hãy mở lại thực thể để thấy bản mới rồi sửa tiếp.")

    def _copy(self) -> oxi.Store:
        store = oxi.Store()
        store.extend(self._store)
        return store

    def _put(self, store: oxi.Store, local: str, spec: ClassSpec, label: str, payload: dict) -> None:
        node = _node(local)
        errors: list[dict] = []
        store.add(oxi.Quad(node, RDF_TYPE, _node(spec.name), OUTSIDE))
        store.add(oxi.Quad(node, LABEL, oxi.Literal(label, language="vi"), OUTSIDE))
        alt_labels = payload.get("altLabels") or []
        for alt in alt_labels if isinstance(alt_labels, list) else []:
            if isinstance(alt, str) and alt.strip():
                if not spec.alt_labels:
                    errors.append(_problem(f"Lớp «{spec.label}» không có tên gọi khác.", where="altLabels"))
                    break
                store.add(oxi.Quad(node, ALT_LABEL, oxi.Literal(alt.strip(), language="vi"), OUTSIDE))

        statements = payload.get("statements") or []
        if not isinstance(statements, list):
            raise AdminError("Các quan hệ phải là một danh sách.")
        for number, statement in enumerate(statements):
            if not isinstance(statement, dict):
                errors.append(_problem(f"Quan hệ {number + 1}: không đọc được.", row=number))
                continue
            # ``row``: vị trí của dòng trên form, để lời báo lỗi chỉ đúng dòng người sửa đang thấy.
            row = statement["row"] if isinstance(statement.get("row"), int) else number
            field = spec.field(str(statement.get("property", "")))
            if field is None:
                errors.append(_problem(f"Quan hệ {row + 1}: thuộc tính này không thuộc lớp «{spec.label}».", row=row))
                continue
            where = f"Quan hệ {row + 1} ({field.name})"
            at = {"row": row, "property": field.property}
            value = _value(field, statement.get("value"), where, errors, at)
            source = str(statement.get("source") or "").strip()
            coordinate = _text(statement.get("coordinate"))
            if field.sourced is None and (source or coordinate):
                errors.append(_problem(f"{where}: thuộc tính này không gắn nguồn.", **at))
            elif field.sourced and not source:
                errors.append(_problem(f"{where}: phải chọn nguồn khẳng định quan hệ này.", **at))
            elif coordinate and not source:
                errors.append(_problem(f"{where}: đã ghi vị trí thì phải chọn nguồn, hoặc xoá vị trí.", **at))
            elif source and not coordinate:
                errors.append(_problem(f"{where}: ghi rõ vị trí trong nguồn, ví dụ «khoản 1 Điều 24».", **at))
            elif source and self.class_of(source, store) != SOURCE_CLASS:
                errors.append(_problem(f"{where}: «{source}» không phải một nguồn.", **at))
            elif value is not None:
                graph = self._address(store, source, coordinate) if source else OUTSIDE
                store.add(oxi.Quad(node, _node(field.property), value, graph))
        if errors:
            raise AdminError("Dữ liệu chưa hợp lệ.", errors)

    def _address(self, store: oxi.Store, source: str, coordinate: str) -> oxi.NamedNode:
        """Địa chỉ trích dẫn của (nguồn, vị trí): dùng lại nếu đã có, chưa có thì tạo."""

        for quad in store.quads_for_pattern(None, _node("thuocNguon"), _node(source), OUTSIDE):
            if any(q.object.value == coordinate for q in store.quads_for_pattern(quad.subject, _node("toaDo"), None, OUTSIDE)):
                return quad.subject
        base = "TD" + source + iri_name(coordinate)
        local, suffix = base, 2
        while _exists(store, _node(local)):
            local, suffix = f"{base}{suffix}", suffix + 1
        address = _node(local)
        store.add(oxi.Quad(address, RDF_TYPE, _node(ADDRESS_CLASS), OUTSIDE))
        store.add(oxi.Quad(address, _node("thuocNguon"), _node(source), OUTSIDE))
        store.add(oxi.Quad(address, _node("toaDo"), oxi.Literal(coordinate, language="vi"), OUTSIDE))
        return address

    @staticmethod
    def _drop_unused_addresses(store: oxi.Store) -> None:
        for quad in list(store.quads_for_pattern(None, RDF_TYPE, _node(ADDRESS_CLASS), OUTSIDE)):
            if next(iter(store.quads_for_pattern(None, None, None, quad.subject)), None) is None:
                for own in list(store.quads_for_pattern(quad.subject, None, None, None)):
                    store.remove(own)

    # --- sửa loại (lớp) và thuộc tính -------------------------------------------

    def class_version(self, name: str) -> str:
        spec = self.schema.all_classes[name]
        return _version({**asdict(spec), "choices": {c: self.label(c) for f in spec.fields for c in f.choices}})

    def save_class(self, old: str | None, payload: dict) -> str:
        """Tạo loại mới (``old`` là None) hoặc sửa loại ``old``: tên, định danh, và các ô của nó."""

        with self._lock:
            before = None
            if old is not None:
                before = self.schema.classes.get(old)
                if before is None:
                    raise NotFound(f"Không có lớp «{old}».")
                if payload.get("version") and payload["version"] != self.class_version(old):
                    raise Conflict("Lớp này vừa được sửa ở nơi khác nên chưa lưu. Hãy mở lại lớp rồi sửa tiếp.")
            name, label, fields, renames, choice_labels = self._read_class(old, before, payload)
            store, schema = self._copy(), self.schema

            for was, new, field_name in renames:  # định danh thuộc tính là chung cho mọi loại dùng nó
                schema = schema.renamed_property(was, new, field_name)
                _rename_predicate(store, was, new)
                _rename_subject(store, was, new)
            members = ([q.subject for q in store.quads_for_pattern(None, RDF_TYPE, _node(old), OUTSIDE)]
                       if before else [])
            kept = {field.property for field in fields} | {was for was, _, _ in renames}
            removed = [field for field in (before.fields if before else ()) if field.property not in kept]
            doomed = [(field.name, q) for field in removed for member in members
                      for q in store.quads_for_pattern(member, _node(field.property), None, None)]
            if before and before.alt_labels and not payload.get("altLabels"):
                doomed += [("tên gọi khác", q) for member in members
                           for q in store.quads_for_pattern(member, ALT_LABEL, None, OUTSIDE)]
            if doomed and not payload.get("confirm"):
                counts: dict[str, int] = {}
                for field_name, _ in doomed:
                    counts[field_name] = counts.get(field_name, 0) + 1
                raise Conflict(f"Lưu thay đổi này sẽ xoá {len(doomed)} quan hệ đang có của các thực thể thuộc lớp «{before.label}».",
                               [f"{field_name}: {count} quan hệ" for field_name, count in counts.items()], confirm=True)
            for _, quad in doomed:
                store.remove(quad)
            if before and name != old:
                _move(store, (None, RDF_TYPE, _node(old), None),
                      lambda q: oxi.Quad(q.subject, RDF_TYPE, _node(name), q.graph_name))
                _rename_subject(store, old, name)

            spec = ClassSpec(name, label, bool(payload.get("altLabels")),
                             tuple(sorted(fields, key=lambda field: (not field.required, field.name))))
            schema = schema.with_class(spec, replacing=old)
            for field in fields:  # tên hiển thị của thuộc tính cũng chung cho mọi loại
                schema = schema.renamed_property(field.property, field.property, field.name)
                _set_label(store, field.property, field.name)
            _set_label(store, name, label)
            for choice, choice_label in choice_labels.items():
                _set_label(store, choice, choice_label)
            dropped = {old} if old and old != name else set()
            dropped |= {field.property for field in removed}
            dropped |= {c for field in (before.fields if before else ()) for c in field.choices}
            self._drop_unused_vocabulary(store, schema, dropped)
            self._commit(store, schema)
            return name

    def delete_class(self, name: str, version: str | None = None) -> None:
        with self._lock:
            spec = self.schema.classes.get(name)
            if spec is None:
                raise NotFound(f"Không có lớp «{name}».")
            if version and version != self.class_version(name):
                raise Conflict("Lớp này vừa được sửa ở nơi khác nên chưa xoá. Hãy mở lại lớp.")
            if name in CODE_NAMES:
                raise Conflict(f"Lớp «{spec.label}» được mã nguồn của chatbot dùng trực tiếp nên không xoá được.")
            members = self.counts().get(name, 0)
            if members:
                raise Conflict(f"Còn {members} thực thể thuộc lớp «{spec.label}»; xoá chúng hoặc chuyển sang lớp khác trước.")
            targeting = self.schema.targeting(name)
            if targeting:
                raise Conflict("Còn thuộc tính ở lớp khác trỏ tới lớp này; sửa các thuộc tính đó trước.",
                               [f"{self.schema.all_classes[owner].label} · {field.name}" for owner, field in targeting])
            store, schema = self._copy(), self.schema.without_class(name)
            self._drop_unused_vocabulary(store, schema, {name} | {f.property for f in spec.fields}
                                         | {c for f in spec.fields for c in f.choices})
            self._commit(store, schema)

    def _read_class(self, old: str | None, before: ClassSpec | None, payload: dict):
        """Đọc và kiểm nội dung form sửa loại; mọi lỗi báo cùng lúc, kèm ô bị sai."""

        errors: list[dict] = []
        name = str(payload.get("name") or "").strip()
        label = _text(payload.get("label"))
        if not label:
            errors.append(_problem("Lớp phải có tên.", where="label"))
        if not _CLASS_ID.match(name):
            errors.append(_problem(f"Định danh lớp {_ID_RULE}, và chữ đầu viết hoa, ví dụ «QuyDinhMoi».", where="name"))
        elif name != old:
            if old in CODE_NAMES:
                errors.append(_problem("Lớp này được mã nguồn dùng trực tiếp nên không đổi định danh được.", where="name"))
            elif self._taken(self._store, name):
                errors.append(_problem(f"Định danh «{name}» đã được dùng.", where="name"))
        existing = {field.property: field for spec in self.schema.all_classes.values() for field in spec.fields}
        known_choices = {c for field in existing.values() for c in field.choices}
        raw_fields = payload.get("fields") or []
        if not isinstance(raw_fields, list):
            raise AdminError("Các thuộc tính phải là một danh sách.")
        fields, renames, choice_labels, seen = [], [], {}, set()
        for index, raw in enumerate(raw_fields):
            raw = raw if isinstance(raw, dict) else {}
            at = {"field": index}
            prop = str(raw.get("property") or "").strip()
            was = str(raw.get("was") or "").strip() or None
            field_name = _text(raw.get("name"))
            kind = raw.get("kind")
            target = str(raw.get("target") or "").strip() or None
            sourced = raw.get("sourced")
            count = len(errors)
            if not _PROPERTY_ID.match(prop):
                errors.append(_problem(f"Thuộc tính {index + 1}: định danh thuộc tính {_ID_RULE}, và chữ đầu viết thường, "
                                       "ví dụ «thoiHanNop».", key="property", **at))
            elif prop in seen:
                errors.append(_problem(f"Thuộc tính {index + 1}: «{prop}» trùng với một thuộc tính khác của lớp này.",
                                       key="property", **at))
            elif was and before is not None and before.field(was) is None:
                errors.append(_problem(f"Thuộc tính {index + 1}: lớp này không có thuộc tính «{was}».", key="property", **at))
            elif was and was != prop:
                if was in CODE_NAMES:
                    errors.append(_problem(f"Thuộc tính {index + 1}: thuộc tính «{was}» được mã nguồn dùng trực tiếp nên không "
                                           "đổi định danh được.", key="property", **at))
                elif self._taken(self._store, prop):
                    errors.append(_problem(f"Thuộc tính {index + 1}: định danh «{prop}» đã được dùng; không gộp hai thuộc tính.",
                                           key="property", **at))
            elif prop not in existing and self._taken(self._store, prop):
                errors.append(_problem(f"Thuộc tính {index + 1}: định danh «{prop}» đã được dùng cho thứ khác.",
                                       key="property", **at))
            seen.add(prop)
            if not field_name:
                errors.append(_problem(f"Thuộc tính {index + 1}: chưa có tên hiển thị.", key="name", **at))
            if kind not in KINDS:
                errors.append(_problem(f"Thuộc tính {index + 1}: chọn kiểu giá trị.", key="kind", **at))
            if kind == "link" and target not in self.schema.classes and target != name:
                errors.append(_problem(f"Thuộc tính {index + 1}: chọn lớp mà thuộc tính này trỏ tới.", key="target", **at))
            choices = []
            if kind == "choice":
                raw_choices = raw.get("choices") if isinstance(raw.get("choices"), list) else []
                for choice in raw_choices:
                    choice = choice if isinstance(choice, dict) else {}
                    choice_id, choice_label = str(choice.get("id") or "").strip(), _text(choice.get("label"))
                    if not choice_id and not choice_label:
                        continue
                    if not _ID.match(choice_id):
                        errors.append(_problem(f"Thuộc tính {index + 1}: giá trị «{choice_label or choice_id}»: định danh "
                                               f"{_ID_RULE}.", key="choices", **at))
                    elif not choice_label:
                        errors.append(_problem(f"Thuộc tính {index + 1}: giá trị «{choice_id}» chưa có tên.", key="choices", **at))
                    elif choice_id in choices:
                        errors.append(_problem(f"Thuộc tính {index + 1}: giá trị «{choice_id}» bị lặp.", key="choices", **at))
                    elif choice_id not in known_choices and self._taken(self._store, choice_id):
                        errors.append(_problem(f"Thuộc tính {index + 1}: định danh «{choice_id}» đã được dùng cho thứ khác.",
                                               key="choices", **at))
                    else:
                        choices.append(choice_id)
                        choice_labels[choice_id] = choice_label
                if not choices:
                    errors.append(_problem(f"Thuộc tính {index + 1}: cần ít nhất một giá trị để chọn.", key="choices", **at))
            if sourced not in (True, False, None):
                errors.append(_problem(f"Thuộc tính {index + 1}: chọn luật gắn nguồn.", key="sourced", **at))
            if len(errors) > count:
                continue
            fields.append(Field(prop, field_name, kind, bool(raw.get("required")), bool(raw.get("single")),
                                target if kind == "link" else None, tuple(choices), sourced))
            if was and was != prop:
                renames.append((was, prop, field_name))
        if before is not None:
            kept = {field.property for field in fields} | {was for was, _, _ in renames}
            for field in before.fields:
                if field.property not in kept and field.property in CODE_NAMES:
                    errors.append(_problem(f"Thuộc tính «{field.name}» được mã nguồn dùng trực tiếp nên không bỏ được.",
                                           where="fields"))
        if errors:
            raise AdminError("Lớp chưa hợp lệ.", errors)
        return name, label, fields, renames, choice_labels

    def _drop_unused_vocabulary(self, store: oxi.Store, schema: Schema, candidates: set[str]) -> None:
        """Bỏ nhãn của loại, thuộc tính, giá trị chọn không còn ai dùng."""

        names = _schema_names(schema)
        for local in candidates - names:
            node = _node(local)
            used = (_any(store.quads_for_pattern(None, node, None, None))
                    or _any(store.quads_for_pattern(None, None, node, None))
                    or any(q.predicate != LABEL for q in store.quads_for_pattern(node, None, None, None)))
            if not used:
                for quad in list(store.quads_for_pattern(node, LABEL, None, OUTSIDE)):
                    store.remove(quad)

    # --- ghi ------------------------------------------------------------------

    def _commit(self, store: oxi.Store, schema: Schema | None = None) -> None:
        self._drop_unused_addresses(store)
        shapes = self._shapes_graph(schema)
        errors = self._violations(store, schema or self.schema, shapes)
        if errors:
            if len(errors) > MAX_LISTED:
                errors = errors[:MAX_LISTED] + [_problem(f"… và {len(errors) - MAX_LISTED} lỗi khác.")]
            raise AdminError("Dữ liệu không khớp lược đồ." if schema is None
                             else "Dữ liệu đang có không khớp lược đồ mới nên chưa lưu.", errors)
        files = {self.path: serialize(store)}
        if schema is not None:
            files[self.shapes_path] = schema.to_turtle()
        if self.persist is not None:
            self.persist(files)
        for path, data in files.items():
            write_bytes(data, path)
        self._store = store
        if schema is not None:
            self.schema, self._shapes = schema, shapes
        if self.on_change is not None:
            self.on_change(self.path)

    def _shapes_graph(self, schema: Schema | None):
        from rdflib import Graph

        if schema is not None:
            return Graph().parse(data=schema.to_turtle().decode("utf-8"), format="turtle")
        if self._shapes is None:
            self._shapes = Graph().parse(self.shapes_path, format="turtle")
        return self._shapes

    def _violations(self, store: oxi.Store, schema: Schema, shapes) -> list[dict]:
        """Kiểm toàn bộ đồ thị bằng SHACL và viết mỗi vi phạm thành một câu người sửa đọc được."""

        import pyshacl
        from rdflib import RDF, Graph, Namespace

        data = Graph().parse(data="".join(f"{q.subject} {q.predicate} {q.object} .\n" for q in store), format="nt")
        conforms, results, _ = pyshacl.validate(data, shacl_graph=shapes, inference="none")
        if conforms:
            return []
        sh = Namespace(SH)
        found = {}
        for result in results.subjects(RDF.type, sh.ValidationResult):
            subject = local_id(str(results.value(result, sh.focusNode)))
            raw_path = str(results.value(result, sh.resultPath) or "")
            path = local_id(raw_path)
            value = results.value(result, sh.value)
            component = str(results.value(result, sh.sourceConstraintComponent)).rsplit("#", 1)[-1]
            spec = schema.classes.get(self.class_of(subject, store, schema) or "")
            field = spec.field(path) if spec else None
            message = _VIOLATIONS.get(component, str(results.value(result, sh.resultMessage)))
            if component == "ClassConstraintComponent" and field and field.target in schema.classes:
                message = f"phải trỏ tới một thực thể thuộc lớp «{schema.classes[field.target].label}»"
            where = field.name if field else ("tên" if raw_path in (LABEL.value, "") else path)
            text = f"{self.label(subject, store)} · {where}: {message}"
            found[text] = _problem(text, entity=subject, property="label" if raw_path == LABEL.value else path,
                                   value=local_id(str(value)) if value is not None else None)
        return [found[text] for text in sorted(found)]
