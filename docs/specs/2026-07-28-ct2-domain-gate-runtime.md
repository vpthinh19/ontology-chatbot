# CT2 domain gate runtime

## Mục tiêu

Đưa PhoBERT gate vào pipeline production mà không phụ thuộc PyTorch. CTranslate2
chạy encoder PhoBERT INT8; NumPy chạy classification head đã fine-tune. Gate
đứng trước model sinh SPARQL và chặn câu hỏi ngoài phạm vi ontology.

Model gate được nghiệm thu với threshold lấy từ validation là
`0.7527403316567737`. Trên test độc lập, model giữ `95,58%` câu trong miền và
chặn `98,84%` câu ngoài miền. Tiêu chí production là false acceptance không
quá `1,2%` và in-scope recall ít nhất `95%`.

## Cấu trúc dataset

Hai dataset nằm chung dưới `resources/dataset` nhưng có nhiệm vụ riêng:

```text
resources/dataset/
├── main/
│   ├── train.jsonl
│   ├── val.jsonl
│   ├── test.jsonl
│   ├── manifest.json
│   └── README.md
└── gate/
    ├── train.jsonl
    ├── val.jsonl
    ├── test.jsonl
    ├── manifest.json
    └── README.md
```

`main` ánh xạ câu hỏi sang SPARQL; `gate` phân loại `in_scope` và
`out_of_scope`. Mọi settings, CLI, test và tài liệu phải dùng đường dẫn mới;
không để compatibility alias hoặc bản sao ở vị trí cũ.

## Artifact conversion

Script `convert_domain_gate` nhận training artifact
`artifacts/models/phobert-gate/` (checkpoint nằm trong `model/`, threshold nằm
trong `manifest.json`) và tạo
`artifacts/deployment/phobert-gate/`.

Artifact gồm:

```text
phobert-gate/
├── model.bin
├── config.json
├── vocabulary.json
├── classifier.npz
├── tokenizer.json
├── tokenizer_config.json
├── vocab.txt
├── bpe.codes
└── manifest.json
```

CTranslate2 converter chỉ xuất encoder và cố ý bỏ classification head. Script
phải trích bốn tensor sau từ checkpoint PyTorch:

- `classifier.dense.weight`
- `classifier.dense.bias`
- `classifier.out_proj.weight`
- `classifier.out_proj.bias`

Các tensor được lưu float32 trong `classifier.npz`. Manifest lưu format,
quantization, model nguồn, threshold, label mapping, pipeline
`dense -> tanh -> out_proj`, phiên bản CTranslate2 và SHA-256 của mọi file bắt
buộc. Output directory phải rỗng để tránh trộn artifact cũ và mới.

Conversion được phép cần PyTorch vì đây là công đoạn offline. Runtime chỉ cần
CTranslate2, Transformers tokenizer và NumPy.

## Runtime gate

`CTranslate2DomainGate` load một `ctranslate2.Encoder`, tokenizer,
`classifier.npz` và manifest đúng một lần khi server khởi động. Với mỗi câu:

1. Chuẩn hóa bằng `normalize_model_input`.
2. Tokenize tối đa 128 token, không word-segment.
3. Chạy encoder CT2 và lấy `last_hidden_state[:, 0, :]`.
4. Tính `tanh(cls @ dense.weight.T + dense.bias)`.
5. Tính logits bằng `hidden @ out_proj.weight.T + out_proj.bias`.
6. Softmax và lấy `P(in_scope)`.
7. Nhận khi xác suất lớn hơn hoặc bằng threshold trong manifest.

Giao diện runtime chỉ công bố:

```python
@dataclass(frozen=True)
class GateDecision:
    accepted: bool
    probability: float

class DomainGate(Protocol):
    def decide(self, text: str) -> GateDecision: ...
```

Classification head là một phần của cùng checkpoint PhoBERT, không phải model
thứ hai hoặc ensemble.

## Pipeline và API

```text
Câu hỏi
  -> PhoBERT CT2 gate
     -> rejected: trả thông báo phạm vi hỗ trợ
     -> accepted
        -> T5Gemma2 CT2 sinh SPARQL
        -> xác minh và thực thi SPARQL
        -> render câu trả lời
```

`OntologyChatbot` nhận cả `QueryGenerator` và `DomainGate`. Câu bị gate từ chối
không được gọi generator hoặc ontology. API trả HTTP 200 cùng thông báo tiếng
Việt ổn định vì đây là kết quả nghiệp vụ, không phải lỗi server.

CLI `serve_sparql` bắt buộc nhận `--model-dir` và `--gate-model-dir`; cả hai
artifact được load trên cùng device và compute type do người vận hành chọn.

## Xác minh

Conversion chưa hợp lệ nếu thiếu một trong các kiểm tra sau:

- artifact có đủ file và checksum khớp;
- tensor classification head có đúng shape;
- tokenizer không sinh `<unk>` hoặc cắt dữ liệu gate;
- CT2+NumPy và PyTorch được đánh giá trên cùng test split, cùng threshold;
- confusion matrix phải giống nhau; ROC-AUC và xác suất được báo kèm sai lệch;
- câu bị từ chối không gọi model sinh SPARQL;
- toàn bộ test dataset, conversion, runtime và API đều qua.

Kết quả probe trước triển khai trên 860 câu cho thấy CT2 INT8 + NumPy giữ nguyên
confusion matrix và toàn bộ metric quyết định của checkpoint PyTorch; có 2 quyết
định cá thể đổi chỗ do lượng tử hóa.

## Không thực hiện

- Không giữ PyTorch trong dependency production.
- Không dùng ONNX Runtime.
- Không tự cài đặt encoder hoặc tokenizer.
- Không nhúng classification head vào một model giả hoặc gọi nó là model lai.
- Không giữ đường dẫn dataset cũ hay compatibility shim.
- Không thay đổi ontology, dataset content hoặc model sinh SPARQL.
