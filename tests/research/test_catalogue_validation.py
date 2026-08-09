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
        (":StandardEnglishCertificateTableRule03IELTS", "opaque record"),
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


@pytest.mark.parametrize(
    "amount",
    ["460000", "505000", "510000", "550000", "600000", "620000", "24500000"],
)
def test_tuition_programs_by_rate_returns_programs_for_every_declared_amount(amount: str) -> None:
    catalogue = load_catalogue(QUERY_CATALOGUE_PATH)
    spec = catalogue["tuition-programs-by-rate"]
    target = spec.target_template.replace("${amount}", amount)

    assert execute_select(load_ontology(), target), amount


@pytest.mark.parametrize(
    ("certificate", "score", "expected"),
    [
        (":TCFCertificate", "100", []),
        (":TCFCertificate", "200", [{"answer": "Bậc 1 - A1"}]),
        (":KLPTCertificate", "300", [{"answer": "Bậc 2 - A2"}]),
        (":KLPTCertificate", "400", [{"answer": "Bậc 4 - B2"}]),
        (":KLPTCertificate", "450", [{"answer": "Bậc 5 - C1"}]),
    ],
)
def test_language_certificate_level_respects_exclusive_minimums(
    certificate: str,
    score: str,
    expected: list[dict[str, str]],
) -> None:
    catalogue = load_catalogue(QUERY_CATALOGUE_PATH)
    target = catalogue["language-certificate-level"].target_template
    target = target.replace("${certificate}", certificate).replace("${score}", score)

    assert execute_select(load_ontology(), target) == expected


@pytest.mark.parametrize(
    ("credits", "expected"),
    [
        ("35", [{"answer": "Sinh viên năm thứ hai"}]),
        ("70", [{"answer": "Sinh viên năm thứ ba"}]),
        ("105", []),
        ("105.1", [{"answer": "Sinh viên năm thứ tư"}]),
    ],
)
def test_study_year_band_respects_inclusive_boundaries(
    credits: str,
    expected: list[dict[str, str]],
) -> None:
    catalogue = load_catalogue(QUERY_CATALOGUE_PATH)
    target = catalogue["study-year-band"].target_template.replace("${credits}", credits)

    assert execute_select(load_ontology(), target) == expected


def test_study_year_bands_remain_reachable_by_credit_count() -> None:
    """Bảng xếp hạng năm đào tạo bị họ ``*-details`` cũ bỏ lại phía sau.

    Họ đó dựng câu trả lời từ ``sourceDocument`` nên không còn chỗ trong lược đồ
    mới; điều cần giữ là bốn mốc tín chỉ vẫn tra được.
    """

    graph = load_ontology()
    rows = execute_select(
        graph,
        "SELECT ?answer WHERE { ?band a :StudyYearBand ; :resultLabel ?answer . }",
    )

    assert len(rows) == 4


@pytest.mark.parametrize(
    ("query_id", "slots", "expected_in_answer", "expected_in_citation"),
    [
        (
            "article-with-source",
            {"article": "24"},
            "nghỉ học tạm thời",
            "Điều 24",
        ),
        (
            "clause-with-source",
            {"article": "20", "clause": "2"},
            "buộc thôi học",
            "khoản 2 Điều 20",
        ),
        # ĐIỂM không còn họ riêng: ``point-with-source`` đã bỏ vì nó trả về ĐÚNG
        # cùng một thứ với ``document-official-text`` trên trọn 108 thực thể của
        # nó - hai đích đều hợp lệ cho một câu hỏi là ép model đoán bừa.
        (
            "document-official-text",
            {"anchor": ":Regulation1052Article25Clause01PointC"},
            "Trưởng Khoa",
            "điểm c khoản 1 Điều 25",
        ),
        # IRI của điểm đ mã hoá "đ" thành "DD" - ca dễ dựng sai nhất.
        (
            "document-official-text",
            {"anchor": ":Regulation1052Article06Clause02PointDD"},
            "học phần SV phải học xong",
            "điểm đ khoản 2 Điều 6",
        ),
    ],
)
def test_every_level_of_a_document_answers_with_its_own_source(
    query_id: str,
    slots: dict[str, str],
    expected_in_answer: str,
    expected_in_citation: str,
) -> None:
    """Người hỏi không biết "Quyết định 1052" là gì, nên mỗi câu trả lời phải tự
    kèm nguồn: vị trí trong văn bản, số quyết định, ngày ban hành và nơi tra."""

    catalogue = load_catalogue(QUERY_CATALOGUE_PATH)
    target = catalogue[query_id].target_template
    for name, value in slots.items():
        target = target.replace("${" + name + "}", value)

    rows = execute_select(load_ontology(), target)

    assert len(rows) == 1
    assert expected_in_answer in str(rows[0]["nộidung"])
    citation = str(rows[0]["căncứ"])
    assert expected_in_citation in citation
    assert "1052/QĐ-ĐHNT ngày 17/7/2025" in citation
    assert str(rows[0]["xemtại"]).startswith("https://")


def test_a_query_that_answers_with_its_source_is_declared_in_the_catalogue() -> None:
    """Guard đối chiếu chính xác, nên một truy vấn kèm nguồn phải nằm trong danh
    mục - nếu không backend sẽ từ chối nó dù truy vấn hoàn toàn đúng."""

    from ontchatbot.catalogue import find_query_family

    catalogue = load_catalogue(QUERY_CATALOGUE_PATH)
    # Chọn ĐỘNG mọi họ trả nguyên văn kèm nguồn thay vì chốt một tên: các họ này
    # đã đổi tên và gộp vào nhau nhiều lần, mà hợp đồng cần giữ là "truy vấn kèm
    # nguồn phải khớp danh mục", không phải "họ tên X còn tồn tại".
    with_source = [
        query_id
        for query_id, spec in catalogue.items()
        if spec.tier == "primary"
        and {"?nộidung", "?căncứ", "?xemtại"} <= set(spec.target_template.split())
    ]
    # Ba cấp: hỏi theo TÊN (văn bản, phụ lục, điểm) và hỏi theo SỐ (điều, khoản).
    assert len(with_source) >= 3, f"chỉ còn {len(with_source)} họ trả kèm nguồn"

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
    checked = 0
    for query_id, slots, target in _instantiated_targets(catalogue, primary_only=True):
        rows = execute_select(graph, target, max_rows=200)
        if not rows:
            continue
        checked += 1
        key = (
            frozenset(slots.items()),
            frozenset(tuple(sorted(row.items())) for row in rows),
        )
        by_result.setdefault(key, []).append(query_id)

    collisions = sorted(
        {tuple(sorted(set(ids))) for ids in by_result.values() if len(set(ids)) > 1}
    )

    assert collisions == []
    assert checked >= 1000, f"chỉ kiểm được {checked} truy vấn, danh mục có vấn đề?"


def test_no_answer_cell_is_a_wall_of_text() -> None:
    """Một ô trong câu trả lời không được là cả một khối văn bản.

    Truy vấn trả về hàng chục nghìn ký tự là câu trả lời không ai đọc được.
    Answer Exact chấm khối đó là hoàn hảo miễn nó khớp reference, nên độ dài phải
    được canh riêng.

    Đo theo TỪNG Ô chứ không theo tổng: một danh sách 19 biểu mẫu dài là chính
    đáng, một ô chứa nguyên cả điều luật thì không. Họ tra nguyên văn được miễn -
    người dùng hỏi đúng nguyên văn Điều 24 thì phải nhận nguyên văn Điều 24.

    Ngưỡng 500 có biên rộng: ô dài nhất hiện tại của nhóm không được miễn là 343.
    """

    catalogue = load_catalogue(QUERY_CATALOGUE_PATH)
    graph = load_ontology()

    verbatim = {
        query_id
        for query_id, spec in catalogue.items()
        if any(tuple(path) == ("officialText",) for sel in spec.coverage for path in sel.paths)
    }

    checked = 0
    oversized = []
    exercised: set[str] = set()
    for query_id, slots, target in _instantiated_targets(catalogue, primary_only=True):
        if query_id in verbatim:
            continue
        for row in execute_select(graph, target, max_rows=200):
            checked += 1
            exercised.add(query_id)
            for column, value in row.items():
                if value is not None and len(str(value)) > 500:
                    oversized.append((query_id, column, len(str(value)), slots))

    assert oversized[:5] == []
    # Canh danh mục hỏng, KHÔNG chốt một con số cố định: mỗi đợt gộp họ lại bớt
    # vài họ primary nên số dòng tụt dần một cách chính đáng (65 họ / 1.030 dòng
    # -> 62 họ / 990 dòng). Buộc theo SỐ HỌ thật sự trả ra dữ liệu thì canary vẫn
    # bắt được danh mục vỡ - lúc đó cả trăm họ câm cùng lúc - mà không bắt phải
    # sửa test sau mỗi lần gộp đúng đắn.
    askable = {q for q, spec in catalogue.items() if spec.tier == "primary"} - verbatim
    assert len(exercised) >= 0.7 * len(askable), (
        f"chỉ {len(exercised)}/{len(askable)} họ primary trả ra dữ liệu"
    )
    assert checked >= 15 * len(exercised), f"chỉ kiểm được {checked} dòng, danh mục có vấn đề?"
