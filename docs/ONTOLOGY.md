# Ontology học vụ

## Nguồn dữ liệu duy nhất

Toàn bộ kiến thức học vụ được truy xuất nằm trong
`resources/ontology/ontology.ttl`. Đây là **cơ sở dữ liệu duy nhất** của công cụ:
LLM lớn có thể diễn đạt lại context, nhưng không được thêm dữ kiện học vụ không
có trong node được trả về.

Ontology lấy căn cứ từ các văn bản chính thức trong `references/`, gồm Quyết
định 1052 và quy chế kèm theo, các văn bản sửa đổi/liên quan, Quyết định 317 về
học bổng, phần danh mục ngành của Quyết định 729, hướng dẫn thanh toán và danh
mục biểu mẫu.

## Hai nhóm node

**Node văn bản** giữ cấu trúc tài liệu, chương, điều, khoản, điểm, phụ lục và
bảng. Node mang nguyên văn, trích dẫn và URL nguồn.

**Node nghiệp vụ** giữ thủ tục, yêu cầu, bước, trường hợp, quy tắc, đơn vị, biểu
mẫu, ngành, chứng chỉ và các khái niệm mà người dùng có thể hỏi. Quan hệ
`basedOn` nối dữ kiện nghiệp vụ về node văn bản làm căn cứ.

V3 truy xuất node đầy đủ thay vì chọn một literal riêng lẻ. Với thủ tục, công cụ
có thể lấy literal trên node và trên các node con trực tiếp trong cùng query.
LLM lớn nhận toàn bộ context này và chọn phần liên quan đến câu hỏi.

## Bảng nguyên văn

Bảng là trường hợp cần giữ hình dạng nguồn. Mỗi bảng được biểu diễn bằng một node
`DocumentTable` và lưu nguyên khối Markdown trong `verbatimTableText`. Dấu phân
cột, tiêu đề nhiều hàng và ô rỗng đều là dữ liệu có nghĩa.

Không tách nội dung bảng thành từng cell hoặc từng mapping kỹ thuật. Nếu cùng
một ánh xạ vừa nằm trong bảng nguyên văn vừa nằm trong các cạnh RDF, hai bản có
thể trôi lệch. Một node bảng tạo ra một nguồn sự thật duy nhất.

Các thực thể có vai trò ngoài bảng vẫn được giữ độc lập. Ví dụ một ngành hoặc
chứng chỉ mà node khác trỏ tới không bị xóa chỉ vì tên nó cũng xuất hiện trong
bảng; điều bị loại là bản sao của chính ánh xạ hàng–cột.

## Trích dẫn

Node trả lời phải dẫn được về văn bản chính thức. Context công cụ dùng hai trường
chính:

- `citationLabel`: trích dẫn tự giải thích được;
- `documentUrl`: đường dẫn tới văn bản gốc.

Các quan hệ `inDocument` và `partOf` cho biết bảng hoặc đoạn văn nằm ở đâu. LLM
nên giữ nguồn khi tổng hợp câu trả lời, nhất là với điều kiện, ngoại lệ và bảng.

## Danh mục khả năng trả lời

`resources/ontology/answer_inventory.json` được sinh từ ontology. Đếm trực tiếp
các entry có `status == "supported"` cho kết quả **4.047 khả năng trả lời**.
Artifact cũng có 21 entry `excluded` kèm lý do; các mục bị loại không được tính
vào khả năng công bố.

Một khả năng trả lời là một đường hợp lệ từ node neo tới literal hoặc nhãn đọc
được. Con số này đo phạm vi cấu trúc của ontology, không phải số câu hỏi tự nhiên
và không phải metric model.

## Quan hệ với danh mục truy vấn

Danh mục khả năng trả lời mô tả ontology có thể cung cấp gì. Danh mục truy vấn
mô tả công cụ được phép lấy theo shape nào. Dataset chỉ được tạo sau hai lớp đó
và phải dùng `query_id` còn tồn tại.

Shape chính v3 gom các đường của cùng loại node thành một query `*-facts`. Shape
bảng trả toàn `verbatimTableText`. Vì vậy số khả năng trả lời không cần tương
ứng một-một với số họ truy vấn.

## Giới hạn nội dung

- Mức học phí cá nhân không được lưu vì thay đổi theo dữ liệu đăng ký thực tế.
- Công thức hoặc ký hiệu hỏng trong bản nguồn không được đoán để điền.
- Khoảng trống và mơ hồ của văn bản được giữ nguyên, không “sửa” bằng kiến thức
  ngoài.
- Ontology chưa tự giải quyết hiệu lực theo thời gian cho nhiều phiên bản văn
  bản.

## Kiểm tra

```bash
uv run pytest tests/ontology
uv run validate_sparql_dataset
```

Lệnh thứ hai kiểm cả chuỗi ontology → danh mục khả năng trả lời → danh mục truy
vấn → dataset. Nếu đỏ, tài liệu không được tuyên bố chuỗi đã sẵn sàng.
