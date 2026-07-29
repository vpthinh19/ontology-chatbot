# Thiết kế tăng mật độ dữ liệu train cho quy trình học vụ

## Bối cảnh

Vòng phục hồi trước đã nâng độ chính xác quy trình của T5Gemma2 từ 82,05%
lên 89,73%. Kết quả này chứng minh việc tăng độ phủ train theo target SPARQL
có hiệu quả, nhưng chưa đạt ngưỡng nghiệm thu 95% dành cho quy trình học vụ.

Dataset hiện có 2.888 câu, gồm 2.079 câu train, 402 câu validation và 407 câu
test. Trong train có 962 câu quy trình phủ đủ 142 target SPARQL. Tuy nhiên,
110/142 target mới có đúng sáu câu. Mật độ này còn thấp khi mỗi target phải
được nhận diện qua nhiều cách diễn đạt tiếng Việt và bốn register khác nhau.

Test quy trình hiện còn 19 lỗi. Hai register yếu nhất là `neutral` với 88,89%
và `noisy` với 77,27%. Validation và test đã được xác nhận đúng semantic; lỗi
còn lại được xem là bằng chứng train chưa dạy đủ, không phải lý do để thay đổi
tập đánh giá.

## Mục tiêu

Bổ sung 600–800 câu train chất lượng cao để T5Gemma2 học chắc toàn bộ miền quy
trình học vụ, đặc biệt là:

- nhận diện đúng quy trình được hỏi;
- phân biệt hướng dẫn, điều kiện, kết quả, thời hạn, nguồn và biểu mẫu;
- xử lý tốt câu trung tính, khẩu ngữ, viết tắt và không dấu còn hiểu được;
- giữ nguyên khả năng từ chối câu ngoài miền.

Mục tiêu không phải học thuộc câu test. Benchmark chỉ cho biết những chiều
ngữ nghĩa đang yếu để định hướng cách viết train mới.

## Nguyên tắc cố định

- Giữ nguyên toàn bộ validation và test.
- Không chuyển câu giữa các split.
- Không sao chép, rút gọn, bỏ dấu hoặc paraphrase sát câu validation/test để
  tạo train.
- Không thay đổi ontology, query catalogue, schema SPARQL, preprocessing,
  tokenizer, model, hyperparameter hoặc giao thức benchmark.
- Không tăng OOD đại trà; OOD safe rejection hiện đã đạt 94,44%.
- Không dùng template rồi thay tên quy trình hàng loạt.
- Không tạo câu nhiễu đến mức người dùng bình thường cũng không hiểu được.
- Chỉ fine-tune sau khi toàn bộ dataset qua cổng kiểm tra tĩnh.

## Đơn vị phân bổ

Mỗi target được xem là một ánh xạ độc lập:

```text
quy trình cụ thể × nội dung cần hỏi × SPARQL canonical
```

Ví dụ, ba target sau phải được dạy riêng:

```text
Đăng ký học phần × hướng dẫn
Đăng ký học phần × điều kiện
Đăng ký học phần × thời hạn
```

Quota train được chốt như sau:

- mọi target quy trình đạt ít nhất 10 câu;
- target canonical được mong đợi trong 19 lỗi benchmark đạt 14–18 câu;
- target hướng dẫn của 22 quy trình đạt ít nhất 14 câu;
- các target quan trọng của đăng ký học phần đạt 18–20 câu;
- khoảng 60% dữ liệu mới thuộc `neutral` và `noisy`;
- phần còn lại duy trì `formal`, `colloquial` và tạo cặp tương phản.

Ngân sách toàn vòng là 600–800 câu train mới. Nếu quota thực tế đòi hỏi vượt
ngân sách, phải dừng và báo cáo trước khi mở rộng.

## Cặp tương phản

Model phải học đồng thời thực thể và nội dung cần hỏi. Với cùng một quy trình,
train cần các câu gần nhau về chủ đề nhưng khác rõ mục đích:

| Câu hỏi | Nội dung cần lấy |
|---|---|
| Đổi ngành như thế nào? | Hướng dẫn |
| Em có được đổi ngành không? | Điều kiện |
| Hạn nộp đơn đổi ngành là khi nào? | Thời hạn |
| Nộp đơn đổi ngành ở đâu? | Nơi tiếp nhận |
| Đổi ngành dùng mẫu nào? | Biểu mẫu bắt buộc |
| Tải đơn đổi ngành ở đâu? | Liên kết tải biểu mẫu |
| Ai quyết định cho đổi ngành? | Thẩm quyền |
| Sau khi đổi ngành thì kết quả cũ ra sao? | Kết quả |

Cặp tương phản phải tự nhiên đối với chính quy trình đó. Không được tạo một
khung câu chung rồi thay tên thực thể một cách cơ học.

## Quy trình biên soạn

Dữ liệu được viết theo từng lô 40–80 câu:

```text
Target ontology
    ↓
Tính số câu còn thiếu theo quota
    ↓
Viết câu theo register và chiều ngữ nghĩa yếu
    ↓
Đối chiếu semantic với target
    ↓
Thực thi SPARQL trên ontology
    ↓
Kiểm tra trùng lặp và rò rỉ val/test
    ↓
Nhập vào train
```

Mỗi lô phải qua đủ các cổng sau:

1. Câu hỏi thực sự yêu cầu dữ liệu mà target trả về.
2. Câu hỏi trỏ đúng quy trình, kể cả khi có các quy trình gần nghĩa.
3. Nội dung cần hỏi khớp đúng thuộc tính SPARQL.
4. SPARQL parse được, thực thi được và trả đúng dữ liệu ontology.
5. Câu tự nhiên, có ý nghĩa độc lập và phù hợp register đã gán.
6. Không có câu sao chép hoặc paraphrase sát validation/test.
7. Hai câu chỉ khác đại từ, dấu câu hoặc lỗi chính tả không được tính là hai
   sample độc lập.
8. Câu `noisy` vẫn phải đủ thông tin để con người hiểu được.

Mười chín lỗi benchmark chỉ được quy về các chiều cần tăng cường, chẳng hạn
nhận diện thực thể, phân biệt điều kiện với kết quả hoặc phân biệt nguồn với
hướng dẫn. Target cần tăng quota là target canonical mà câu test mong đợi,
không phải target model đã dự đoán nhầm. Nội dung nguyên văn của test không
được dùng làm mẫu train.

## Khóa dataset và nghiệm thu

Sau khi hoàn thành 600–800 câu mới:

1. Xác minh quota của đủ 142 target.
2. Xác minh phân bố bốn register và các cặp tương phản.
3. Xác minh toàn bộ SPARQL với ontology canonical.
4. Kiểm tra trùng lặp nội bộ và rò rỉ sang validation/test.
5. Sinh báo cáo phân bố và khóa checksum dataset.
6. Fine-tune T5Gemma2 đúng một lần với cấu hình đã chốt.
7. Chọn checkpoint bằng validation.
8. Benchmark test đúng một lần, báo cáo toàn bộ lỗi rồi dừng.

Tiêu chí nghiệm thu không thay đổi:

| Tiêu chí | Ngưỡng |
|---|---:|
| System Answer Exact toàn test | ≥90% |
| Answer Exact riêng quy trình | ≥95% |
| Từng register quy trình | ≥90% |
| Bảy câu người dùng cốt lõi | 100% |
| OOD safe rejection | ≥94% |
| False rejection hướng dẫn đăng ký học phần | 0 |

Nếu checkpoint không đạt, chỉ báo cáo kết quả. Không tự sửa dataset, thay đổi
hyperparameter hoặc chạy thêm một lần huấn luyện dựa trên test vừa xem.

## Giới hạn vận hành

Vòng này chỉ tăng mật độ train cho quy trình học vụ. Không thực hiện các công
việc sau:

- benchmark BARTpho hoặc ViT5;
- chuyển đổi CTranslate2;
- sửa webapp, UX hoặc deployment;
- mở rộng ontology hoặc query catalogue;
- refactor package, CLI hay hệ thống báo cáo;
- sửa script phụ nếu lỗi của nó không trực tiếp chặn biên soạn hoặc nghiệm thu
  dataset.

Nếu công cụ phụ gặp lỗi nhưng công việc chính vẫn làm được bằng công cụ hiện
có, ghi nhận và tiếp tục. Nếu lỗi thực sự chặn dataset hoặc fine-tuning, dừng
và báo cáo thay vì mở rộng phạm vi để sửa.
