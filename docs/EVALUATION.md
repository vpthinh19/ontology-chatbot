# Đánh giá

## Metric

Mỗi prediction được xử lý theo các lớp sau:

| Metric | Cách tính | Ý nghĩa |
|---|---|---|
| Validation loss | Cross-entropy token với teacher forcing | Tín hiệu hội tụ/overfit |
| Parse rate | Query qua RDFLib parser | Đúng cú pháp |
| Execution rate | Query chạy không lỗi | Có thể thực thi |
| Result precision | Phần kết quả dự đoán nằm trong reference | Mức dư dữ liệu |
| Result recall | Phần reference được truy vấn lấy ra | Mức thiếu dữ liệu |
| Result F1 | Trung bình điều hòa precision/recall | Mức đúng một phần |
| Answer exact | Multiset literal trả về trùng reference | Trả đúng dữ liệu |
| Query string exact | Chuỗi query trùng target canonical | Sinh đúng biểu diễn chuẩn |

Answer exact là metric chính. Nó bỏ qua thứ tự dòng và tên biến SPARQL tùy ý,
nhưng vẫn so kiểu dữ liệu, giá trị, số cột và cách các giá trị được nhóm trong
từng dòng. Một query khác chuỗi nhưng trả đúng dữ liệu vẫn được tính đúng.

Metric được báo cáo tổng thể, theo register và theo các đặc trưng SPARQL suy ra
tự động. Lỗi được chia
thành parse, execution, sai IRI, sai property, thiếu/thừa nhánh, sai literal và
sai ngữ nghĩa còn lại.

Result precision/recall/F1 được tính trên multiset dòng kết quả của từng câu,
sau đó lấy macro average để query trả nhiều dòng không lấn át query ngắn. Query
parse/execution lỗi hoặc trả rỗng nhận 0 cho cả ba metric; reference luôn khác
rỗng. Tên biến và thứ tự dòng không quan trọng, nhưng RDF datatype, language
tag, số cột và việc ghép các giá trị trong cùng một dòng phải được bảo toàn.

## Train, validation và test

- Train loss được vẽ theo bước; validation loss theo mốc đánh giá để nhận biết
  hội tụ hoặc overfit.
- Validation sinh query bằng greedy decoding. Answer exact được dùng chọn
  checkpoint; nếu bằng điểm, giữ checkpoint xuất hiện sớm hơn.
- Validation result F1 là metric chẩn đoán, không thay tiêu chí chọn checkpoint.
- Test chỉ chạy với checkpoint đã chọn và là số dùng so sánh ba model.

Vì validation và test có mục tiêu khác nhau, không gộp hai con số thành một tỷ
lệ chung. Điểm test phải luôn đi kèm số câu (168), phân bố register và đặc
trưng SPARQL.

## Biểu đồ công khai

`generate_reports` sinh biểu đồ dataset. Sau huấn luyện hợp lệ, báo cáo model
bổ sung:

- đường train loss/validation loss và validation answer exact/result F1;
- cột so sánh test answer exact và result precision/recall/F1;
- parse rate và execution rate;
- breakdown theo phong cách câu hỏi và đặc trưng SPARQL;
- phân bố nhóm lỗi;
- thời gian train, VRAM đỉnh và tốc độ inference.

Các JSON gốc được giữ cạnh SVG để người đọc kiểm tra con số mà không cần mở
code trainer.

Điểm chất lượng chính được đo bằng checkpoint Hugging Face mở lại qua
`from_pretrained()`, cùng backend Transformers cho cả ba model. CTranslate2
chỉ đo parity và hiệu năng triển khai. BLEU, ROUGE và token F1 không dùng vì
độ giống chuỗi không chứng minh query trả đúng dữ liệu.
