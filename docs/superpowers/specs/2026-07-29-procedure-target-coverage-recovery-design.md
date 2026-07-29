# Thiết kế phục hồi độ phủ truy vấn quy trình

## Bối cảnh

Checkpoint T5Gemma2 hiện tại đạt `System Answer Exact` 86,67% trên 300 câu
test, nhưng nhóm truy vấn quy trình chỉ đạt 64/78 câu, tương đương 82,05%.
Các lỗi bao gồm cả câu hỏi cốt lõi như `đăng ký học phần sao`, nên checkpoint
chưa đủ an toàn cho nghiệm thu hoặc production.

Nguyên nhân nằm ở đơn vị đo độ phủ của dataset. Train hiện có 441 câu quy
trình nhưng phải biểu diễn 142 target SPARQL khác nhau. Phân bố theo target là:

| Số mẫu cho một target | Số target |
|---:|---:|
| 1 | 5 |
| 2 | 47 |
| 3 | 44 |
| 4 | 28 |
| 5 | 14 |
| 6 | 2 |
| 7 | 1 |
| 9 | 1 |

Vì vậy, số lượng ở cấp `query_id` tạo cảm giác đã phủ đủ nhưng mỗi ánh xạ cụ
thể từ ý người dùng sang SPARQL vẫn quá mỏng. Ví dụ `procedure-instruction`
có 58 câu cho 22 quy trình, trong khi target hướng dẫn đăng ký học phần chỉ có
ba cách diễn đạt trong train.

## Mục tiêu

Tăng độ tin cậy của model trên các quy trình học vụ bằng cách cân bằng train
theo từng target ngữ nghĩa cụ thể, đồng thời giữ nguyên tính độc lập của
validation/test và ranh giới từ chối ngoài miền.

Đơn vị độ phủ mới là:

```text
thực thể hoặc nhóm thực thể × nội dung cần hỏi × dạng target SPARQL
```

Đối với quy trình, đơn vị này thường có dạng:

```text
quy trình cụ thể × thuộc tính cần lấy
```

Ví dụ `CourseRegistrationProcedure × instructionProvision` và
`CourseRegistrationProcedure × eligibilityProvision` là hai target độc lập,
không được gộp thành một nhóm `procedure-*` đã phủ chung.

## Phạm vi cố định

- Chỉ bổ sung và cân bằng tập train.
- Giữ nguyên nội dung và checksum của validation/test hiện tại.
- Không chép hoặc sửa nhẹ câu validation/test để đưa vào train.
- Không thay đổi ontology, query catalogue, schema SPARQL, preprocessing,
  tokenizer, model, hyperparameter hoặc giao thức benchmark.
- Không thêm luật ánh xạ từ khóa vào backend.
- Không chạy fine-tuning trong giai đoạn biên soạn và audit dataset.
- Sau khi dataset qua toàn bộ cổng tĩnh, chỉ fine-tune T5Gemma2 một lần.
- Không tự động mở vòng bổ sung hoặc fine-tuning thứ hai nếu chưa đạt mục tiêu.

## Chiến lược độ phủ

### Mức nền cho toàn bộ miền quy trình

Mỗi target SPARQL quy trình phải có ít nhất sáu câu train độc lập về cách diễn
đạt. Sáu câu phải cùng truyền đạt một ý nghĩa và cùng target, nhưng không phải
là phép thay từ cơ học từ một câu mẫu.

Mỗi target phải phủ đủ bốn register khi ngữ nghĩa cho phép:

- `formal`: văn phong hành chính hoặc yêu cầu rõ ràng;
- `neutral`: câu hỏi thông thường, đầy đủ;
- `colloquial`: lời nói tự nhiên của sinh viên;
- `noisy`: viết tắt, không dấu, thiếu từ hoặc lỗi gõ vẫn còn hiểu được.

Hai câu còn lại ưu tiên câu ngắn và cách nói gián tiếp. Không ép lỗi chính tả
vào mọi target nếu cách viết đó không tự nhiên.

Nâng 142 target hiện tại lên mức nền sáu mẫu cần bổ sung khoảng 415 câu train.

### Mức ưu tiên cho nghiệp vụ cốt lõi

Ngưỡng ưu tiên được xác định trước để không thay đổi theo kết quả train:

- mọi target `procedure-instruction` có ít nhất 10 câu;
- target hướng dẫn đăng ký học phần có ít nhất 12 câu;
- target chuẩn của từng ca lỗi quy trình trong benchmark hiện tại có ít nhất
  8 câu, trừ khi đã thuộc ngưỡng cao hơn ở hai dòng trên;
- các target quy trình còn lại giữ mức nền sáu câu.

Các ngưỡng này tập trung vào những quy trình sau:

- đăng ký học phần;
- học lại và học cải thiện;
- nghỉ học tạm thời, bảo lưu và trở lại học;
- chuyển ngành, chuyển trường và học chương trình thứ hai;
- hoãn thi và nghỉ học do ốm;
- đồ án, khóa luận và xét tốt nghiệp;
- công nhận tín chỉ và trao đổi sinh viên;
- mở thêm lớp học phần;
- đóng học phí;
- biểu mẫu gắn với các quy trình trên.

Target hướng dẫn đăng ký học phần phải được ưu tiên đầu tiên. Các câu phải phủ
được ít nhất những cách diễn đạt tự nhiên sau mà không sao chép test:

```text
hướng dẫn thực hiện
làm thế nào / làm sao / ra sao
cần làm gì
đăng ký môn hoặc chọn học phần cho học kỳ
đk hp / dk hoc phan / câu không dấu tương đương
```

Phần ưu tiên dự kiến bổ sung thêm khoảng 35–135 câu ngoài mức nền. Tổng ngân
sách của đợt phục hồi là 450–550 câu train; nếu việc áp dụng đúng các ngưỡng
trên cần vượt mức này thì phải dừng và báo cáo trước khi mở rộng phạm vi.

## Cặp tương phản

Model phải học đồng thời thực thể và khía cạnh được hỏi. Với cùng một quy
trình, train cần các cặp diễn đạt gần nhau nhưng khác target, chẳng hạn:

| Câu hỏi | Khía cạnh |
|---|---|
| đổi ngành như thế nào | hướng dẫn |
| có được đổi ngành không | điều kiện |
| hạn nộp đơn đổi ngành là khi nào | thời hạn |
| đơn đổi ngành nộp ở đâu | nơi tiếp nhận |
| đổi ngành dùng mẫu nào | biểu mẫu bắt buộc |
| tải đơn đổi ngành ở đâu | liên kết tải biểu mẫu |
| ai quyết định việc đổi ngành | thẩm quyền |
| sau khi được đổi ngành thì kết quả cũ ra sao | kết quả |

Các cặp phải được viết tự nhiên cho chính quy trình đó. Không tạo một template
rồi thay tên hàng loạt giữa các quy trình.

## Ranh giới trong miền và ngoài miền

Không tăng hàng loạt OOD chung vì train đã có 420 câu `no-information` và
checkpoint còn bị từ chối nhầm câu trong miền. Chỉ thêm hard negative gần các
nghiệp vụ cốt lõi khi nó làm rõ ranh giới ngữ nghĩa.

Ví dụ bắt buộc cho đăng ký học phần:

| Câu hỏi | Target |
|---|---|
| đăng ký học phần như thế nào | SPARQL hướng dẫn đăng ký |
| vì sao phải đăng ký học phần | `không có thông tin` |
| nên đăng ký giảng viên nào | `không có thông tin` |
| học phần nào dễ qua nhất | `không có thông tin` |

Mỗi nhóm hard negative mới phải đi cùng các positive tương phản. Không thêm
negative chỉ để tăng số lượng. Tổng hard negative mới không vượt quá 10% số
mẫu positive được bổ sung.

## Phương pháp biên soạn

Các mẫu mới được biên soạn và rà soát theo từng target. Script chỉ được dùng
để thống kê, xác minh và phát hiện lỗi; không được dùng để sinh hàng loạt câu
hỏi bằng thay thế từ.

Mỗi mẫu phải vượt các câu hỏi kiểm tra sau:

1. Người dùng bình thường có thể nói câu này không?
2. Câu chỉ có một cách hiểu hợp lý trong giới hạn ontology không?
3. SPARQL có trả đúng dữ liệu được hỏi, không chỉ đúng chủ đề không?
4. Câu có khác thực chất với các mẫu cùng target không?
5. Câu có vô tình gần trùng validation/test sau preprocessing không?
6. Nếu là noisy, câu vẫn còn đủ nghĩa để một người Việt hiểu được không?

## Audit trước fine-tuning

Dataset chỉ được phép dùng để train khi có báo cáo chứng minh:

- mọi target quy trình đạt mức nền sáu mẫu;
- các target ưu tiên đạt ngưỡng 8–12 mẫu đã gán;
- bốn register được phủ ở cấp target, không chỉ cấp `query_id`;
- không có thay đổi validation/test;
- không trùng đầu vào giữa các split sau preprocessing;
- không có câu gần trùng validation/test theo kiểm tra character-trigram
  Jaccard hiện hành với ngưỡng 0,84 trong cùng `query_id`;
- mỗi `query_id → target` hợp lệ theo catalogue;
- mọi SPARQL parse, vượt kiểm tra an toàn, thực thi và trả dữ liệu;
- mọi source/target round-trip qua tokenizer của T5Gemma2;
- phân bố positive/OOD và số lượng hard negative được báo cáo;
- các câu người dùng trong `resources/cases/user_queries.txt` vẫn thuộc test
  hoặc tập hồi quy, không bị đưa nguyên văn vào train.

Báo cáo độ phủ phải hiển thị tối thiểu các cột:

```text
query_id | target cụ thể | thực thể neo | số mẫu | register | mức ưu tiên
```

## Fine-tuning và nghiệm thu

Sau khi audit đạt, fine-tune T5Gemma2 một lần từ base model bằng giao thức đã
khóa. Không thay đổi seed, scheduler, learning rate, epoch, decoding hoặc bất
kỳ tham số nào để đuổi theo test.

Checkpoint chỉ được coi là đạt nếu đồng thời thỏa mãn:

- `System Answer Exact` toàn test từ 90% trở lên;
- `System Answer Exact` trên toàn bộ `procedure-*` từ 95% trở lên;
- các câu người dùng cốt lõi trong tập hồi quy đạt 100%;
- không còn `false_rejection` ở target hướng dẫn đăng ký học phần;
- nhóm `noisy` đạt ít nhất 85%;
- OOD `safe_rejection_rate` không thấp hơn 94%;
- không xuất hiện lỗi SPARQL hoặc IRI mới có tính hệ thống.

Nếu một điều kiện không đạt, kết quả được báo cáo theo target cụ thể. Không tự
động sửa dataset hoặc chạy thêm một checkpoint; người dùng quyết định bước kế
tiếp theo dựa trên báo cáo đó.

## Sản phẩm của đợt triển khai

1. Train được bổ sung 450–550 mẫu có kiểm duyệt.
2. Báo cáo ma trận độ phủ ở cấp target ngữ nghĩa.
3. Báo cáo leakage, catalogue, SPARQL và tokenizer đều đạt.
4. Một artifact T5Gemma2 mới và một báo cáo benchmark so sánh trực tiếp với
   checkpoint hiện tại.
5. Danh sách lỗi còn lại ở dạng câu hỏi người dùng và nguyên nhân nghiệp vụ,
   không chỉ là thuật ngữ nội bộ của codebase.
