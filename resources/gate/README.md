# Dataset nhận diện phạm vi ontology

Dataset huấn luyện PhoBERT quyết định một câu hỏi có được ontology hiện tại hỗ
trợ đầy đủ hay không. Mỗi dòng JSON Lines có đúng hai trường:

```json
{"input":"điều kiện tốt nghiệp là gì","label":"in_scope"}
{"input":"thư viện mở cửa lúc nào","label":"out_of_scope"}
```

- `in_scope`: toàn bộ yêu cầu trong câu có thể được trả lời bằng ontology và
  danh mục SPARQL hiện tại.
- `out_of_scope`: không thể trả lời, chỉ trả lời được một phần, không có yêu
  cầu rõ ràng hoặc nằm ngoài phạm vi hỗ trợ.

| Split | In scope | Out of scope | Tổng |
|---|---:|---:|---:|
| Train | 1.403 | 1.403 | 2.806 |
| Validation | 430 | 430 | 860 |
| Test | 430 | 430 | 860 |

Positive giữ nguyên câu hỏi và split của dataset sinh SPARQL. Negative gồm ba
nhóm: trợ lý đa miền ngoài học vụ, câu hỏi đại học gần miền nhưng ontology
không hỗ trợ, và câu trộn trong đó ontology chỉ trả lời được một phần. Câu có
dấu, không dấu, viết tắt và ngôn ngữ nói đều được giữ lại. Dataset không qua
word segmentation.

Các câu ngoài miền đa dụng được tuyển chọn từ MASSIVE 1.1; câu đại học gần
miền được tuyển chọn từ PTIT Student Q&A 2025. Cả hai nguồn phát hành theo
CC BY 4.0:

- <https://github.com/alexa/massive>
- <https://huggingface.co/datasets/HeyDunaX/ptit-student-qa>

Có thể kiểm tra schema, cân bằng và trùng lặp xuyên split bằng:

```bash
uv run --frozen validate_gate_dataset
```
