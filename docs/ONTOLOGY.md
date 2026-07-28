# Ontology

Nguồn dữ liệu canonical là
[`resources/ontology/ontology.ttl`](../resources/ontology/ontology.ttl), dùng
namespace `http://www.ntu.edu.vn/ontology/academic#`.

## Quy ước đặt tên

- Class và individual dùng IRI tiếng Anh dạng `PascalCase`.
- Property dùng IRI tiếng Anh dạng `camelCase`.
- `rdfs:label@vi` là tên tiếng Việt chính, đầy đủ và ổn định.
- `skos:altLabel@vi` chỉ chứa tên gọi thay thế thực sự hữu ích, không chứa câu
  hỏi mẫu.

Alias là metadata phục vụ mô tả và tìm kiếm trong công cụ ontology. Runtime
truy vấn bằng canonical IRI do model sinh từ target SPARQL.

## Hình dạng graph

Ontology hiện có 9 class, 6 object property, 13 datatype property và 32 named
individual. Tất cả tài nguyên được đặt tên đều có `rdfs:label@vi`.

Object property giữ vai trò nối node:

- `handledBy`, `receivedBy`: đơn vị xử lý và đơn vị nhận hồ sơ;
- `hasDocument`: biểu mẫu của quy trình;
- `basedOnRegulation`: văn bản làm căn cứ;
- `supportsPaymentMethod`: phương thức thanh toán;
- `appliesTuitionRate`: định mức học phí áp dụng.

Thông tin trả lời trực tiếp nằm ở datatype property. `content` là hướng dẫn
tổng quát; `condition` và `outcome` là các literal lặp khi người dùng hỏi một
khía cạnh cụ thể. Email, URL, địa điểm, số điện thoại và học phí cũng là
datatype property.

Condition và Outcome không phải node riêng vì chúng không có dữ liệu hoặc quan
hệ độc lập. Ngược lại phòng ban, biểu mẫu, văn bản, phương thức thanh toán và
định mức học phí vẫn là node vì được nối, tái sử dụng hoặc mang nhiều thuộc
tính.

## Kiểm tra tính toàn vẹn

```bash
uv run validate_sparql_dataset
uv run generate_reports
```

Hai lệnh lần lượt chạy toàn bộ target trên graph và kiểm tra thống kê ontology,
bao gồm tài nguyên thiếu label tiếng Việt. SHA-256 của ontology được lưu cùng
manifest dataset để kết quả có thể tái lập.
