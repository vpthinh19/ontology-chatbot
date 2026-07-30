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

Ontology canonical hiện đã vượt cổng cấu trúc, provenance và semantic index.
Lớp nguồn chứa 32 điều cùng Phụ lục 1–3 của Quyết định 1052, học phí và 41 ngành
của Quyết định 729, hướng dẫn thanh toán cùng danh mục biểu mẫu. Các literal
`officialText@vi`, label và provenance đã được đối chiếu với nguồn `NTUdocs`.

Audit cấu trúc đã tách riêng Khoản 2 Điều 20 và bốn điểm `đ)` từng bị gộp vào
điểm `d)`. Kiểm thử hiện so sánh các khoản/điểm đánh số trong văn bản cha với
node con trên toàn bộ 32 điều.

Semantic index có 22 quy trình và 2 chính sách. Điều 20 được tách thành chính
sách cảnh báo, chính sách buộc thôi học và quy trình xin chuyển chương trình;
Điều 29 có quy trình học liên thông; Điều 30 có quy trình nghỉ ốm cùng liên kết
đến nghỉ học ngắn ngày, nghỉ học tạm thời và hoãn thi. Ba liên kết kết quả
không có căn cứ của các quy trình xin phép nghỉ học, miễn học/miễn thi/cộng
điểm thưởng và xin học trở lại cùng property `documentUrl` rỗng đã được loại bỏ.

Inventory máy đọc được nằm tại
`resources/ontology/answer_inventory.json`. File này được sinh xác định từ
graph, chỉ lưu anchor, đường tới literal/label và provenance; nó không sao chép
câu trả lời. Các quyết định không hỗ trợ được ghi bằng trạng thái `excluded` và
lý do. Inventory hiện có 2.953 mục `supported`; 259 label của bản ghi kỹ thuật
nội bộ cùng năm quyết định nghiệp vụ không hỗ trợ được đánh dấu `excluded`.

Query catalogue canonical nằm tại `resources/dataset/catalogue.jsonl`, có
51 họ truy vấn và phủ toàn bộ các mục `supported`. Model chỉ sinh IRI của thực
thể người dùng có thể nhắc tới. Các bản ghi kỹ thuật như dòng quy đổi chứng chỉ
hoặc dòng học phí được SPARQL tìm từ chứng chỉ, điểm, ngành, khóa và các điều
kiện nghiệp vụ thay vì bắt model học thuộc IRI của từng dòng.

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
