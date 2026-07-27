# Stage F — đóng băng release SPARQL v2

Stage F đã hoàn tất. Dataset v2 được chuyển từ candidate sang `frozen` và trở
thành dataset mặc định của project. Không train hoặc dùng điểm test model trong
giai đoạn này.

## Release được khóa

- 936 câu, 234 semantic family và 102 target SPARQL duy nhất.
- Split train/validation/test: 656/140/140 câu, tương ứng 164/35/35 family.
- Mỗi family có đủ formal, neutral, colloquial và noisy.
- Mỗi split có đủ năm query shape.
- Không có family, câu chuẩn hóa hoặc near-duplicate rò qua biên split.
- 100% target dùng term tồn tại trong ontology v12, thực thi được và giữ nguyên
  kết quả đã review ở Stage D.
- Không có ô kết quả rỗng hoặc URI/BNode bị projection ra ngoài.

## Tokenizer thật

| Model | Source max / 128 | Target max / 160 | `<unk>` | Round-trip target |
|---|---:|---:|---:|---:|
| BARTpho-syllable | 32 | 93 | 0 | 102/102 |
| ViT5-base | 30 | 124 | 0 | 102/102 |

Hai tokenizer đều đạt budget và tái tạo chính xác toàn bộ target canonical.
ViT5 dùng artifact tokenizer đã chuẩn bị và được kiểm tra lại checksum.

## Artifact tái lập

- `stage_e_manifest.json`: candidate bất biến trước release gate.
- `stage_f_audit.json`: toàn bộ kiểm tra, thống kê tokenizer và checksum.
- `resources/datasets/sparql_v2/manifest.json`: manifest frozen đang dùng.

Bước tiếp theo là Stage G: trước hết chạy learning audit trên train/validation,
sau đó mới khóa cấu hình, train nhiều seed và mở test v2 đúng một lần.
