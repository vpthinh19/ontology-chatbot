# Hoàn tất Stage D — bổ sung coverage có mục tiêu

Stage D đối chiếu `language_draft.jsonl` với ontology v12, sau đó chỉ thêm câu
khi có nhu cầu người dùng hoặc query shape cụ thể còn thiếu. Không dùng model,
điểm benchmark hoặc mục tiêu số lượng để chọn dữ liệu.

## Kết quả trước và sau

| Đại lượng | Sau Stage C | Sau Stage D |
|---|---:|---:|
| Record | 865 | 936 |
| Semantic family | 217 | 234 |
| Target SPARQL | 85 | 102 |
| Formal / neutral / colloquial / noisy | 216 / 217 / 216 / 216 | 234 / 234 / 234 / 234 |
| Direct | 440 | 444 |
| Graph hop | 280 | 316 |
| Multi-column | 100 | 116 |
| Aggregate | 33 | 44 |
| Aggregate + filter | 12 | 16 |

Stage D thêm 71 câu thuộc 17 family mới và hoàn thiện ba register còn thiếu
của `cap-066-f04`. Toàn bộ 234 family hiện có đúng bốn register.

## Coverage đã bổ sung

- Phân biệt rõ Phòng Công tác Chính trị và Sinh viên là nơi **nhận** hồ sơ
  chuyển ngành, còn Phòng Đào tạo Đại học là nơi **xử lý**; có cả câu hỏi từng
  vai trò và câu hỏi hai vai trò cùng lúc.
- Bổ sung tên phòng phụ trách cho bảy quy trình còn thiếu: đăng ký học phần,
  học lại, rút môn, học cải thiện, xét tốt nghiệp, chuyển ngành và học phí.
- Bổ sung kết quả ghi nhận điểm học cải thiện và tên đơn gia hạn nộp học phí.
- Hoàn chỉnh phép đếm nhóm học phí theo khóa với K65.
- Thêm hai cấu trúc aggregate hữu ích: đếm kèm liệt kê quy trình và đếm biểu
  mẫu.
- Thêm câu hỏi lấy trọn thông tin liên hệ của ba phòng chức năng thường gặp:
  Công tác Sinh viên, Đào tạo Đại học và Tài chính.

Ma trận `stage_d_coverage.json` tách rõ hai khái niệm: IRI có xuất hiện trong
target không đồng nghĩa với nhu cầu người dùng đã được phủ; ngược lại, một
individual không được ghi trực tiếp vẫn có thể được truy cập qua graph path.
Vì vậy chín IRI “uncovered” theo phép đếm đơn giản của Stage C không bị tự động
biến thành chín family mới.

## Những gì chủ ý không nhân rộng

- Không tạo mọi tổ hợp nhóm học phí × `programName`.
- Không tạo mọi tổ hợp quy trình × văn bản căn cứ.
- Chưa thêm thẻ liên hệ đầy đủ cho Văn phòng Trường vì email trực tiếp đã có và
  ba phòng gắn với quy trình sinh viên được ưu tiên hơn.

Các quyết định `add`, `complete`, `defer` và `not_gap` cùng lý do nằm trong
`stage_d_decisions.json`.

## Cổng chất lượng

- 102/102 target parse, thực thi và trả kết quả trên ontology v12.
- Không có exact duplicate sau normalizer hoặc lexical near-duplicate khác
  family ở ngưỡng 0,84.
- Không có meta-language, filler, family nhiều target hoặc target rỗng.
- BARTpho: source/target không `<unk>`, không lỗi round-trip; source tối đa 32
  token, target tối đa 93 token.
- ViT5: source/target không `<unk>`, không lỗi round-trip; source tối đa 30
  token, target tối đa 124 token.
- Test riêng Stage D và tokenizer đạt trước khi chạy toàn bộ test suite.

Đầu ra Stage D là `resources/datasets/sparql_v2/coverage_draft.jsonl`. Stage E
mới chia toàn bộ family thành train/validation/test; chưa train model và chưa
mở benchmark trong Stage D.
