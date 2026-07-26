# Thử nghiệm giới hạn kiến trúc với T5Gemma2

## Câu hỏi thí nghiệm

Thử nghiệm này được thực hiện trước Stage B để kiểm tra liệu chất lượng hiện tại
có bị giới hạn bởi kiến trúc model hay không. `google/t5gemma-2-270m-270m`
được train trên đúng SPARQL dataset v1 đã đóng băng và so với kết quả chính thức
của BARTpho, ViT5. Không sửa câu nguồn, target, split, normalizer hoặc ontology
sau khi xem benchmark.

Đây là thử nghiệm bổ sung, chưa tự động thay đổi danh sách hai model chính trong
`PROJECT_SPEC.md`. Quyết định đưa T5Gemma2 vào nghiên cứu chính chỉ nên được đưa
ra sau khi cân nhắc chênh lệch chất lượng và chi phí bên dưới.

## Thiết lập công bằng

- Dataset: 636 train, 312 validation; benchmark đóng băng gồm 164 câu.
- Seed: 7, 21 và 42.
- 60 epoch, đánh giá mỗi 10 epoch, learning rate `3e-5` không scheduler.
- Effective batch size 8, AdamW 8-bit, BF16, TF32, dynamic padding.
- Greedy decoding, không `torch.compile`; chọn checkpoint chỉ bằng
  `answer_exact_rate` trên validation.
- GPU: NVIDIA GeForce RTX 4050 Laptop GPU 6 GB.
- Revision T5Gemma2:
  `7c38f16641f455ef0685b18431faf1b17722d5a1`.

T5Gemma2 có 786.029.296 tham số trainable, nên tên checkpoint
`270m-270m` không có nghĩa toàn model chỉ có 270 triệu tham số. Model cần
gradient checkpointing và eval batch size 4 để train ổn định trong 6 GB VRAM;
các lựa chọn này không đổi effective batch hoặc số optimizer update.

## Kiểm tra tokenizer và generation

Tokenizer local mã hóa được toàn bộ 80 target SPARQL duy nhất, không sinh
`<unk>`, giải mã vòng lại chính xác. Độ dài lớn nhất là 33 token ở nguồn và 65
token ở target, thấp hơn giới hạn 128/160.

Có hai mặc định của checkpoint không phù hợp với sinh cấu trúc:

1. tokenizer thêm BOS nhưng không tự thêm EOS vào target;
2. generation config mặc định bật sampling (`top_k=64`, `top_p=0.95`).

Pipeline vì vậy bổ sung EOS vào label nếu còn thiếu và ép greedy decoding
(`do_sample=False`). Trước sửa, loss giảm nhưng output thường không kết thúc và
parse rate bằng 0. Sau sửa, learning audit 100 update trên 16 mẫu đạt 100%
parse/execute và 93,75% exact. Đây là sửa giao tiếp tokenizer/generation có thể
tái lập, không phải sửa vocabulary hay dữ liệu.

## Kết quả

Các số `±` là trung bình và độ lệch chuẩn mẫu của ba seed.

| Model | Validation answer exact | Benchmark parse/execute | Benchmark answer exact | Benchmark canonical exact |
|---|---:|---:|---:|---:|
| BARTpho | 67,09% ± 1,30 | 99,59% ± 0,35 | 75,00% ± 2,20 | 74,19% ± 2,46 |
| ViT5 | 71,58% ± 0,49 | 100,00% ± 0,00 | 78,05% ± 1,61 | 77,03% ± 0,93 |
| **T5Gemma2** | **72,76% ± 1,67** | 99,80% ± 0,35 | **83,74% ± 1,86** | **83,33% ± 1,96** |

T5Gemma2 hơn ViT5 1,18 điểm phần trăm trên validation và 5,69 điểm trên
benchmark answer exact. Vì chỉ có ba seed, kết quả cho thấy lợi thế thực nghiệm
trên bộ test này nhưng chưa đủ để tuyên bố ý nghĩa thống kê rộng hơn.

### Từng seed

| Seed | Checkpoint tốt nhất | Validation answer exact | Benchmark parse | Benchmark answer exact |
|---:|---:|---:|---:|---:|
| 7 | epoch 60 | 71,79% | 99,39% | 81,71% |
| 21 | epoch 50 | 71,79% | 100,00% | 85,37% |
| 42 | epoch 20 | 74,68% | 100,00% | 84,15% |

Checkpoint tốt nhất xuất hiện ở ba epoch khác nhau. Seed 21 giảm từ 67,95% ở
epoch 30 xuống 62,50% ở epoch 40 rồi phục hồi lên 71,79% ở epoch 50. Model lớn
vẫn nhạy với seed và overfit/dao động trên dataset nhỏ; không nên chọn một số
epoch cố định mà bỏ validation checkpoint selection.

### Theo cách diễn đạt

| Register (41 câu/loại) | BARTpho | ViT5 | T5Gemma2 |
|---|---:|---:|---:|
| formal | 81,30% | 85,37% | 83,74% ± 3,73 |
| neutral | 89,43% | 91,06% | **91,87% ± 2,82** |
| colloquial | 81,30% | 87,80% | 83,74% ± 1,41 |
| noisy | 47,97% | 47,97% | **75,61% ± 4,88** |

Hai cột baseline là mean ba seed từ báo cáo v1. Cải thiện lớn nhất nằm ở câu
nhiễu: +27,64 điểm so với cả hai baseline. T5Gemma2 không thắng ViT5 ở formal
và colloquial, nên lợi thế tổng thể không đồng đều trên mọi cách diễn đạt.

### Theo dạng query

| Query shape (số câu) | BARTpho | ViT5 | T5Gemma2 |
|---|---:|---:|---:|
| direct (78) | 86,75% | 82,91% | **90,60% ± 2,67** |
| graph_hop (54) | 77,16% | 80,25% | **85,19% ± 1,85** |
| multi_column (16) | 58,33% | **91,67%** | 85,42% ± 7,22 |
| aggregate (8) | 37,50% | 29,17% | **37,50% ± 12,50** |
| aggregate_filter (8) | 16,67% | 37,50% | **50,00% ± 21,65** |

T5Gemma2 mạnh hơn rõ ở direct, graph hop và aggregate filter, nhưng kém ViT5 ở
multi-column. Hai nhóm aggregate chỉ có 8 câu mỗi nhóm nên độ lệch lớn và không
đủ để kết luận chắc chắn.

## Chi phí trên RTX 4050 6 GB

| Model | Thời gian train | VRAM train cực đại | Tốc độ suy luận batch 1 | VRAM suy luận cực đại |
|---|---:|---:|---:|---:|
| BARTpho | 24,68 ± 1,16 phút | 2,97 GiB | 6,08 câu/giây | 0,75 GiB |
| ViT5 | 22,95 ± 0,47 phút | 2,34 GiB | 3,34 câu/giây | 0,45 GiB |
| T5Gemma2 | 27,41 ± 0,12 phút | 4,82 GiB | 2,30 câu/giây | 1,49 GiB |

T5Gemma2 fit được và cả ba lượt train đều hoàn tất, nhưng gần giới hạn phần
cứng: VRAM train gấp khoảng 2,06 lần ViT5; tốc độ sinh chỉ bằng khoảng 69% ViT5
và 38% BARTpho. Số đo là Transformers/PyTorch, chưa phải CTranslate2.

## Kết luận trước Stage B

Kiến trúc/pretraining đúng là một phần giới hạn: giữ nguyên dữ liệu mà
T5Gemma2 tăng benchmark answer exact từ 78,05% lên 83,74%, đặc biệt cải thiện
câu nhiễu. Kỳ vọng model mới outperform hai baseline được xác nhận trên bộ
benchmark hiện tại.

Dataset vẫn là giới hạn độc lập: validation chỉ tăng 1,18 điểm, aggregate còn
yếu, multi-column giảm, và đường học dao động theo seed. Model mạnh hơn nâng
trần nhưng không thay thế Stage B. Stage B vẫn cần cải thiện độ bao phủ, cân
bằng query shape, chất lượng paraphrase/noisy và kiểm soát semantic family mà
không dùng benchmark v1 để chỉnh dữ liệu.

Về lựa chọn thực tế: T5Gemma2 là ứng viên chất lượng tốt nhất; ViT5 vẫn là
ứng viên hiệu quả tài nguyên tốt nhất; BARTpho vẫn là đối chứng Việt ngữ có tốc
độ sinh cao nhất. Không nên loại hai baseline chỉ vì kết quả thử nghiệm này.

## Tái lập

```bash
uv run --extra train train_sparql --model t5gemma2 --epochs 60 --eval-every-epochs 10 --seed 7 --save-model --benchmark-after-training --local-files-only --output-dir artifacts/sparql_official_v1
uv run --extra train evaluate_sparql_model --model t5gemma2 --model-dir artifacts/sparql_official_v1/t5gemma2/seed-7/model --suite benchmark --batch-size 1
uv run summarize_sparql_experiments --models bartpho vit5 t5gemma2 --output artifacts/sparql_official_v1/summary_with_t5gemma2.json
```
