# Báo cáo thí nghiệm SPARQL v1

## Mục đích và giao thức

Thí nghiệm so sánh `vinai/bartpho-syllable` và `VietAI/vit5-base` trên cùng
bài toán sinh trực tiếp câu `SELECT` SPARQL từ câu hỏi tiếng Việt. Mỗi model
được train độc lập với seed 7, 21 và 42. Checkpoint được chọn duy nhất bằng
`answer_exact_rate` trên validation; benchmark đóng băng chỉ được dùng sau
khi train.

- Dataset: 636 câu train và 312 câu validation, 237 semantic family.
- Benchmark: 164 câu độc lập, cân bằng 41 câu cho mỗi register.
- Epoch: 60; đánh giá mỗi 10 epoch; learning rate `3e-5` không scheduler.
- Effective batch size: 8; dynamic padding bội số 8.
- AdamW 8-bit, BF16, TF32, greedy decoding, `torch.compile=False`.
- Chấm checkpoint đã lưu với batch size 1.
- Phần cứng: NVIDIA GeForce RTX 4050 Laptop GPU 6 GB.
- Phần mềm: Python 3.12, PyTorch 2.13.0+cu130, Transformers 5.14.1.

Revision model được khóa:

- BARTpho: `36eee8b4d648dd99da56462edcda3c5c97f7f3de`;
- ViT5: `2209a38d735ede63e88f5aa52bcdc11a05a37b85`.

Checksum dataset, benchmark và ontology nằm trong
`resources/benchmarks/sparql_v1_manifest.json`. Artifact model và report JSON
nằm dưới `artifacts/sparql_official_v1/` và không được commit vì kích thước
lớn. Các bảng dưới đây báo cáo trung bình ± độ lệch chuẩn mẫu của ba seed.

## Kết quả chính

| Model | Validation answer exact | Benchmark parse/execute | Benchmark answer exact | Benchmark canonical exact |
|---|---:|---:|---:|---:|
| BARTpho | 67,09% ± 1,30 | 99,59% ± 0,35 | 75,00% ± 2,20 | 74,19% ± 2,46 |
| ViT5 | 71,58% ± 0,49 | 100,00% ± 0,00 | **78,05% ± 1,61** | **77,03% ± 0,93** |

`answer_exact` là metric đầu-cuối chính: chạy query dự đoán trên ontology rồi
so sánh bảng kết quả với đáp án reference. `canonical exact` nghiêm hơn vì yêu
cầu chuỗi query canonical trùng hoàn toàn. ViT5 tốt hơn trung bình 3,05 điểm
phần trăm ở metric chính và ổn định hơn giữa các seed. BARTpho vẫn hợp lệ vì
điểm parse/execute gần tuyệt đối và có ưu thế ở một số query đơn giản.

### Kết quả từng seed trên benchmark

| Model | Seed | Parse | Answer exact | Canonical exact |
|---|---:|---:|---:|---:|
| BARTpho | 7 | 99,39% | 73,17% | 71,95% |
| BARTpho | 21 | 100,00% | 77,44% | 76,83% |
| BARTpho | 42 | 99,39% | 74,39% | 73,78% |
| ViT5 | 7 | 100,00% | 79,88% | 78,05% |
| ViT5 | 21 | 100,00% | 76,83% | 76,22% |
| ViT5 | 42 | 100,00% | 77,44% | 76,83% |

## Theo dạng câu hỏi

| Query shape (số câu) | BARTpho answer exact | ViT5 answer exact |
|---|---:|---:|
| direct (78) | **86,75% ± 1,96** | 82,91% ± 2,67 |
| graph_hop (54) | 77,16% ± 3,85 | **80,25% ± 1,07** |
| multi_column (16) | 58,33% ± 3,61 | **91,67% ± 3,61** |
| aggregate (8) | **37,50% ± 0,00** | 29,17% ± 7,22 |
| aggregate_filter (8) | 16,67% ± 7,22 | **37,50% ± 12,50** |

ViT5 vượt trội rõ ở câu nhiều cột và nhỉnh hơn ở đường đi qua object property.
BARTpho tốt hơn ở truy vấn trực tiếp. `aggregate` và `aggregate_filter` mới có
8 câu mỗi nhóm, nên vừa là điểm yếu thật vừa có độ bất định lớn; chưa đủ căn
cứ để suy rộng từ chênh lệch giữa hai model.

## Theo cách diễn đạt

| Register (41 câu/loại) | BARTpho answer exact | ViT5 answer exact |
|---|---:|---:|
| formal | 81,30% ± 3,73 | **85,37% ± 2,44** |
| neutral | 89,43% ± 1,41 | **91,06% ± 3,73** |
| colloquial | 81,30% ± 1,41 | **87,80% ± 2,44** |
| noisy | 47,97% ± 5,08 | 47,97% ± 1,41 |

Câu nhiễu/viết tắt là điểm yếu lớn nhất của cả hai model. Các lỗi phổ biến là
thiếu nhánh, sai property, thừa nhánh và sai IRI; lỗi cú pháp chỉ xuất hiện ở
hai lượt BARTpho, mỗi lượt một câu.

## Chi phí

| Model | Thời gian train | VRAM train cực đại | Tốc độ benchmark | VRAM suy luận cực đại |
|---|---:|---:|---:|---:|
| BARTpho | 24,68 ± 1,16 phút | 2,97 GiB | 6,08 ± 0,11 câu/giây | 0,75 GiB |
| ViT5 | 22,95 ± 0,47 phút | 2,34 GiB | 3,34 ± 0,13 câu/giây | 0,45 GiB |

Trên máy thử nghiệm, ViT5 train nhanh hơn và dùng ít VRAM hơn, nhưng BARTpho
sinh query nhanh hơn khoảng 1,82 lần. Đây là số đo Transformers/PyTorch batch
size 1, chưa phải kết quả CTranslate2.

Artifact triển khai được chọn bằng validation và được chấm riêng sau convert;
xem `DEPLOYMENT.md`. Không dùng bảng benchmark trên để chọn seed phát hành.

## Kết luận và giới hạn

ViT5 là model ưu tiên cho chất lượng tổng thể; BARTpho là đối chứng mạnh và có
lợi thế tốc độ/direct query. Cả hai đều chứng minh pipeline tokenizer → sinh
SPARQL → parse → thực thi hoạt động ổn định trên GPU 6 GB.

Không sửa dataset, normalizer hay hyperparameter sau khi xem benchmark v1.
Nếu cải thiện câu noisy hoặc aggregate, phải tạo một vòng phát triển mới bằng
train/validation và công bố benchmark v2 độc lập. Bộ benchmark hiện còn nhỏ ở
hai nhóm aggregate và chỉ bao phủ ontology học vụ v11, nên không dùng kết quả
này để tuyên bố khả năng sinh SPARQL tổng quát ngoài miền.

## Tái lập

Ví dụ train và chấm một lượt; thay `--model` và `--seed` để chạy đủ sáu lượt:

```bash
uv run --extra train train_sparql --model bartpho --epochs 60 --eval-every-epochs 10 --seed 7 --save-model --benchmark-after-training --local-files-only --output-dir artifacts/sparql_official_v1
uv run --extra train evaluate_sparql_model --model bartpho --model-dir artifacts/sparql_official_v1/bartpho/seed-7/model --suite benchmark --batch-size 1
```

Tổng hợp trung bình, độ lệch và kiểm tra đủ model/seed:

```bash
uv run summarize_sparql_experiments --output artifacts/sparql_official_v1/summary.json
```
