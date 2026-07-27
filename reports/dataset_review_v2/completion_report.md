# Hoàn tất Stage B — semantic draft trên ontology v12

Stage B đã hoàn tất. `sparql_v1` vẫn là baseline bất biến; đầu ra để Stage C
biên tập là `resources/datasets/sparql_v2/draft.jsonl`.

## Kết quả

| Đại lượng | Giá trị |
|---|---:|
| Record kế thừa từ train/val v1 | 948 |
| Family sau khi gộp/tách | 233 |
| Target SPARQL duy nhất | 87 |
| Target có kết quả rỗng | 0 |
| Câu test v1 được sao chép | 0 |

## Quyết định đã áp dụng

- 28 family `fix` trong phạm vi v2 đã được giải quyết.
- 5 family gần trùng đã được gộp bằng `family_id`.
- `prod-0262` được tách thành `cap-066-f04` với target đếm và liệt kê.
- Câu hỏi loại trừ sức khỏe và ngành Ô tô có `FILTER` tương ứng.
- Câu hỏi riêng đơn học trở lại chỉ lấy `StudyResumptionRequestForm`.
- Câu hỏi Condition/Outcome kiểu ontology cũ đã được đổi về nhu cầu người dùng
  và target literal của `condition`/`outcome`.
- Câu hỏi nơi nhận hồ sơ chuyển ngành dùng `receivedBy`; câu hỏi nơi xử lý tiếp
  tục dùng `handledBy`.
- Hai family đăng ký học phần giữ `content` như nội dung tổng quát theo quyết
  định nghiệp vụ, không bổ sung dữ liệu giả.

20 family từng bị chặn bởi dữ liệu tốt nghiệp, học bổng và vai trò phòng ban
không cần đổi target sau khi ontology v12 đã thống nhất sự thật. Family hỏi nơi
tiếp nhận hồ sơ chuyển ngành là trường hợp còn lại và đã chuyển sang
`receivedBy`.

## Bằng chứng

- `completion_manifest.json` khóa checksum nguồn, ontology và draft.
- `target_evidence_v12.jsonl` lưu kết quả thực thi thật của cả 87 target.
- Script `apply_dataset_stage_b` tái sinh draft và từ chối decision chưa được
  xử lý, family có nhiều target, target rỗng hoặc ký tự ngoài contract.
- Cả 87 target round-trip chính xác, không `<unk>` trên tokenizer thật của
  BARTpho và ViT5; độ dài lớn nhất lần lượt là 91 và 123 token.

## Cổng tiếp theo

Stage C có thể bắt đầu trực tiếp trên `draft.jsonl`. Stage C chỉ biên tập chất
lượng câu tiếng Việt và metadata register; không đổi target đã khóa nếu không
phát hiện bằng chứng ngữ nghĩa mới.
