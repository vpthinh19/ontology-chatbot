# Chatbot hỏi đáp học vụ dựa trên ontology

## Tóm tắt

Kiến trúc v3 của dự án xác định một công cụ truy xuất kiến thức học vụ để một
LLM lớn gọi trong quá trình trả lời người dùng. Công cụ không tự viết câu trả lời
cuối: nó chuyển yêu cầu truy xuất thành SPARQL đã được giới hạn, lấy **trọn
node** liên quan từ ontology, rồi trả dữ liệu cùng nguồn cho LLM tổng hợp. Lớp
điều phối tool-calling hoàn chỉnh chưa được tích hợp trong runtime hiện tại.

Ontology là nơi giữ nội dung có thẩm quyền. Dataset hiện có **5.088 câu**, gồm
4.299 câu huấn luyện, 400 câu kiểm định và 389 câu kiểm tra. Danh mục khả năng
trả lời hiện ghi nhận **4.064 khả năng trả lời** được hỗ trợ. Đây là số liệu về
artifact dữ liệu, không phải điểm chất lượng của model.

Kiến trúc v3 có ba nguyên tắc:

1. LLM hội thoại là bên quyết định khi nào cần gọi công cụ ontology.
2. Hình dạng truy xuất chính là toàn bộ thuộc tính đọc được của một node, kèm
   trích dẫn và đường dẫn nguồn.
3. Mỗi bảng trong văn bản nguồn là một node chứa nguyên khối bảng; hệ thống
   không chép lại từng ô thành các sự thật song song.

Các kết quả model v2 đã bị rút khỏi tài liệu công khai. Dataset dùng để dựng
model đó hỏng, nên model và các metric của nó không phải baseline và không phải
phương án lui.

## 1. Bài toán nghiên cứu

Thông tin học vụ nằm rải trong quy chế, quyết định, phụ lục, hướng dẫn thanh
toán và danh mục biểu mẫu. Một LLM hội thoại có thể diễn đạt câu trả lời dễ đọc,
nhưng không nên tự nhớ hay đoán nội dung pháp quy.

Câu hỏi nghiên cứu của v3 là:

> Có thể cung cấp cho một LLM lớn đúng node ontology có liên quan, đầy đủ ngữ
> cảnh và nguồn, để LLM trả lời dựa trên dữ liệu kiểm chứng được hay không?

Công cụ chỉ phục vụ miền ontology đi kèm. Câu hỏi ngoài phạm vi hoặc yêu cầu
không ánh xạ được tới một node được hỗ trợ phải được từ chối.

## 2. Các khái niệm nền tảng

| Khái niệm | Nghĩa trong dự án |
|---|---|
| Ontology | Đồ thị RDF chứa thực thể học vụ, quan hệ, literal và nguồn. |
| Node | Một thực thể được định danh trong đồ thị, chẳng hạn một thủ tục, điều khoản hoặc bảng. |
| Trọn node | Nhãn, literal, dữ kiện con trực tiếp và thông tin nguồn của node được lấy trong cùng một lần truy xuất. |
| SPARQL | Ngôn ngữ truy vấn nội bộ của công cụ ontology. |
| Danh mục truy vấn | Danh sách hữu hạn các shape SPARQL công cụ được phép thực thi. |
| LLM lớn | Model hội thoại bên ngoài công cụ; model gọi công cụ và viết câu trả lời cuối. |
| Bảng nguyên văn | Một bảng nguồn được giữ trong `verbatimTableText` như một khối Markdown duy nhất. |

Ontology không phải kho đoạn văn để tìm gần nghĩa. Quan hệ trong đồ thị giúp
định vị node; toàn bộ nội dung đọc được của node cung cấp ngữ cảnh cho LLM.

## 3. Phương pháp đề xuất

Luồng v3:

```text
người dùng
  → LLM hội thoại
  → gọi công cụ ontology khi cần dữ kiện học vụ
  → sinh/chọn truy vấn thuộc danh mục
  → kiểm tra chỉ đọc và khớp shape
  → lấy trọn node cùng nguồn
  → LLM hội thoại tổng hợp câu trả lời
```

LLM hội thoại không được nhận quyền truy vấn tùy ý. Công cụ chỉ thực thi
`SELECT` an toàn và khớp một shape trong
`resources/dataset/catalogue.jsonl`. Truy vấn sai, ngoài danh mục hoặc rỗng
được trả về như một lần gọi công cụ không có dữ liệu; LLM không được bù bằng
phỏng đoán.

### 3.1. Hình dạng đầu vào và đầu ra của model

Trong kiến trúc v3, model ở lớp hội thoại nhận câu hỏi và có quyền gọi một công
cụ chuyên biệt. Công cụ nhận yêu cầu học vụ và trả **context có cấu trúc**, chứ
không trả câu trả lời đã viết sẵn.

Ví dụ rút gọn cho câu “bảo lưu cần làm gì”:

```text
LLM → công cụ:
{"question": "bảo lưu cần làm gì"}

Công cụ → LLM:
- node: TemporaryAcademicLeaveProcedure
- thuộc tính/giá trị: nhãn, yêu cầu, bước, nơi nộp, kết quả, thủ tục tiếp theo
- nguồn: trích dẫn đầy đủ
- đường dẫn: văn bản chính thức
```

Shape SPARQL chính dùng một node neo và lấy literal của chính node lẫn các node
con trực tiếp:

```sparql
SELECT ?thuoctinh ?giatri ?nguon ?duongdan WHERE {
  {
    :TemporaryAcademicLeaveProcedure ?p ?giatri .
    FILTER(isLiteral(?giatri))
    ?p rdfs:label ?thuoctinh
  }
  UNION
  {
    :TemporaryAcademicLeaveProcedure ?l ?con .
    ?con ?p ?giatri .
    FILTER(isLiteral(?giatri))
    ?p rdfs:label ?thuoctinh
  }
  # catalogue bổ sung trích dẫn và URL nguồn
}
```

Đây là “lấy trọn node”: câu hỏi về cách làm, điều kiện hay nơi nộp đều có thể
nhận cùng một node thủ tục đầy đủ. LLM lớn đọc context và chọn phần cần thiết
cho câu trả lời hiện tại.

Với bảng, công cụ trả nguyên `verbatimTableText` của node bảng:

```text
node: Regulation1052Article18Clause02Table01
giá trị: toàn bộ bảng xếp loại học lực dưới dạng Markdown
nguồn: khoản chứa bảng và URL văn bản
```

Mỗi bảng chỉ có một bản nguyên văn. Không có một lớp ô/bản ghi thứ hai có thể
lệch cột hoặc mâu thuẫn với bảng nguồn.

## 4. Đồ thị tri thức học vụ

Ontology được xây dựng từ Quyết định 1052 về đào tạo đại học và các phụ lục,
Quyết định 626 về quy chế tuyển sinh đại học,
Quyết định 1965 sửa đổi phụ lục, phần còn hiệu lực cần dùng của Quyết định 753,
Quyết định 317 về học bổng, Phụ lục II của Quyết định 729 về ngành đào tạo, các
hướng dẫn thanh toán và danh mục biểu mẫu của Trường Đại học Nha Trang.

`resources/ontology/ontology.ttl` là cơ sở dữ liệu nội dung duy nhất. Mức học
phí theo sinh viên không được lưu vì phụ thuộc kỳ, khóa, ngành, chương trình và
học phần thực tế; ontology chỉ giữ những hướng dẫn thanh toán có nguồn ổn định.

`resources/ontology/answer_inventory.json` được sinh từ ontology và hiện có
4.064 mục `supported`. Mỗi mục biểu diễn một đường trả lời được phép từ node tới
literal hoặc nhãn. Chi tiết về node văn bản, node nghiệp vụ và bảng nguyên văn
nằm trong [tài liệu ontology](docs/ONTOLOGY.md).

## 5. Dataset

Ba split JSONL hiện có:

| Tập | Số câu | Vai trò |
|---|---:|---|
| Huấn luyện | 4.299 | Kho ví dụ cho ánh xạ câu hỏi sang shape truy xuất |
| Kiểm định | 400 | Kiểm tra lựa chọn/cấu hình mà không dùng tập kiểm tra |
| Kiểm tra | 389 | Đánh giá cuối sau khi cấu hình đã cố định |
| **Tổng** | **5.088** | Tổng số dòng thực tế trong ba tệp |

Các số này được đếm trực tiếp từ
`resources/dataset/train.jsonl`, `resources/dataset/val.jsonl` và
`resources/dataset/test.jsonl`; trường `dataset.records` và
`dataset.splits` trong `reports/dataset.json` ghi cùng các giá trị.

`reports/dataset.json` còn ghi phân bố hiện có theo miền:

| Miền | Số câu |
|---|---:|
| Quy tắc học vụ | 894 |
| Thủ tục | 1.114 |
| Biểu mẫu | 621 |
| Ngoài miền | 638 |
| Văn bản | 931 |
| Học phí/hướng dẫn thanh toán | 159 |
| Chứng chỉ | 188 |

Chuỗi kiểm tra đối chiếu mọi `query_id`, target, giá trị slot, tên gọi, register,
nhóm từ chối và checksum với catalogue/ontology hiện hành. Trạng thái có thể đọc
máy nằm ở `training_readiness` và `coverage` trong `reports/dataset.json`.

Xem [tài liệu dataset](docs/DATASET.md) và
[bản kê trong thư mục dataset](resources/dataset/README.md).

## 6. Đánh giá

Thước sinh SPARQL v3 công bố ba số rời: **đúng node · đúng dạng · từ chối
đúng**; không gộp thành accuracy tổng. Validation và test mỗi bên chỉ còn HAI nhóm: câu truy vấn node và câu
ngoài miền. Họ "liệt kê năng lực" đã bị bỏ khỏi thiết kế ngày 2026-08-14 -
công cụ chỉ truy ra dữ kiện hoặc nói không có thông tin. Chín câu người thật được báo riêng ở mức đúng `query_id`, không
trộn vào benchmark sinh.

Độ trung thành của câu trả lời cuối là một lớp đánh giá tiếp theo: LLM chỉ được
dùng context công cụ, không thêm dữ kiện không có trong node.

Với bảng, phép kiểm phải so toàn khối `verbatimTableText` và giữ vị trí cột.
Với node thường, phép kiểm phải kiểm tra đủ các thuộc tính liên quan và trích
dẫn, không chỉ một literal tình cờ đúng.

Repository hiện không công bố metric model v3. Giao thức chi tiết nằm trong
[docs/EVALUATION.md](docs/EVALUATION.md).

## 7. Trạng thái model cũ

Model seq2seq v2 được huấn luyện từ dataset hỏng. Mọi số đo, kết luận so sánh và
artifact triển khai của nó đã bị rút khỏi tài liệu công khai. Model đó không
được dùng làm baseline, không được dùng để đánh giá v3 và không phải phương án
lui.

[docs/TRAINING.md](docs/TRAINING.md) chỉ giữ mô tả quy trình lịch sử để giải
thích code nghiên cứu còn trong repository. [docs/MODEL_CARD.md](docs/MODEL_CARD.md)
ghi rõ model đã ngừng.

## 8. Kiểm tra và artifact

Chuỗi mong muốn là:

```text
văn bản nguồn → ontology → danh mục khả năng trả lời
               → danh mục truy vấn → ba split JSONL → báo cáo dẫn xuất
```

Chạy kiểm tra read-only:

```bash
.venv/bin/python -m pytest tests -q
uv run validate_sparql_dataset
```

`uv run generate_reports` ghi lại artifact dẫn xuất; không chạy lệnh này khi
chỉ kiểm tra vì nó có thể thay đổi report/manifest. Nguồn số liệu được mô tả ở
[reports/README.md](reports/README.md).

Khi nguồn thay đổi, sinh lại toàn chuỗi theo đúng thứ tự:

```bash
.venv/bin/python -m ontchatbot.research.inventory
.venv/bin/python -m ontchatbot.research.build_catalogue
.venv/bin/python -m ontchatbot.cli.generate_dataset
.venv/bin/python -m ontchatbot.cli.report
```

## 9. Giới hạn

- Dataset kiểm được tính sẵn sàng của dữ liệu, không tự nó chứng minh chất lượng
  một model chưa huấn luyện và đánh giá lại.
- Chưa có benchmark công khai cho kiến trúc LLM gọi công cụ.
- Chất lượng câu trả lời cuối phụ thuộc cả việc gọi công cụ, truy xuất node và
  khả năng bám nguồn của LLM lớn.
- Một node đầy đủ có thể chứa nhiều thông tin hơn câu hỏi cần; LLM phải chọn lọc
  nhưng không được làm mất điều kiện hoặc ngoại lệ quan trọng.
- Bảng nguyên văn tránh sai lệch do chép từng ô, nhưng đòi hỏi LLM đọc đúng cấu
  trúc hàng/cột.

## 10. Tài liệu

- [Ý tưởng và ranh giới](docs/CONCEPT.md)
- [Kiến trúc v3](docs/ARCHITECTURE.md)
- [Ontology](docs/ONTOLOGY.md)
- [Dataset](docs/DATASET.md)
- [Quy trình huấn luyện lịch sử](docs/TRAINING.md)
- [Đánh giá v3](docs/EVALUATION.md)
- [Triển khai v3](docs/DEPLOYMENT.md)
