# Audit dataset SPARQL v1

Trạng thái: **read-only; chưa sửa nội dung dataset**.

## Tổng quan

- Record: 1112
- Family: 401
- Target SPARQL duy nhất: 80
- Validator hiện tại: đạt
- Exact duplicate sau normalizer: 0
- Ứng viên near-duplicate khác family: 6

### Theo split

| Split | Record | Family | Target |
|---|---:|---:|---:|
| train | 636 | 159 | 79 |
| val | 312 | 78 | 78 |
| test | 164 | 164 | 80 |

## Những gì ảnh hưởng trực tiếp đến model học

- Target validation chưa từng xuất hiện nguyên vẹn ở train: 1
- Target test chưa từng xuất hiện nguyên vẹn ở train: 1
- Ontology term trong validation chưa xuất hiện ở target train: 0
- Ontology term trong test chưa xuất hiện ở target train: 0
- Family train/val có đúng một register: 0
- Family train/val có đủ bốn register: 237
- Family test chỉ có một record: 164 / 164
- Số target train có đúng hai family: 74 / 79
- Target xuất hiện ở cả train/val/test: 77 / 80

### Độ dài generic

| Đại lượng | p50 | p95 | max |
|---|---:|---:|---:|
| Source words | 13 | 20 | 26 |
| Normalized source words | 13 | 21 | 26 |
| Target characters | 75 | 221 | 274 |

### Tokenizer thực tế

| Model | Source max | Source >128 | Source có `<unk>` | Target max | Target >160 | Target `<unk>` | Round-trip lỗi |
|---|---:|---:|---:|---:|---:|---:|---:|
| bartpho | 32 | 0 | 12 | 93 | 0 | 0 | 0 |
| vit5 | 30 | 0 | 0 | 124 | 0 | 0 | 0 |

## Bằng chứng từ validation của model

Chỉ dùng validation của các lượt train cũ; không đọc điểm test để đưa ra ưu tiên v2.

| Model | Run | Observation | Answer exact |
|---|---:|---:|---:|
| bartpho | 3 | 936 | 67.09% |
| vit5 | 3 | 936 | 71.58% |

### Theo register

| Register | bartpho | vit5 |
|---|---:|---:|
| colloquial | 71.37% | 77.78% |
| formal | 73.93% | 83.76% |
| neutral | 80.77% | 81.20% |
| noisy | 42.31% | 43.59% |

### Theo query shape

| Query shape | bartpho | vit5 |
|---|---:|---:|
| aggregate | 47.22% | 38.89% |
| aggregate_filter | 58.33% | 66.67% |
| direct | 76.92% | 74.36% |
| graph_hop | 63.89% | 72.22% |
| multi_column | 38.54% | 68.75% |

### Theo độ mới của target so với train

| Nhóm | Observation | Answer exact |
|---|---:|---:|
| seen_exact_target | 1848 | 69.43% |
| unseen_exact_target_seen_terms | 24 | 62.50% |

- Record validation sai ở mọi lượt quan sát: 30
- Persistent failure theo register: colloquial=3, formal=1, neutral=3, noisy=23
- Persistent failure theo shape: aggregate=4, direct=11, graph_hop=12, multi_column=3
- Family validation có answer exact ≤ 50%: 14
- Phân loại lỗi: extra_branch=133, missing_branch=143, parse_error=18, semantic_mismatch=18, wrong_iri=83, wrong_property=179

## Coverage ontology

- Named individual được neo trực tiếp trong target: 22 / 32
- Datatype property xuất hiện trong target: 13 / 13
- Object property xuất hiện trong target: 5 / 5
- Class xuất hiện trong target: 6 / 6

Named individual không được neo trực tiếp vẫn có thể được lấy qua object property. Các term chưa xuất hiện chỉ là ứng viên kiểm tra coverage; không tự động thêm câu hỏi.

## Worksheet review

- Tổng family: 401
- Priority: high=35, low=356, medium=10
- Flag: cross_split_lexical_near_duplicate=4, lexical_near_duplicate=8, normalizer_changes_input=217, ontology_meta_language=17, rare_train_target=2, source_unknown_token_bartpho=10, target_missing_from_train=3, validation_answer_exact_at_most_50_percent=14
- Audit không tự quyết định keep/fix/split/merge/drop.

## Giới hạn

- Lexical near-duplicate candidates are review hints, not proof of semantic leakage.
- Ontology terms absent from targets are coverage candidates, not automatic data gaps.
- Learning evidence uses validation runs only; benchmark/test metrics are excluded.
- Register correctness and question naturalness require human review.
