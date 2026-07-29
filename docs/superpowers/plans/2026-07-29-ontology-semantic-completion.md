# Ontology Semantic Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sửa đầy đủ cấu trúc nguồn bị thiếu, hoàn thiện chỉ mục ngữ nghĩa tối giản cho Điều 20, 29 và 30, rồi tạo inventory máy đọc được trước khi xây lại catalogue/dataset.

**Architecture:** Một RDF graph chứa hai lớp: cây tài liệu chính thức giữ `officialText@vi`, còn policy/procedure là chỉ mục ngữ nghĩa chỉ nối về provision nguồn. Inventory được sinh xác định từ các named individual ngữ nghĩa và được kiểm tra bằng cách đi thật trên graph; candidate dataset không được dùng làm nguồn thiết kế ontology.

**Tech Stack:** Python 3.12, RDFLib 7.6+, OWL RL, Turtle, JSON, pytest 9, uv.

## Global Constraints

- Nguồn đối chiếu tại máy làm việc là `NTUdocs/Qd1052.md`, `NTUdocs/Qd729.md`, `NTUdocs/huong_dan_dong_hoc_phi.md` và `NTUdocs/bieumau_url.txt`.
- Không sửa hoặc commit các file người dùng đang giữ: `.gitignore`, `resources/ontology/ontology_v9.properties`, `uv.lock`, `NTUdocs/`, `bieumau_url.html`, `test.html`, `test_phobert.py`, `test_preprocess.py`.
- Không thêm dữ kiện không có căn cứ, không sửa câu chữ `officialText` ngoài việc tách đúng đoạn nguồn.
- IRI class/individual dùng tiếng Anh `PascalCase`; property dùng `camelCase`; label dùng tiếng Việt và language tag `@vi`.
- Object property chỉ là đường đi; kết quả query phải là label, literal hoặc giá trị tổng hợp.
- Không mở rộng candidate dataset cho node mới, không fine-tune, benchmark hoặc chạy web app trong kế hoạch này.
- Mọi chỉnh sửa thủ công dùng `apply_patch`; lệnh sinh inventory/report chỉ được ghi vào đúng file đầu ra đã định trước.
- Mỗi commit chỉ chứa file thuộc task tương ứng và không có `Co-authored-by`.

---

### Task 1: Sửa cây điều–khoản–điểm của Quyết định 1052

**Files:**
- Modify: `tests/ontology/test_documents.py`
- Modify: `resources/ontology/ontology.ttl` tại các node Điều 6, 8, 12, 20 và 22

**Interfaces:**
- Consumes: `ontology_graph`, namespace fixture `academic`, `hasPart`, `partOf`, `identifier`, `orderIndex`, `officialText`.
- Produces: cây nguồn đầy đủ với `Decision1052Article20Clause02` và bốn node `PointDD`; test cấu trúc áp dụng cho toàn bộ 32 điều.

- [ ] **Step 1: Viết kiểm thử thất bại cho cấu trúc đánh số tổng quát**

Thêm vào `tests/ontology/test_documents.py`:

```python
import re


CLAUSE_LINE = re.compile(r"(?m)^(\d+)\.\s")
POINT_LINE = re.compile(r"(?m)^([a-zđ])\)\s")


def _identifiers(graph, parent, academic):
    return {
        str(graph.value(child, academic.identifier))
        for child in graph.objects(parent, academic.hasPart)
        if graph.value(child, academic.identifier) is not None
    }


def test_decision_1052_numbered_children_match_parent_text(
    ontology_graph, academic
) -> None:
    for index in range(1, 33):
        article = academic[f"Decision1052Article{index:02d}"]
        text = str(ontology_graph.value(article, academic.officialText))
        expected = {f"Khoản {number}" for number in CLAUSE_LINE.findall(text)}
        actual = {
            value for value in _identifiers(ontology_graph, article, academic)
            if value.startswith("Khoản ")
        }
        assert actual == expected, article

    for clause in ontology_graph.subjects(RDF.type, academic.Clause):
        text = str(ontology_graph.value(clause, academic.officialText))
        expected = {f"Điểm {letter}" for letter in POINT_LINE.findall(text)}
        if not expected:
            continue
        actual = {
            value for value in _identifiers(ontology_graph, clause, academic)
            if value.startswith("Điểm ")
        }
        assert actual == expected, clause
```

Thêm kiểm tra riêng Điều 20 để ngăn nội dung Khoản 2 bị trộn lại:

```python
def test_article_20_clauses_are_separated_without_duplicate_points(
    ontology_graph, academic
) -> None:
    clause_1 = academic.Decision1052Article20Clause01
    clause_2 = academic.Decision1052Article20Clause02
    assert _identifiers(ontology_graph, academic.Decision1052Article20, academic) == {
        "Khoản 1", "Khoản 2", "Khoản 3"
    }
    assert _identifiers(ontology_graph, clause_1, academic) == {
        "Điểm a", "Điểm b", "Điểm c"
    }
    assert _identifiers(ontology_graph, clause_2, academic) == {"Điểm a", "Điểm b"}
    assert "buộc thôi học" not in str(
        ontology_graph.value(clause_1, academic.officialText)
    ).casefold()
    assert "buộc thôi học" in str(
        ontology_graph.value(clause_2, academic.officialText)
    ).casefold()
    for point in ontology_graph.objects(clause_1, academic.hasPart):
        assert len(list(ontology_graph.objects(point, academic.officialText))) == 1
        assert len(list(ontology_graph.objects(point, academic.orderIndex))) == 1
```

- [ ] **Step 2: Chạy test và xác nhận lỗi đúng nguyên nhân**

Run:

```bash
uv run pytest tests/ontology/test_documents.py::test_decision_1052_numbered_children_match_parent_text tests/ontology/test_documents.py::test_article_20_clauses_are_separated_without_duplicate_points -v
```

Expected: FAIL vì thiếu Khoản 2 Điều 20 và bốn `Điểm đ`; kiểm tra Điều 20 cũng thấy mỗi điểm đang có nhiều `officialText`/`orderIndex`.

- [ ] **Step 3: Tách Khoản 2 Điều 20 đúng nguồn**

Trong `ontology.ttl`:

```turtle
:Decision1052Article20Clause02 a :Clause, owl:NamedIndividual ;
    rdfs:label "Khoản 2 Điều 20"@vi ;
    :hasPart :Decision1052Article20Clause02PointA,
        :Decision1052Article20Clause02PointB ;
    :identifier "Khoản 2"@vi ;
    :officialText """2. Sau mỗi học kỳ chính, SV bị buộc thôi học nếu thuộc một trong những trường hợp sau đây:
a) Vượt quá 02 lần cảnh báo kết quả học tập liên tiếp.
b) Vượt quá thời gian tối đa được phép học tại Trường quy định tại khoản 4 Điều 2 của Quy chế này."""@vi ;
    :orderIndex "2"^^xsd:nonNegativeInteger ;
    :partOf :Decision1052Article20 ;
    :sourceDocument :Decision1052 .

:Decision1052Article20Clause02PointA a :Point, owl:NamedIndividual ;
    rdfs:label "Điểm a Khoản 2 Điều 20"@vi ;
    :identifier "Điểm a"@vi ;
    :officialText "a) Vượt quá 02 lần cảnh báo kết quả học tập liên tiếp."@vi ;
    :orderIndex "1"^^xsd:nonNegativeInteger ;
    :partOf :Decision1052Article20Clause02 ;
    :sourceDocument :Decision1052 .

:Decision1052Article20Clause02PointB a :Point, owl:NamedIndividual ;
    rdfs:label "Điểm b Khoản 2 Điều 20"@vi ;
    :identifier "Điểm b"@vi ;
    :officialText "b) Vượt quá thời gian tối đa được phép học tại Trường quy định tại khoản 4 Điều 2 của Quy chế này."@vi ;
    :orderIndex "2"^^xsd:nonNegativeInteger ;
    :partOf :Decision1052Article20Clause02 ;
    :sourceDocument :Decision1052 .
```

Đồng thời rút `Decision1052Article20Clause01` về đúng Khoản 1; ba PointA/B/C chỉ còn một literal và thứ tự 1/2/3. Thêm Clause02 vào `Decision1052Article20 :hasPart`.

- [ ] **Step 4: Bổ sung bốn `PointDD` đúng nguyên văn**

Tạo node theo cùng shape `Point`:

```text
Điều 6 Khoản 2:  đ) Học phần học trước: học phần SV phải học xong (có thể đạt hoặc không đạt) trước khi học các học phần tiếp theo.
Điều 8 Khoản 1:  đ) Đối với SV từ Trường khác đến sẽ được bố trí vào lớp SV phù hợp với khối lượng tín chỉ được Nhà trường bảo lưu.
Điều 12 Khoản 2: đ) Hướng dẫn và hỗ trợ SV học tập, nghiên cứu ngoài giờ lên lớp theo phương thức trực tiếp và trực tuyến.
Điều 22 Khoản 1: đ) Hoàn thành các học phần Giáo dục quốc phòng – An ninh và Giáo dục thể chất và các học phần điều kiện khác (nếu có).
```

Mỗi node có `identifier "Điểm đ"@vi`, `partOf`, `sourceDocument`, một
`officialText@vi`; thêm vào `hasPart` giữa PointD và PointE. Đặt lại
`orderIndex` theo đúng thứ tự nguồn:

```text
Điều 6 Khoản 2:  A=1 B=2 C=3 D=4 DD=5 E=6 G=7 H=8 I=9
Điều 8 Khoản 1:  A=1 B=2 C=3 D=4 DD=5 E=6
Điều 12 Khoản 2: A=1 B=2 C=3 D=4 DD=5 E=6 G=7 H=8
Điều 22 Khoản 1: A=1 B=2 C=3 D=4 DD=5 E=6
```

- [ ] **Step 5: Chạy kiểm thử ontology và audit khớp nguồn tại máy làm việc**

Run:

```bash
uv run pytest tests/ontology/test_documents.py -v
uv run pytest tests/ontology -q
uv run python - <<'PY'
import re
import unicodedata
from pathlib import Path
from rdflib import Graph, Namespace

ns = Namespace("http://www.ntu.edu.vn/ontology/academic#")
graph = Graph().parse("resources/ontology/ontology.ttl", format="turtle")
source = Path("NTUdocs/Qd1052.md").read_text(encoding="utf-8")
normalize = lambda value: re.sub(
    r"\s+", " ", unicodedata.normalize("NFC", str(value))
).strip()
source = normalize(source)
names = (
    "Decision1052Article20Clause01",
    "Decision1052Article20Clause01PointA",
    "Decision1052Article20Clause01PointB",
    "Decision1052Article20Clause01PointC",
    "Decision1052Article20Clause02",
    "Decision1052Article20Clause02PointA",
    "Decision1052Article20Clause02PointB",
    "Decision1052Article06Clause02PointDD",
    "Decision1052Article08Clause01PointDD",
    "Decision1052Article12Clause02PointDD",
    "Decision1052Article22Clause01PointDD",
)
for name in names:
    values = list(graph.objects(ns[name], ns.officialText))
    assert len(values) == 1, (name, values)
    assert normalize(values[0]) in source, name
print(f"verified {len(names)} source fragments")
PY
```

Expected: PASS và in `verified 11 source fragments`.

- [ ] **Step 6: Commit cấu trúc nguồn**

```bash
git add resources/ontology/ontology.ttl tests/ontology/test_documents.py
git commit -m "Repair official ontology hierarchy"
```

---

### Task 2: Hoàn thiện policy và procedure index

**Files:**
- Modify: `tests/ontology/test_schema.py`
- Modify: `tests/ontology/test_procedures_and_forms.py`
- Modify: `tests/ontology/test_sparql_smoke.py`
- Modify: `resources/ontology/ontology.ttl`

**Interfaces:**
- Consumes: cây provision đã sửa ở Task 1 và bốn role property hiện có.
- Produces: `AcademicPolicy`, hai policy, `ArticulationStudyProcedure`, `SickLeaveProcedure`, các liên kết chính xác cho Điều 20/29/30.

- [ ] **Step 1: Viết kiểm thử thất bại cho schema và tập node ngữ nghĩa mới**

Trong `test_schema.py`, thêm `academic.AcademicPolicy` vào `semantic_classes` và xác nhận `documentUrl` không tồn tại:

```python
assert not list(ontology_graph.triples((academic.documentUrl, None, None)))
```

Trong `test_procedures_and_forms.py`, thêm hai procedure vào `PROCEDURES`:

```python
"ArticulationStudyProcedure",
"SickLeaveProcedure",
```

Thêm kiểm tra:

```python
def test_policy_index_points_to_exact_article_20_clauses(
    ontology_graph, academic
) -> None:
    expected = {
        academic.AcademicWarningPolicy: academic.Decision1052Article20Clause01,
        academic.AcademicDismissalPolicy: academic.Decision1052Article20Clause02,
    }
    assert set(ontology_graph.subjects(RDF.type, academic.AcademicPolicy)) == set(expected)
    for policy, provision in expected.items():
        assert (policy, RDF.type, OWL.NamedIndividual) in ontology_graph
        assert (policy, academic.sourceDocument, academic.Decision1052) in ontology_graph
        assert set(ontology_graph.objects(policy, academic.sourceProvision)) == {provision}
        assert ontology_graph.value(policy, academic.officialText) is None
```

Sửa bảng `expected` và thêm các assertion tương đương với map hợp lệ sau:

```python
semantic_updates = {
    academic.eligibilityProvision: {
        academic.ArticulationStudyProcedure: {
            academic.Decision1052Article29Clause01,
        },
        academic.SickLeaveProcedure: {
            academic.Decision1052Article30Clause01,
            academic.Decision1052Article30Clause02,
        },
        academic.TemporaryAcademicLeaveProcedure: {
            academic.Decision1052Article24Clause01,
            academic.Decision1052Article30Clause01,
        },
        academic.ExamPostponementProcedure: {
            academic.Decision1052Article17Clause04,
            academic.Decision1052Article30Clause02,
        },
        academic.ClassAbsenceRequestProcedure: {
            academic.Decision1052Article17Clause01PointA,
            academic.Decision1052Article30Clause01,
        },
    },
    academic.deadlineProvision: {
        academic.ArticulationStudyProcedure: {
            academic.Decision1052Article29Clause02,
        },
        academic.SickLeaveProcedure: {
            academic.Decision1052Article30Clause01,
            academic.Decision1052Article30Clause02,
        },
        academic.ExamPostponementProcedure: {
            academic.Decision1052Article17Clause04,
            academic.Decision1052Article30Clause02,
        },
        academic.ClassAbsenceRequestProcedure: {
            academic.Decision1052Article17Clause01PointA,
            academic.Decision1052Article30Clause01,
        },
    },
    academic.instructionProvision: {
        academic.ArticulationStudyProcedure: {
            academic.Decision1052Article29,
        },
        academic.SickLeaveProcedure: {
            academic.Decision1052Article30,
        },
        academic.TemporaryAcademicLeaveProcedure: {
            academic.Decision1052Article24,
            academic.Decision1052Article30Clause01,
        },
        academic.ExamPostponementProcedure: {
            academic.Decision1052Article17,
            academic.Decision1052Article30Clause02,
        },
        academic.ClassAbsenceRequestProcedure: {
            academic.Decision1052Article17,
            academic.Decision1052Article30Clause01,
        },
        academic.DismissalTransferRequestProcedure: {
            academic.Decision1052Article20Clause03,
        },
    },
}
assert not list(
    ontology_graph.objects(
        academic.ClassAbsenceRequestProcedure,
        academic.resultProvision,
    )
)
```

- [ ] **Step 2: Viết smoke query thất bại cho ba chủ đề mới**

Thêm các case vào `test_sparql_smoke.py`:

```python
(
    "SELECT ?answer WHERE { :AcademicDismissalPolicy :sourceProvision ?part . ?part :officialText ?answer . }",
    "answer",
    "Vượt quá 02 lần cảnh báo",
),
(
    "SELECT ?answer WHERE { :ArticulationStudyProcedure :instructionProvision ?part . ?part :officialText ?answer . }",
    "answer",
    "Học liên thông",
),
(
    "SELECT ?answer WHERE { :SickLeaveProcedure :instructionProvision ?part . ?part :officialText ?answer . }",
    "answer",
    "xin nghỉ ốm",
),
```

- [ ] **Step 3: Chạy các test mới và xác nhận thất bại vì graph chưa có node**

```bash
uv run pytest tests/ontology/test_schema.py tests/ontology/test_procedures_and_forms.py tests/ontology/test_sparql_smoke.py -q
```

Expected: FAIL vì `AcademicPolicy`, hai procedure và các edge chưa tồn tại; `documentUrl` vẫn còn.

- [ ] **Step 4: Thêm policy và procedure vào Turtle**

Thêm shape cốt lõi:

```turtle
:AcademicPolicy a owl:Class ;
    rdfs:label "Chính sách học vụ"@vi .

:AcademicWarningPolicy a :AcademicPolicy, owl:NamedIndividual ;
    rdfs:label "Chính sách cảnh báo kết quả học tập"@vi ;
    :sourceDocument :Decision1052 ;
    :sourceProvision :Decision1052Article20Clause01 .

:AcademicDismissalPolicy a :AcademicPolicy, owl:NamedIndividual ;
    rdfs:label "Chính sách buộc thôi học"@vi ;
    :sourceDocument :Decision1052 ;
    :sourceProvision :Decision1052Article20Clause02 .

:ArticulationStudyProcedure a :AcademicProcedure, owl:NamedIndividual ;
    rdfs:label "Quy trình học liên thông"@vi ;
    :sourceDocument :Decision1052 ;
    :sourceProvision :Decision1052Article29 ;
    :eligibilityProvision :Decision1052Article29Clause01 ;
    :deadlineProvision :Decision1052Article29Clause02 ;
    :instructionProvision :Decision1052Article29 .

:SickLeaveProcedure a :AcademicProcedure, owl:NamedIndividual ;
    rdfs:label "Quy trình xin nghỉ ốm"@vi ;
    :sourceDocument :Decision1052 ;
    :sourceProvision :Decision1052Article30 ;
    :eligibilityProvision :Decision1052Article30Clause01,
        :Decision1052Article30Clause02 ;
    :deadlineProvision :Decision1052Article30Clause01,
        :Decision1052Article30Clause02 ;
    :instructionProvision :Decision1052Article30 .
```

Cập nhật ba procedure liên quan đúng bảng ở Step 1. Đổi `DismissalTransferRequestProcedure :instructionProvision` sang Clause03. Xóa `ClassAbsenceRequestProcedure :resultProvision`. Xóa toàn bộ khai báo `documentUrl`.

- [ ] **Step 5: Chạy test ontology**

```bash
uv run pytest tests/ontology -q
```

Expected: toàn bộ test ontology PASS; số procedure là 22, policy là 2.

- [ ] **Step 6: Commit semantic index**

```bash
git add resources/ontology/ontology.ttl tests/ontology/test_schema.py tests/ontology/test_procedures_and_forms.py tests/ontology/test_sparql_smoke.py
git commit -m "Complete ontology semantic index"
```

---

### Task 3: Sinh và xác minh answer inventory

**Files:**
- Create: `src/ontchatbot/research/inventory.py`
- Modify: `src/ontchatbot/settings.py`
- Create: `resources/ontology/answer_inventory.json`
- Create: `tests/research/test_inventory.py`

**Interfaces:**
- Consumes: `Graph`, `ONTOLOGY_NS`, `ONTOLOGY_PATH`, named individuals và các edge semantic của Task 2.
- Produces: `build_answer_inventory(graph: Graph) -> dict[str, object]`,
  `resolve_answer_path(graph: Graph, anchor: str, path: list[str]) -> list[Literal]`,
  `write_answer_inventory(graph: Graph, path: Path) -> None`, manifest JSON xác định.

- [ ] **Step 1: Viết test thất bại cho contract inventory**

Thêm `ANSWER_INVENTORY_PATH = ONTOLOGY_DIR / "answer_inventory.json"` vào kế hoạch interface và viết test trước:

```python
import json
from rdflib import URIRef

from ontchatbot.research.inventory import build_answer_inventory, resolve_answer_path
from ontchatbot.settings import ANSWER_INVENTORY_PATH, ONTOLOGY_NS


def test_committed_inventory_matches_canonical_graph(ontology_graph) -> None:
    committed = json.loads(ANSWER_INVENTORY_PATH.read_text(encoding="utf-8"))
    assert committed == build_answer_inventory(ontology_graph)


def test_supported_inventory_paths_end_in_literals(ontology_graph) -> None:
    inventory = build_answer_inventory(ontology_graph)
    entries = inventory["entries"]
    assert entries
    assert len({entry["id"] for entry in entries}) == len(entries)
    for entry in entries:
        assert entry["status"] in {"supported", "excluded"}
        assert URIRef(ONTOLOGY_NS + entry["anchor"]) in ontology_graph.all_nodes()
        if entry["status"] == "excluded":
            assert entry["reason"]
            continue
        assert entry["answer_kind"] in {"label", "literal", "aggregate"}
        assert entry["path"]
        assert entry["provenance"]
        values = resolve_answer_path(
            ontology_graph,
            entry["anchor"],
            entry["path"],
        )
        assert values
        assert all(not isinstance(value, URIRef) for value in values)
        for local_name in entry["provenance"]:
            assert URIRef(ONTOLOGY_NS + local_name) in ontology_graph.all_nodes()
        if entry["answer_kind"] == "aggregate":
            assert entry["operation"]


def test_known_semantic_decisions_are_in_inventory(ontology_graph) -> None:
    entries = {item["id"]: item for item in build_answer_inventory(ontology_graph)["entries"]}
    assert entries["AcademicDismissalPolicy-sourceProvision-officialText"]["status"] == "supported"
    assert entries["SickLeaveProcedure-instructionProvision-officialText"]["status"] == "supported"
    assert entries["ClassAbsenceRequestProcedure-resultProvision"]["status"] == "excluded"
```

- [ ] **Step 2: Chạy test và xác nhận module/file chưa tồn tại**

```bash
uv run pytest tests/research/test_inventory.py -v
```

Expected: collection FAIL vì chưa có `ontchatbot.research.inventory`.

- [ ] **Step 3: Viết generator tối giản**

`inventory.py` chỉ xét `owl:NamedIndividual` không thuộc các type nguồn `Article`, `Clause`, `Point`, `Appendix`, `DocumentTable`, `DocumentTableRow`, `Chapter`, `AttachedRegulation`. Nó sinh:

1. đường trực tiếp tới literal, trừ `skos:altLabel`;
2. các provision role tới `officialText`;
3. các quan hệ nghiệp vụ tới `rdfs:label`.

Các hằng số phải là:

```python
PROVISION_PROPERTIES = (
    "sourceProvision",
    "instructionProvision",
    "eligibilityProvision",
    "deadlineProvision",
    "resultProvision",
    "paymentInstructionProvision",
)
LABEL_PROPERTIES = (
    "requiresForm",
    "submittedTo",
    "reviewedBy",
    "decidedBy",
    "supportsPaymentMethod",
    "supportsBank",
    "appliesToProgram",
    "appliesToCourseCategory",
    "appliesToEducationLevel",
    "appliesToCertificate",
    "mapsToCompetencyLevel",
    "grantsCourseExemption",
    "belongsToDisciplineGroup",
)
EXCLUSIONS = (
    {
        "id": "ClassAbsenceRequestProcedure-resultProvision",
        "anchor": "ClassAbsenceRequestProcedure",
        "answer_kind": "literal",
        "path": [],
        "provenance": ["Decision1052Article17Clause01PointB"],
        "status": "excluded",
        "reason": "Provision mô tả việc xem xét, không bảo đảm một kết quả.",
    },
    {
        "id": "SickLeaveProcedure-submittedTo",
        "anchor": "SickLeaveProcedure",
        "answer_kind": "label",
        "path": [],
        "provenance": ["Decision1052Article30"],
        "status": "excluded",
        "reason": "Hai nhánh nghỉ ốm không có một đơn vị nhận hồ sơ chung rõ ràng.",
    },
    {
        "id": "ArticulationStudyProcedure-requiresForm",
        "anchor": "ArticulationStudyProcedure",
        "answer_kind": "label",
        "path": [],
        "provenance": ["Decision1052Article29"],
        "status": "excluded",
        "reason": "Điều 29 không quy định biểu mẫu cụ thể.",
    },
)
```

`build_answer_inventory` trả:

```python
{
    "schema_version": 1,
    "ontology_namespace": ONTOLOGY_NS,
    "entries": sorted(entries, key=lambda item: item["id"]),
}
```

`resolve_answer_path` mở rộng `rdfs:label` và local property theo namespace dự
án, đi tuần tự từng cạnh và chỉ trả `Literal`; IRI ở terminal là lỗi validation.
Mỗi supported entry được giữ lại chỉ khi hàm này trả ít nhất một giá trị.
`answer_kind` là `label` khi terminal là `rdfs:label`, còn lại là `literal`.
`provenance` lấy từ `sourceProvision`; nếu không có thì lấy chính document part
được đi tới hoặc `sourceDocument` của anchor. `write_answer_inventory` dùng
`json.dumps(..., ensure_ascii=False, indent=2) + "\n"`.

Thêm `main()` để lệnh sau tái tạo được file mà không thêm entry point vào `pyproject.toml`:

```bash
uv run python -m ontchatbot.research.inventory
```

- [ ] **Step 4: Sinh manifest và chạy test**

```bash
uv run python -m ontchatbot.research.inventory
uv run pytest tests/research/test_inventory.py -v
```

Expected: inventory được sắp xếp ổn định, test PASS hai lần liên tiếp và lần sinh thứ hai không làm thay đổi file.

- [ ] **Step 5: Commit inventory**

```bash
git add src/ontchatbot/settings.py src/ontchatbot/research/inventory.py resources/ontology/answer_inventory.json tests/research/test_inventory.py
git commit -m "Add ontology answer inventory"
```

---

### Task 4: Gỡ target candidate dựa trên triple sai

**Files:**
- Modify: `resources/dataset/main/train.jsonl`
- Modify: `resources/dataset/main/catalogue.jsonl`
- Modify: `resources/dataset/main/manifest.json`
- Modify: `tests/research/test_dataset_content.py`
- Modify: `tests/research/test_reporting.py`
- Modify: `README.md`
- Modify: `docs/CONCEPT.md`
- Modify: `docs/DATASET.md`
- Modify: `resources/dataset/main/README.md`
- Modify: `docs/superpowers/specs/2026-07-29-ontology-dataset-readiness-design.md`
- Regenerate: `reports/dataset.json`
- Regenerate: `reports/figures/dataset-splits.svg`
- Regenerate: `reports/figures/query-features.svg`
- Regenerate: `reports/figures/registers.svg`

**Interfaces:**
- Consumes: ontology canonical không còn `ClassAbsenceRequestProcedure :resultProvision`.
- Produces: candidate pool 455 câu vẫn parse/chạy được nhưng không tuyên bố bao phủ 22 procedure mới.

- [ ] **Step 1: Chạy test toàn bộ để ghi nhận hai contract cũ bị vỡ**

```bash
uv run pytest tests/research/test_dataset_content.py -q
```

Expected: FAIL vì candidate còn target result trả rỗng và test cũ yêu cầu mọi `AcademicProcedure` phải xuất hiện trong candidate.

- [ ] **Step 2: Sửa test để candidate chỉ cần là tập con hợp lệ của ontology**

Đổi test coverage procedure thành:

```python
def test_candidate_procedure_iris_exist_in_ontology() -> None:
    graph = load_ontology()
    catalogue = load_catalogue(QUERY_CATALOGUE_PATH)
    report = validate_release(load_release(), graph, catalogue)
    existing = {
        f":{str(node).rsplit('#', 1)[-1]}"
        for node in graph.subjects(RDF.type, ACADEMIC.AcademicProcedure)
    }
    declared = {
        value
        for spec in catalogue.values()
        if spec.domain == "procedure"
        for slot in spec.slots.values()
        for value in slot.values
    }
    seen = {
        value
        for query_id, slots in report["slot_coverage"].items()
        if catalogue[query_id].domain == "procedure"
        for details in slots.values()
        for value in details["seen_train"]
    }
    assert declared <= existing
    assert seen <= existing
```

Không thêm `ArticulationStudyProcedure` hoặc `SickLeaveProcedure` vào candidate catalogue.

- [ ] **Step 3: Loại đúng record và slot sai**

Xóa nguyên dòng `question-000049` khỏi `train.jsonl`. Xóa
`:ClassAbsenceRequestProcedure` khỏi danh sách `values` của duy nhất họ
`procedure-result`. Không renumber các ID khác và không viết lại nội dung câu
hỏi.

- [ ] **Step 4: Cập nhật snapshot và báo cáo bằng generator hiện có**

Đổi các mô tả snapshot đang hoạt động từ `456/340/58/58` thành
`455/339/58/58`; tài liệu lịch sử đã được đánh dấu superseded vẫn giữ số liệu
lịch sử. Sửa `tests/research/test_reporting.py` kỳ vọng 455.

Run:

```bash
uv run generate_reports
```

Expected: `manifest.json`, `reports/dataset.json` và ba SVG được sinh lại; ontology SHA và candidate SHA khớp file hiện tại.

- [ ] **Step 5: Xác minh candidate vẫn hợp lệ**

```bash
uv run validate_sparql_dataset
uv run pytest tests/research/test_dataset.py tests/research/test_dataset_content.py tests/research/test_reporting.py tests/research/test_documentation_status.py -q
```

Expected: PASS; candidate vẫn có 24 họ, ba split hợp lệ và không target nào trả rỗng.

- [ ] **Step 6: Commit đồng bộ candidate**

```bash
git add README.md docs/CONCEPT.md docs/DATASET.md docs/superpowers/specs/2026-07-29-ontology-dataset-readiness-design.md resources/dataset/main reports tests/research/test_dataset_content.py tests/research/test_reporting.py
git commit -m "Remove unsupported candidate result query"
```

---

### Task 5: Công bố trạng thái ontology mới và xác minh toàn dự án

**Files:**
- Modify: `docs/ONTOLOGY.md`
- Modify: `README.md`
- Modify: `docs/DATASET.md`
- Modify: `tests/research/test_documentation_status.py`

**Interfaces:**
- Consumes: graph, inventory và candidate đã đồng bộ.
- Produces: tài liệu nói đúng rằng ontology canonical đã đạt gate, còn catalogue/dataset chính thức vẫn chưa được xây.

- [ ] **Step 1: Viết regression test tài liệu trước**

Thêm assertion:

```python
def test_docs_separate_canonical_ontology_from_candidate_dataset() -> None:
    ontology = _read("docs/ONTOLOGY.md")
    dataset = _read("docs/DATASET.md")
    readme = _read("README.md")
    assert "answer_inventory.json" in ontology
    assert "22 quy trình" in ontology
    assert "2 chính sách" in ontology
    assert "ontology canonical" in readme
    assert "candidate pool" in dataset
    assert "không được full fine-tune" in _read("docs/TRAINING.md")
```

- [ ] **Step 2: Chạy test và xác nhận docs chưa phản ánh trạng thái mới**

```bash
uv run pytest tests/research/test_documentation_status.py -v
```

Expected: FAIL ở các câu mô tả ontology canonical/inventory.

- [ ] **Step 3: Cập nhật tài liệu đang hoạt động**

Ghi rõ trong `docs/ONTOLOGY.md`:

- nguồn, cấu trúc và semantic index đã qua audit;
- graph có 22 `AcademicProcedure` và 2 `AcademicPolicy`;
- Điều 20/29/30 đã có đường truy vấn rõ;
- `answer_inventory.json` là cầu nối kế tiếp sang query catalogue;
- ontology canonical không đồng nghĩa candidate dataset đã production-ready.

README chỉ tóm tắt trạng thái này; `docs/DATASET.md` tiếp tục chặn full
fine-tuning cho tới khi catalogue/dataset chính thức được xây từ inventory.

- [ ] **Step 4: Chạy xác minh sạch từ đầu**

```bash
uv run python -m ontchatbot.research.inventory
git diff --exit-code -- resources/ontology/answer_inventory.json
uv run pytest tests/ontology -q
uv run validate_sparql_dataset
uv run pytest -q
git diff --check
git status --short
```

Expected: inventory tái tạo không đổi; ontology, candidate và toàn bộ test PASS;
`git diff --check` không có lỗi. `git status` chỉ còn những file người dùng đã
giữ từ trước cùng thay đổi tài liệu của Task 5.

- [ ] **Step 5: Commit tài liệu trạng thái**

```bash
git add README.md docs/ONTOLOGY.md docs/DATASET.md tests/research/test_documentation_status.py
git commit -m "Document canonical ontology status"
```

- [ ] **Step 6: Ghi nhận trạng thái bàn giao**

```bash
git log --oneline -8
git status --short
```

Expected: năm commit triển khai tách biệt; không merge branch; không có file
người dùng bị staged hoặc sửa bởi kế hoạch.
