# Thiết kế phục hồi độ phủ truy vấn quy trình

## Bối cảnh

Checkpoint T5Gemma2 hiện tại đạt `System Answer Exact` 86,67% trên 300 câu
test, nhưng nhóm truy vấn quy trình chỉ đạt 64/78 câu, tương đương 82,05%.
Các lỗi bao gồm cả câu hỏi cốt lõi như `đăng ký học phần sao`, nên checkpoint
chưa đủ an toàn cho nghiệm thu hoặc production.

Validation quy trình chỉ đạt 62/78 câu, tương đương 79,49%. Validation hiện
phủ 59/142 target quy trình và test phủ 58/142 target. Chỉ 6/142 target trong
train có đủ bốn register; vì vậy benchmark hiện tại chưa thể chứng minh toàn
miền quy trình đã tốt.

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
có 58 câu cho 22 quy trình. Riêng đăng ký học phần chỉ có ba câu mang
`query_id` này; nếu tính thêm hai câu `procedure-overview` dùng chung target
SPARQL thì target vẫn chỉ có năm cách diễn đạt trong train.

## Mục tiêu

Tăng độ tin cậy của model trên các quy trình học vụ bằng cách cân bằng train
theo từng target ngữ nghĩa cụ thể, đồng thời giữ nguyên tính độc lập của
validation/test và ranh giới từ chối ngoài miền.

Quy trình học vụ là miền ưu tiên tuyệt đối của dataset. Các miền học phí,
chứng chỉ, quy mô lớp và biểu mẫu vẫn được giữ để chatbot hữu ích, nhưng không
được làm giảm độ phủ hoặc chất lượng đánh giá quy trình. Sau đợt phục hồi, số
mẫu quy trình trong train phải ít nhất gấp hai lần số mẫu
`no-information`.

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

- Bổ sung và cân bằng train, validation và test theo target quy trình.
- Không tái chia split và không chuyển câu giữa train, validation và test.
- Câu validation/test hiện có được giữ nguyên nếu audit chứng minh câu hỏi,
  SPARQL và kết quả ontology khớp nhau.
- Chỉ sửa câu hoặc target validation/test khi audit có bằng chứng về sai lệch
  ngữ nghĩa; mọi thay đổi phải được ghi lại cùng lý do.
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

Sau khi áp dụng mức nền và mức ưu tiên, train dự kiến có 891–991 câu quy trình
trên tổng số khoảng 2.000–2.125 câu. Miền quy trình khi đó chiếm khoảng 44–48%
train tùy số mẫu thực tế và có số positive lớn hơn ít nhất hai lần nhóm từ
chối.

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
sách của đợt phục hồi là 450–550 câu positive quy trình trong train; nếu việc
áp dụng đúng các ngưỡng trên cần vượt mức này thì phải dừng và báo cáo trước
khi mở rộng phạm vi.

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
negative chỉ để tăng số lượng. Tổng hard negative mới không vượt quá 25 câu
và chỉ được thêm khi train sau cùng vẫn có số positive quy trình lớn hơn hoặc
bằng hai lần tổng số câu `no-information`.

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

## Audit validation/test hiện có

Toàn bộ 78 câu quy trình trong validation và 78 câu quy trình trong test phải
được đọc và đối chiếu riêng lẻ trước khi thêm dữ liệu mới. Mỗi câu được kiểm
tra theo ba lớp:

```text
ý nghĩa câu hỏi → dữ liệu SPARQL yêu cầu → kết quả thực thi trên ontology
```

Kết quả audit chỉ có ba trạng thái:

1. `keep`: câu hỏi rõ nghĩa và kết quả SPARQL trả đủ nội dung được hỏi;
2. `revise-input`: target đúng nhưng câu hỏi chứa thêm ý mà target không trả;
3. `revise-target`: câu hỏi rõ nghĩa nhưng target hiện tại chọn sai dữ liệu.

Không dùng trạng thái mơ hồ như `acceptable` hoặc `challenge`. Câu khó vẫn
được giữ nếu có một đáp án chuẩn rõ ràng. Với câu hỏi nhiều ý, nếu SPARQL hiện
tại không trả đủ và catalogue không có target kết hợp tương ứng, câu được rút
gọn về một ý được hỗ trợ. Đợt phục hồi này không mở rộng query catalogue để
theo đuổi mọi tổ hợp tùy ý.

Audit phải chú ý đặc biệt các câu đã phát hiện rủi ro:

- câu hỏi vừa yêu cầu điều kiện vừa yêu cầu hướng dẫn;
- câu hỏi vừa hỏi thời hạn vừa hỏi thời gian hiệu lực hoặc kết quả;
- câu hỏi yêu cầu đếm nhưng SPARQL chỉ liệt kê;
- câu dùng `bảo lưu` có thể chỉ nghỉ tạm thời hoặc bảo lưu tín chỉ;
- câu đồng thời nhắc trao đổi sinh viên và công nhận tín chỉ.

Mọi chỉnh sửa giữ nguyên split và ID. Báo cáo audit ghi ID, trạng thái, nội
dung cũ, nội dung mới và lý do nghiệp vụ. Benchmark cũ vẫn tồn tại trong
artifact đã lưu; độ đúng của benchmark cuối quan trọng hơn việc giữ checksum
của một nhãn đã được chứng minh là sai.

## Mở rộng validation/test

Sau audit, validation và test được bổ sung nhưng không tái chia. Mỗi một trong
142 target SPARQL quy trình phải có ít nhất:

- một câu độc lập trong validation;
- một câu độc lập trong test.

Các target `procedure-instruction` phải có ít nhất hai câu ở mỗi split đánh
giá. Target hướng dẫn đăng ký học phần phải có ít nhất bốn câu trong
validation và bốn câu trong test, bao gồm đủ formal, neutral, colloquial và
noisy.

Câu bổ sung không được sao chép hoặc sửa nhẹ câu train hay split đánh giá còn
lại. Theo độ phủ hiện tại, dự kiến bổ sung 85–120 câu quy trình vào mỗi split.
Nếu cần vượt ngưỡng này để thỏa contract thì dừng và báo cáo trước khi mở rộng.

Toàn bộ câu test bổ sung phải được khóa trước khi bắt đầu fine-tuning. Sau khi
xem prediction cuối, không sửa test hoặc thêm train để đuổi theo chính các câu
đó. Báo cáo cuối tách kết quả của 300 câu test hiện có và phần target quy trình
mới bổ sung, đồng thời công bố kết quả hợp nhất.

## Audit trước fine-tuning

Dataset chỉ được phép dùng để train khi có báo cáo chứng minh:

- mọi target quy trình đạt mức nền sáu mẫu;
- các target ưu tiên đạt ngưỡng 8–12 mẫu đã gán;
- bốn register được phủ ở cấp target, không chỉ cấp `query_id`;
- cả 156 câu quy trình validation/test cũ đã có kết quả audit ngữ nghĩa;
- mọi chỉnh sửa validation/test đều có bằng chứng và giữ nguyên split/ID;
- đủ 142 target quy trình trong cả validation và test;
- mọi target hướng dẫn và đăng ký học phần đạt ngưỡng đánh giá riêng;
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
- từng register trong riêng miền quy trình đạt ít nhất 90%;
- OOD `safe_rejection_rate` không thấp hơn 94%;
- không xuất hiện lỗi SPARQL hoặc IRI mới có tính hệ thống.

Nếu một điều kiện không đạt, kết quả được báo cáo theo target cụ thể. Không tự
động sửa dataset hoặc chạy thêm một checkpoint; người dùng quyết định bước kế
tiếp theo dựa trên báo cáo đó.

## Sản phẩm của đợt triển khai

1. Train được bổ sung 450–550 positive quy trình có kiểm duyệt và không quá
   25 hard negative tương phản.
2. Validation và test mỗi split được bổ sung 85–120 mẫu quy trình độc lập.
3. Báo cáo audit ngữ nghĩa của 156 câu quy trình đánh giá hiện có.
4. Báo cáo ma trận độ phủ ở cấp target ngữ nghĩa cho cả ba split.
5. Báo cáo leakage, catalogue, SPARQL và tokenizer đều đạt.
6. Một artifact T5Gemma2 mới và một báo cáo benchmark so sánh trực tiếp với
   checkpoint hiện tại.
7. Danh sách lỗi còn lại ở dạng câu hỏi người dùng và nguyên nhân nghiệp vụ,
   không chỉ là thuật ngữ nội bộ của codebase.
