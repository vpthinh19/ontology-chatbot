# Ontology

## Nguồn sự thật

Ontology được xây từ công văn và tài liệu học vụ chính thức. Chỉ những thông tin
có căn cứ trong nguồn này mới được đưa vào graph. Dữ liệu cũ không được sao
chép sang ontology mới nếu chưa đối chiếu lại nguồn.

Thứ tự xây dựng bắt buộc:

```text
tài liệu chính thức → ontology → inventory khả năng trả lời
                    → query catalogue → dataset
```

SPARQL và câu hỏi huấn luyện phải đi theo graph đã xác nhận, không dùng dataset
để quyết định ngược lại hình dạng ontology.

## Trạng thái nghiệm thu

Lớp nguồn hiện tại đã chứa 32 điều và Phụ lục 1–3 của Quyết định 1052, học phí
và 41 ngành của Quyết định 729, hướng dẫn thanh toán cùng danh mục biểu mẫu.
Các literal `officialText@vi`, label và provenance đã qua kiểm tra tự động với
nguồn `NTUdocs`.

Kết quả này chưa đủ để khóa ontology canonical. Lớp semantic index phải được
đọc lại theo vai trò và lập inventory khả năng trả lời. Các điểm đã biết cần
chốt trước khi khóa IRI gồm:

- Điều 30 về nghỉ ốm và quan hệ với nghỉ học, nghỉ tạm thời, hoãn thi;
- Điều 29 về học liên thông;
- Điều 20 về cảnh báo học tập và buộc thôi học;
- `resultProvision` của `ClassAbsenceRequestProcedure`;
- property không có dữ liệu như `documentUrl`.

Không cần xây lại lớp nguồn. Mỗi khoảng trống semantic được xử lý bằng cách nối
đúng provision, thêm chỉ mục có căn cứ hoặc ghi rõ không hỗ trợ.

## Định dạng và namespace

Nguồn canonical dùng Turtle tại `resources/ontology/ontology.ttl` và được đọc
bằng RDFLib. Namespace project phải ổn định sau khi dataset bắt đầu được tạo;
đổi IRI hoặc quan hệ sau thời điểm đó đòi hỏi kiểm tra lại toàn bộ target.

## Quy ước đặt tên

- Class và individual dùng IRI tiếng Anh dạng `PascalCase`.
- Property dùng IRI tiếng Anh dạng `camelCase`.
- `rdfs:label@vi` là tên tiếng Việt chính, đầy đủ và ổn định.
- `skos:altLabel@vi` chỉ chứa tên gọi thay thế thực sự hữu ích.
- Alias không chứa câu hỏi mẫu và không thay thế canonical IRI trong SPARQL.

## Hình dạng graph

Ontology là đồ thị. Object property nối các node có danh tính hoặc dữ liệu độc
lập, chẳng hạn quy trình, đơn vị xử lý, biểu mẫu và văn bản. Datatype property
giữ literal được trả lời trực tiếp, chẳng hạn nội dung, email, URL, địa điểm,
số điện thoại hoặc giá trị số.

Khi người dùng hỏi tên một node, query project `rdfs:label`. Khi hỏi một thuộc
tính, query project datatype property tương ứng. Object property chỉ là đường
đi và không được trả thẳng về giao diện.

Một khái niệm chỉ nên trở thành node nếu nó có danh tính, quan hệ hoặc thuộc
tính riêng. Văn bản không có cấu trúc độc lập nên giữ dưới dạng literal để graph
không phình thành các node chỉ có label.

## Kiểm tra tính toàn vẹn

Ontology mới phải vượt các kiểm tra sau trước khi tạo dataset:

1. Turtle parse được và namespace đúng contract.
2. Mọi class, property và named individual có `rdfs:label@vi`.
3. IRI duy nhất, tiếng Anh và đúng quy ước chữ hoa/thường.
4. Domain/range và kiểu literal nhất quán.
5. Không có node mồ côi hoặc node chỉ làm bản sao của một literal.
6. Mỗi dữ kiện trả lời được truy ngược về tài liệu chính thức.
7. Các query catalogue chạy được và chỉ project label/literal.
8. Mỗi khả năng trả lời quan trọng được ghi vào inventory với trạng thái
   `supported` hoặc `excluded` kèm lý do.

Số lượng class, property, individual và triple chỉ mô tả hình dạng graph, không
thay thế kiểm tra coverage từ inventory sang catalogue và dataset.
