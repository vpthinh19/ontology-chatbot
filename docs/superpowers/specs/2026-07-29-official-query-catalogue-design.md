# Catalogue truy vấn SPARQL chính thức

## Mục tiêu

Xây catalogue SPARQL làm cầu nối một chiều từ ontology canonical tới dataset:

```text
ontology → answer inventory → query catalogue → dataset
```

Catalogue phải diễn đạt các câu hỏi người dùng thực sự có thể hỏi, phủ toàn bộ
dữ liệu production được đánh dấu `supported`, và không biến từng node lưu trữ
kỹ thuật thành một IRI mà model phải học thuộc.

Phạm vi công việc này chỉ gồm inventory, catalogue và bộ kiểm tra tương ứng.
Không biên soạn lại câu hỏi, full fine-tune hoặc benchmark model trong bước này.

## Quyết định kiến trúc

Catalogue được tổ chức theo **ý định nghiệp vụ**, không theo từng triple và
không theo từng node kỹ thuật. Một họ truy vấn có thể bao phủ nhiều anchor và
nhiều mục inventory thông qua slot hữu hạn hoặc mẫu graph.

Có hai loại IRI:

1. **IRI ngữ nghĩa** là đối tượng người dùng có thể nhắc tới trực tiếp, chẳng
   hạn quy trình, chính sách, chứng chỉ, ngành học và biểu mẫu. Model được phép
   sinh các IRI này trong slot đã khai báo hữu hạn.
2. **IRI bản ghi kỹ thuật** dùng để lưu một dòng dữ liệu hoặc quy tắc, chẳng
   hạn `CertificateConversionRule`, `TuitionRate`, các band phân loại và quy
   tắc sĩ số. Model không sinh IRI của từng bản ghi. SPARQL tìm bản ghi phù hợp
   từ điều kiện nghiệp vụ trong câu hỏi.

Ví dụ, câu hỏi về IELTS 6.0 cung cấp `:IELTSCertificate` và số `6.0`; query tìm
`CertificateConversionRule` phù hợp. Model không phải biết IRI của rule.

## Contract catalogue

Catalogue canonical tiếp tục nằm tại:

```text
resources/dataset/main/catalogue.jsonl
```

Mỗi dòng mô tả một họ truy vấn và giữ các trường hiện có:

- `query_id`: định danh ý định ổn định;
- `domain`: miền hiển thị và báo cáo;
- `target_template`: SPARQL canonical hoặc marker từ chối;
- `slots`: IRI ngữ nghĩa hữu hạn và giá trị số động.

Contract được bổ sung trường `coverage`. Trường này chứa các selector khai báo
những khả năng trong answer inventory mà họ truy vấn bao phủ. Mỗi selector gồm:

- một hoặc nhiều class của anchor;
- một hoặc nhiều đường dữ liệu kết thúc ở label/literal;
- điều kiện tùy chọn giới hạn anchor cụ thể khi một class có nhiều vai trò.

Coverage là metadata kiểm chứng; nó không xuất hiện trong output model và
không được dùng để sinh target tự do. Các selector được đối chiếu trực tiếp với
graph và inventory nên không tạo một danh sách sao chép 2.531 ID.

Hình dạng selector được khóa như sau:

```json
{
  "anchor_classes": ["AcademicProcedure"],
  "paths": [["instructionProvision", "officialText"]],
  "anchors": ["TemporaryAcademicLeaveProcedure"]
}
```

`anchor_classes` và `paths` là danh sách không rỗng. `anchors` được phép bỏ;
khi có, nó chỉ thu hẹp selector vào các semantic anchor đã nêu và mọi anchor
phải thuộc một trong các class khai báo. Không thêm biểu thức lọc hoặc ngôn ngữ
selector tổng quát khác.

`no-information` không khai báo coverage ontology và luôn có target chính xác
`không có thông tin`.

## Các nhóm họ truy vấn

Catalogue cần bao phủ tối thiểu các nhóm sau.

### Quy trình và chính sách học vụ

- nội dung/hướng dẫn tổng quát;
- điều kiện;
- thời hạn;
- kết quả có căn cứ;
- biểu mẫu và URL tải;
- đơn vị tiếp nhận, đơn vị xem xét và thẩm quyền quyết định;
- căn cứ chính thức;
- danh sách label khi người dùng hỏi nhiều thực thể.

Các slot quy trình/chính sách là IRI ngữ nghĩa hữu hạn. Object property chỉ là
đường đi; `SELECT` chỉ project `rdfs:label`, literal hoặc giá trị tổng hợp.

### Học phí và thanh toán

- mức học phí theo ngành, nhóm ngành, khóa, trình độ và loại học phần;
- đơn vị tiền và căn cứ áp dụng;
- phương thức thanh toán, ngân hàng, phí và cảnh báo;
- thời lượng tính học phí tiến sĩ khi nguồn có dữ liệu.

`TuitionRate` và `PaymentFeeRule` là bản ghi kỹ thuật được SPARQL lựa chọn bằng
điều kiện, không phải slot IRI của model.

### Biểu mẫu và văn bản

- danh sách/tên/số biểu mẫu;
- URL trang danh mục và URL tải;
- tiêu đề, số, ngày ban hành, thời điểm hiệu lực và nội dung căn cứ của văn bản
  khi inventory cho phép trả lời.

### Quy tắc học vụ định lượng

- xếp loại học lực;
- xác định năm đào tạo;
- xếp loại tốt nghiệp;
- sĩ số lớp;
- các ngưỡng và nhãn kết quả có trong graph.

Các band/rule được tìm bằng giá trị đầu vào, class và các điều kiện min/max.

### Quy đổi chứng chỉ

- bậc năng lực từ chứng chỉ và điểm;
- tiêu chí hoặc ngưỡng cần đạt;
- miễn học phần và đáp ứng chuẩn đầu ra;
- ngữ cảnh chương trình, ngành và nhóm người học;
- quy đổi điểm chứng chỉ tin học.

`CertificateConversionRule` luôn được tìm qua quan hệ và điều kiện. Catalogue
không chấp nhận IRI của từng conversion rule làm slot.

## Điều chỉnh answer inventory

Inventory hiện mô tả 2.531 mục `supported` trên 50 hình dạng đường dữ liệu.
Phần lớn là các thuộc tính lặp của bản ghi kỹ thuật. Những dữ liệu nghiệp vụ
trong các bản ghi này vẫn phải được catalogue bao phủ qua truy vấn quan hệ.

Label chỉ dùng để đặt tên cho bản ghi kỹ thuật nội bộ không phải là câu trả lời
production. Các mục như vậy phải chuyển thành `excluded` với lý do máy đọc
được, thay vì tạo họ truy vấn chỉ để trả tên tự sinh của rule. Không loại thuộc
tính nghiệp vụ, ngưỡng, kết quả, provenance hoặc label của thực thể ngữ nghĩa.

Mọi thay đổi inventory phải được sinh xác định từ graph và quy tắc phân loại đã
kiểm thử; không sửa tay file manifest.

## Luồng kiểm chứng

Validator thực hiện đúng chiều:

```text
supported inventory entry
        ↓ khớp duy nhất hoặc có chủ đích với coverage selector
query family
        ↓ instantiate slot/test case hợp lệ
SPARQL canonical
        ↓ parse + safety contract
ontology canonical
        ↓ execute
label / literal / numeric result
```

Các kiểm tra bắt buộc:

1. Mọi mục inventory `supported` có ít nhất một họ catalogue bao phủ.
2. Selector không khớp mục nào là lỗi.
3. IRI slot chỉ chứa semantic anchor đúng class; IRI bản ghi kỹ thuật bị từ
   chối bởi contract.
4. Mọi template parse được và chỉ dùng `SELECT` đọc dữ liệu.
5. Không cho phép update, service bên ngoài, graph động hoặc project URI thô.
6. Mỗi finite slot được instantiate và chạy có kết quả.
7. Query số có các case đại diện và case biên được khai báo trong test, gồm
   min/max, fallback và trường hợp không khớp.
8. Kết quả cuối chỉ là label, literal hoặc số; object property không được trả
   trực tiếp.
9. Catalogue sinh kết quả xác định và không phụ thuộc dataset câu hỏi hiện có.

Một inventory entry có thể được nhiều family sử dụng khi cùng dữ liệu phục vụ
nhiều cách hỏi. Coverage không bắt buộc duy nhất, nhưng mọi chồng lấn phải được
báo cáo để tránh family trùng ý nghĩa ngoài chủ đích.

## Ranh giới với dataset

455 câu hiện tại tiếp tục là candidate pool trong khi catalogue được xây. Sau
khi catalogue vượt validator:

1. rà từng target candidate theo catalogue mới;
2. giữ, sửa hoặc loại từng câu;
3. biên soạn coverage train/validation/test theo catalogue chính thức.

Không dùng candidate target để thêm ngược capability vào catalogue. Không đặt
trước kích thước dataset từ số mục inventory: nhiều mục dữ liệu có thể dùng
cùng một họ truy vấn và một target có thể cần nhiều cách diễn đạt độc lập.

## Tiêu chí hoàn tất

Catalogue đạt cổng nghiệm thu khi:

- inventory không còn mục `supported` chưa được ánh xạ;
- không có IRI bản ghi kỹ thuật trong slot model;
- mọi query parse, an toàn và chạy đúng trên ontology;
- các truy vấn động vượt test nhánh và biên;
- catalogue, inventory và tài liệu trạng thái đồng bộ;
- toàn bộ test hiện có cùng test catalogue mới đều qua.

Kết quả của bước này là một contract truy vấn production có thể dùng để xây
dataset chính thức. Nó chưa phải bằng chứng model hoặc webapp đã sẵn sàng.
