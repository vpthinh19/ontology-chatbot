# NTU Academic Chatbot — PhoBERT NER + Ontology-Grounded RAG

Chatbot tiếng Việt cho thủ tục học vụ Đại học Nha Trang. Pipeline tách biệt
hai năng lực: **PhoBERT** fine-tune cho **Named Entity Recognition** (token-
level BIO) trên 5 lớp ontology, sau đó dùng **RapidFuzz** + **owlready2**
để gắn span vào individual ontology cụ thể và sinh trả lời bằng template
schema-agnostic. Toàn bộ giao thức giữa các module là dict JSON nên việc
mở rộng ontology trên Protégé không cần đụng đến code Python.

## Kiến trúc

5 module OOP (singleton qua `Cls.get()`) + scripts CLI hướng chức năng.

| Module | Vai trò | API chính |
|---|---|---|
| `Preprocessor` (`preprocessor.py`) | Vietnamese text → tokens. Một nguồn duy nhất cho mọi text utility. | `clean`, `normalize`, `segment`, `normalize_for_match`, `strip_diacritics`, `is_url` |
| `NerModel` (`ner_model.py`) | PhoBERT NER inference + training-data adapter | `extract_entities`, `decode_bio`, `bio_labels`, `make_encoder`, `make_tokenize_fn`, `load_split` |
| `Ontology` (`ontology.py`) | OWL repository — load, fuzzy match, JSON describe | `tags`, `class_local`, `resolve`, `describe`, `list_class` |
| `Renderer` (`renderer.py`) | JSON dict → Vietnamese chat string (không phụ thuộc owlready) | `render`, `render_blocks`, `compose` |
| `Pipeline` (`pipeline.py`) | Orchestrator 5 stages — preprocess → ner → match → query → present | `answer` (sync), `aanswer` (async wrapper) |

Sơ đồ luồng dữ liệu chi tiết: [`docs/data_flow.puml`](docs/data_flow.puml)
(render online tại <https://www.plantuml.com/plantuml>).

### JSON contract

`Ontology.describe()` trả về dict tự mô tả: 4 fixed identity keys
(`type`, `iri`, `class`, `label`); mỗi key khác là Vietnamese `rdfs:label`
của một property. Renderer iterate dict theo insertion order.

```json
{
  "type": "individual",
  "iri": "QuyTrinh_NopHocPhi",
  "class": "AcademicProcedure",
  "label": "Quy trình đóng học phí",
  "Mô tả quy trình": "\nSinh viên thanh toán...",
  "Được xử lý bởi": [
    { "type": "individual", "iri": "PhongKHTC", "class": "AdministrativeOffice",
      "label": "Phòng Tài chính",
      "Trưởng phòng/Chánh văn phòng": "...", "Website": "https://..." }
  ],
  "Áp dụng mức học phí": [ ... ]
}
```

Quy ước:
- Paragraph property values mang leading `\n` (marker → Renderer render
  free-flow text, không bullet).
- Dedup tự động: ancestor đã link `(predicate, target_iri)` → con không
  lặp lại.
- Recursion mặc định `depth=2`: top-level entity full + object-property
  targets carry their own data.

### Hierarchy markers (text output)

```
[Title]                  ← bare label, không emoji
[paragraph property]

• [entity-level section]: value     ← top-level marker
  ◦ [nested target data]: value     ← under single object target
• [section]:
  - [list item / target]            ← multi-target / multi-value
    ◦ [target's own data]: value
```

3 markers cho 3 ngữ nghĩa: `•` entity section, `-` list item, `◦` nested.

## Cấu trúc thư mục

```
src/ontchatbot/
├── __init__.py            (lazy public exports)
├── config.py              paths + hyper-params + fuzzy threshold
├── logging_setup.py       rotating logger
├── pipeline.py            Pipeline + PipelineContext
├── preprocessor.py        Preprocessor (text utility)
├── ner_model.py           NerModel (PhoBERT NER + training adapter)
├── ontology.py            Ontology (OWL repository + fuzzy + JSON)
├── renderer.py            Renderer + GREETING/RENDER constants
├── data/
│   └── sources.py         hand-curated NER samples
├── scripts/               functional CLI scripts
│   ├── build_dataset.py
│   ├── train.py
│   ├── evaluate.py
│   └── serve.py           FastAPI
└── viz/                   matplotlib visualizations

resources/                  bundled with the wheel
├── ontology/
│   ├── label_map.json
│   └── Ontology_AcademicProcedure_v8.owx
└── datasets/
    ├── train.jsonl
    └── test.jsonl

webui/index.html            single-page chat UI
docs/data_flow.puml         architecture diagram
tests/                      pytest (~95 tests)
```

## Yêu cầu

- Python 3.13+
- (Tuỳ chọn) GPU CUDA 13.0+ cho training & inference nhanh

## Quick start

```bash
uv sync                        # cài dependencies
uv run pytest                  # chạy 95 tests (~13s)
uv run build_dataset           # compile JSONL từ data/sources.py
uv run train                   # fine-tune PhoBERT (~10 phút trên GPU)
uv run evaluate                # → artifacts/evaluation/*.png
uv run serve                   # → http://127.0.0.1:8000
```

## Mở rộng ontology — workflow zero-code

Chỉ cần edit ontology trong Protégé:

1. Thêm class / individual / object property / data property mới.
2. Đặt Vietnamese `rdfs:label` cho mỗi entity (sẽ thành section header).
3. Thêm `hasAlias` literals cho fuzzy match (các cách diễn đạt tự nhiên).
4. Save → backend tự nhận khi restart, **không sửa code Python**.

Để model NER nhận diện class mới, bổ sung samples trong `data/sources.py`
+ thêm class vào `resources/ontology/label_map.json` + retrain.

## Hành vi đáng chú ý

- **Threshold-based multi-match**: span như `"k65"` resolve thành cả
  `Phi_K65_550k` và `Phi_K65_620k` — không bị top-1 collapse.
- **Class-listing fallback**: span match class label (vd `"quy trình học vụ"`)
  → render flat list mọi individual của class.
- **Minimal greeting**: chỉ greet khi user nhắn pure greeting; query có
  entity → trả lời thẳng, không prefix `"Xin chào"`.
- **Async API**: `Pipeline.aanswer()` wrap qua `asyncio.to_thread` để
  FastAPI không block event loop trong lúc PhoBERT inference.
- **Per-module logger**: `logging.getLogger("ontchatbot.ontology")` tune
  level độc lập với `ontchatbot.preprocessor`.

## Testing

```bash
uv run pytest                                  # full suite
uv run pytest tests/test_renderer.py           # chỉ renderer (no OWL load)
uv run pytest tests/test_ontology.py -v        # ontology + fuzzy + dedup
```

Renderer tests dùng synthetic dict — không load OWL → chạy ms.

## Tham khảo

- PhoBERT: <https://github.com/VinAIResearch/PhoBERT>
- Owlready2: <https://owlready2.readthedocs.io/>
- RapidFuzz: <https://rapidfuzz.github.io/RapidFuzz/>
- underthesea: <https://github.com/undertheseanlp/underthesea>
