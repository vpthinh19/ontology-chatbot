# Thiết kế hoàn thiện cấu trúc và chỉ mục ngữ nghĩa ontology

**Ngày:** 2026-07-29  
**Trạng thái:** Đã được người dùng duyệt
**Phạm vi:** `resources/ontology/ontology.ttl`, kiểm thử ontology và inventory
khả năng trả lời. Dataset hiện tại chỉ được chỉnh tối thiểu nếu một target ứng
viên trở thành truy vấn rỗng do sửa lỗi ontology.

## 1. Mục tiêu

Hoàn thiện ontology trước khi xây lại query catalogue và dataset chính thức:

1. cấu trúc tài liệu nguồn phản ánh đúng điều, khoản và điểm trong `NTUdocs`;
2. người đọc có thể truy vấn các khái niệm học vụ bằng IRI có nghĩa, không phải
   nhớ số điều khoản;
3. nội dung trả lời vẫn chỉ đến từ literal hoặc label trong ontology;
4. mọi khả năng trả lời được kiểm kê bằng dữ liệu máy đọc được;
5. không để dataset ứng viên quyết định ngược lại hình dạng ontology.

## 2. Các phương án đã xem xét

### Chỉ truy vấn provision nguồn

Model sinh trực tiếp IRI như `Decision1052Article20Clause02`. Graph nhỏ hơn,
nhưng target phụ thuộc số hiệu văn bản và khó đọc. Khi văn bản được thay thế,
ý nghĩa của IRI trong dataset cũng khó duy trì.

### Chỉ mục ngữ nghĩa tối giản trên lớp nguồn — chọn

Giữ nguyên cây tài liệu chính thức và thêm một số node có nghĩa đối với người
dùng, chẳng hạn chính sách cảnh báo hoặc quy trình học liên thông. Node ngữ
nghĩa chỉ nối tới provision nguồn; không sao chép `officialText`.

### Chuyển phần lớn điều khoản thành node ngữ nghĩa

Truy vấn thuận tiện nhưng graph phình to, tăng trùng lặp và tạo nhiều quyết
định chủ quan. Phương án này trái với nguyên tắc tối giản của dự án.

## 3. Hình dạng graph

Ontology tiếp tục có hai lớp trong cùng một RDF graph:

```text
[Chính sách / quy trình / quy tắc]
                 │
        sourceProvision hoặc
        *Provision theo vai trò
                 │
                 ▼
[Văn bản] → [Điều] → [Khoản] → [Điểm] → officialText@vi
```

Lớp nguồn giữ nội dung chính thức và provenance. Lớp ngữ nghĩa là chỉ mục mỏng
để SPARQL tìm đúng phần nguồn. Object property là đường đi; giao diện chỉ nhận
label, literal hoặc giá trị tổng hợp từ SPARQL.

## 4. Sửa cấu trúc tài liệu nguồn

### Điều 20

Tạo `Decision1052Article20Clause02` và hai điểm con `PointA`, `PointB`.

Nội dung Khoản 2 hiện đang bị trộn vào `Decision1052Article20Clause01` và các
điểm con của Khoản 1. Việc sửa phải:

- giữ Khoản 1 chỉ gồm phần cảnh báo và ba điểm a, b, c;
- chuyển hai trường hợp buộc thôi học sang Khoản 2, điểm a và b;
- cập nhật `hasPart`, `partOf`, `orderIndex`, `identifier`, label và
  `officialText@vi`;
- giữ Khoản 3 là thủ tục xin chuyển chương trình sau khi bị buộc thôi học.

Không được chỉ thêm một node Khoản 2 trong khi để nội dung tiếp tục bị lặp tại
Khoản 1.

### Bốn điểm `đ)` bị thiếu

Bổ sung đúng nội dung đang nằm trong `officialText` của node cha cho:

- `Decision1052Article06Clause02PointDD`;
- `Decision1052Article08Clause01PointDD`;
- `Decision1052Article12Clause02PointDD`;
- `Decision1052Article22Clause01PointDD`.

Quy ước `PointDD` phân biệt chữ Việt `đ)` với `PointD` là `d)`. Các node cha
phải liệt kê cả hai theo đúng thứ tự; nội dung ở các điểm sau không được dịch
chuyển hoặc đổi nghĩa.

### Kiểm tra cấu trúc tổng quát

Kiểm thử phải đọc các dòng đánh số ở đúng cấp hiện tại: khoản ở đầu dòng trong
`officialText` của điều, và điểm ở đầu dòng trong `officialText` của khoản.
Danh sách đó được so với `identifier` của các node con trực tiếp. Kiểm tra này
áp dụng cho toàn bộ 32 điều, không hard-code riêng năm lỗi đã biết. Ngoại lệ
chỉ được chấp nhận khi được ghi rõ và có lý do từ hình dạng tài liệu nguồn.

## 5. Chỉ mục ngữ nghĩa tối giản

### Chính sách cảnh báo và buộc thôi học

Thêm class:

```text
AcademicPolicy — "Chính sách học vụ"
```

Thêm hai named individual:

| IRI | Label | Provision nguồn |
|---|---|---|
| `AcademicWarningPolicy` | Chính sách cảnh báo kết quả học tập | `Decision1052Article20Clause01` |
| `AcademicDismissalPolicy` | Chính sách buộc thôi học | `Decision1052Article20Clause02` |

Hai node dùng `sourceDocument Decision1052` và `sourceProvision`. Chúng không
dùng các property chỉ dành cho quy trình, không có `officialText` riêng và
không bị gán thành `AcademicProcedure`.

`DismissalTransferRequestProcedure` tiếp tục biểu diễn hành động sinh viên có
thể thực hiện theo Khoản 3. `instructionProvision` của nó phải trỏ chính xác
tới Khoản 3 thay vì toàn Điều 20.

### Học liên thông

Thêm `ArticulationStudyProcedure`, label "Quy trình học liên thông":

- `sourceDocument`: `Decision1052`;
- `sourceProvision`: `Decision1052Article29`;
- `eligibilityProvision`: Khoản 1;
- `deadlineProvision`: Khoản 2;
- `instructionProvision`: Điều 29 để trả toàn bộ hướng dẫn khi người dùng hỏi
  chung.

Không gán form, đơn vị nhận hoặc kết quả nếu tài liệu không nói rõ. Khoản 3 mô
tả cách học và khả năng được xem xét miễn/bảo lưu, không được gọi sai là kết
quả chắc chắn của việc đăng ký.

### Nghỉ ốm

Thêm `SickLeaveProcedure`, label "Quy trình xin nghỉ ốm":

- `sourceDocument`: `Decision1052`;
- `sourceProvision` và `instructionProvision`: Điều 30;
- `eligibilityProvision`: Khoản 1 và Khoản 2;
- `deadlineProvision`: Khoản 1 và Khoản 2.

Node tổng quát này không gắn cả Form 04 và Form 09, vì hai biểu mẫu thuộc hai
nhánh điều kiện khác nhau. Các liên kết cụ thể được đặt ở quy trình tương ứng:

- `TemporaryAcademicLeaveProcedure` bổ sung Khoản 1 Điều 30 vào
  `eligibilityProvision` và `instructionProvision`; Form 09 giữ nguyên;
- `ExamPostponementProcedure` bổ sung Khoản 2 Điều 30 vào
  `eligibilityProvision`, `deadlineProvision` và `instructionProvision`; Form
  04 giữ nguyên;
- `ClassAbsenceRequestProcedure` giữ nguồn chính ở Điều 17 và bổ sung Khoản 1
  Điều 30 cho điều kiện, thời hạn và hướng dẫn nghỉ ốm ngắn ngày.

Không suy đoán thêm đơn vị nhận hồ sơ khi cách diễn đạt trong nguồn không đủ
rõ. Các actor đã có chỉ được giữ nếu có căn cứ trực tiếp từ provision hiện tại.

## 6. Sửa vai trò property

Xóa `resultProvision Decision1052Article17Clause01PointB` khỏi
`ClassAbsenceRequestProcedure`. Điểm này chỉ nói khoa/viện xem xét trường hợp
nghỉ thực hành có lý do chính đáng, không mô tả kết quả được bảo đảm.

Xóa khai báo `documentUrl` vì graph không có triple dữ liệu nào dùng property
này. `webPageUrl` và `downloadUrl` tiếp tục phục vụ đúng hai loại URL hiện có.

Không tạo property tổng quát mới như `relatedTo`, `topicOf` hoặc
`relatedProcedure`. Các đường truy vấn hiện tại đã đủ diễn đạt phạm vi được
duyệt.

## 7. Inventory khả năng trả lời

Tạo `resources/ontology/answer_inventory.json` dưới dạng manifest được duyệt
từ graph. Inventory không sao chép câu trả lời và không trở thành nguồn sự
thật thứ hai. Các mục `supported` được kiểm tra tự động từ graph; các mục
`excluded` ghi lại quyết định có chủ ý của người thiết kế. Mỗi mục chứa tối
thiểu:

```json
{
  "id": "academic-dismissal-policy-content",
  "anchor": "AcademicDismissalPolicy",
  "answer_kind": "literal",
  "path": ["sourceProvision", "officialText"],
  "provenance": ["Decision1052Article20Clause02"],
  "status": "supported"
}
```

`answer_kind` chỉ nhận `label`, `literal` hoặc `aggregate`. Mục `aggregate`
phải có thêm `operation`; mục `excluded` có thể để `path` rỗng nhưng bắt buộc
có `reason`. Chỉ chấp nhận hai trạng thái:

- `supported`: đường đi chạy được và trả label/literal/giá trị tổng hợp;
- `excluded`: chủ đề đã xem xét nhưng không có đủ dữ liệu hoặc nằm ngoài phạm
  vi.

Kiểm thử phải xác nhận:

- mọi IRI và property trong inventory tồn tại;
- mọi đường `supported` thực thi được và trả ít nhất một kết quả;
- kết quả cuối là label, literal hoặc giá trị tổng hợp, không phải object IRI;
- mọi provision được liệt kê truy ngược được về tài liệu nguồn;
- không có `id` trùng.

Query catalogue chính thức chỉ được xây từ các mục `supported` sau khi
inventory này được nghiệm thu.

## 8. Ảnh hưởng tới dataset ứng viên

Dataset hiện tại là nguồn ứng viên, không phải contract của ontology. Không
được giữ một triple sai chỉ để target cũ tiếp tục chạy.

Hiện có một record hỏi “kết quả” của `ClassAbsenceRequestProcedure`. Khi xóa
liên kết sai, record này phải được loại khỏi pool ứng viên; không được đổi câu
hỏi sang một ý nghĩa khác chỉ để giữ số lượng. Đây là sửa tương thích, không
phải giai đoạn nâng cấp dataset và không làm thay đổi trạng thái ứng viên của
ba split.

Không bổ sung hàng loạt câu hỏi, không fine-tune và không benchmark trong đợt
refactor ontology này.

## 9. Kiểm thử và tiêu chí hoàn tất

Refactor hoàn tất khi:

1. RDFLib parse được Turtle và toàn bộ test ontology hiện có vẫn đạt;
2. audit cấu trúc không còn thiếu Khoản 2 Điều 20 hoặc bốn điểm `đ)`;
3. nội dung sau khi tách vẫn đối chiếu được với `NTUdocs/Qd1052.md`;
4. các node policy và procedure mới có label tiếng Việt, IRI tiếng Anh,
   provenance và đúng vai trò;
5. query smoke cho Điều 20, 29 và 30 trả đúng `officialText`;
6. `ClassAbsenceRequestProcedure` không còn result giả;
7. `documentUrl` không còn trong schema;
8. inventory vượt toàn bộ kiểm tra tính toàn vẹn;
9. toàn bộ test suite đạt;
10. không thay đổi các file người dùng đang giữ ngoài phạm vi.

Mỗi nhóm thay đổi được commit riêng: cấu trúc nguồn, semantic index, inventory
và đồng bộ tài liệu. Không merge nhánh cho đến khi ontology, catalogue, dataset
và runtime đều ổn định.
