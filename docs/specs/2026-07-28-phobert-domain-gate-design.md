# PhoBERT domain gate

## Mục tiêu

Thêm một bộ phân loại nhị phân đứng trước model sinh SPARQL. Gate chỉ cho qua
những câu hỏi mà ontology hiện tại có đủ dữ liệu và hệ thống có truy vấn tương
ứng để trả lời đầy đủ. Mọi câu còn lại bị từ chối trước khi sinh SPARQL.

Gate giải quyết nhận diện phạm vi hỗ trợ. Nó không thay model sinh SPARQL,
không đánh giá SPARQL đúng hay sai và không mở rộng miền ontology.

## Định nghĩa nhãn

- `in_scope`: toàn bộ yêu cầu trong câu đều có thể được trả lời bằng ontology
  và contract SPARQL hiện tại.
- `out_of_scope`: ontology không thể trả lời, chỉ trả lời được một phần, câu
  không có yêu cầu rõ ràng hoặc nội dung không thuộc phạm vi hỗ trợ.

Câu trộn nhiều yêu cầu chỉ mang nhãn `in_scope` khi tất cả yêu cầu đều được hỗ
trợ. Chào hỏi, hội thoại xã giao, văn bản vô nghĩa và câu hỏi thuộc môi trường
đại học nhưng thiếu dữ liệu trong ontology đều là `out_of_scope`.

## Luồng xử lý

```text
Câu hỏi
  -> chuẩn hóa văn bản nhẹ
  -> PhoBERT binary classifier
     -> P(in_scope) < threshold: trả thông báo ngoài phạm vi
     -> P(in_scope) >= threshold
        -> model sinh SPARQL
        -> xác minh SPARQL
        -> truy vấn ontology
        -> trả câu trả lời
```

Gate dùng `vinai/phobert-base-v2` với classification head hai nhãn. Đầu vào
không được word-segment. Fine-tuning và inference phải dùng cùng một hàm chuẩn
hóa; không thêm fuzzy matching, sentence similarity hoặc luật định tuyến theo
từ khóa.

## Dataset

Dataset gate nằm riêng tại `resources/gate/` với ba file `train.jsonl`,
`val.jsonl` và `test.jsonl`. Mỗi dòng chỉ có hai trường:

```json
{"input":"điều kiện tốt nghiệp là gì","label":"in_scope"}
{"input":"thư viện mở cửa lúc nào","label":"out_of_scope"}
```

Positive giữ nguyên câu hỏi và split tương ứng từ dataset sinh SPARQL hiện
tại. Mỗi split bổ sung số lượng negative bằng số positive để việc huấn luyện
và so sánh dễ diễn giải.

Negative phải phủ ba nhóm:

1. Ngoài miền rõ ràng: kiến thức phổ thông, thời tiết, chính trị, sáng tác và
   hội thoại xã giao.
2. Gần miền nhưng không được ontology hỗ trợ: câu hỏi về môi trường đại học có
   từ vựng gần với dữ liệu học vụ nhưng thiếu dữ liệu hoặc truy vấn tương ứng.
3. Biên khó: câu mơ hồ, noisy, viết tắt, không dấu, văn bản vô nghĩa và câu
   trộn yêu cầu được hỗ trợ với yêu cầu không được hỗ trợ.

Mọi nhóm ngoài phạm vi đã biết phải xuất hiện trong cả train, validation và
test; hai tập held-out giữ lại cách diễn đạt chứ không giữ lại toàn bộ chủ đề.
Đây là phép đo production trong miền chức năng cố định, tương tự dataset sinh
SPARQL. Một challenge set riêng có thể đo chủ đề OOD chưa từng thấy nhưng không
được dùng làm tiêu chí bật production.

Validation dùng để chọn checkpoint và threshold; test chỉ dùng một lần cho báo
cáo cuối. Negative đã xuất hiện trong một lần phân tích test không được tái sử
dụng trong test kế tiếp. Kiểm tra tự động phải phát hiện schema sai, nhãn sai,
trùng lặp, gần trùng xuyên split kể cả khi chỉ khác dấu câu, và mất cân bằng.
Việc một negative có vô tình được ontology hỗ trợ hay không phải được đối chiếu
thủ công với danh mục 215 query canonical.

## Huấn luyện

- Một lần chạy với seed cố định `42`.
- Cross-entropy hai lớp và dropout mặc định của model.
- Learning rate `2e-5`, cosine scheduler, `warmup_steps=0.1` tổng số step.
- Dynamic padding; tối đa 5 epoch; chọn checkpoint có validation macro-F1 cao
  nhất.
- Mixed precision được chọn theo khả năng phần cứng, giống quy ước chung của
  dự án.

Không tuning nhiều seed hoặc dò hyperparameter trong lần triển khai đầu tiên.

## Ngưỡng và đánh giá

Inference lấy softmax `P(in_scope)`. Threshold được chọn hoàn toàn trên
validation, ưu tiên false acceptance rate không quá 1%, sau đó tối đa hóa
in-scope recall. Không chọn lại threshold từ test.

Báo cáo tối thiểu gồm:

- in-scope precision, recall và F1;
- out-of-scope recall;
- false acceptance rate và false rejection rate;
- confusion matrix;
- ROC-AUC, precision-recall curve và phân bố `P(in_scope)`;
- độ trễ và bộ nhớ của gate;
- kết quả end-to-end tách riêng câu trong miền và ngoài miền.

Mục tiêu nghiệm thu ban đầu là false acceptance rate không quá 1% đồng thời
in-scope recall đạt ít nhất 95% trên test độc lập. Nếu không đạt đồng thời hai
điều kiện, gate chưa được bật mặc định trong webapp.

## Phạm vi không thực hiện

- Không dùng cosine similarity từ vector `[CLS]` làm quyết định.
- Không word-segment và không thêm thư viện tách từ.
- Không sửa ontology hoặc dataset sinh SPARQL để phục vụ gate.
- Không thay đổi model sinh SPARQL hay benchmark ba model hiện tại.
- Không tối ưu ONNX/CTranslate2 trước khi PyTorch baseline đạt tiêu chí.
