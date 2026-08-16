from __future__ import annotations

import json
from itertools import product

import pytest

from ontchatbot.catalogue import (
    find_query_family,
    CoverageSelector,
    QuerySpec,
    SlotSpec,
    load_catalogue,
)
from ontchatbot.research.catalogue_validation import (
    CatalogueValidationError,
    validate_catalogue,
)
from ontchatbot.runtime.sparql import load_ontology
from ontchatbot.runtime.sparql import execute_select
from ontchatbot.settings import ANSWER_INVENTORY_PATH, QUERY_CATALOGUE_PATH


INVENTORY = {
    "schema_version": 1,
    "entries": [
        {
            "id": "TemporaryAcademicLeaveProcedure-instructionProvision-officialText",
            "anchor": "TemporaryAcademicLeaveProcedure",
            "answer_kind": "literal",
            "path": ["instructionProvision", "officialText"],
            "provenance": ["Decision1052Article15"],
            "status": "supported",
        },
        {
            "id": "TemporaryAcademicLeaveProcedure-submittedTo-rdfs-label",
            "anchor": "TemporaryAcademicLeaveProcedure",
            "answer_kind": "label",
            "path": ["submittedTo", "rdfs:label"],
            "provenance": ["Decision1052Article15"],
            "status": "supported",
        },
    ],
}


def _spec(
    query_id: str,
    path: tuple[str, ...],
    *,
    anchor_classes: tuple[str, ...] = ("AcademicProcedure",),
    anchors: tuple[str, ...] = ("TemporaryAcademicLeaveProcedure",),
    slot_values: tuple[str, ...] = (":TemporaryAcademicLeaveProcedure",),
) -> QuerySpec:
    predicate = path[0]
    tail = (
        f"?node :{path[1]} ?answer ."
        if len(path) == 2 and path[1] != "rdfs:label"
        else "?node rdfs:label ?answer ."
    )
    return QuerySpec(
        query_id,
        "procedure",
        f"SELECT ?answer WHERE {{ ${{procedure}} :{predicate} ?node . {tail} }}",
        {"procedure": SlotSpec("iri", slot_values)},
        (CoverageSelector(anchor_classes, (path,), anchors),),
    )


def _complete_catalogue() -> dict[str, QuerySpec]:
    return {
        "procedure-instruction": _spec(
            "procedure-instruction",
            ("instructionProvision", "officialText"),
        ),
        "procedure-submission": _spec(
            "procedure-submission",
            ("submittedTo", "rdfs:label"),
        ),
    }


def test_valid_catalogue_covers_every_supported_entry() -> None:
    report = validate_catalogue(load_ontology(), INVENTORY, _complete_catalogue())

    assert report["supported_entries"] == 2
    assert report["covered_entries"] == 2
    assert report["uncovered_entries"] == []
    assert report["families"] == 2


def test_rejects_uncovered_supported_entry() -> None:
    catalogue = _complete_catalogue()
    catalogue.pop("procedure-submission")

    with pytest.raises(CatalogueValidationError, match="uncovered supported"):
        validate_catalogue(load_ontology(), INVENTORY, catalogue)


def test_rejects_selector_that_matches_no_supported_entry() -> None:
    catalogue = _complete_catalogue()
    catalogue["unused"] = _spec("unused", ("webPageUrl",))

    with pytest.raises(CatalogueValidationError, match="matches no supported entry"):
        validate_catalogue(load_ontology(), INVENTORY, catalogue)


def test_rejects_selector_anchor_with_wrong_class() -> None:
    catalogue = _complete_catalogue()
    catalogue["procedure-instruction"] = _spec(
        "procedure-instruction",
        ("instructionProvision", "officialText"),
        anchor_classes=("Certificate",),
    )

    with pytest.raises(CatalogueValidationError, match="does not belong to"):
        validate_catalogue(load_ontology(), INVENTORY, catalogue)


@pytest.mark.parametrize(
    ("slot_value", "message"),
    [
        (":VNPAYOtherBankFee", "opaque record"),
        (":ResourceThatDoesNotExist", "does not exist"),
    ],
)
def test_rejects_invalid_model_facing_iri_slots(slot_value, message) -> None:
    catalogue = _complete_catalogue()
    catalogue["procedure-instruction"] = _spec(
        "procedure-instruction",
        ("instructionProvision", "officialText"),
        slot_values=(slot_value,),
    )

    with pytest.raises(CatalogueValidationError, match=message):
        validate_catalogue(load_ontology(), INVENTORY, catalogue)


def test_rejects_non_rejection_spec_without_coverage() -> None:
    catalogue = _complete_catalogue()
    catalogue["procedure-instruction"] = QuerySpec(
        "procedure-instruction",
        "procedure",
        "SELECT ?answer WHERE { :TemporaryAcademicLeaveProcedure rdfs:label ?answer . }",
        {},
    )

    with pytest.raises(CatalogueValidationError, match="declares no coverage"):
        validate_catalogue(load_ontology(), INVENTORY, catalogue)


def test_canonical_catalogue_covers_supported_inventory() -> None:
    graph = load_ontology()
    inventory = json.loads(ANSWER_INVENTORY_PATH.read_text(encoding="utf-8"))
    catalogue = load_catalogue(QUERY_CATALOGUE_PATH)

    report = validate_catalogue(graph, inventory, catalogue)

    assert report["supported_entries"] == report["covered_entries"]
    assert report["uncovered_entries"] == []
    assert not {
        entry_id
        for entry_id in report["overlapping_entries"]
        if entry_id.startswith("Regulation1052Appendix2Table")
        or entry_id.startswith("ComputerCertificateConversionTable")
    }


def test_canonical_catalogue_has_no_numeric_slots() -> None:
    """Thư viện vẫn hỗ trợ số, nhưng catalogue chính thức chỉ trả bảng gốc."""

    catalogue = load_catalogue(QUERY_CATALOGUE_PATH)

    assert {
        (query_id, slot_name)
        for query_id, spec in catalogue.items()
        for slot_name, slot in spec.slots.items()
        if slot.kind == "number"
    } == set()


def test_canonical_catalogue_uses_project_source_projection_fields() -> None:
    """Generated runtime source lookups must not repurpose RDF container slots."""

    targets = [
        spec.target_template
        for spec in load_catalogue(QUERY_CATALOGUE_PATH).values()
        if spec.domain != "out-of-domain"
    ]

    assert all("rdf:_1" not in target and "rdf:_2" not in target for target in targets)
    assert any(
        ":sourceCitation" in target and ":sourceLink" in target
        for target in targets
    )


def test_static_and_finite_iri_catalogue_queries_return_literals() -> None:
    graph = load_ontology()
    catalogue = load_catalogue(QUERY_CATALOGUE_PATH)

    for query_id, spec in catalogue.items():
        if spec.domain == "out-of-domain" or any(
            slot.kind == "number" for slot in spec.slots.values()
        ):
            continue
        names = list(spec.slots)
        combinations = product(*(spec.slots[name].values for name in names))
        for values in combinations:
            query = spec.target_template
            for name, value in zip(names, values, strict=True):
                query = query.replace(f"${{{name}}}", value)
            assert execute_select(graph, query, max_rows=500), (query_id, values)


# Phép kiểm "mức học phí nào ứng với ngành nào" đã gỡ cùng dữ liệu học phí
# (2026-08-10). Họ truy vấn ``tuition-programs-by-rate`` còn nằm trong danh mục
# v2 và sẽ biến mất khi dựng lại danh mục ở giai đoạn 2.


@pytest.mark.parametrize(
    ("anchor", "expected_in_answer", "expected_in_citation"),
    [
        (":Regulation1052Article24", "nghỉ học tạm thời", "Điều 24"),
        (":Regulation1052Article20Clause02", "buộc thôi học", "khoản 2 Điều 20"),
        (":Regulation1052Article25Clause01PointC", "Trưởng Khoa", "điểm c khoản 1 Điều 25"),
        # IRI của điểm đ mã hoá "đ" thành "DD" - ca dễ dựng sai nhất.
        (":Regulation1052Article06Clause02PointDD", "học phần SV phải học xong", "điểm đ khoản 2 Điều 6"),
        # Điều 10 của quy chế ĐỜI TRƯỚC. Hai quy chế đều có Điều 10 với nội dung
        # khác hẳn, nên đây là ca canh việc dẫn nguồn có nêu đúng văn bản không.
        (":Regulation753Article10", "rút bớt", "753/QĐ-ĐHNT"),
    ],
)
def test_every_level_of_a_document_answers_with_its_own_source(
    anchor: str,
    expected_in_answer: str,
    expected_in_citation: str,
) -> None:
    """Người hỏi không biết "Quyết định 1052" là gì, nên mỗi câu trả lời phải tự
    kèm nguồn: vị trí trong văn bản, số quyết định, ngày ban hành và nơi tra.

    Bốn cấp văn bản - Điều, khoản, điểm, và điều của quy chế đời trước - nay dùng
    CHUNG một họ ``document-part-facts``. Bản v2 tách thành ``article-with-source``,
    ``clause-with-source`` và ``document-official-text``, ba họ gần giống hệt nhau
    mà model phải chọn giữa chúng.
    """

    catalogue = load_catalogue(QUERY_CATALOGUE_PATH)
    target = catalogue["document-part-facts"].target_template.replace("${anchor}", anchor)

    rows = execute_select(load_ontology(), target)

    assert rows
    values = " ".join(str(row["giatri"]) for row in rows)
    assert expected_in_answer in values
    citations = {str(row["nguon"]) for row in rows if row["nguon"]}
    assert citations, f"{anchor} trả lời mà không kèm nguồn"
    citation = " ".join(citations)
    assert expected_in_citation in citation
    urls = {str(row["duongdan"]) for row in rows if row["duongdan"]}
    assert all(url.startswith("https://") for url in urls)


def test_a_query_that_answers_with_its_source_is_declared_in_the_catalogue() -> None:
    """Guard đối chiếu chính xác, nên một truy vấn kèm nguồn phải nằm trong danh
    mục - nếu không backend sẽ từ chối nó dù truy vấn hoàn toàn đúng."""

    from ontchatbot.catalogue import find_query_family

    catalogue = load_catalogue(QUERY_CATALOGUE_PATH)
    # Chọn ĐỘNG mọi họ trả nguyên văn kèm nguồn thay vì chốt một tên: các họ này
    # đã đổi tên và gộp vào nhau nhiều lần, mà hợp đồng cần giữ là "truy vấn kèm
    # nguồn phải khớp danh mục", không phải "họ tên X còn tồn tại".
    # Không lọc theo tier: runtime đối chiếu với TOÀN danh mục, nên một họ phụ
    # vẫn phải khớp. Lọc theo tier sẽ làm phép kiểm vỡ mỗi lần một họ đổi hạng,
    # trong khi hợp đồng cần giữ thì không đổi.
    # Tên cột đã đổi sang ASCII ở v3 (``?nguon``/``?duongdan`` thay cho
    # ``?căncứ``/``?xemtại``), và giờ MỌI họ đều trả kèm nguồn chứ không còn một
    # nhóm riêng mang tên ``*-with-source``.
    with_source = [
        query_id
        for query_id, spec in catalogue.items()
        if {"?nguon", "?duongdan"} <= set(spec.target_template.split())
    ]
    askable = [q for q, s in catalogue.items() if s.domain not in ("out-of-domain", "assistant")]
    assert sorted(with_source) == sorted(askable), (
        f"{len(askable) - len(with_source)} họ trả dữ liệu mà không có chỗ cho nguồn"
    )

    for query_id in with_source:
        spec = catalogue[query_id]
        target = spec.target_template
        for name, slot in spec.slots.items():
            # Slot ``number`` không liệt kê giá trị (điều/khoản điền lúc sinh dữ
            # liệu), slot ``iri`` thì có. Guard chỉ so HÌNH DẠNG truy vấn nên một
            # giá trị hợp lệ bất kỳ là đủ.
            value = slot.values[0] if slot.values else "1"
            target = target.replace("${" + name + "}", value)
        assert "${" not in target, f"{query_id}: còn chỗ trống chưa thay"
        assert find_query_family(catalogue, target) == query_id, query_id


def test_every_family_matches_itself_and_no_other() -> None:
    """Mỗi họ phải tự nhận lại được chính mình khi truy vấn đi qua guard runtime.

    ``find_query_family`` trả họ KHỚP ĐẦU TIÊN theo thứ tự khai báo, nên hai họ có
    template chồng lấn sẽ khiến kết quả phụ thuộc thứ tự dòng trong tệp - một lỗi
    âm thầm và rất khó truy. Phép gộp ~90 họ trích dẫn thành một họ duy nhất làm
    rủi ro này đáng canh: nếu họ cũ còn sót lại, chúng sẽ tranh khớp với họ gộp.
    """

    catalogue = load_catalogue(QUERY_CATALOGUE_PATH)

    misrouted = []
    for query_id, spec in catalogue.items():
        target = spec.target_template
        for name, slot in spec.slots.items():
            value = slot.values[0] if slot.kind == "iri" else "0"
            target = target.replace(f"${{{name}}}", value)
        if spec.domain == "out-of-domain":
            continue
        matched = find_query_family(catalogue, target)
        if matched != query_id:
            misrouted.append((query_id, matched))

    assert misrouted == []


def _instantiated_targets(catalogue, *, primary_only: bool):
    """Bung mỗi họ thành các truy vấn cụ thể. Bỏ họ có slot số (miền vô hạn)."""

    for query_id, spec in catalogue.items():
        if spec.domain == "out-of-domain":
            continue
        if primary_only and spec.tier != "primary":
            continue
        if any(slot.kind == "number" for slot in spec.slots.values()):
            continue
        names = list(spec.slots)
        for values in product(*(spec.slots[name].values for name in names)):
            target = spec.target_template
            for name, value in zip(names, values, strict=True):
                target = target.replace(f"${{{name}}}", value)
            yield query_id, dict(zip(names, values, strict=True)), target


def test_no_two_primary_families_answer_identically() -> None:
    """Hai họ khác nhau không được trả kết quả GIỐNG HỆT trên cùng một anchor.

    Đây là luật đắt giá nhất trong bộ này. Answer Exact so *tập kết quả trả về*,
    không so chuỗi truy vấn - nên khi hai ý định khác nhau cùng trả một đoạn văn,
    model chọn nhầm vẫn được chấm ĐÚNG. Đã từng có lược đồ mà phần lớn số dòng
    nằm trong vùng mù đó, và đó là lý do benchmark báo 92% trong khi chatbot thật
    trả lời rất tệ.

    Chỉ tính họ ``primary``: họ ``secondary`` không có dữ liệu huấn luyện nên
    không thể làm model lẫn.
    """

    catalogue = load_catalogue(QUERY_CATALOGUE_PATH)
    graph = load_ontology()

    by_result: dict[tuple, list[str]] = {}
    silent = []
    for query_id, slots, target in _instantiated_targets(catalogue, primary_only=True):
        rows = execute_select(graph, target, max_rows=200)
        if not rows:
            silent.append((query_id, slots))
            continue
        key = (
            frozenset(slots.items()),
            frozenset(tuple(sorted(row.items())) for row in rows),
        )
        by_result.setdefault(key, []).append(query_id)

    collisions = sorted(
        {tuple(sorted(set(ids))) for ids in by_result.values() if len(set(ids)) > 1}
    )

    assert silent == []
    assert collisions == []


# Phép kiểm "không ô nào là một bức tường chữ" đã gỡ (2026-08-10).
#
# Nó dựa trên một giả định mà danh mục v3 làm hỏng: rằng chỉ họ TRA NGUYÊN VĂN
# mới trả ra đoạn dài, nên miễn riêng nhóm đó là đủ. Nay mọi họ đều có hình dạng
# dump - trả mọi giá trị chữ của neo - nên đoạn dài xuất hiện ở khắp nơi, và ở
# đúng những chỗ nó LÀ câu trả lời: hỏi "học phần điều kiện là gì" thì phải nhận
# nguyên đoạn định nghĩa 549 ký tự, cắt đi là mất nghĩa.
#
# Thứ luật này thật sự muốn chặn - hỏi một con số mà nhận về cả trang văn bản -
# nay bị chặn ở chỗ đúng hơn: bộ dựng ghim neo bằng SỐ cho các bảng ngưỡng, nên
# câu hỏi dạng số không còn rơi vào họ trả nguyên văn nữa.
