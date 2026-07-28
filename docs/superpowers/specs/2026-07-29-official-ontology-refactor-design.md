# Refactor ontology từ nguồn học vụ chính thức

## Mục tiêu và nguồn dữ liệu

Xây lại ontology Turtle từ các nguồn được cung cấp:

- `NTUdocs/Qd1052.md`: Quy chế đào tạo đại học, gồm 32 điều và Phụ lục 1–3;
- `NTUdocs/Qd729.md`: mức học phí và danh mục ngành đào tạo;
- `NTUdocs/huong_dan_dong_hoc_phi.md`: hướng dẫn các phương thức thanh toán;
- `NTUdocs/bieumau_url.txt`: URL gốc của trang danh mục biểu mẫu;
- `bieumau_url.html`: ảnh chụp HTML do người dùng cào từ trang danh mục, chứa
  tên biểu mẫu và 19 liên kết tải xuống.

Ontology hiện tại không được dùng làm nguồn sự thật. Chỉ giữ một individual,
property hoặc literal cũ khi đối chiếu được với các nguồn trên. Không thêm dữ
kiện suy đoán về phòng ban, quy trình, thời hạn, kết quả hoặc URL.

Khi nguồn xung đột, Quyết định 1052 quyết định số và ý nghĩa pháp lý của biểu
mẫu; HTML chỉ là nguồn cho mục niêm yết và URL tải. Không ghép hai nguồn chỉ vì
trùng số biểu mẫu.

## Nguyên tắc mô hình lai

Ontology có ba lớp liên kết:

1. **Nguồn chính thức:** giữ cấu trúc và nguyên văn của quyết định, chương,
   điều, khoản, điểm, phụ lục và dòng bảng.
2. **Chỉ mục ngữ nghĩa:** biểu diễn quy trình người học thực hiện và liên kết
   từng khía cạnh tới đúng provision nguồn.
3. **Quy tắc có cấu trúc:** biểu diễn bảng học phí, phân loại, quy mô lớp và quy
   đổi chứng chỉ để SPARQL có thể lọc/so sánh số liệu.

Không sao chép nguyên văn provision thành `content`, `condition` hoặc `outcome`
trên quy trình. Query đi qua object property đến provision rồi project
`officialText`. Nhờ vậy dữ liệu trả lời chỉ có một nguồn, không bị lệch giữa
bản tóm tắt và công văn.

## Namespace và quy ước

- Giữ namespace `http://www.ntu.edu.vn/ontology/academic#`.
- Class và named individual dùng IRI tiếng Anh `PascalCase`.
- Property dùng IRI tiếng Anh `camelCase`.
- Mọi tài nguyên được đặt tên có `rdfs:label@vi`.
- `skos:altLabel@vi` chỉ dùng cho tên gọi/viết tắt thực sự, không chứa câu hỏi.
- Nội dung nguyên văn dùng `rdf:langString` với `@vi`.
- Số tiền là `xsd:nonNegativeInteger`, điểm là `xsd:decimal`, ngày là
  `xsd:date`, chỉ số thứ tự và khóa là kiểu số nguyên phù hợp.
- Không dùng blank-node `owl:unionOf` cho domain/range. Tạo superclass rõ ràng
  hoặc bỏ domain quá hẹp khi một property dùng cho nhiều loại tài nguyên.
- Không dựa vào OWL reasoning để một query production cho kết quả đúng; các
  triple cần truy vấn được khai báo trực tiếp.

## Schema lớp nguồn

### Classes

- `DocumentComponent`
  - `OfficialDocument`
  - `DocumentPart`
- `OfficialDocument`
  - `Decision`
  - `GuidanceDocument`
- `DocumentPart`
  - `AttachedRegulation`
  - `Chapter`
  - `Article`
  - `Clause`
  - `Point`
  - `Appendix`
  - `DocumentTable`
  - `DocumentTableRow`

### Object properties

- `hasPart`: `DocumentComponent → DocumentPart`
- `partOf`: `DocumentPart → DocumentComponent`, inverse định danh của `hasPart`
- `sourceDocument`: tài nguyên ngữ nghĩa/quy tắc → `OfficialDocument`
- `sourceProvision`: tài nguyên ngữ nghĩa/quy tắc → `DocumentPart`

### Datatype properties

- `documentNumber`
- `issueDate`
- `effectiveFromAcademicYear`
- `effectiveFromSemester`
- `validUntilSuperseded`
- `identifier`: ví dụ `Điều 24`, `Khoản 1`, `Điểm a`
- `orderIndex`
- `title`
- `officialText`
- `documentUrl`

### Cấu trúc nguồn cần tạo

`Decision1052` có ba điều ban hành và một `AttachedRegulation`. Quy chế đính
kèm có 5 chương, 32 điều và Phụ lục 1–3. Mỗi khoản/điểm có IRI cấu trúc, ví dụ:

```text
Decision1052Article24Clause01PointA
```

Số văn bản được lưu đúng là `1052/QĐ-ĐHNT`; không giữ biến thể OCR `1051`.

`Decision729` có ba điều ban hành, Phụ lục I về học phí và Phụ lục II về danh
mục ngành. `TuitionPaymentGuidance` có ba provision tương ứng ba nhóm phương
thức thanh toán.

## Schema chỉ mục ngữ nghĩa

### Classes

- `AcademicProcedure`
- `AcademicActor`
  - `OrganizationalUnit`
  - `DecisionAuthority`
- `FormDocument`
- `FormCatalogue`
- `FormCatalogueEntry`

### Object properties

Tất cả property provision dưới đây trỏ tới `DocumentPart` và là subproperty
ngữ nghĩa của `sourceProvision`:

- `eligibilityProvision`
- `instructionProvision`
- `deadlineProvision`
- `resultProvision`

Các đường nối còn lại:

- `requiresForm`
- `hasCatalogueEntry`
- `catalogueEntryForForm`
- `submittedTo`
- `reviewedBy`
- `decidedBy`

### Datatype properties

- `formNumber`
- `webPageUrl`
- `listedFormNumber`
- `listedTitle`
- `downloadUrl`

### Các quy trình cần tạo

1. `CourseRegistrationProcedure` — Điều 9.
2. `ExtraClassOpeningRequestProcedure` — Điều 8, Điều 10, Mẫu 01.
3. `CourseRetakeProcedure` — Điều 11.
4. `GradeImprovementProcedure` — Điều 11.
5. `GraduationProjectRegistrationProcedure` — Điều 14, Mẫu 02.
6. `ClassAbsenceRequestProcedure` — Điều 17, Mẫu 03.
7. `ExamPostponementProcedure` — Điều 17/30, Mẫu 04.
8. `DismissalTransferRequestProcedure` — Điều 20, Mẫu 05.
9. `CreditRecognitionProcedure` — Điều 21, Mẫu 06.
10. `CourseExemptionAndBonusProcedure` — Điều 21, Mẫu 07.
11. `GraduationReviewProcedure` — Điều 22.
12. `EarlyGraduationReviewProcedure` — Điều 22, Mẫu 08.
13. `TemporaryAcademicLeaveProcedure` — Điều 24/30, Mẫu 09.
14. `StudyWithdrawalProcedure` — Điều 24, Mẫu 10.
15. `StudyResumptionProcedure` — Điều 24, Mẫu 11.
16. `MajorChangeProcedure` — Điều 25, Mẫu 12.
17. `UniversityTransferProcedure` — Điều 26, Mẫu 13.
18. `StudentExchangeProcedure` — Điều 27, Mẫu 14.
19. `SecondProgramRegistrationProcedure` — Điều 28, Mẫu 15.
20. `TuitionPaymentProcedure` — hướng dẫn thanh toán và Quyết định 729.

Không tạo quy trình “rút môn học” hoặc “xét học bổng” vì nguồn hiện có không
quy định các nội dung mà ontology cũ từng lưu.

### Actor nguồn xác nhận

Chỉ tạo actor xuất hiện trong nguồn, gồm tối thiểu:

- `Student`
- `University`
- `UniversityPresident`
- `AcademicManagementUnit`
- `StudentAffairsOffice`
- `FacultyOrInstitute`
- `Department`
- `ProfessionalCouncil`
- `GraduationCouncil`

`AcademicManagementUnit` giữ đúng tên vai trò trong Quyết định 1052; không tự
đồng nhất nó với một phòng cụ thể nếu điều khoản không nói rõ.

## Biểu mẫu

Tạo `UndergraduateFormCatalogue` với:

```text
https://pdtdaihoc.ntu.edu.vn/van-ban-phap-quy
```

Tạo `Decision1052Form01` đến `Decision1052Form15`. Đây là 15 biểu mẫu chuẩn của
Quyết định 1052; mỗi form có số và label lấy từ đúng điều khoản viện dẫn.

Tạo một `FormCatalogueEntry` cho từng liên kết trong `bieumau_url.html`. Mỗi
entry giữ `listedTitle`, số niêm yết nếu có và `downloadUrl` tuyệt đối được
resolve trên origin `https://pdtdaihoc.ntu.edu.vn`. Chuỗi điều hướng `../` trong
HTML được chuẩn hóa về đường dẫn gốc `/uploads/...`; không nối nó phía sau
`/van-ban-phap-quy`. Ví dụ một href trỏ tới
`../../uploads/38/files/Van-Ban-Truong/...` phải trở thành
`https://pdtdaihoc.ntu.edu.vn/uploads/38/files/Van-Ban-Truong/...`. Các mục bổ
sung như phiếu điều chỉnh điểm vẫn là catalogue entry nhưng không tự động trở
thành biểu mẫu của Quyết định 1052.

Danh mục HTML có ngày đăng 21/08/2020 và đánh số theo phiên bản cũ. Ví dụ, đơn
xin nghỉ học tạm thời là Mẫu 8 trên trang nhưng là Mẫu 9 trong Quyết định 1052.
Vì vậy `catalogueEntryForForm` chỉ được thêm sau khi đối chiếu ý nghĩa/tên gọi;
không join theo `formNumber`. Nếu tên gọi chưa đủ chắc chắn hoặc trang không có
liên kết, form chuẩn vẫn tồn tại nhưng không nối tới catalogue entry tải xuống.
Trường hợp một form có nhiều bản tải thì giữ nhiều catalogue entry, không ghi
đè URL.

## Schema học phí

### Classes

- `AcademicProgram`
- `DisciplineGroup`
- `EducationLevel`
- `CourseCategory`
- `TuitionRate`
- `BillingUnit`
- `DoctoralTuitionDurationRule`

### Object properties

- `belongsToDisciplineGroup`
- `appliesToProgram`
- `appliesToDisciplineGroup`
- `appliesToEducationLevel`
- `appliesToCourseCategory`
- `billingUnit`
- `appliesToEntryQualification`

### Datatype properties

- `amount`
- `currencyCode` (`VND`)
- `minimumCohortNumber`
- `durationInYears`

### Dữ liệu

- Tạo đủ 41 `AcademicProgram` trong Phụ lục II của Quyết định 729 và nối đúng
  bốn khối ngành.
- Tạo mức học phí chuẩn theo trình độ, khối ngành, loại học phần và đơn vị thu.
- Tạo mức chương trình kiểm định theo từng ngành và khóa bắt đầu; không dùng các
  tên nhóm vô nghĩa như `K65TuitionBand1`.
- Một mức “từ khóa 65 trở về sau” dùng `minimumCohortNumber 65`, không dùng mã
  khóa chính xác.
- Tạo học phí tiến sĩ theo năm, bao gồm trường hợp dự án Noherd.
- Tạo quy tắc thu 3 hoặc 4 năm theo trình độ đầu vào và quy tắc 4 năm cho ngành
  Kinh tế và quản lý tài nguyên biển.
- Quyết định 729 có hiệu lực từ Học kỳ I năm học 2025–2026 đến khi có quy định
  mới; mọi mức phí liên kết trực tiếp `Decision729`.

## Schema thanh toán học phí

### Classes

- `PaymentMethod`
- `Bank`
- `PaymentFeeRule`

### Properties

- `supportsPaymentMethod`
- `supportsBank`
- `paymentInstructionProvision`
- `feePolicyText`
- `feeAmount`
- `paymentWarningText`

Tạo riêng VNPAY, QR, Mobile/Internet Banking và nộp tiền mặt tại quầy. Tạo ba
ngân hàng Agribank, VietinBank, LienVietPostBank. Bảo toàn chính xác chính sách
phí và cảnh báo dùng mã sinh viên/không đưa tài khoản của Trường cho ngân hàng.
Không giữ thông tin “trễ hạn bị cấm thi” hoặc biểu mẫu gia hạn vì nguồn không có.

## Schema bảng quy tắc học vụ

### Classes

- `AcademicPerformanceBand`
- `StudyYearBand`
- `GraduationClassificationBand`
- `ClassSizeRule`

### Properties dùng chung

- `minimumValue`
- `maximumValue`
- `minimumInclusive`
- `maximumInclusive`
- `resultLabel`
- `criterionText`

Tạo cấu trúc cho bảng xếp loại học lực Điều 18, xếp năm Điều 19, xếp loại tốt
nghiệp Điều 23 và quy mô lớp Phụ lục 1. `criterionText` luôn giữ cách viết của
nguồn; numeric boundary phục vụ FILTER SPARQL.

## Schema quy đổi chứng chỉ

### Classes

- `Certificate`
  - `LanguageCertificate`
  - `ComputerCertificate`
- `LearnerCategory`
- `LanguageCompetencyLevel`
- `CourseExemption`
- `CertificateConversionRule`

### Object properties

- `appliesToCertificate`
- `appliesToLearnerCategory`
- `appliesToProgram`
- `grantsCourseExemption`
- `mapsToCompetencyLevel`

### Datatype properties

- `minimumScore`
- `maximumScore`
- `minimumInclusive`
- `maximumInclusive`
- `requiredLevelCode`
- `convertedGrade`
- `satisfiesOutputStandard`
- `criterionText`
- `officialCertificateName`

Tạo rule riêng theo từng ô có dữ liệu trong Phụ lục 2–3. Ngữ cảnh được phân
biệt giữa sinh viên không chuyên ngữ chương trình chuẩn, sáu chương trình đặc
biệt và sinh viên ngành Ngôn ngữ Anh. Các ô categorical như `HSK 3`, `N4`,
`TOPIK 3` dùng `requiredLevelCode`; ô điểm số dùng numeric boundary khi rõ ràng.

Mọi rule vẫn giữ `criterionText` đúng nguyên văn, kể cả khi đã có numeric field.
Ô chứa nhiều ngưỡng hoặc ký hiệu so sánh cần được tách thành rule chỉ khi việc
tách không làm mất ý nghĩa của bảng; nếu chưa chắc chắn, giữ nguyên criterion
và không tự suy diễn boundary.

Phụ lục 3 tạo rule cho ba khoảng điểm của IC3, ICDL, MOS và điểm quy đổi 8, 9,
10. Danh mục viết tắt trong Phụ lục 2 trở thành các `Certificate` có label và
tên đầy đủ chính thức.

## Alias và ngôn ngữ

- Label dùng đúng tên tiếng Việt chính thức.
- Alias chỉ giữ dạng có ích như `CTĐT`, `ĐATN`, `CĐTN`, `ĐKHP`, `bảo lưu`,
  `học lại`, `học cải thiện`, `CNTT`, tên viết tắt chứng chỉ và ngân hàng.
- Không dùng alias để chứa câu hỏi, mức điểm hoặc điều kiện.
- Các viết tắt chat như `hp`, `đk`, `hc` thuộc preprocessing, không cần lặp lại
  thành alias cho mọi entity.

## Dữ liệu cũ phải loại bỏ hoặc sửa

Loại bỏ:

- `CourseWithdrawalProcedure`
- `ScholarshipReviewProcedure`
- `TuitionPaymentExtensionForm`
- URL tải trực tiếp của biểu mẫu cũ
- contact/head/location của phòng ban không có trong nguồn
- các tuition band và program-name literal cũ
- literal được diễn giải hoặc bịa thêm như “trễ hạn bị cấm thi”

Sửa bằng dữ liệu nguồn:

- `CourseRetakeProcedure` phải dựa trên Quyết định 1052, không phải 729.
- Bảo lưu phải dùng đúng Mẫu 09; thôi học Mẫu 10; học trở lại Mẫu 11.
- Đăng ký học phần phải có đầy đủ giới hạn 15–27, 12–18, tối đa 32, ngoại lệ
  học kỳ cuối/phụ và điều kiện tiên quyết.
- Chuyển ngành phải giữ đủ bốn nhóm điều kiện và thời hạn hai tuần.
- Xét tốt nghiệp phải giữ đầy đủ điều kiện, chu kỳ xét, thẩm quyền và thời hạn.
- Học phí/phương thức thanh toán phải khớp toàn bộ Quyết định 729 và hướng dẫn.

## Kiểm chứng

Ontology mới chỉ được chấp nhận khi:

1. RDFLib parse Turtle thành công.
2. OWL RL closure không gây lỗi hoặc sinh mâu thuẫn kiểu hiển nhiên.
3. Mọi named resource có `rdfs:label@vi`; mọi official text có `@vi`.
4. Không còn IRI cũ bị liệt kê trong mục loại bỏ.
5. Mọi semantic procedure/rule có đường truy nguồn tới document/provision.
6. Có đủ 32 điều, Phụ lục 1–3 của 1052, hai phụ lục của 729 và ba provision
   hướng dẫn thanh toán.
7. Có đủ 15 form chuẩn, 19 catalogue entry có URL, 41 chương trình và toàn bộ
   rate/rule trong các bảng nguồn.
8. SPARQL smoke test trả đúng cho tối thiểu: đăng ký học phần, học lại, bảo lưu,
   chuyển ngành, tốt nghiệp, biểu mẫu, học phí theo ngành/khóa, phương thức
   thanh toán, xếp loại điểm, quy mô lớp, ngoại ngữ và tin học.
9. Query chỉ project label hoặc literal; object property chỉ tạo đường đi.
10. Mọi URL tải biểu mẫu dùng origin `https://pdtdaihoc.ntu.edu.vn`, có đường
    dẫn gốc `/uploads/...` (giữ nguyên hoa/thường của href nếu có) và không còn
    đoạn `../`.
11. Không thay đổi code/dataset/model trong commit refactor ontology.
