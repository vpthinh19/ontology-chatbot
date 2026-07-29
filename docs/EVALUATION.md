# Đánh giá

Tài liệu này định nghĩa giao thức áp dụng cho ontology và dataset đã khóa.
T5Gemma2 đã được nghiệm thu trên release 2.150 câu: test đạt 84,67% Answer
Exact, 83,33% In-domain Answer Exact, 94,44% Safe Rejection và 86,67% System
Answer Exact. Chưa có benchmark so sánh đủ ba model; kết quả từ dữ liệu cũ
không được dùng để xếp hạng hoặc chọn model cuối cùng.

## Hai nhóm test

Test được báo cáo theo hai nhóm độc lập:

- `in-domain`: reference là một SPARQL canonical có kết quả;
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
| Query string exact | Chuỗi query trùng target canonical | Đúng biểu diễn chuẩn |

Answer Exact bỏ qua thứ tự dòng và tên biến nhưng giữ kiểu dữ liệu, language
tag, số cột và cách ghép giá trị trong từng dòng.

## Metric ngoài miền

| Metric | Cách tính | Ý nghĩa |
|---|---|---|
| Marker exact | Prediction trùng `không có thông tin` | Model chủ động từ chối đúng contract |
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

Biểu đồ công khai phải lấy dữ liệu từ JSON máy đọc và gồm:

- train/validation loss;
- In-domain Answer Exact của ba model;
- marker exact, false acceptance và mixed-query rejection;
- System Answer Exact theo nhóm;
- lỗi theo register và đặc trưng SPARQL;
- thời gian train, VRAM và tốc độ inference.

Không dùng BLEU, ROUGE hoặc token F1 làm bằng chứng trả lời đúng dữ liệu.
