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

- Train loss được vẽ theo bước; validation answer exact được vẽ theo mốc đánh
  giá để quan sát khả năng tổng quát hóa và dấu hiệu overfit.
- Validation sinh query bằng greedy decoding. Answer exact được dùng chọn
  checkpoint; nếu bằng điểm, giữ checkpoint xuất hiện sớm hơn.
- Validation result F1 là metric chẩn đoán, không thay tiêu chí chọn checkpoint.
- Test chỉ chạy với checkpoint đã chọn và là số dùng so sánh ba model. Mọi
  query test đã được dạy trong train; câu chữ của test thì chưa xuất hiện ở
  train hoặc validation.

Vì validation và test có mục tiêu khác nhau, không gộp hai con số thành một tỷ
lệ chung. Điểm test phải luôn đi kèm số câu (430), phân bố register và đặc
trưng SPARQL.

## Biểu đồ công khai

`generate_reports` sinh biểu đồ dataset. Sau huấn luyện hợp lệ, báo cáo model
bổ sung:

- đường train loss và validation answer exact;
- cột so sánh validation answer exact, test answer exact và test result F1;
- test answer exact theo phong cách câu hỏi và đặc trưng SPARQL;
- số liệu parse, execution, precision/recall/F1, nhóm lỗi, thời gian train,
  VRAM và tốc độ inference trong JSON nguồn.

Các JSON gốc được giữ cạnh SVG để người đọc kiểm tra con số mà không cần mở
code trainer.

Điểm chất lượng chính được đo bằng checkpoint Hugging Face mở lại qua
`from_pretrained()`, cùng backend Transformers cho cả ba model. CTranslate2
chỉ đo parity và hiệu năng triển khai. BLEU, ROUGE và token F1 không dùng vì
độ giống chuỗi không chứng minh query trả đúng dữ liệu.

## Đánh giá domain gate

Gate xem `in_scope` là lớp dương và được báo cáo độc lập với benchmark sinh
SPARQL:

| Metric | Cách tính | Ý nghĩa |
|---|---|---|
| In-scope recall | `TP / (TP + FN)` | Tỷ lệ câu ontology trả lời được được cho qua |
| False acceptance rate | `FP / (FP + TN)` | Tỷ lệ câu ngoài phạm vi lọt vào generator |
| Macro F1 | Trung bình F1 của hai lớp | Chất lượng cân bằng tổng thể |
| ROC-AUC | Xếp hạng xác suất hai lớp | Khả năng tách lớp không phụ thuộc một ngưỡng |

Ngưỡng được chọn trên validation rồi cố định trong manifest. Trên 860 câu test,
gate đạt recall 95,58%, false acceptance rate 1,16% và ma trận
`TP=411, FN=19, FP=5, TN=425`. Đây là trade-off bảo thủ: ưu tiên không đưa câu
ontology không thể trả lời vào model sinh SPARQL.

Sau conversion, evaluator chạy lại toàn bộ test bằng CT2+NumPy và so từng xác
suất, quyết định cùng ma trận với prediction PyTorch. Artifact production phải
giữ nguyên ma trận và đạt cả hai ngưỡng FAR ≤ 1,2%, recall ≥ 95%.
