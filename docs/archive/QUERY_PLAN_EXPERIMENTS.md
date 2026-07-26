# Lịch sử thử nghiệm QueryPlan — không còn là đặc tả

Tài liệu này chỉ giữ provenance của hướng thử nghiệm trước ngày 2026-07-26.
Không dùng nội dung ở đây để thiết kế code, ontology, dataset hoặc benchmark
mới. Kiến trúc chính hiện nằm trong `docs/PROJECT_SPEC.md`.

## Hướng cũ

Model từng sinh grammar `query route ...`, backend parse/validate domain-range
và trả `EntityResult`/`LiteralResult`. Dataset production cũ có 960 câu (652
train, 308 validation), 77 capability và 252 semantic family. Benchmark
QueryPlan v2 có 184 câu và được niêm phong theo ontology v10.

Hướng này bị loại vì model dính với một grammar tự thiết kế trong khi backend
vẫn phải triển khai một query engine riêng. SPARQL đã cung cấp join, filter,
aggregate và traversal theo chuẩn, nên QueryPlan tạo thêm tầng dư thừa.

## Kết quả lịch sử

Validation QueryPlan batch 1 ngày 2026-07-25:

| Model | Semantic exact | Parse | Noisy |
|---|---:|---:|---:|
| ViT5-base | 75,00% | 100,00% | 41,56% |
| BARTpho-syllable | 72,08% | 99,35% | 44,16% |
| T5Gemma | 70,45% | 100,00% | 45,45% |

Các số liệu này chứng minh model có thể học output có cấu trúc và cho thấy câu
noisy khó, nhưng không phải kết quả của kiến trúc SPARQL và không được so trực
tiếp với benchmark mới.

Learning audit nhỏ từng cho thấy BARTpho cần nhiều bước mới giảm loss mạnh và
dropout 0 giúp overfit tập audit. Đây chỉ là gợi ý để kiểm tra lại trên
validation SPARQL, không phải hyperparameter đã khóa.

## Artifact cũ

Nguồn QueryPlan đã được dùng để biên soạn dataset/benchmark SPARQL v1 rồi được
loại khỏi cây nguồn hiện hành. Git vẫn giữ đầy đủ các mốc cần audit:

- `61a9edd`: 960 câu nguồn, mapping và release SPARQL đầu tiên;
- `fc13671`: bổ sung các family aggregate/filter;
- `d08a7fd`: benchmark SPARQL độc lập đã đóng băng.

Module `query_engine.py` hiện hành là executor SPARQL tối giản, không phải query
engine traversal của hướng cũ.
