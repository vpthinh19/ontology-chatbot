# Ontology

## Nguồn sự thật

Ontology được xây từ công văn và tài liệu học vụ chính thức trong `references/`.
Chỉ những thông tin có căn cứ trong nguồn này mới được đưa vào đồ thị.

`resources/ontology/ontology.ttl` là **cơ sở dữ liệu duy nhất** của chatbot: mọi
truy vấn SPARQL đều chạy trên tệp này. Ontology không có phiên bản. Khi công văn
thay đổi, sửa trực tiếp tại đây rồi chạy bộ kiểm tra ở cuối tài liệu này.

## Ba tầng

```
TẦNG VĂN BẢN     nguyên văn công văn, dùng làm chứng cứ
  Decision / GuidanceDocument / FormCatalogue
  Article, Clause, Point, Appendix, DocumentTable
  officialText, citationLabel, articleNumber, clauseNumber, pointLetter

TẦNG TRÍCH DẪN   không phải class riêng: chính phần văn bản là trích dẫn
  mọi dữ kiện nghiệp vụ ──:basedOn──▶ DocumentPart

TẦNG NGHIỆP VỤ   đây là ĐÁP ÁN trả cho người dùng
  AcademicProcedure ──hasStep──▶ ProcedureStep
                    ──hasRequirement──▶ Requirement
                    ──hasDeadline──▶ Deadline
                    ──hasOutcome──▶ Outcome
                    ──hasConsequence──▶ Consequence
  AcademicCase ──hasResolution──▶ CaseResolution ──resolvedBy──▶ AcademicProcedure
```

Thứ tự xây dựng bắt buộc:

```text
tài liệu chính thức → ontology → danh mục khả năng trả lời
                    → danh mục truy vấn → dataset
```

SPARQL và câu hỏi huấn luyện phải đi theo graph đã xác nhận, không dùng dataset
để quyết định ngược lại hình dạng ontology.

## Vì sao tách ba tầng

Nguyên tắc dẫn đường: **mỗi câu hỏi khác nhau phải chạm vào dữ liệu khác nhau.**

Bản trước đó trả lời câu hỏi về một quy trình bằng nguyên văn cả điều luật, có
trường hợp dài 5.957 ký tự. Bốn ý định khác nhau — cách thực hiện, điều kiện,
thời hạn, kết quả — cùng trả về một khối văn bản, nên ranh giới giữa chúng không
học được. Điều 24 chứa ba thủ tục, khiến câu trả lời về bảo lưu lẫn cả nội dung
thôi học. Nguồn thì chỉ nằm trong tên IRI nên không thể hỏi "quy định này ở điều
mấy".

Tầng nghiệp vụ tách các dữ kiện đó ra; tầng văn bản giữ nguyên văn làm chứng cứ;
`:basedOn` nối hai bên và **cả hai đều trả lời được**.

## Quy mô hiện tại

| Thành phần | Số lượng |
|---|---:|
| Bộ ba RDF | 7.519 |
| Lớp | 46 |
| Quan hệ giữa các thực thể | 34 |
| Thuộc tính dữ liệu | 50 |
| Thực thể có định danh | 822 |

| Tầng văn bản | Số lượng |
|---|---:|
| Điều | 35 |
| Khoản | 114 |
| Điểm | 103 |
| Phụ lục | 5 |
| Bảng | 13 |

| Tầng nghiệp vụ | Số lượng |
|---|---:|
| Quy trình học vụ | 22 |
| Chính sách học vụ | 2 |
| Bước thực hiện | 44 |
| Điều kiện | 33 |
| Trường hợp áp dụng | 4 |
| Hướng xử lý của trường hợp | 6 |
| Thời hạn | 7 |
| Kết quả xử lý | 10 |
| Hệ quả về sau | 2 |

Danh mục khả năng trả lời tại `resources/ontology/answer_inventory.json` được
sinh từ đồ thị. Có 3.047 khả năng được hỗ trợ; 260 mục là nhãn của bản ghi kỹ
thuật nội bộ hoặc quyết định nghiệp vụ không đủ dữ liệu, được ghi `excluded`
kèm lý do. Danh mục truy vấn tại `resources/dataset/catalogue.jsonl` gồm 167 họ
và phủ toàn bộ các khả năng được hỗ trợ.

## Quy tắc biên soạn tầng nghiệp vụ

Tầng văn bản chỉ chép nguyên văn nên khó sai. Tầng nghiệp vụ diễn giải công văn
thành đáp án, nên nó là nơi duy nhất có thể sai nội dung học vụ mà không ai phát
hiện. Mỗi quy tắc dưới đây đều được kiểm tra tự động, và mỗi quy tắc tồn tại vì
một lỗi **đã thực sự xảy ra** khi soạn thảo — không phải quy tắc phòng xa.

### Ranh giới giữa các loại node

Nếu người biên soạn còn phân vân giữa hai loại thì model chắc chắn sẽ học sai.
Dùng đúng một câu hỏi để quyết định:

| Loại | Trả lời câu hỏi | Không được chứa |
|---|---|---|
| `AcademicCase` | *hoàn cảnh nào kích hoạt thủ tục?* | nghĩa vụ phải làm, giấy tờ phải nộp |
| `Requirement` | *điều gì phải đúng thì mới được xét?* | hành động, thời hạn |
| `ProcedureStep` | *ai làm gì, theo thứ tự nào?* | điều kiện được xét |
| `Deadline` | *phải làm trước hoặc trong bao lâu?* | nội dung hành động |
| `Outcome` | *đơn được giải quyết ra sao?* | hệ quả về sau |
| `Consequence` | *về sau sinh viên chịu ảnh hưởng gì?* | quyết định trên đơn |

`Outcome` và `Consequence` tách nhau vì bản nháp từng gán "muốn quay lại phải xét
tuyển đầu vào như thí sinh khác" làm `Outcome` của thủ tục thôi học — đó không
phải kết quả xử lý đơn mà là hệ quả về sau.

### Mỗi dữ kiện phải dẫn được về công văn

Mọi node tầng nghiệp vụ phải có `:basedOn` trỏ tới phần văn bản **nhỏ nhất thực
sự chứng minh dữ kiện đó**, không trỏ chung tới cả Điều. Trích dẫn dừng ở mức
bảng: người đọc chỉ cần biết dữ kiện nằm ở bảng nào, mục nào.

Dữ liệu không đến từ công văn — địa chỉ, điện thoại phòng ban lấy từ website —
để ở `OrganizationalUnit`, lớp này không nằm trong danh sách bắt buộc dẫn nguồn.

### Điều kiện phải nói rõ nó áp dụng cho ai

Điều kiện chỉ áp dụng cho một trường hợp phải khai `:scopedToCase`. Bản nháp từng
gắn "phải học ít nhất 01 học kỳ" cho toàn bộ thủ tục nghỉ học tạm thời, trong khi
Điều 24 chỉ áp cho điểm d — lý do cá nhân. Hậu quả: người đi nghĩa vụ quân sự bị
trả nhầm điều kiện không liên quan.

### Một hoàn cảnh dẫn tới nhiều thủ tục thì phải nói rõ khi nào áp dụng cái nào

Một `AcademicCase` được phép dùng chung giữa nhiều thủ tục và **không** được nhân
bản giả tạo. Nhưng khi nó dẫn tới nhiều thủ tục, mỗi `CaseResolution` phải khai
`:conditionText` nói rõ khi nào áp dụng.

"Ốm" dẫn tới ba thủ tục, và chính công văn đã có tiêu chí phân nhánh:

```text
:IllnessCase :hasResolution
    ├─ "Ốm trong quá trình học và điều trị dưới 10 ngày."
    │    → :SickLeaveProcedure                  (Điều 30 khoản 1)
    ├─ "Ốm phải điều trị dài ngày từ 10 ngày trở lên."
    │    → :TemporaryAcademicLeaveProcedure     (Điều 30 khoản 1)
    └─ "Ốm trong đợt thi kết thúc học phần."
         → :ExamPostponementProcedure           (Điều 30 khoản 2)
```

Với câu hỏi mơ hồ, truy vấn hợp lệ là **liệt kê điều kiện phân nhánh kèm tên thủ
tục**, không trả thẳng các bước — vì không tồn tại một câu trả lời đúng duy nhất.

### Không chép cùng một nội dung vào hai chỗ

Thời hạn nằm ở `Deadline`, không được chép lại vào `stepText`. Hai bản sao sẽ
lệch nhau khi cập nhật.

### Tên gọi thay thế chỉ là tên gọi, không phải cách hỏi

Không đặt chỉ tiêu số lượng. Chỉ tiêu "≥8 nhãn" khuyến khích thêm nhãn lỏng nghĩa
như "bị tai nạn" cho trường hợp *"tai nạn phải điều trị thời gian dài"* — dataset
sinh từ đó sẽ dạy model trả lời sai một cách tự tin. Cách diễn đạt tình huống và
biến thể khẩu ngữ thuộc **tầng dataset**, không thuộc ontology.

### Các bước phải được đánh số liên tục

`:stepOrder` phải là 1..n liên tục trong mỗi thủ tục; `:requirementOrder` phải
duy nhất. Kết quả SPARQL vốn không có thứ tự, nên mọi truy vấn trả danh sách bắt
buộc `ORDER BY` theo thuộc tính này — không được dựa vào thứ tự IRI.

### Mọi nội dung tiếng Việt phải được đánh dấu ngôn ngữ

Mọi literal nội dung tiếng Việt phải gắn `@vi`.

## Quy ước đặt tên

- Class và individual dùng IRI tiếng Anh dạng `PascalCase`.
- Property dùng IRI tiếng Anh dạng `camelCase`.
- `rdfs:label@vi` là tên tiếng Việt chính, đầy đủ và ổn định.
- Namespace project phải ổn định sau khi dataset bắt đầu được tạo; đổi IRI sau
  thời điểm đó đòi hỏi kiểm tra lại toàn bộ target.

## Node kỹ thuật nội bộ

`ProcedureStep`, `Requirement`, `Deadline`, `Outcome`, `Consequence`,
`CaseResolution` là node nội bộ của một quy trình: người dùng không gọi tên
chúng, nên chúng không bao giờ là neo của một khả năng trả lời — nội dung của
chúng được hỏi thông qua quy trình chứa chúng.

`TuitionRate`, `CertificateConversionRule` và các bảng ngưỡng là **bản ghi kỹ
thuật**: chúng vẫn là neo, nhưng nhãn của chúng bị loại. SPARQL phải tìm tới
chúng bằng điều kiện nghiệp vụ chứ model không học thuộc IRI của từng bản ghi.

## Kiểm tra tính toàn vẹn

Ontology được kiểm tra theo các tiêu chí sau trước khi tạo dataset:

1. Turtle đọc được và sử dụng đúng namespace quy định.
2. Mọi lớp và quan hệ được dùng đều đã khai báo, và ngược lại.
3. Mọi class, property và named individual có `rdfs:label@vi`.
4. IRI duy nhất, tiếng Anh và đúng quy ước chữ hoa/thường.
5. Không có quan hệ nào trỏ tới một node không tồn tại.
6. `officialText` là văn bản thuần — không còn ký tự markdown.
7. Mỗi dữ kiện nghiệp vụ truy ngược được về tài liệu chính thức bằng `:basedOn`.
8. Các truy vấn trong danh mục chạy được và chỉ trả về nhãn hoặc literal.
9. Mỗi khả năng trả lời được ghi vào danh mục với trạng thái `supported` hoặc
   `excluded` kèm lý do.

Sau mỗi lần sửa đồ thị, chạy hai lệnh sau. Lệnh đầu kiểm tra lược đồ, quy tắc
biên soạn và câu trả lời của từng miền; lệnh sau kiểm tra cả chuỗi từ ontology
tới dataset.

```bash
uv run pytest tests/ontology
uv run validate_sparql_dataset
```

## Danh mục biểu mẫu

Phụ lục 4 "Danh mục biểu mẫu" chỉ được liệt kê trong mục lục công văn, nội dung
thật nằm trên trang văn bản pháp quy của Phòng Đào tạo Đại học. Website đánh số
biểu mẫu **khác** Phụ lục 4, nên `FormCatalogueEntry` (số theo web) và
`FormDocument` (số theo quyết định) là hai lớp tách biệt, nối bằng
`catalogueEntryForForm`. Tuyệt đối không gộp hai lớp này.

## Giới hạn đã biết

- Công thức tính điểm trung bình ở Điều 18 khoản 1 không có trong đồ thị: bản
  chuyển đổi của công văn đã làm hỏng ký hiệu toán nên không khôi phục được.
  Phần diễn giải các ký hiệu được giữ.
- Chưa mô hình hoá hiệu lực theo thời gian (`effectiveUntil`, `supersedes`).
  Hiện mỗi công văn chỉ có một phiên bản nên chưa cần, nhưng lược đồ phải chừa
  chỗ trước khi có văn bản sửa đổi.
- 167 họ truy vấn là nhiều so với nhu cầu thực; một phần sinh máy để bảo đảm độ
  phủ và cần rà lại khi thiết kế dataset.
