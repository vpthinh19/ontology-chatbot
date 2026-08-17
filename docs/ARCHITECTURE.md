# Kiến trúc hệ thống

## Tổng quan

V3 đặt chatbot ontology bên trong vòng lặp dùng công cụ của một LLM lớn:

```text
người dùng
  → LLM lớn
      → gọi công cụ ontology
          → chuẩn hoá yêu cầu
          → sinh hoặc chọn SPARQL thuộc danh mục
          → kiểm tra chỉ đọc + khớp shape
          → RDFLib lấy trọn node và nguồn
      ← context có cấu trúc
  ← câu trả lời dựa trên context
```

Công cụ không sở hữu hội thoại và không viết câu trả lời cuối. LLM không được
truy cập ontology bằng query tự do.

## Hợp đồng của công cụ

Đầu vào tối thiểu là yêu cầu truy xuất học vụ do LLM chuyển tới. Đầu ra thành
công gồm:

- node hoặc các node được chọn;
- các cặp thuộc tính–giá trị đọc được của node;
- literal trên node con trực tiếp khi shape khai báo;
- trích dẫn tự giải thích;
- URL văn bản chính thức;
- trạng thái truy xuất.

Đầu ra không có dữ liệu phải phân biệt được với lỗi hệ thống để LLM không nhầm
“ngoài phạm vi” với “dịch vụ hỏng”.

## Shape chính: node đầy đủ

Các họ `*-facts` trong danh mục dùng cùng ý tưởng:

```sparql
{ :Anchor ?p ?giatri . FILTER(isLiteral(?giatri)) }
UNION
{ :Anchor ?l ?con . ?con ?p ?giatri . FILTER(isLiteral(?giatri)) }
```

Kết quả được gắn nhãn thuộc tính, trích dẫn và URL trước khi trả cho LLM. Query
không chỉ lấy một cạnh theo đúng từ khóa câu hỏi; nó lấy context của node để LLM
xử lý điều kiện và ngoại lệ trong cùng một lượt.

## Shape bảng

Các họ bảng neo trực tiếp vào node `DocumentTable`. Giá trị chính là
`verbatimTableText`; quan hệ `inDocument` và `partOf` cung cấp ngữ cảnh, còn
`citationLabel` và `documentUrl` cung cấp nguồn.

Mỗi bảng là một node nguyên văn. Không dựng cell, row hay mapping song song cho
các giá trị chỉ tồn tại trong bảng. Điều này bảo toàn vị trí cột và tạo một điểm
duy nhất để kiểm tra độ trung thực với nguồn.

## Các cửa kiểm

Trước khi chạy, query phải:

1. là truy vấn chỉ đọc;
2. không gọi nguồn ngoài;
3. khớp chính xác một shape trong danh mục truy vấn;
4. giới hạn đầu ra theo hợp đồng runtime.

Sau khi chạy, công cụ kiểm tra kết quả có dữ liệu đọc được và nguồn theo yêu cầu.
Công cụ không tự sửa query gần đúng.

## Ranh giới code hiện tại

Repository vẫn chứa runtime seq2seq/CTranslate2 và code huấn luyện cũ để truy
vết lịch sử. Chúng không đại diện cho kiến trúc hệ thống và không phải fallback.
`src/ontchatbot/runtime/llm.py` là phần thử nghiệm ánh xạ câu hỏi sang query bằng
LLM, nhưng lớp điều phối tool-calling hoàn chỉnh vẫn cần được tích hợp và đánh
giá trước khi công bố triển khai.

## Quan sát và ghi vết

Mỗi lần gọi công cụ cần ghi request ID, yêu cầu đã chuẩn hoá, query nguyên văn,
shape khớp, node neo, trạng thái kiểm tra, số giá trị trả về, nguồn và latency.
Không ghi lại suy luận riêng tư của LLM.

## Artifact

- `resources/ontology/ontology.ttl`: dữ liệu có thẩm quyền;
- `resources/ontology/answer_inventory.json`: danh mục khả năng trả lời;
- `resources/ontology/catalogue.jsonl`: hợp đồng query;
- ba split JSONL: ví dụ ánh xạ;
- `artifacts/reports/dataset.json`: snapshot thống kê dẫn xuất.

Tính tương thích của cả chuỗi do test quyết định; một trường “ready” trong report
không thay thế kết quả kiểm tra hiện hành.
