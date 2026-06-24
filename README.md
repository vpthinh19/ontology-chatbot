# NTU Academic Chatbot - BARTpho (text→cây JSON) + Ontology traversal

Chatbot tiếng Việt tra cứu thủ tục học vụ Trường ĐH Nha Trang. Model seq2seq
**BARTpho-syllable** biến câu hỏi thành một **cây truy vấn JSON** (`{act, items}`); tầng
**ontology** (owlready2) **duyệt** cây đó theo quan hệ để lấy đúng thông tin; `render` ghép
thành câu trả lời. **Không có tầng luật/intent ở giữa** - model lo hiểu ngôn ngữ (mềm dẻo),
ontology lo tri thức có cấu trúc (chính xác).

Đây là đề tài **nghiên cứu**: chứng minh ưu thế của ontology (truy vấn có cấu trúc) so với một
cơ sở dữ liệu phẳng truy hồi văn bản. Trình bày khái niệm cho người đọc: `docs/CONCEPT.md`.

## Luồng

```
text → preprocess (làm sạch) → BARTpho CT2 (text→cây) → tree.parse → ontology.traverse → render → reply
```

## Cấu trúc thư mục

Hệ thống và công cụ dev tách bạch. `src/` chỉ chứa hệ thống chạy thật và các script tái lập;
mọi công cụ thời phát triển (dựng dataset, build ontology) nằm trong `dev/` (gitignored).

```
src/ontchatbot/
├── config.py            đường dẫn, mã model, siêu tham số
├── capabilities.py      năm nhóm năng lực truy vấn (trục đánh giá dùng chung)
├── tree.py              hợp đồng cây JSON (parse khoan dung / parse_strict)
├── ontology.py          nạp OWL + khớp theo type + thuật toán duyệt
├── preprocess.py        làm sạch text (NFC, nắn dấu, bung teencode) - không hiểu câu
├── model.py             BARTpho CT2: text → cây JSON (ctranslate2, int8 CPU)
├── render.py            định tuyến act (chào/ood/vague) + ghép kết quả → câu trả lời
├── pipeline.py          điều phối các pha (một chiều)
├── baseline/            đối chứng: ontology vs cơ sở dữ liệu phẳng (BGE-M3 + rerank)
└── scripts/
    ├── serve.py            FastAPI: /chat, /healthz
    ├── train.py            train BARTpho (GPU) → artifacts/models/bartpho_tree
    ├── evaluate.py         đánh giá 2 mức (cấu trúc cây ⊕ đầu-cuối P/R/F1 theo 5 nhóm năng lực)
    ├── convert_ct2.py      HF → CTranslate2 int8 (deploy)
    ├── build_flat_db.py    đập ontology → cơ sở dữ liệu phẳng (resources/baseline/flat_db.jsonl)
    ├── visualize.py        sinh hình cho CONCEPT.md từ báo cáo đánh giá/đối chứng
    └── upload_hf.py        đẩy model CT2 lên Hugging Face cho deploy

resources/
├── ontology/                ontology hệ thống (OWL/XML .owx; .owl RDF/XML là fallback)
├── datasets/                train.jsonl / test.jsonl (câu → cây JSON)
└── baseline/flat_db.jsonl   cơ sở dữ liệu phẳng sinh từ ontology (cho đối chứng)

webui/   giao diện chat       artifacts/   model + báo cáo       tests/   bộ test pytest

dev/   (GITIGNORED - công cụ thời phát triển, giữ làm provenance)
├── dataset_construction/   khâu dựng dataset (catalog/Codex/oracle/merge)
└── ontology_build/         build_ontology.py + nguồn (cách dựng nhãn/alias)
```

## Dependencies (uv, tách theo extra)

| Nhóm | Gồm | Dùng cho |
|---|---|---|
| core | owlready2, ctranslate2, transformers, tokenizers, sentencepiece, numpy | runtime (duyệt + inference CT2) |
| `--extra inference` | + fastapi, huggingface_hub | serve (CPU) |
| `--extra train` | + torch, datasets, accelerate, bitsandbytes, flagembedding, scikit-learn, matplotlib | train (GPU) + đối chứng |

Inference deploy dùng **CTranslate2 int8** (không cần torch). `uv conflicts` chặn cài đồng thời `train` ⊕ `inference`.

## Lệnh

| Lệnh | Mô tả |
|---|---|
| `uv run pytest` | Bộ test |
| `uv run --extra train python -m ontchatbot.scripts.train` | Train BARTpho (GPU) |
| `uv run --extra train python -m ontchatbot.scripts.evaluate` | Đánh giá 2 mức theo 5 nhóm năng lực |
| `uv run --extra train python -m ontchatbot.scripts.convert_ct2` | HF → CTranslate2 int8 (deploy) |
| `uv run --extra inference python -m ontchatbot.scripts.build_flat_db` | Sinh cơ sở dữ liệu phẳng từ ontology |
| `uv run --extra train python -m ontchatbot.baseline.benchmark` | Đối chứng ontology vs cơ sở dữ liệu phẳng |
| `uv run --extra inference python -m ontchatbot.scripts.serve` | FastAPI tại <http://127.0.0.1:8000> |

Công cụ dựng dataset / build ontology chạy từ `dev/`, ví dụ:
`PYTHONPATH=dev uv run --extra inference python -m dataset_construction.merge_dataset`.

## Tham khảo

- BARTpho: <https://github.com/VinAIResearch/BARTpho>
- owlready2: <https://owlready2.readthedocs.io/>
- CTranslate2: <https://github.com/OpenNMT/CTranslate2>
