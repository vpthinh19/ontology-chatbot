# Official Ontology Refactor Implementation Plan

> **Trạng thái:** Kế hoạch này ghi lại lần triển khai lớp nguồn ontology. Các
> checkbox hoàn thành không có nghĩa semantic index đã được khóa canonical. Xem
> [đặc tả readiness](../specs/2026-07-29-ontology-dataset-readiness-design.md).

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Thay ontology cũ bằng ontology Turtle mô hình lai, truy nguồn được tới QĐ 1052, QĐ 729, hướng dẫn học phí và danh mục URL biểu mẫu đã cung cấp.

**Architecture:** Một graph duy nhất gồm lớp nguồn chính thức, chỉ mục quy trình ngữ nghĩa và các quy tắc số hóa. Quy trình không sao chép nội dung; object property dẫn tới provision/rule, còn SPARQL chỉ trả label hoặc literal. Mỗi miền dữ liệu có test contract và smoke query riêng.

**Tech Stack:** Turtle, RDF/OWL, SKOS, RDFLib 7.6, OWL RL 7.6, pytest 9, SPARQL 1.1.

## Global Constraints

- Nguồn sự thật chỉ gồm `NTUdocs/Qd1052.md`, `NTUdocs/Qd729.md`, `NTUdocs/huong_dan_dong_hoc_phi.md`, `NTUdocs/bieumau_url.txt` và `bieumau_url.html`.
- Giữ namespace `http://www.ntu.edu.vn/ontology/academic#`.
- Class và named individual dùng IRI tiếng Anh `PascalCase`; property dùng IRI tiếng Anh `camelCase`.
- Mọi named resource trong namespace dự án có `rdfs:label@vi`; mọi `officialText` có language tag `vi`.
- Không dùng `owl:unionOf`; không yêu cầu OWL reasoning để query production trả kết quả đúng.
- QĐ 1052 quyết định số và ý nghĩa pháp lý của biểu mẫu; HTML chỉ quyết định nhãn niêm yết và URL tải.
- URL tải dùng origin `https://pdtdaihoc.ntu.edu.vn`, được resolve về `/uploads/...` và không chứa `../`.
- `skos:altLabel@vi` chỉ chứa tên gọi hoặc viết tắt thật; không chứa câu hỏi, điểm số hay điều kiện.
- Không tạo lại `Condition`, `Outcome`, `content`, `hasCondition`, `hasOutcome`, `CourseWithdrawalProcedure`, `ScholarshipReviewProcedure` hoặc `TuitionPaymentExtensionForm`.
- Không sửa code runtime, dataset, model, artifact, README hoặc dependency trong kế hoạch này.
- Không thêm trailer `Co-authored-by` vào commit.
- Không stage `.gitignore`, `resources/ontology/ontology_v9.properties`, `uv.lock`, `NTUdocs/`, `bieumau_url.html`, `test.html`, `test_phobert.py` hoặc `test_preprocess.py`.

## File Structure

- Modify: `resources/ontology/ontology.ttl` — graph production duy nhất.
- Delete: `tests/tools/test_ontology.py` — contract theo số lượng ontology cũ.
- Create: `tests/ontology/conftest.py` — fixture graph và namespace dùng chung.
- Create: `tests/ontology/test_schema.py` — quy ước RDF/OWL, label và provenance.
- Create: `tests/ontology/test_documents.py` — cấu trúc nguồn QĐ 1052, QĐ 729 và hướng dẫn.
- Create: `tests/ontology/test_procedures_and_forms.py` — quy trình, actor, biểu mẫu và URL.
- Create: `tests/ontology/test_tuition_and_payment.py` — ngành, học phí và thanh toán.
- Create: `tests/ontology/test_academic_rules.py` — bảng xếp loại và quy mô lớp.
- Create: `tests/ontology/test_certificate_rules.py` — Phụ lục 2–3.
- Create: `tests/ontology/test_sparql_smoke.py` — query đầu-cuối chỉ trả literal.

---

### Task 1: Schema nền và lớp nguồn chính thức

**Files:**
- Delete: `tests/tools/test_ontology.py`
- Create: `tests/ontology/conftest.py`
- Create: `tests/ontology/test_schema.py`
- Create: `tests/ontology/test_documents.py`
- Replace: `resources/ontology/ontology.ttl`

**Interfaces:**
- Consumes: namespace `ONTOLOGY_NS` và hàm `load_ontology()` hiện có.
- Produces: fixture `ontology_graph: rdflib.Graph`, fixture `academic: rdflib.Namespace`, schema nguồn và toàn bộ hierarchy văn bản.

- [ ] **Step 1: Viết fixture và test schema thất bại**

Tạo fixture session-scope:

```python
import pytest
from rdflib import Graph, Namespace

from ontchatbot.runtime.sparql import load_ontology
from ontchatbot.settings import ONTOLOGY_NS


@pytest.fixture(scope="session")
def ontology_graph() -> Graph:
    return load_ontology()


@pytest.fixture(scope="session")
def academic() -> Namespace:
    return Namespace(ONTOLOGY_NS)
```

Trong `test_schema.py`, kiểm tra tập lớp chứa đủ `DocumentComponent`,
`OfficialDocument`, `Decision`, `GuidanceDocument`, `DocumentPart`,
`AttachedRegulation`, `Chapter`, `Article`, `Clause`, `Point`, `Appendix`,
`DocumentTable`, `DocumentTableRow`; `hasPart` inverse `partOf`; mọi named
resource có label `@vi`; không có `owl:unionOf` và các IRI cũ bị cấm.

- [ ] **Step 2: Chạy test để xác nhận ontology cũ thất bại**

```bash
uv run pytest tests/ontology/test_schema.py -q
```

Expected: FAIL vì ontology cũ chưa có source schema.

- [ ] **Step 3: Viết schema và nguồn QĐ 1052**

Thay ontology cũ bằng prefix, ontology declaration và schema theo đặc tả. Dùng
các IRI `Decision1052`, `Decision1052EnactmentArticle01..03`,
`Decision1052Regulation`, `Decision1052Chapter01..05`,
`Decision1052Article01..32`, `Decision1052Appendix01..03`.

Chép ba điều ban hành từ `NTUdocs/Qd1052.md:28-33` và quy chế/phụ lục từ
`NTUdocs/Qd1052.md:82-632`. Mỗi điều thuộc đúng
chương; mỗi khoản/điểm có IRI dạng `Decision1052Article24Clause03PointA`, có
`identifier`, `orderIndex`, `partOf`, `sourceDocument` và nguyên văn tương ứng.
Lưu số `1052/QĐ-ĐHNT`, ngày `2025-07-17`, hiệu lực `2025-2026`; không lưu `1051`.
Appendix 1–3 có `DocumentTable` và `DocumentTableRow` riêng để các rule ở Task
4–5 trỏ về đúng dòng nguồn.

```turtle
:hasPart a owl:ObjectProperty ;
    owl:inverseOf :partOf ;
    rdfs:domain :DocumentComponent ;
    rdfs:range :DocumentPart ;
    rdfs:label "có thành phần"@vi .

:Decision1052 a owl:NamedIndividual, :Decision ;
    rdfs:label "Quyết định số 1052/QĐ-ĐHNT"@vi ;
    :documentNumber "1052/QĐ-ĐHNT" ;
    :issueDate "2025-07-17"^^xsd:date ;
    :effectiveFromAcademicYear "2025-2026" .
```

- [ ] **Step 4: Thêm test document và chạy xanh**

Assert 3 enactment article, 1 attached regulation, 5 chapter, 32 article và
Appendix 1–3. Từng article `01..32` có đúng một `partOf` chapter,
`sourceDocument Decision1052`, `officialText@vi`. Không bịa nội dung Appendix 4.

```bash
uv run pytest tests/ontology/test_schema.py tests/ontology/test_documents.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add resources/ontology/ontology.ttl tests/ontology tests/tools/test_ontology.py
git commit -m "Rebuild official ontology foundation"
```

---

### Task 2: Quy trình, actor và biểu mẫu

**Files:**
- Modify: `resources/ontology/ontology.ttl`
- Create: `tests/ontology/test_procedures_and_forms.py`

**Interfaces:**
- Consumes: `DocumentPart`, `sourceDocument`, `sourceProvision`, các article QĐ 1052.
- Produces: 20 `AcademicProcedure`, actor nguồn xác nhận, 15 form chuẩn và 19 catalogue entry tải xuống.

- [ ] **Step 1: Viết test quy trình và biểu mẫu thất bại**

Hard-code tập 20 procedure IRI và ánh xạ form:

```python
PROCEDURES = {
    "CourseRegistrationProcedure", "ExtraClassOpeningRequestProcedure",
    "CourseRetakeProcedure", "GradeImprovementProcedure",
    "GraduationProjectRegistrationProcedure", "ClassAbsenceRequestProcedure",
    "ExamPostponementProcedure", "DismissalTransferRequestProcedure",
    "CreditRecognitionProcedure", "CourseExemptionAndBonusProcedure",
    "GraduationReviewProcedure", "EarlyGraduationReviewProcedure",
    "TemporaryAcademicLeaveProcedure", "StudyWithdrawalProcedure",
    "StudyResumptionProcedure", "MajorChangeProcedure",
    "UniversityTransferProcedure", "StudentExchangeProcedure",
    "SecondProgramRegistrationProcedure", "TuitionPaymentProcedure",
}
```

```python
FORM_TO_PROCEDURE = {
    1: "ExtraClassOpeningRequestProcedure",
    2: "GraduationProjectRegistrationProcedure",
    3: "ClassAbsenceRequestProcedure",
    4: "ExamPostponementProcedure",
    5: "DismissalTransferRequestProcedure",
    6: "CreditRecognitionProcedure",
    7: "CourseExemptionAndBonusProcedure",
    8: "EarlyGraduationReviewProcedure",
    9: "TemporaryAcademicLeaveProcedure",
    10: "StudyWithdrawalProcedure",
    11: "StudyResumptionProcedure",
    12: "MajorChangeProcedure",
    13: "UniversityTransferProcedure",
    14: "StudentExchangeProcedure",
    15: "SecondProgramRegistrationProcedure",
}
```

Assert mỗi procedure có `sourceDocument` và ít nhất một provision role. Assert
15 form có `formNumber`; catalogue có đúng 19 entry với URL tuyệt đối cùng
origin và không chứa `..`.

- [ ] **Step 2: Chạy test để xác nhận thất bại**

```bash
uv run pytest tests/ontology/test_procedures_and_forms.py -q
```

Expected: FAIL vì semantic layer chưa tồn tại.

- [ ] **Step 3: Thêm semantic layer, procedure và actor**

Thêm các class/property trong đặc tả. Tạo đúng 20 procedure, nối tới khoản/điểm
thay vì sao chép literal. Chỉ tạo Student, University, UniversityPresident,
AcademicManagementUnit, StudentAffairsOffice, FacultyOrInstitute, Department,
ProfessionalCouncil, GraduationCouncil. Không thêm contact, trưởng phòng hoặc
địa chỉ không có nguồn. Alias chỉ dùng cho tên thật như CTĐT, ĐATN, CĐTN, ĐKHP,
bảo lưu, học lại và học cải thiện; viết tắt chat như `hp`, `đk`, `hc` không được
lặp vào ontology.

- [ ] **Step 4: Thêm form chuẩn và catalogue HTML**

Tạo `Decision1052Form01..15` theo số mới; tạo `UndergraduateFormCatalogue`; tạo
`FormCatalogueEntry001..019` theo 19 thẻ `a[href]`. Resolve href trên origin
`https://pdtdaihoc.ntu.edu.vn`, giữ path/encoding, loại `../`.

Chỉ thêm `catalogueEntryForForm` khi tên/ngữ nghĩa chắc chắn. Entry “Đơn xin
nghỉ học tạm thời” không được nối Form 08 mới; “Đơn xin bảo lưu học phần” không
được nối Form 14 mới. Phiếu điểm/bản sao bằng cuối trang chỉ là catalogue entry.

- [ ] **Step 5: Chạy test và commit**

```bash
uv run pytest tests/ontology/test_schema.py tests/ontology/test_documents.py \
  tests/ontology/test_procedures_and_forms.py -q
git add resources/ontology/ontology.ttl tests/ontology/test_procedures_and_forms.py
git commit -m "Add sourced academic procedures and forms"
```

Expected: PASS rồi commit thành công.

---

### Task 3: QĐ 729, học phí và phương thức thanh toán

**Files:**
- Modify: `resources/ontology/ontology.ttl`
- Modify: `tests/ontology/test_documents.py`
- Create: `tests/ontology/test_tuition_and_payment.py`

**Interfaces:**
- Consumes: source schema và provenance properties.
- Produces: Decision729, 41 chương trình thuộc 4 khối ngành, rate theo điều kiện, duration rule, 4 phương thức và 3 ngân hàng.

- [ ] **Step 1: Viết test QĐ 729 và học phí thất bại**

Assert `Decision729` có document number `729/QĐ-ĐHNT`, issue date `2025-05-28`,
3 enactment article, Appendix I–II, hiệu lực HK I 2025–2026 và
`validUntilSuperseded true`.

Assert số chương trình theo khối là `8, 1, 23, 9` và tổng 41. Assert các tuple
mức phí từ `NTUdocs/Qd729.md:45-82`: 345000/credit học phần tổng quát; 500000
khối III; 570000 khối V; 460000 Ngôn ngữ Anh; 505000 các ngành khác khối VII;
cao học 785000/850000/915000; tiến sĩ 39500000/42600000/46000000 mỗi năm và
Noherd 24500000; toàn bộ mức kiểm định khóa 63, 65, 66, 67.

- [ ] **Step 2: Chạy test để xác nhận thất bại**

```bash
uv run pytest tests/ontology/test_tuition_and_payment.py -q
```

Expected: FAIL vì ontology chưa có dữ liệu QĐ 729 mới.

- [ ] **Step 3: Thêm source QĐ 729 và schema học phí**

Tạo `Decision729EnactmentArticle01..03`, `Decision729Appendix01..02` và các row
nguồn với `officialText@vi`. Thêm `AcademicProgram`, `DisciplineGroup`,
`EducationLevel`, `CourseCategory`, `TuitionRate`, `BillingUnit`,
`DoctoralTuitionDurationRule` cùng properties trong đặc tả.

Chép đủ 41 ngành ở `NTUdocs/Qd729.md:89-133`; giữ riêng chương trình song ngữ
Pháp–Việt. Dùng `minimumCohortNumber` cho “từ khóa ... trở về sau”; không dùng
exact cohort code hoặc tên Band. Mọi rate trỏ tới `Decision729` và row nguồn.

- [ ] **Step 4: Thêm hướng dẫn thanh toán**

Tạo `TuitionPaymentGuidance` và ba provision từ đúng ba đoạn đánh số trong
`NTUdocs/huong_dan_dong_hoc_phi.md`. Tạo VNPAY, QR, Mobile/Internet Banking,
CashAtBankCounter; Agribank, VietinBank, LienVietPostBank; fee rule 0, 3300,
5500 cùng điều kiện nguyên văn. Giữ cảnh báo gửi mã sinh viên và không gửi tài
khoản Trường. Không thêm “trễ hạn bị cấm thi” hay gia hạn học phí.

- [ ] **Step 5: Chạy test và commit**

```bash
uv run pytest tests/ontology/test_documents.py \
  tests/ontology/test_tuition_and_payment.py -q
git add resources/ontology/ontology.ttl tests/ontology/test_documents.py \
  tests/ontology/test_tuition_and_payment.py
git commit -m "Model official tuition and payment data"
```

Expected: PASS rồi commit thành công.

---

### Task 4: Quy tắc học vụ có khoảng số

**Files:**
- Modify: `resources/ontology/ontology.ttl`
- Create: `tests/ontology/test_academic_rules.py`

**Interfaces:**
- Consumes: QĐ 1052 Article 18, 19, 23 và Appendix 1.
- Produces: band/rule có numeric boundary để SPARQL FILTER và criterion nguyên văn.

- [ ] **Step 1: Viết test rule thất bại**

Assert có 6 `AcademicPerformanceBand`, 4 `StudyYearBand`, 4
`GraduationClassificationBand` và 14 `ClassSizeRule`. Kiểm tra inclusive/
exclusive cho các khoảng; riêng “Trên 105” phải là minimum 105 exclusive,
không tự sửa thành `>= 105`. Dấu `*` ở maximum quy mô lớp được giữ trong
`criterionText` nhưng không biến thành numeric maximum.

- [ ] **Step 2: Chạy test để xác nhận thất bại**

```bash
uv run pytest tests/ontology/test_academic_rules.py -q
```

Expected: FAIL vì các bảng chưa được số hóa.

- [ ] **Step 3: Thêm bảng phân loại và quy mô lớp**

Chép đúng các band từ `NTUdocs/Qd1052.md:291-310`, `385-390` và 14 trường hợp
quy mô lớp từ `515-528` (tách lý thuyết/thực hành ở Giáo dục thể chất và Quốc
phòng–An ninh). Mỗi rule có `sourceProvision`, `sourceDocument`,
`criterionText@vi`, `resultLabel@vi` khi có và boundary kiểu `xsd:decimal`.

- [ ] **Step 4: Chạy test và commit**

```bash
uv run pytest tests/ontology/test_academic_rules.py tests/ontology/test_schema.py -q
git add resources/ontology/ontology.ttl tests/ontology/test_academic_rules.py
git commit -m "Add structured academic rules"
```

Expected: PASS rồi commit thành công.

---

### Task 5: Quy đổi chứng chỉ Phụ lục 2–3

**Files:**
- Modify: `resources/ontology/ontology.ttl`
- Create: `tests/ontology/test_certificate_rules.py`

**Interfaces:**
- Consumes: `Decision1052Appendix02`, `Decision1052Appendix03`, 41 program IRI.
- Produces: certificate, learner category và conversion rule truy vấn được.

- [ ] **Step 1: Viết test coverage bảng thất bại**

Assert 15 chứng chỉ ngoại ngữ (TOEIC, TOEFL iBT, IELTS, Linguaskill, Aptis,
Cambridge English Scale, HSK, TOCFL, JLPT, JPT, TRKI, DELF, TCF, TOPIK, KLPT),
3 chứng chỉ tin học (IC3, ICDL, MOS), 3 learner context và rule count:

```python
EXPECTED_RULES = {
    "StandardEnglishCertificateTable": 26,
    "StandardOtherLanguageCertificateTable": 46,
    "SpecialProgramEnglishCertificateTable": 36,
    "SpecialProgramOtherLanguageCertificateTable": 48,
    "EnglishMajorOtherLanguageCertificateTable": 47,
    "ComputerCertificateTable": 9,
}
```

Assert mỗi rule có `criterionText@vi`, source appendix/row, certificate và
learner/program context. Assert IC3/ICDL/MOS có đủ ba khoảng đổi thành 8, 9, 10.

- [ ] **Step 2: Chạy test để xác nhận thất bại**

```bash
uv run pytest tests/ontology/test_certificate_rules.py -q
```

Expected: FAIL vì chưa có schema/rule chứng chỉ.

- [ ] **Step 3: Thêm certificate schema và danh mục chính thức**

Thêm class/property trong đặc tả. Dùng tên đầy đủ đúng bảng viết tắt
`NTUdocs/Qd1052.md:608-622`; không tự tạo tên đầy đủ cho Linguaskill, Aptis hoặc
Cambridge khi nguồn chỉ ghi tên cột. Dùng `skos:altLabel@vi` cho viết tắt thật.

- [ ] **Step 4: Số hóa từng ô Phụ lục 2–3**

Tạo một rule cho từng ô có ý nghĩa trong `Qd1052.md:539-600` và `628-632`.
Giữ nguyên ô có nhiều dòng/ngưỡng trong một `criterionText` nếu nguồn không cho
phép tách chắc chắn. Chỉ điền numeric boundary cho ký hiệu/range rõ ràng; cấp độ
như HSK 3, N4, TOPIK 3 dùng `requiredLevelCode`. Sáu chương trình đặc biệt nối
tới đúng `AcademicProgram` đã tạo ở Task 3.

- [ ] **Step 5: Chạy test và commit**

```bash
uv run pytest tests/ontology/test_certificate_rules.py \
  tests/ontology/test_tuition_and_payment.py -q
git add resources/ontology/ontology.ttl tests/ontology/test_certificate_rules.py
git commit -m "Model official certificate conversions"
```

Expected: PASS rồi commit thành công.

---

### Task 6: Kiểm chứng toàn graph và SPARQL đầu-cuối

**Files:**
- Modify: `tests/ontology/test_schema.py`
- Create: `tests/ontology/test_sparql_smoke.py`
- Modify: `resources/ontology/ontology.ttl` only if a failing invariant exposes a data error.

**Interfaces:**
- Consumes: toàn bộ ontology từ Task 1–5 và `execute_select()` hiện có.
- Produces: bằng chứng parse, OWL RL, provenance, coverage và answer projection.

- [ ] **Step 1: Thêm global invariant test**

Sao graph sang graph mới và chạy:

```python
from owlrl import DeductiveClosure, OWLRL_Semantics

DeductiveClosure(OWLRL_Semantics).expand(expanded_graph)
```

Assert closure không lỗi; không resource nào vừa là ObjectProperty vừa là
DatatypeProperty; mọi typed literal chuyển được bằng `toPython()`; mọi semantic
procedure/rule có `sourceDocument` và đường tới `DocumentPart`; không còn IRI bị
cấm; mọi named resource dự án có label `@vi`.

- [ ] **Step 2: Viết smoke query cho các nhóm câu hỏi**

Tạo query dùng `execute_select()` cho 12 nhóm:

```text
đăng ký học phần; học lại; bảo lưu; chuyển ngành; xét tốt nghiệp;
biểu mẫu và URL; học phí theo ngành/khóa; phương thức thanh toán;
xếp loại điểm; quy mô lớp; quy đổi ngoại ngữ; quy đổi tin học
```

Mỗi query dùng `SELECT` cột rõ ràng và project `rdfs:label` hoặc literal; assert
không result nào là URI/BNode. Thêm query URL có origin đúng và query học phí
khóa 66 trả đúng ngành/mức tiền.

- [ ] **Step 3: Chạy toàn bộ ontology suite**

```bash
uv run pytest tests/ontology -q
```

Expected: PASS.

- [ ] **Step 4: Chạy regression runtime và toàn suite**

```bash
uv run pytest tests/runtime/test_query_engine.py tests/runtime/test_render.py -q
uv run pytest -q
```

Expected: ontology/runtime tests PASS. Nếu full suite còn failure ở dataset cũ,
ghi rõ failure đó nhưng không sửa dataset trong task ontology.

- [ ] **Step 5: Kiểm tra phạm vi diff và commit cuối**

```bash
git diff --check
git status --short
git diff --name-only HEAD~5..HEAD
git add resources/ontology/ontology.ttl tests/ontology
git commit -m "Verify official ontology queries"
```

Expected: các commit triển khai chỉ chứa `resources/ontology/ontology.ttl`,
`tests/ontology/**` và việc xóa `tests/tools/test_ontology.py`; file người dùng
vẫn không được stage.
