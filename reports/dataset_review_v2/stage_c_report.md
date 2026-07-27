# Hoàn tất Stage C — review ngôn ngữ

Stage C đã đọc đủ 948 input của semantic draft theo family và bốn register.
Không dùng điểm model hoặc benchmark để quyết định giữ, sửa hay loại câu.

## Kết quả trước và sau

| Đại lượng | Sau Stage B | Sau Stage C |
|---|---:|---:|
| Record | 948 | 865 |
| Semantic family | 233 | 217 |
| Target SPARQL | 87 | 85 |
| Formal | 237 | 216 |
| Neutral | 237 | 217 |
| Colloquial | 237 | 216 |
| Noisy | 237 | 216 |

Stage C viết lại 87 input và loại 83 input. Hai target biến mất chỉ là hai biến
thể SPARQL không `DISTINCT` của truy vấn liệt kê toàn bộ condition/outcome;
target canonical `SELECT DISTINCT` tương ứng vẫn được giữ. Không target nào của
record còn lại bị sửa.

## Những gì đã sửa

- Loại câu nói về ontology, class, cá thể, cơ sở tri thức, chatbot hoặc cách hệ
  thống lưu dữ liệu.
- Viết lại câu dùng “đầu ra”, “liên kết”, “check”, `full`, `list` và các cách
  diễn đạt máy móc khác.
- Đồng bộ câu hỏi kết quả học bổng với nguyên tắc xếp hạng và giới hạn chỉ tiêu.
- Làm rõ biểu mẫu xét tốt nghiệp chỉ dùng khi đề nghị xét sớm.
- Phân biệt nơi tiếp nhận và nơi xử lý hồ sơ chuyển ngành trong ngôn ngữ hỏi.
- Rút năm family đã merge từ tám câu gần trùng về đúng bốn register.
- Chỉ giữ một family sạch cho mỗi truy vấn liệt kê toàn cục; bỏ các bản sao dùng
  ngôn ngữ schema.
- Giữ những câu nói đời thường có nghĩa rõ như “đóng tiền học sao” và “tui rớt
  môn rồi”, không biến noisy thành chữ bị phá ngẫu nhiên.

## Cổng chất lượng

- 216 family có đủ formal, neutral, colloquial và noisy.
- `cap-066-f04` là family duy nhất có một câu; đây là nhu cầu đếm kèm liệt kê và
  được để Stage D bổ sung có mục tiêu.
- Không có exact duplicate sau normalizer.
- Không có lexical near-duplicate khác family ở ngưỡng 0,84.
- Không còn meta-language hoặc filler bị cấm.
- 85/85 target thực thi có kết quả trên ontology v12.
- BARTpho: không `<unk>` ở source/target, source tối đa 32 token, target tối đa
  93 token.
- ViT5: không `<unk>` ở source/target, source tối đa 30 token, target tối đa
  124 token.

Đầu ra Stage C là `resources/datasets/sparql_v2/language_draft.jsonl`. Stage D
chỉ bổ sung family khi ma trận coverage chứng minh đang thiếu; không nhân
paraphrase để lấy lại 83 câu đã loại.
