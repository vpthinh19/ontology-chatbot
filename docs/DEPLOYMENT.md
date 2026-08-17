# Triển khai kiến trúc v3

## Trạng thái

Chưa có benchmark triển khai công khai cho v3. Runtime seq2seq/CTranslate2 còn
trong repository là dấu vết của kiến trúc đã ngừng, không phải phương án lui và
không được dùng để suy ra chất lượng hệ thống hiện hành.

## Thành phần cần triển khai

Một deployment v3 gồm:

1. LLM lớn hỗ trợ gọi công cụ;
2. lớp điều phối hội thoại và policy gọi công cụ;
3. công cụ ontology nhận yêu cầu truy xuất;
4. thành phần ánh xạ yêu cầu sang SPARQL thuộc danh mục;
5. validator chỉ đọc và matcher danh mục truy vấn;
6. RDFLib cùng `ontology.ttl`;
7. serializer trả trọn node, trích dẫn và URL.

LLM lớn và công cụ phải là hai ranh giới rõ ràng. Công cụ không được nhận query
tùy ý từ model và LLM không được tự bổ sung dữ kiện khi công cụ trả rỗng.

## Hợp đồng trả về

Kết quả thành công nên có dạng khái niệm:

```json
{
  "status": "ok",
  "nodes": [
    {
      "id": "TemporaryAcademicLeaveProcedure",
      "facts": [{"property": "...", "value": "..."}],
      "citation": "...",
      "source_url": "..."
    }
  ]
}
```

Node bảng trả `verbatimTableText` trong `facts` như một khối, không trả danh
sách cell. Trạng thái `no_data` phải mang lý do có kiểm soát; lỗi nạp ontology,
timeout và exception phải dùng kênh lỗi hệ thống.

## An toàn

- chỉ nhận SPARQL `SELECT`;
- cấm thao tác ghi và nguồn dữ liệu bên ngoài;
- query phải khớp chính xác catalogue;
- giới hạn kích thước kết quả;
- escape dữ liệu khi hiển thị;
- giữ URL nguồn và trích dẫn trong context;
- không cho LLM biến kết quả rỗng thành câu trả lời dựa trên trí nhớ.

## Quan sát

Mỗi tool call cần request ID, query nguyên văn, shape khớp, node neo, trạng thái,
số giá trị, nguồn và latency. Log không lưu chain-of-thought của LLM. Dữ liệu
người dùng cần được xử lý theo chính sách của môi trường triển khai.

## Điều kiện phát hành

Không phát hành v3 cho tới khi:

- chuỗi ontology → inventory → catalogue → dataset xanh;
- tool-calling được kiểm thử cả trong miền, ngoài miền và lỗi;
- bảng nguyên văn round-trip không đổi;
- câu trả lời cuối được đánh giá độ bám nguồn;
- manifest triển khai ghim checksum ontology và catalogue.

`artifacts/reports/provenance.json` hiện có trạng thái `stale` cho metric model và
deployment; không có số liệu cũ nào được dùng làm tiêu chí phát hành.
