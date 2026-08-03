---
license: gemma
language:
- vi
library_name: transformers
pipeline_tag: other
base_model: google/t5gemma-2-270m-270m
tags:
- sparql
- ontology
- vietnamese
- ctranslate2
---

# NTU Ontology Chatbot — T5Gemma2

Model seq2seq tiếng Việt sinh truy vấn SPARQL cho chatbot hỏi đáp quy trình học
vụ Trường Đại học Nha Trang. Model sinh đúng một trong hai dạng:

```text
SELECT ?answer WHERE { ... }
```

```text
không có thông tin
```

Model không chứa câu trả lời học vụ. SPARQL phải được xác minh và thực thi trên
ontology của project để lấy nhãn hoặc literal trả về người dùng.

## Huấn luyện

- Base model: `google/t5gemma-2-270m-270m`;
- dataset: 4.454 câu (3.645 train, 402 validation, 407 test);
- PEFT LoRA rank 32, alpha 64, dropout 0; adapter tốt nhất được merge vào base;
- batch 8, learning rate 1e-4, cosine scheduler, BF16, seed 42;
- greedy decoding; checkpoint chọn bằng validation Answer Exact;
- hoàn tất 18 epoch do dừng sớm.

## Kết quả — baseline v0.4.1

| Backend | Answer Exact | Result F1 | System Answer Exact |
|---|---:|---:|---:|
| Transformers | 90,66% | 92,74% | 92,38% |
| CTranslate2 int8 | 91,15% | 93,38% | 92,87% |

Kết quả đo trên 407 câu test độc lập. T5Gemma2 đạt 96,22% Answer Exact trên 185
câu quy trình. Safe Rejection ngoài miền đạt 92,22%; câu noisy và hard negative
gần miền vẫn là giới hạn chính.

Repository lưu fingerprint tại `reports/provenance.json`. Khi
`model_metrics.status` là `stale`, bảng này chỉ mô tả baseline v0.4.1 và không
phải kết quả đánh giá ontology/dataset canonical mới.

## Sử dụng Transformers

```python
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

repo = "vpthinh19/ntu-ontology-t5gemma-2"
tokenizer = AutoTokenizer.from_pretrained(repo, fix_mistral_regex=False)
model = AutoModelForSeq2SeqLM.from_pretrained(repo)

question = "đăng ký học phần như thế nào"
inputs = tokenizer(question, return_tensors="pt", truncation=True, max_length=128)
output = model.generate(**inputs, max_new_tokens=160, do_sample=False, num_beams=1)
print(tokenizer.decode(output[0], skip_special_tokens=True))
```

Model CTranslate2 int8 nằm trong thư mục `ctranslate2/`. Hệ thống hoàn chỉnh,
ontology, normalizer, validator SPARQL và hướng dẫn tái lập nằm tại
<https://github.com/vpthinh19/ontology-chatbot>.

## Giới hạn và giấy phép

Model chỉ dành cho miền ontology đi kèm, không phải chatbot kiến thức chung.
Output sai hoặc query không có kết quả phải được chuyển thành `Không có thông
tin.`; không thực thi query thay đổi graph. Model kế thừa điều khoản sử dụng
Gemma từ base model.
