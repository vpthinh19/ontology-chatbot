# NTU Academic Chatbot — PhoBERT NER + Ontology RAG

Vietnamese chatbot for NTU academic procedures: PhoBERT fine-tuned for token-level NER, RapidFuzz + owlready2 for ontology-grounded retrieval, schema-agnostic Vietnamese rendering.

## Cấu trúc thư mục

```
src/ontchatbot/
├── config.py                       paths + hyper-params + fuzzy threshold
├── logging_setup.py                rotating logger
├── pipeline.py                     Pipeline + PipelineContext (orchestrator)
├── preprocessor.py                 Preprocessor  (text utility)
├── ner_model.py                    NerModel      (PhoBERT NER)
├── ontology.py                     Ontology      (OWL repo + fuzzy + JSON)
├── renderer.py                     Renderer      (JSON dict → text)
├── scripts/
│   ├── train.py
│   ├── evaluate.py
│   ├── serve.py                    FastAPI
│   └── bench_fuzzy
└── viz/                            matplotlib visualisations

resources/
├── ontology/
│   ├── label_map.json
│   └── Ontology_AcademicProcedure_v8.owx
└── datasets/
    ├── train.jsonl
    └── test.jsonl

webui/                              chat UI
artifacts/                          artifacts output
tests/                              pytest suite
```

## Scripts

| Lệnh | Mô tả |
|---|---|
| `uv sync --extra train` | Cài dependencies cho huấn luyện model (Cần NVIDIA CUDA 12.8+). |
| `uv sync --extra inference` | Cài dependencies cho sử dụng model (Chỉ cần CPU). |
| `uv run pytest` | Chạy bộ test (unit test). |
| `uv run train` | Fine-tune và lưu model ở `artifacts/models/phobert_ner_ft/` |
| `uv run evaluate` | Sinh `artifacts/evaluation/` (confusion matrix, report) |
| `uv run serve` | FastAPI tại <http://0.0.0.0:8000><br>(Dùng model từ `artifacts/models/phobert_ner_ft/` (nếu có)<br>hoặc tải từ Hugging Face repo `vpthinh19/phobert-base-v2`) |

`--help` để xem thêm thông tin và các đối số tùy chọn

## Tham khảo

- PhoBERT: <https://github.com/VinAIResearch/PhoBERT>
- Owlready2: <https://owlready2.readthedocs.io/>
- RapidFuzz: <https://rapidfuzz.github.io/RapidFuzz/>
- underthesea: <https://github.com/undertheseanlp/underthesea>
