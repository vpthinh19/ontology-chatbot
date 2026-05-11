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
│   └── serve.py                    FastAPI
└── viz/                            matplotlib visualisations

resources/
├── ontology/
│   ├── label_map.json
│   └── Ontology_AcademicProcedure_v8.owx
└── datasets/
    ├── train.jsonl
    └── test.jsonl

models/phobert_ner_ft/              model directory (after fine-tuning)

webui/                              chat UI
artifacts/flow/data_flow.png        architecture diagram
tests/                              pytest suite
```

## Scripts

| Lệnh | Mô tả |
|---|---|
| `uv sync --extra cuda` | Cài dependencies (cho thiết bị có NVIDIA CUDA 12.8+). |
| `uv sync --extra cpu` | Cài dependencies (cho thiết bị chỉ có CPU). |
| `uv run pytest` | Chạy bộ test (unit test). |
| `uv run train` | Fine-tune PhoBERT và lưu model ở `models/phobert_ner_ft/`. |
| `uv run evaluate` | Sinh `artifacts/evaluation/*.png` (confusion matrix, report). |
| `uv run serve` | FastAPI tại <http://127.0.0.1:8000><br>(Nếu đã train thì sẽ tự động nạp model từ `models/phobert_ner_ft/`,<br>nếu chưa train thì sẽ tự động tải fine-tuned model từ `vpthinh19/phobert-base-v2`) |

## Tham khảo

- PhoBERT: <https://github.com/VinAIResearch/PhoBERT>
- Owlready2: <https://owlready2.readthedocs.io/>
- RapidFuzz: <https://rapidfuzz.github.io/RapidFuzz/>
- underthesea: <https://github.com/undertheseanlp/underthesea>
