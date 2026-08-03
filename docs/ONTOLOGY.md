# Ontology

## Nguồn sự thật

Ontology được xây từ công văn và tài liệu học vụ chính thức. Chỉ những thông tin
có căn cứ trong nguồn này mới được đưa vào đồ thị.

Thứ tự xây dựng bắt buộc:

```text
tài liệu chính thức → ontology → danh mục khả năng trả lời
                    → danh mục truy vấn → dataset
```

SPARQL và câu hỏi huấn luyện phải đi theo graph đã xác nhận, không dùng dataset
để quyết định ngược lại hình dạng ontology.

## Phạm vi dữ liệu

Ontology biểu diễn 32 điều cùng Phụ lục 1–3 của Quyết định 1052, học phí và 41
ngành trong Quyết định 729, hướng dẫn thanh toán và danh mục biểu mẫu. Nội dung
tiếng Việt được lưu bằng `officialText@vi` và `rdfs:label@vi`; mỗi dữ kiện kèm
thông tin nguồn để có thể truy ngược về tài liệu chính thức. Các khoản và điểm
đánh số là các node riêng, phù hợp với cấu trúc của văn bản nguồn.

Lớp ngữ nghĩa gồm 22 quy trình và 2 chính sách. Ví dụ, Điều 20 được biểu diễn
thành chính sách cảnh báo, chính sách buộc thôi học và quy trình xin chuyển
chương trình; Điều 29 mô tả quy trình học liên thông; Điều 30 liên kết quy trình
nghỉ ốm với nghỉ học ngắn ngày, nghỉ học tạm thời và hoãn thi. Chỉ những quan hệ
có căn cứ trong tài liệu nguồn được lưu trong đồ thị.

Danh mục khả năng trả lời tại `resources/ontology/answer_inventory.json` được
sinh từ đồ thị. Mỗi mục lưu thực thể neo, đường đi tới nhãn hoặc literal và
nguồn dữ liệu, nhưng không sao chép câu trả lời. Danh mục có 2.953 khả năng được
hỗ trợ; 259 nhãn kỹ thuật nội bộ và năm quyết định nghiệp vụ không đủ dữ liệu để
trả lời được ghi là `excluded` cùng lý do.

Danh mục truy vấn tại `resources/dataset/catalogue.jsonl` gồm 51 họ truy vấn và
phủ các khả năng được hỗ trợ. Model chỉ cần sinh IRI của thực thể mà người dùng
có thể nhắc tới. Những bản ghi kỹ thuật, chẳng hạn dòng quy đổi chứng chỉ hoặc
dòng học phí, được SPARQL xác định từ điều kiện nghiệp vụ thay vì buộc model học
thuộc IRI của từng bản ghi.

## Định dạng và namespace

Ontology chính dùng Turtle tại `resources/ontology/ontology.ttl` và được đọc
bằng RDFLib. Namespace project phải ổn định sau khi dataset bắt đầu được tạo;
đổi IRI hoặc quan hệ sau thời điểm đó đòi hỏi kiểm tra lại toàn bộ target.

## Quy ước đặt tên

- Class và individual dùng IRI tiếng Anh dạng `PascalCase`.
- Property dùng IRI tiếng Anh dạng `camelCase`.
- `rdfs:label@vi` là tên tiếng Việt chính, đầy đủ và ổn định.
- `skos:altLabel@vi` chỉ chứa tên gọi thay thế thực sự hữu ích.
- Nhãn thay thế không chứa câu hỏi mẫu và không thay thế IRI chuẩn trong SPARQL.

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

Ontology được kiểm tra theo các tiêu chí sau trước khi tạo dataset:

1. Turtle đọc được và sử dụng đúng namespace quy định.
2. Mọi class, property và named individual có `rdfs:label@vi`.
3. IRI duy nhất, tiếng Anh và đúng quy ước chữ hoa/thường.
4. Domain/range và kiểu literal nhất quán.
5. Không có node mồ côi hoặc node chỉ làm bản sao của một literal.
6. Mỗi dữ kiện trả lời được truy ngược về tài liệu chính thức.
7. Các truy vấn trong danh mục chạy được và chỉ trả về nhãn hoặc literal.
8. Mỗi khả năng trả lời quan trọng được ghi vào danh mục với trạng thái
   `supported` hoặc `excluded` kèm lý do.

Số lượng class, property, individual và triple chỉ mô tả hình dạng graph, không
thay thế kiểm tra độ phủ từ danh mục khả năng trả lời sang truy vấn và dataset.

Chạy `uv run validate_sparql_dataset` để kiểm tra read-only toàn chuỗi
ontology → danh mục khả năng trả lời → danh mục truy vấn → dataset và phát hiện
artifact dẫn xuất bị lệch. `uv run generate_reports` sinh lại
`answer_inventory.json`, manifest, `reports/procedure-dataset.json`,
`reports/provenance.json` và các báo cáo/biểu đồ; lệnh này không ghi vào
`ontology.ttl` hay các file dataset canonical.
