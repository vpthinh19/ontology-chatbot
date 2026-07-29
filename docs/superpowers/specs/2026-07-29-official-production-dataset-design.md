# Dataset production cho ontology chính thức

> **Trạng thái:** Tài liệu này ghi lại thiết kế đã tạo candidate pool 456 câu.
> Nó không còn là tiêu chí nghiệm thu dataset canonical. Xem
> [đặc tả readiness](2026-07-29-ontology-dataset-readiness-design.md).

## Mục tiêu

Dataset huấn luyện một model seq2seq duy nhất thực hiện hai hành vi:

- câu hỏi được hệ thống hỗ trợ → sinh một dòng SPARQL `SELECT`;
- câu hỏi không được hỗ trợ → sinh chính xác `không có thông tin`.

Chatbot hỏi đáp dựa trên ontology là mục tiêu chính. Model chỉ học cách ánh xạ
câu hỏi sang truy vấn hoặc từ chối; nội dung chính thức, mức học phí, URL và các
ngưỡng quy định tiếp tục nằm trong ontology, không được chép thành câu trả lời để
model học thuộc.

Dataset chỉ phụ thuộc ontology chính thức tại
`resources/ontology/ontology.ttl`. Dữ liệu cũ có thể cung cấp cách diễn đạt hữu
ích, nhưng target và thống kê cũ không còn giá trị sau khi ontology được xây lại.

## Ranh giới hỗ trợ

### Trọng tâm: quy trình học vụ

Hai mươi `AcademicProcedure` là nhóm chính. Với mỗi quy trình, catalogue chỉ
công bố những khả năng có dữ liệu thật, ưu tiên:

- hướng dẫn tổng quát;
- điều kiện;
- thời hạn;
- kết quả;
- nơi nộp và nơi xem xét;
- biểu mẫu và URL tải;
- một số truy vấn tổng hợp tương ứng với cách người dùng thường hỏi nhiều thông
  tin liên quan trong cùng một câu.

Không tạo mọi tổ hợp toán học giữa các thuộc tính. Một tổ hợp chỉ được thêm khi
nó có ý nghĩa đối với người dùng và SPARQL trả lời trọn vẹn yêu cầu.

### Nhóm phụ

Chatbot cũng trả lời trực tiếp bốn nhóm có dữ liệu chính thức:

1. học phí và thanh toán;
2. biểu mẫu;
3. quy tắc học vụ định lượng;
4. quy đổi chứng chỉ.

Các nhóm này có độ phủ ngôn ngữ thấp hơn nhóm quy trình nhưng vẫn phải có đủ
cách hỏi chính quy, thông thường, ngôn ngữ nói và noisy.

### Tầng nguồn văn bản

Chương, điều, khoản, điểm, phụ lục và dòng bảng không phải đích hỏi đáp độc lập.
Chúng chỉ là tầng nguồn để SPARQL lấy `officialText`, đối chiếu quy định hoặc
truy nguyên tài liệu. Không sinh các câu như “khoản 2 điều 14 nói gì” trong
dataset production.

## Phương pháp xây dựng

Áp dụng phương pháp kết hợp:

- con người thiết kế phạm vi hỗ trợ, ý nghĩa truy vấn và câu hỏi tiếng Việt;
- công cụ thực thi SPARQL, quản lý ID, chia split, tính thống kê và phát hiện lỗi;
- script không tự sáng tác hàng loạt câu hỏi bằng mẫu để lấp số lượng.

Cách viết tay toàn bộ dễ gây lỗi kỹ thuật và không mở rộng được. Cách sinh hoàn
toàn bằng script tạo câu máy móc, lặp cấu trúc và làm model đạt điểm ảo. Phương
pháp kết hợp giữ SPARQL chính xác mà vẫn đặt chất lượng ngôn ngữ lên trước số
lượng.

## Query catalogue

Catalogue tại `resources/dataset/main/catalogue.jsonl` là danh sách hữu hạn
những khả năng chatbot công bố hỗ trợ. Mỗi mục xác định:

- `query_id`: loại truy vấn ổn định;
- nhóm miền;
- dạng SPARQL được phép;
- các thực thể, thuộc tính hoặc giá trị động cần được phủ trong train;
- yêu cầu kiểm tra kết quả.

`query_id` đại diện cho logic truy vấn, không bắt buộc ánh xạ một-một tới chuỗi
target. Truy vấn định lượng có thể thay đổi literal theo input, chẳng hạn điểm
IELTS hoặc điểm trung bình. Các target cùng `query_id` phải có cùng ý nghĩa và
hình dạng truy vấn đã khai báo trong catalogue.

Mọi IRI, toán tử và dạng SPARQL production cần sinh phải xuất hiện trong train.
Validation và test không giữ lại logic hoặc IRI chưa từng được dạy; chúng chỉ
giữ lại cách diễn đạt và giá trị kiểm thử độc lập.

Mỗi target trong cả ba split phải:

1. là một dòng canonical;
2. vượt validator SPARQL chỉ đọc;
3. thực thi được trên đúng ontology;
4. trả ít nhất một dòng;
5. chỉ project literal hoặc label, không trả URI hay blank node.

## Hình dạng bản ghi

Dataset đích chỉ còn `resources/dataset/main/`, gồm `catalogue.jsonl`, ba split
`train.jsonl`, `val.jsonl`, `test.jsonl` và `manifest.json`. Mỗi dòng trong ba
split giữ năm trường:

```json
{
  "id": "question-000001",
  "query_id": "certificate-score-conversion",
  "register": "colloquial",
  "input": "ielts 5.5 đổi ra bậc mấy vậy",
  "target": "SELECT ..."
}
```

Không thêm `origin`, nhãn phân loại hoặc câu đã chuẩn hóa. Câu bị từ chối dùng:

```json
{
  "id": "question-000002",
  "query_id": "no-information",
  "register": "neutral",
  "input": "xin chào",
  "target": "không có thông tin"
}
```

Dataset và pipeline phân loại `gate` bị loại khỏi kiến trúc đích.

## Tiền xử lý

Dataset lưu nguyên văn câu người dùng. `normalize_model_input` là hàm duy nhất
được dùng giống hệt trong trainer, benchmark và runtime:

```text
input gốc
→ Unicode và khoảng trắng
→ mở rộng viết tắt chắc nghĩa
→ tokenizer
→ model
```

Các viết tắt học vụ chắc nghĩa như `hp`, `đkhp`, `sv`, `ctsv`, `nvqs` và
`cntt` được mở rộng. Tiền xử lý không dò entity, không chọn IRI, không sửa SPARQL
và không fuzzy-match.

Câu không dấu và lỗi gõ hợp lý được dạy bằng dữ liệu. Không tự phục hồi dấu
bằng phỏng đoán. Các ánh xạ ngắn hoặc đa nghĩa hiện có, đặc biệt token một ký tự,
phải được kiểm tra lại bằng ca trong miền lẫn ngoài miền. Mọi quy tắc phải:

- hoạt động theo ranh giới token;
- giữ nguyên từ dài chứa token đó;
- idempotent;
- có test hồi quy từ câu người dùng thực tế.

## Trong miền và ngoài miền

Câu chỉ mang target SPARQL khi ontology và catalogue trả lời được toàn bộ yêu
cầu. Dùng marker `không có thông tin` cho:

- chào hỏi, cảm ơn và trò chuyện chung;
- chủ đề ngoài học vụ;
- câu gần miền nhưng ontology không chứa dữ liệu;
- câu mơ hồ hoặc thiếu dữ kiện bắt buộc;
- văn bản vô nghĩa hoặc quá hỏng để hiểu chắc chắn;
- câu hỗn hợp có ít nhất một yêu cầu không được hỗ trợ.

Không thể liệt kê mọi câu ngoài miền. Dataset phải phủ các nhóm đại diện, hard
negative gần miền và toàn bộ trường hợp thực tế đã biết trong
`resources/cases/user_queries.txt` hoặc nhật ký kiểm thử được tuyển chọn.

## Train, validation và test

Train chứa toàn bộ khả năng production, bao gồm mọi IRI, dạng SPARQL, toán tử và
nhóm từ chối. Mục tiêu là model làm tốt những khả năng đã được dạy, không kiểm
tra zero-shot trên schema ontology.

Validation và test dùng cùng catalogue nhưng cách diễn đạt độc lập. Mỗi split
cùng phủ bốn register:

- `formal`: văn phong hành chính;
- `neutral`: câu hỏi thông thường;
- `colloquial`: ngôn ngữ nói;
- `noisy`: viết tắt, không dấu hoặc lỗi gõ vẫn còn hiểu chắc chắn.

Cấm trùng câu sau preprocessing giữa các split. Câu gần trùng thuộc cùng loại
truy vấn phải được tách hoặc viết lại. Các câu cùng khung nhưng nói về thực thể
khác được báo cáo để rà thủ công thay vì tự động xem là leakage.

Không ấn định tổng số mẫu trước khi hoàn thành catalogue. Quy mô được suy ra từ
số khả năng có thật và số cách diễn đạt cần thiết; không nhân mọi thực thể với
mọi thuộc tính chỉ để tăng số lượng.

## Cổng chất lượng

Dataset chỉ sẵn sàng huấn luyện khi đạt toàn bộ điều kiện:

1. schema bản ghi, ID và register hợp lệ;
2. mọi SPARQL parse, an toàn, chạy có kết quả trên ontology đúng checksum;
3. marker từ chối trùng chính xác `không có thông tin`;
4. toàn bộ catalogue, IRI và cấu trúc production có mặt trong train;
5. không exact leakage hoặc near-duplicate leakage giữa split;
6. phân bố theo nhóm miền, loại truy vấn và register được báo cáo; các nhóm từ
   chối được rà bằng checklist tuyển chọn;
7. source và target round-trip an toàn qua tokenizer model được chọn;
8. toàn bộ câu người dùng thực tế có nhãn được rà thủ công;
9. SPARQL projection trả đúng literal/label mà renderer có thể hiển thị;
10. ontology checksum và manifest dataset đồng bộ.

Sau khi các cổng tĩnh đều qua, chỉ fine-tune một model thử nghiệm để xác nhận
dataset có thể học. Không dò nhiều seed, không tự tăng epoch hoặc đổi
hyperparameter theo điểm test. Lỗi được phân tích theo `query_id`, nhóm miền và
register trước khi sửa dữ liệu.

## Trình tự triển khai

1. Loại bỏ hạ tầng gate và sửa validator cho contract một model.
2. Lập catalogue SPARQL thực thi được từ ontology mới.
3. Biên soạn dữ liệu cho hai mươi quy trình học vụ.
4. Biên soạn bốn nhóm phụ.
5. Bổ sung câu từ chối và các ca người dùng thực tế.
6. Chia split, tạo manifest và chạy toàn bộ cổng chất lượng.
7. Fine-tune thử sau khi dataset đã được nghiệm thu tĩnh.

Việc huấn luyện, benchmark ba kiến trúc và trực quan hóa kết quả là giai đoạn
sau, không được trộn vào quá trình xây catalogue và biên soạn dataset.
