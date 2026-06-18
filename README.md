# NTU Academic Chatbot — BARTpho (text→cây JSON) + Ontology traversal

Chatbot tiếng Việt tra cứu thủ tục học vụ Trường ĐH Nha Trang. Model seq2seq
**BARTpho-syllable** biến câu hỏi thành một **cây truy vấn JSON** (`{act, entities}`); tầng
**ontology** (owlready2) **duyệt** cây đó theo quan hệ để lấy đúng thông tin; `render` ghép
thành câu trả lời. **Không có tầng luật/intent ở giữa** — model lo hiểu ngôn ngữ (mềm dẻo),
ontology lo tri thức có cấu trúc (chính xác).

Đây là đề tài **nghiên cứu**: chứng minh ưu thế của ontology (truy vấn có cấu trúc) so với
CSDL phẳng/similarity (Phase 8). Thiết kế chi tiết: `docs/redesign/DESIGN.md`; trạng thái
sống: `docs/redesign/PROGRESS.md`.

## Luồng

```
text → preprocess (làm sạch) → BARTpho (text→cây) → tree.parse → ontology.traverse → render → reply
```

## Cấu trúc thư mục

```
src/ontchatbot/
├── config.py            paths, model ids, hyper-params
├── tree.py              hợp đồng cây JSON (parse khoan dung / parse_strict cho oracle)
├── ontology.py          nạp OWL + khớp theo type + thuật toán duyệt (DESIGN §5)
├── preprocess.py        làm sạch text (NFC, bung teencode) — "ngu", KHÔNG hiểu câu
├── model.py             BARTpho seq2seq: text → cây JSON (khung; chưa train)
├── render.py            act routing (chào/ood/vague) + format Result → câu trả lời
├── pipeline.py          điều phối các pha (một chiều)
├── logging_setup.py     rotating logger
└── scripts/
    ├── build_ontology.py   dựng lại .owl từ v8 (nguồn-đúng) + lint
    ├── serve.py            FastAPI: /chat, /healthz
    ├── eval_traversal.py   eval đúng-cạnh trên cây vàng
    ├── validate_dataset.py oracle nghiêm (strict-parse + so node/giá trị)
    └── catalog.py, run_group.py, merge_dataset.py, …   (sinh dataset Phase 4)

resources/
├── ontology/Ontology_AcademicProcedure.owl   artifact (nguồn = build_ontology.py; source v8 = *_v8.owx, OWL/XML)
├── datasets/{train,test}.jsonl               5898 mẫu (câu → cây JSON)
└── e2e/cases.jsonl                            100 cây vàng (eval đúng-cạnh)

webui/        chat UI       artifacts/    output       tests/    pytest suite
```

## Dependencies (uv, tách theo extra)

| Nhóm | Gồm | Dùng cho |
|---|---|---|
| core | owlready2, ctranslate2, transformers, tokenizers, sentencepiece, numpy | runtime (duyệt + inference CT2) |
| `--extra inference` | + fastapi | serve (CPU) |
| `--extra train` | + torch (cu130), datasets, accelerate, bitsandbytes, matplotlib, model2vec, bm25s | train (GPU) + benchmark Phase 8 |

Inference deploy dùng **CTranslate2 int8** (không cần torch). `uv conflicts` chặn cài đồng thời `train` ⊕ `inference`.

## Lệnh

| Lệnh | Mô tả |
|---|---|
| `uv sync` | Cài core + dev (pytest) |
| `uv run python -m ontchatbot.scripts.build_ontology` | Dựng ontology + lint (gate: ERROR → exit 1) |
| `uv run pytest` | Bộ test (65 pass) |
| `uv run python -m ontchatbot.scripts.eval_traversal` | Eval đúng-cạnh trên cây vàng (100%) |
| `uv run python -m ontchatbot.scripts.validate_dataset` | Oracle nghiêm trên cases.jsonl (100/100) |
| `uv run --extra inference python -m ontchatbot.scripts.serve` | FastAPI tại <http://127.0.0.1:8000> |
| `uv run --extra train python -m ontchatbot.scripts.train` | Train BARTpho (GPU; bf16 + adamw_8bit, vừa 6GB) → `artifacts/models/bartpho_tree` |

`--help` để xem đối số tùy chọn.

## Trạng thái

Lõi (ontology + duyệt + render + dataset) **đã xong & verify**. Model BARTpho **đang train**
(Phase 5: `train.py` xong, vừa 6GB VRAM; chưa lưu model hoàn chỉnh) → `/chat` còn raise
`ModelNotReady`. Lộ trình còn lại: hoàn tất train + `evaluate.py` đúng-cạnh (Phase 5) → convert
CTranslate2 + nối serve (Phase 6) → benchmark ontology vs CSDL phẳng (Phase 8) → deploy
lightning.ai (Phase 7). Chi tiết từng phase: `docs/redesign/PROGRESS.md`.

## Tham khảo

- BARTpho: <https://github.com/VinAIResearch/BARTpho>
- owlready2: <https://owlready2.readthedocs.io/>
- CTranslate2: <https://github.com/OpenNMT/CTranslate2>
