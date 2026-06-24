# NTU Academic Chatbot — BARTpho (text→cây JSON) + duyệt ontology

Chatbot tiếng Việt tra cứu thủ tục học vụ Trường Đại học Nha Trang. Mô hình seq2seq
**BARTpho-syllable** biến câu hỏi thành một **cây truy vấn JSON** (`{act, entities}`); tầng
**ontology** (owlready2) **duyệt** cây đó theo quan hệ để lấy đúng thông tin; `render` ghép kết
quả thành câu trả lời. **Không có tầng luật/intent ở giữa**: mô hình lo hiểu ngôn ngữ (mềm dẻo),
ontology lo tri thức có cấu trúc (chính xác).

Đây là đề tài **nghiên cứu**: chứng minh ưu thế của truy vấn có cấu trúc (ontology) so với một
cơ sở dữ liệu phẳng truy hồi văn bản. Trình bày khái niệm cho người đọc: [`docs/CONCEPT.md`](docs/CONCEPT.md).

## Luồng

```
text → preprocess (làm sạch) → BARTpho CT2 (text→cây) → tree.parse → ontology.traverse → render → reply
```

Một chiều, không vòng lặp, không planner: cây do mô hình sinh đã cho sẵn đường đi; ontology chỉ đi
theo đúng các quan hệ được nêu, lấy điểm khớp cao nhất, không khớp thì trả "không có thông tin «X»".

## Cấu trúc thư mục

Hệ thống chạy thật và công cụ phát triển tách bạch: `src/` chỉ chứa hệ thống + script tái lập;
mọi công cụ thời phát triển (dựng dataset, build ontology) nằm trong `dev/` (gitignored).

```
src/ontchatbot/
├── config.py            đường dẫn, mã model, siêu tham số
├── capabilities.py      năm nhóm năng lực truy vấn
├── tree.py              hợp đồng cho định dạng cây JSON
├── ontology.py          nạp OWL + nội suy duyệt ontology
├── preprocess.py        làm sạch text
├── model.py             BARTpho CT2: text → cây JSON (ctranslate2 + sentencepiece, int8 trên CPU)
├── render.py            xử lý + ghép kết quả → câu trả lời
├── pipeline.py          điều phối các module (một chiều)
├── baseline/            đối chứng: ontology vs csdl phẳng (Semantic + full-text search)
└── scripts/
    ├── serve.py            FastAPI: POST /chat, GET /healthz
    ├── train.py            train BARTpho (GPU) → artifacts/models/bartpho_tree
    ├── evaluate.py         đánh giá 2 mức (cấu trúc cây + đầu-cuối P/R/F1 theo 5 nhóm năng lực)
    ├── convert_ct2.py      HF → CTranslate2 int8 (cho deploy)
    ├── build_flat_db.py    đập ontology → cơ sở dữ liệu phẳng (resources/baseline/flat_db.jsonl)
    ├── visualize.py        sinh hình cho CONCEPT.md từ báo cáo đánh giá/đối chứng
    └── upload_hf.py        đẩy model CT2 lên Hugging Face cho deploy

resources/
├── ontology/                ontology hệ thống (OWL/XML .owx; .owl RDF/XML là fallback)
├── datasets/                train.jsonl / test.jsonl (câu → cây JSON)
└── baseline/flat_db.jsonl   cơ sở dữ liệu phẳng sinh từ ontology (cho đối chứng)

webui/        giao diện chat tĩnh
artifacts/    model + báo cáo đánh giá
tests/        unit test (pytest)
```

## Dependencies (uv, tách theo extra)

| Nhóm | Thêm gì | Dùng cho |
|---|---|---|
| **core** (mặc định) | ctranslate2, owlready2, sentencepiece, numpy | lõi: sinh cây (CT2) + duyệt ontology |
| `--extra inference` | + fastapi[standard], huggingface_hub | chạy server (CPU) |
| `--extra train` | + torch, transformers, datasets, accelerate, bitsandbytes, flagembedding, scikit-learn, matplotlib | train / evaluate / convert / benchmark |

Mấu chốt: **inference KHÔNG cần torch/transformers** — `model.py` chạy CTranslate2 + sentencepiece
trực tiếp, nên ảnh deploy gọn (chỉ core + fastapi). `uv` khai `conflicts` chặn cài đồng thời
`train` + `inference`.

## Lệnh

| Lệnh | Mô tả |
|---|---|
| `uv run pytest` | Unit test |
| `uv run --extra train python -m ontchatbot.scripts.train` | Train BARTpho (cần GPU) |
| `uv run --extra train python -m ontchatbot.scripts.convert_ct2` | HF → CTranslate2 int8 |
| `uv run --extra train python -m ontchatbot.scripts.evaluate` | Đánh giá 2 mức theo 5 nhóm năng lực |
| `uv run --extra inference python -m ontchatbot.scripts.build_flat_db` | Sinh CSDL phẳng từ ontology |
| `uv run --extra train python -m ontchatbot.baseline.benchmark` | Đối chứng ontology vs CSDL phẳng |
| `uv run --extra train python -m ontchatbot.scripts.visualize` | Visualize số liệu |
| `uv run --extra inference python -m ontchatbot.scripts.serve` | FastAPI tại <http://127.0.0.1:8000> |

## Inference trực tiếp thông qua Docker

```
docker run -p 8000:8000 vpt19/ontchatbot:latest
# Truy cập http://127.0.0.1:8000
# POST /chat {"message": "điều kiện bảo lưu"} → {"reply": ..., "entities": [...]}
# GET  /healthz → {"status": "ok"}
```

## Tham khảo

- BARTpho: <https://github.com/VinAIResearch/BARTpho>
- owlready2: <https://owlready2.readthedocs.io/>
- CTranslate2: <https://github.com/OpenNMT/CTranslate2>
