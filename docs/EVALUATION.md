# Đánh giá

Tài liệu này định nghĩa giao thức và báo cáo kết quả trên ontology cùng dataset
4.454 câu. Cả ba model được đánh giá trên cùng 407 câu test.

## Hai nhóm test

Test được báo cáo theo hai nhóm độc lập:

- `in-domain`: đáp án tham chiếu là một truy vấn SPARQL chuẩn có kết quả;
- `out-of-domain`: reference là `không có thông tin`, bao gồm nhóm câu hỗn hợp.

Không dùng một accuracy tổng thể để che chất lượng của một nhóm.

## Metric trong miền

| Metric | Cách tính | Ý nghĩa |
|---|---|---|
| Validation loss | Cross-entropy token với teacher forcing | Hội tụ/overfit |
| Parse rate | Query qua parser | Đúng cú pháp |
| Execution rate | Query chạy không lỗi | Có thể thực thi |
| Result precision/recall/F1 | So multiset dòng kết quả | Mức đúng một phần |
| In-domain Answer Exact | Kết quả thực thi trùng reference | Trả đúng toàn bộ dữ liệu |
| Query string exact | Chuỗi truy vấn trùng đáp án SPARQL chuẩn | Đúng biểu diễn chuẩn |

Answer Exact bỏ qua thứ tự dòng và tên biến nhưng giữ kiểu dữ liệu, language
tag, số cột và cách ghép giá trị trong từng dòng.

## Metric ngoài miền

| Metric | Cách tính | Ý nghĩa |
|---|---|---|
| Marker exact | Đầu ra trùng `không có thông tin` | Model chủ động từ chối đúng quy ước |
| False acceptance | Câu ngoài miền sinh `SELECT` hợp lệ có kết quả | Nguy cơ trả lời sai tự tin |
| Safe rejection | Backend cuối cùng trả `Không có thông tin.` | Hành vi người dùng nhìn thấy |
| Mixed-query rejection | Câu hỗn hợp bị từ chối toàn bộ | Tuân thủ ranh giới miền |

Output sai cú pháp có thể được backend chặn an toàn nhưng không được tính là
marker exact. Nhờ vậy benchmark phân biệt model thực sự học từ chối với lỗi sinh
chuỗi vô tình dẫn tới cùng phản hồi giao diện.

## System Answer Exact

System Answer Exact chạy prediction qua toàn backend:

- câu trong miền đúng khi literal cuối cùng trùng reference;
- câu ngoài miền đúng khi giao diện trả `Không có thông tin.`.

Metric này được báo cáo riêng cho in-domain, out-of-domain, mixed và tổng thể,
luôn kèm số mẫu từng nhóm. In-domain Answer Exact vẫn là chỉ số chính cho năng
lực chatbot ontology.

## Validation và test

Validation dùng greedy decoding và chọn checkpoint theo tiêu chí được cố định
trước huấn luyện. Test chỉ chạy một lần với checkpoint đã chọn. Mọi SPARQL test
thuộc catalogue đã xuất hiện trong train; cách diễn đạt thì chưa xuất hiện ở
train/validation.

Ngoài tập test, bộ `resources/cases/procedure_language.jsonl` gồm 308 câu được
dùng để kiểm tra hành vi triển khai: 220 câu hỏi quy trình và 88 câu gần miền
hoặc ngoài miền cần từ chối. Bộ kiểm tra hồi quy này không tham gia huấn luyện,
không dùng để chọn checkpoint và không thay thế tập test.

Các ngưỡng đánh giá được xác định trước khi chạy test:

- System Answer Exact toàn test đạt ít nhất 90%;
- Answer Exact riêng 185 câu `procedure-*` đạt ít nhất 95%;
- mỗi phong cách trong nhóm quy trình đạt ít nhất 90%;
- các câu người dùng cốt lõi đúng 100%;
- không từ chối nhầm câu hỏi hướng dẫn đăng ký học phần;
- Safe Rejection ngoài miền đạt ít nhất 94%.

Biểu đồ công khai phải lấy dữ liệu từ JSON máy đọc và gồm:

- train/validation loss;
- In-domain Answer Exact của model;
- marker exact, false acceptance và mixed-query rejection;
- System Answer Exact theo nhóm;
- lỗi theo register và đặc trưng SPARQL;
- thời gian train, VRAM và tốc độ inference.

Không dùng BLEU, ROUGE hoặc token F1 làm bằng chứng trả lời đúng dữ liệu.

## Kết quả — baseline v0.4.1

| Model | Parse | Answer Exact | Result F1 | Safe Rejection OOD | System Exact |
|---|---:|---:|---:|---:|---:|
| BARTpho-syllable | 98,11% | 84,03% | 84,44% | 91,11% | 85,75% |
| ViT5-base | 97,48% | 79,61% | 80,28% | 84,44% | 81,08% |
| **T5Gemma2** | **97,79%** | **90,66%** | **92,74%** | **92,22%** | **92,38%** |

T5Gemma2 đạt 96,22% Answer Exact trên 185 câu quy trình; cả bốn phong cách diễn
đạt của nhóm này đều trên 90%. Model vượt ngưỡng System Exact toàn test, Answer
Exact quy trình và từng phong cách quy trình, nhưng chưa đạt ngưỡng Safe
Rejection 94% và yêu cầu của bộ hồi quy negative. T5Gemma2 được chọn vì có kết
quả tổng thể cao nhất; khả năng từ chối ngoài miền vẫn là giới hạn của hệ thống.

Sau chuyển sang CTranslate2 int8, toàn pipeline web đạt 92,87% phản hồi exact
trên cùng test. Chênh lệch này được báo cáo riêng, không dùng để thay kết luận
so sánh ba checkpoint Transformers.

Các metric trên thuộc baseline v0.4.1. `reports/provenance.json` đối chiếu hash
ontology, catalogue, coverage và ba split; nếu `model_metrics.status` hoặc
`deployment_metrics.status` là `stale`, số liệu vẫn được giữ làm lịch sử nhưng
không đại diện cho input canonical mới.
