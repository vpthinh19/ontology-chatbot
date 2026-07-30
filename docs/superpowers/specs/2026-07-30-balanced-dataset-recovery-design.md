# Balanced Dataset Recovery Design

## Mục tiêu

Bổ sung một vòng dữ liệu có kiểm soát để chatbot trả lời chắc chắn các cách hỏi
cơ bản về 22 quy trình học vụ, phân biệt được câu hỏi gần miền nhưng ontology
không có dữ liệu, đồng thời phục hồi phần lớn lỗi còn lại trên bộ test hiện tại.

Vòng này tối ưu chất lượng production của T5Gemma2. Không thay ontology, schema
SPARQL, preprocessing, tokenizer, kiến trúc runtime hoặc hyperparameter.

## Đường cơ sở đã đo

Dataset hiện có 3.558 câu:

- train: 2.749;
- validation: 402;
- test: 407.

Checkpoint T5Gemma2 hiện tại đạt:

- System Answer Exact toàn test: 367/407, tương đương 90,17%;
- truy vấn quy trình: 174/185, tương đương 94,05%;
- OOD safe rejection: 83/90, tương đương 92,22%;
- bảy câu người dùng trọng yếu: 3/7;
- ba câu hướng dẫn đăng ký học phần trọng yếu: 0/3.

Hai phép thử bổ sung cho thấy:

- 211/220 câu hướng dẫn cơ bản đúng, tương đương 95,91%;
- chỉ 11/88 câu gần miền nhưng hỏi điều ontology không hỗ trợ được từ chối
  đúng, tương đương 12,50%.

Điểm yếu chính không phải thiếu toàn bộ tên quy trình. Model đang phụ thuộc quá
nhiều vào thực thể xuất hiện trong câu, chưa phân biệt chắc ý định `hỏi cách làm`
với `hỏi lý do`, `hỏi định nghĩa`, `hỏi lợi ích` hoặc một chi tiết không có.

## Phạm vi dữ liệu mới

Thêm đúng 896 câu vào `resources/dataset/main/train.jsonl`. Không xóa hoặc sửa
câu train hiện có. Các ID mới liên tục từ `question-005777` đến
`question-006672`.

Sau bổ sung, train có 3.645 câu và toàn release có 4.454 câu. Validation và test
giữ nguyên từng byte:

- validation SHA-256:
  `063495561b0025b681d96b9b1fc569208a81cd919dfeeb505c1b10ad1da82669`;
- test SHA-256:
  `7e8cc503a9da1478ab448eca6fcce2adec13771720085ccb06b294c7db336305`.

Phân bố register của 896 câu mới:

| Register | Số câu |
|---|---:|
| noisy | 314 |
| neutral | 224 |
| colloquial | 224 |
| formal | 134 |
| **Tổng** | **896** |

## Bốn khối biên soạn

### 1. Ngôn ngữ hỏi quy trình cơ bản — 352 câu

Mỗi một trong 22 quy trình nhận 16 câu mới. Các câu phải phủ những cấu trúc tự
nhiên sau mà không sao chép nguyên văn validation/test:

- `X như nào`, `X như thế nào`, `X ra sao`, `X sao`;
- `làm sao để X`, `làm thế nào để X`;
- `muốn X thì làm gì`, `cần làm gì để X`, `hướng dẫn X`;
- câu có chủ thể và ngữ cảnh ngắn như `em muốn`, `tui cần`, `kỳ này`;
- cách gọi chính thức, cách gọi thường ngày, viết tắt đã được preprocessing hỗ
  trợ và câu không dấu còn đọc hiểu được.

Không dùng một template rồi chỉ thay tên quy trình. Mỗi nhóm phải thay đổi cả
cấu trúc câu, động từ, ngữ cảnh và mức độ trang trọng. Các câu này luôn hướng
tới `instructionProvision/officialText`.

### 2. Cặp thuộc tính quy trình dễ nhầm — 144 câu

Chín target quy trình còn lỗi nhận 16 câu mới mỗi target:

- hướng dẫn đăng ký học phần;
- điều kiện hoãn thi;
- biểu mẫu tải về của nghỉ học tạm thời;
- nội dung tổng quát đóng học phí;
- nguồn quy định chuyển trường;
- hạn xử lý hoãn thi;
- hướng dẫn xin phép nghỉ học;
- nội dung tổng quát nghỉ học tạm thời;
- kết quả giải quyết chuyển trường.

Mỗi target phải được biên soạn cùng các target dễ nhầm của chính quy trình đó.
Ví dụ, câu hỏi về `điều kiện` phải khác rõ câu hỏi về `hạn`, `kết quả`, `nơi
nộp`, `biểu mẫu` và `nguồn`. Mục tiêu là dạy ý nghĩa thuộc tính chứ không chỉ
dạy tên thực thể.

### 3. OOD gần miền và cặp tương phản — 220 câu

Mỗi quy trình nhận 10 câu mà ontology không trả lời được. Các nhóm ý định gồm:

- lý do hoặc mục đích: `vì sao phải X`, `X để làm gì`;
- định nghĩa hoặc lợi ích: `X là gì`, `lợi ích của X`;
- chi tiết vận hành không được tài liệu nguồn quy định;
- câu thiếu thực thể hoặc thiếu giá trị bắt buộc;
- câu ghép một yêu cầu trong miền với một yêu cầu ngoài miền;
- quy trình gần tên nhưng không tồn tại trong ontology.

Target của toàn bộ khối này là `không có thông tin`. Mỗi cặp phải có một câu
positive gần về từ vựng để model học ranh giới ý định, ví dụ:

```text
đăng ký học phần phải làm thế nào  -> SPARQL hướng dẫn đăng ký học phần
vì sao phải đăng ký học phần       -> không có thông tin
```

### 4. Phục hồi các nhóm ngoài quy trình — 180 câu

Phân bổ theo mức độ lỗi cho 16 query family ngoài quy trình đang sai:

- chủ thể học vụ và văn bản nguồn;
- học phí tiến sĩ;
- tải biểu mẫu;
- quy tắc và nội dung sĩ số lớp;
- danh sách, chi tiết, ngân hàng và phí của phương thức thanh toán;
- cảnh báo thanh toán;
- xếp loại học tập và xếp loại tốt nghiệp theo điểm;
- ngành đào tạo và nhóm ngành;
- quy đổi chứng chỉ;
- metadata văn bản chính thức;
- thông tin biểu mẫu trong văn bản.

Mỗi family nhận từ 10 đến 14 câu, ưu tiên family có nhiều lỗi. Các câu phải tập
trung vào bốn nguyên nhân: nhầm IRI, thiếu nhánh, thừa nhánh và sao chép sai
literal số. Tổng của khối phải đúng 180.

## Quy tắc chất lượng

Mỗi câu mới phải thỏa toàn bộ điều kiện:

1. Câu hỏi có một cách hiểu chính và target đúng với cách hiểu đó.
2. SPARQL hợp lệ, thực thi được và trả kết quả không rỗng, trừ marker
   `không có thông tin`.
3. Nội dung câu hỏi phù hợp dữ liệu thật trong ontology.
4. Không trùng nguyên văn hoặc trùng sau chuẩn hóa với train, validation, test
   và regression suite.
5. Không tạo paraphrase bằng cách chỉ bỏ dấu câu validation/test.
6. Câu noisy vẫn phải là câu một sinh viên thực tế có thể đọc hiểu.
7. Số, mã biểu mẫu, loại lớp, chứng chỉ và phương thức thanh toán phải được
   đối chiếu riêng để tránh nhầm thực thể.
8. Các câu nhiều cột hoặc nhiều nhánh phải nêu đủ thông tin người dùng muốn
   nhận, không nhồi thêm trường dữ liệu không được hỏi.

Validator hiện có là cổng bắt buộc sau từng khối. Việc biên soạn là thủ công;
script chỉ được dùng để đếm quota, kiểm tra ID, duplicate, leakage và thực thi
SPARQL.

## Regression suite cho cách hỏi quy trình

Ghi cố định phép thử production tại
`resources/cases/procedure_language.jsonl`:

- 220 câu positive: 22 quy trình nhân 10 cách hỏi cơ bản;
- 88 câu negative gần miền: 22 quy trình nhân 4 ý định không được hỗ trợ.

Không đưa nguyên văn 308 câu này vào train. Suite được chạy trước và sau
fine-tuning bằng execution-based Answer Exact. Đây là regression suite đã biết,
không được trình bày như test khoa học độc lập.

## Nghiệm thu

Sau khi toàn bộ static gate đạt, fine-tune BARTpho, ViT5 và T5Gemma2 từ
checkpoint pretrained gốc, mỗi model đúng một lần bằng PEFT LoRA theo
`2026-07-30-peft-lora-training-design.md`. Không resume checkpoint hiện tại,
không đổi seed, epochs, learning rate hoặc decoding sau khi xem kết quả.

Các điều kiện đạt đồng thời:

| Tiêu chí | Ngưỡng |
|---|---:|
| 220 câu hướng dẫn cơ bản | 100% |
| 88 câu negative gần miền | ít nhất 95% |
| System Answer Exact trên 407 test hiện tại | ít nhất 90% |
| Answer Exact trên 185 câu quy trình | ít nhất 95% |
| Mỗi register quy trình | ít nhất 90% |
| Ba câu đăng ký học phần trọng yếu | 3/3 |
| OOD safe rejection hiện tại | ít nhất 94% |

Nếu một ngưỡng không đạt, chỉ báo cáo lỗi và dừng. Không chỉnh dữ liệu rồi chạy
lại trong cùng vòng.

## Tính độc lập của đánh giá

Vì lỗi của test hiện tại đã được dùng để chọn vùng bổ sung train, kết quả trên
407 câu này sau phục hồi là metric chẩn đoán/production, không còn là ước lượng
hoàn toàn độc lập. Regression suite cũng đã được dùng để mô tả mục tiêu nên
không phải benchmark mù.

Trước khi công bố kết quả nghiên cứu cuối cùng cần khóa một holdout mới, không
dùng prediction của nó để tiếp tục sửa dataset. Việc tạo holdout cuối này nằm
ngoài vòng phục hồi hiện tại để không làm loãng mục tiêu production trước mắt.

## Ngoài phạm vi

- thay ontology hoặc catalogue;
- sửa preprocessing, tokenizer, schema SPARQL hoặc runtime;
- tuning hyperparameter hoặc chạy nhiều seed;
- CTranslate2, web application hoặc UX;
- tạo benchmark khoa học cuối cùng;
- merge nhánh hiện tại.
