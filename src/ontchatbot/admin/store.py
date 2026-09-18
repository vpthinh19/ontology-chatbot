"""Thêm, sửa, xoá mục của ontology theo lược đồ.

Mỗi lần ghi đi bốn bước: dựng bản mới trong bộ nhớ, kiểm bản đó bằng lược đồ SHACL, ghi
tệp TriG theo thứ tự cố định, rồi báo để engine tìm kiếm nạp lại. Khi chạy trên Cloud Run,
bản mới được ghi lên Cloud Storage ngay trước khi ghi tệp. Bước nào hỏng thì tệp trên đĩa
giữ nguyên.

"Sửa" là sửa thật: mục được thay bằng đúng những gì người sửa gửi lên, kể cả nguồn của
từng câu. Địa chỉ trích dẫn được tạo khi người sửa chọn nguồn và ghi vị trí; địa chỉ không
còn câu nào dùng thì bị dọn.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterable
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pyoxigraph as oxi

from ..settings import ONTOLOGY_NS
from .schema import RDFS_LABEL, SKOS_ALT_LABEL, XSD, Field, Schema
from .trig import iri_name, load, serialize, write_bytes

RDF_TYPE = oxi.NamedNode("http://www.w3.org/1999/02/22-rdf-syntax-ns#type")
LABEL = oxi.NamedNode(RDFS_LABEL)
ALT_LABEL = oxi.NamedNode(SKOS_ALT_LABEL)
OUTSIDE = oxi.DefaultGraph()
IDENTITY = (RDF_TYPE, LABEL, ALT_LABEL)
SOURCE_CLASS = "Nguon"
ADDRESS_CLASS = "DiaChiTrichDan"
#: Lời giải thích cho từng loại vi phạm SHACL mà lược đồ dùng.
_VIOLATIONS = {
    "MinCountConstraintComponent": "thiếu giá trị bắt buộc",
    "MaxCountConstraintComponent": "chỉ được có một giá trị",
    "DatatypeConstraintComponent": "sai kiểu dữ liệu",
    "LanguageInConstraintComponent": "chữ phải gắn nhãn tiếng Việt",
    "ClassConstraintComponent": "phải trỏ tới một mục đúng loại",
    "InConstraintComponent": "giá trị không nằm trong danh sách cho phép",
    "ClosedConstraintComponent": "ô này không thuộc loại thông tin của mục",
}
_KIND_NAMES = {"integer": "số nguyên", "decimal": "số", "date": "ngày (YYYY-MM-DD)"}


class AdminError(Exception):
    """Yêu cầu không thực hiện được; ``errors`` liệt kê từng lý do cho người sửa."""

    status = 400

    def __init__(self, message: str, errors: Iterable[str] = ()) -> None:
        super().__init__(message)
        self.errors = list(errors)


class NotFound(AdminError):
    status = 404


class Conflict(AdminError):
    status = 409


class Unavailable(AdminError):
    status = 503


def _node(local: str) -> oxi.NamedNode:
    return oxi.NamedNode(ONTOLOGY_NS + local)


def _local(value: str) -> str:
    return value[len(ONTOLOGY_NS):] if value.startswith(ONTOLOGY_NS) else value


def _exists(store: oxi.Store, node: oxi.NamedNode) -> bool:
    return next(iter(store.quads_for_pattern(node, None, None, None)), None) is not None


def _label(payload: dict) -> str:
    label = payload.get("label")
    if not isinstance(label, str) or not label.strip():
        raise AdminError("Mục phải có tên.")
    return label.strip()


def _value(field: Field, raw, where: str, errors: list[str]):
    text = raw if isinstance(raw, str) else ("" if raw is None else str(raw))
    if not text.strip():
        errors.append(f"{where}: chưa có giá trị.")
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
            return oxi.Literal(text.strip(), datatype=oxi.NamedNode(XSD + "anyURI"))
    except (ValueError, InvalidOperation):
        errors.append(f"{where}: «{text.strip()}» không phải {_KIND_NAMES[field.kind]}.")
        return None
    return oxi.Literal(text)


class AdminStore:
    def __init__(
        self,
        path: Path | str,
        schema: Schema,
        *,
        shapes_path: Path | str | None = None,
        on_change: Callable[[Path], None] | None = None,
        persist: Callable[[bytes], None] | None = None,
    ) -> None:
        """``persist`` nhận đúng nội dung sắp ghi, trước khi tệp trên đĩa đổi: bản triển khai dùng nó để
        ghi lên kho bền (Cloud Storage). Nó báo lỗi thì lần sửa bị huỷ, tệp và bộ nhớ giữ nguyên."""

        self.path = Path(path)
        self.schema = schema
        self.shapes_path = Path(shapes_path) if shapes_path else self.path.with_name("shapes.ttl")
        self.on_change = on_change
        self.persist = persist
        self._store = load(self.path)
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
            self._store = load(self.path)
            return True

    # --- đọc ------------------------------------------------------------------

    def label(self, local: str, store: oxi.Store | None = None) -> str:
        for quad in (store or self._store).quads_for_pattern(_node(local), LABEL, None, OUTSIDE):
            return quad.object.value
        return local

    def class_of(self, local: str, store: oxi.Store | None = None) -> str | None:
        for quad in (store or self._store).quads_for_pattern(_node(local), RDF_TYPE, None, OUTSIDE):
            name = _local(quad.object.value)
            if name in self.schema.classes or name == ADDRESS_CLASS:
                return name
        return None

    def counts(self) -> dict[str, int]:
        return {name: sum(1 for _ in self._store.quads_for_pattern(None, RDF_TYPE, _node(name), OUTSIDE))
                for name in self.schema.classes}

    def list(self, class_name: str) -> list[dict[str, str]]:
        if class_name not in self.schema.classes:
            raise NotFound(f"Không có loại thông tin «{class_name}».")
        items = [{"id": _local(quad.subject.value), "label": self.label(_local(quad.subject.value))}
                 for quad in self._store.quads_for_pattern(None, RDF_TYPE, _node(class_name), OUTSIDE)]
        return sorted(items, key=lambda item: item["label"].casefold())

    def get(self, local: str) -> dict:
        class_name = self.class_of(local)
        if class_name is None or class_name == ADDRESS_CLASS:
            raise NotFound(f"Không có mục «{local}».")
        node = _node(local)
        statements = []
        for quad in self._store.quads_for_pattern(node, None, None, None):
            if quad.predicate in IDENTITY:
                continue
            source, coordinate = self._address_parts(self._store, quad.graph_name)
            statements.append({
                "property": _local(quad.predicate.value),
                "value": _local(quad.object.value) if isinstance(quad.object, oxi.NamedNode) else quad.object.value,
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
            "references": self._references(self._store, node),
        }

    def _address_parts(self, store: oxi.Store, graph) -> tuple[str | None, str | None]:
        if isinstance(graph, oxi.DefaultGraph):
            return None, None
        source = coordinate = None
        for quad in store.quads_for_pattern(graph, None, None, OUTSIDE):
            name = _local(quad.predicate.value)
            if name == "thuocNguon":
                source = _local(quad.object.value)
            elif name == "toaDo":
                coordinate = quad.object.value
        return source, coordinate

    def _references(self, store: oxi.Store, node: oxi.NamedNode) -> list[dict]:
        """Những gì đang trỏ tới mục: câu của mục khác, hoặc địa chỉ trích dẫn còn được dùng."""

        found = {}
        for quad in store.quads_for_pattern(None, None, node, None):
            if quad.predicate == RDF_TYPE:
                continue
            subject = _local(quad.subject.value)
            if self.class_of(subject, store) == ADDRESS_CLASS:
                if next(iter(store.quads_for_pattern(None, None, None, quad.subject)), None) is None:
                    continue
                reference = {"id": None, "label": self._address_parts(store, quad.subject)[1] or subject,
                             "property": "trích dẫn"}
            else:
                spec = self.schema.classes.get(self.class_of(subject, store) or "")
                field = spec.field(_local(quad.predicate.value)) if spec else None
                reference = {"id": subject, "label": self.label(subject, store),
                             "property": field.name if field else _local(quad.predicate.value)}
            found[(reference["id"], reference["label"], reference["property"])] = reference
        return sorted(found.values(), key=lambda r: (r["property"], r["label"].casefold()))

    # --- ghi ------------------------------------------------------------------

    def create(self, payload: dict) -> str:
        with self._lock:
            spec = self.schema.classes.get(payload.get("class"))
            if spec is None:
                raise AdminError("Chọn loại thông tin của mục mới.")
            label = _label(payload)
            local = iri_name(label)
            if not local:
                raise AdminError("Tên phải có ít nhất một chữ cái hoặc chữ số.")
            if _exists(self._store, _node(local)):
                raise Conflict(f"Định danh «{local}» sinh từ tên này đã được dùng; hãy đặt tên khác.")
            store = self._copy()
            self._put(store, local, spec, label, payload)
            self._commit(store)
            return local

    def update(self, local: str, payload: dict) -> None:
        with self._lock:
            class_name = self.class_of(local)
            if class_name is None or class_name == ADDRESS_CLASS:
                raise NotFound(f"Không có mục «{local}».")
            label = _label(payload)
            store = self._copy()
            for quad in list(store.quads_for_pattern(_node(local), None, None, None)):
                store.remove(quad)
            self._put(store, local, self.schema.classes[class_name], label, payload)
            self._commit(store)

    def delete(self, local: str) -> None:
        with self._lock:
            class_name = self.class_of(local)
            if class_name is None or class_name == ADDRESS_CLASS:
                raise NotFound(f"Không có mục «{local}».")
            store = self._copy()
            node = _node(local)
            for quad in list(store.quads_for_pattern(node, None, None, None)):
                store.remove(quad)
            self._drop_unused_addresses(store)
            references = self._references(store, node)
            if references:
                raise Conflict("Còn mục khác trỏ tới mục này; sửa hoặc xoá chúng trước.",
                               [f"{r['label']} · {r['property']}" for r in references])
            self._commit(store)

    def _copy(self) -> oxi.Store:
        store = oxi.Store()
        store.extend(self._store)
        return store

    def _put(self, store: oxi.Store, local: str, spec, label: str, payload: dict) -> None:
        node = _node(local)
        errors: list[str] = []
        store.add(oxi.Quad(node, RDF_TYPE, _node(spec.name), OUTSIDE))
        store.add(oxi.Quad(node, LABEL, oxi.Literal(label, language="vi"), OUTSIDE))
        alt_labels = payload.get("altLabels") or []
        for alt in alt_labels if isinstance(alt_labels, list) else []:
            if isinstance(alt, str) and alt.strip():
                if not spec.alt_labels:
                    errors.append(f"{spec.label} không có ô tên gọi khác.")
                    break
                store.add(oxi.Quad(node, ALT_LABEL, oxi.Literal(alt.strip(), language="vi"), OUTSIDE))

        statements = payload.get("statements") or []
        if not isinstance(statements, list):
            raise AdminError("Các câu phải là một danh sách.")
        for number, statement in enumerate(statements, start=1):
            field = spec.field(str(statement.get("property", ""))) if isinstance(statement, dict) else None
            if field is None:
                errors.append(f"Dòng {number}: ô này không thuộc loại {spec.label}.")
                continue
            where = f"Dòng {number} ({field.name})"
            value = _value(field, statement.get("value"), where, errors)
            source = str(statement.get("source") or "").strip()
            coordinate = str(statement.get("coordinate") or "").strip()
            if field.sourced is None and (source or coordinate):
                errors.append(f"{where}: ô này không gắn nguồn.")
            elif field.sourced and not source:
                errors.append(f"{where}: phải chọn nguồn khẳng định câu này.")
            elif source and not coordinate:
                errors.append(f"{where}: ghi rõ vị trí trong nguồn, ví dụ «khoản 1 Điều 24».")
            elif source and self.class_of(source, store) != SOURCE_CLASS:
                errors.append(f"{where}: «{source}» không phải một nguồn.")
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

    def _commit(self, store: oxi.Store) -> None:
        self._drop_unused_addresses(store)
        errors = self._violations(store)
        if errors:
            raise AdminError("Dữ liệu không khớp lược đồ.", errors)
        data = serialize(store)
        if self.persist is not None:
            self.persist(data)
        write_bytes(data, self.path)
        self._store = store
        if self.on_change is not None:
            self.on_change(self.path)

    def _violations(self, store: oxi.Store) -> list[str]:
        """Kiểm toàn bộ đồ thị bằng SHACL và viết mỗi vi phạm thành một câu người sửa đọc được."""

        import pyshacl
        from rdflib import RDF, Graph, Namespace

        if self._shapes is None:
            self._shapes = Graph().parse(self.shapes_path, format="turtle")
        data = Graph().parse(data="".join(f"{q.subject} {q.predicate} {q.object} .\n" for q in store), format="nt")
        conforms, results, _ = pyshacl.validate(data, shacl_graph=self._shapes, inference="none")
        if conforms:
            return []
        sh = Namespace("http://www.w3.org/ns/shacl#")
        found = set()
        for result in results.subjects(RDF.type, sh.ValidationResult):
            subject = _local(str(results.value(result, sh.focusNode)))
            path = _local(str(results.value(result, sh.resultPath) or ""))
            component = str(results.value(result, sh.sourceConstraintComponent)).rsplit("#", 1)[-1]
            spec = self.schema.classes.get(self.class_of(subject, store) or "")
            field = spec.field(path) if spec else None
            message = _VIOLATIONS.get(component, str(results.value(result, sh.resultMessage)))
            if component == "ClassConstraintComponent" and field and field.target in self.schema.classes:
                message = f"phải trỏ tới một mục loại «{self.schema.classes[field.target].label}»"
            found.add(f"{self.label(subject, store)} · {field.name if field else path or 'tên'}: {message}")
        return sorted(found)
