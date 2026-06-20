# NTU Academic Chatbot — BARTpho (text→cây JSON) + Ontology traversal

Chatbot tiếng Việt tra cứu thủ tục học vụ Trường ĐH Nha Trang. Model seq2seq
**BARTpho-syllable** biến câu hỏi thành một **cây truy vấn JSON** (`{act, items}`); tầng
**ontology** (owlready2) **duyệt** cây đó theo quan hệ để lấy đúng thông tin; `render` ghép
thành câu trả lời. **Không có tầng luật/intent ở giữa** — model lo hiểu ngôn ngữ (mềm dẻo),
ontology lo tri thức có cấu trúc (chính xác).

Đây là đề tài **nghiên cứu**: chứng minh ưu thế của ontology (truy vấn có cấu trúc) so với
CSDL phẳng/similarity (Phase 8). Khái niệm cho người đọc: `docs/CONCEPT.md`.

## Luồng

```
text → preprocess (làm sạch) → BARTpho CT2 (text→cây) → tree.parse → ontology.traverse → render → reply
```

## Cấu trúc thư mục

Hệ thống và giàn-giáo-dev tách bạch. `src/` chỉ chứa hệ thống chạy thật + script tái lập;
mọi tài nguyên dev nằm trong `dev/` (gitignored).

```
src/ontchatbot/
├── config.py            paths, model ids, hyper-params
├── tree.py              hợp đồng cây JSON (parse khoan dung / parse_strict cho oracle)
├── ontology.py          nạp OWL + khớp theo type + thuật toán duyệt (DESIGN §5)
├── preprocess.py        làm sạch text (NFC, nắn dấu, bung teencode) — "ngu", KHÔNG hiểu câu
├── model.py             BARTpho CT2: text → cây JSON (ctranslate2.Translator, int8 CPU)
├── render.py            act routing (chào/ood/vague) + format Result → câu trả lời
├── pipeline.py          điều phối các pha (một chiều)
├── logging_setup.py     rotating logger
└── scripts/
    ├── serve.py            FastAPI: /chat, /healthz
    ├── train.py            train BARTpho (GPU) → artifacts/models/bartpho_tree
    ├── evaluate.py         eval 2 mức (cấu-trúc-cây ⊕ đầu-cuối P/R/F1)
    ├── convert_ct2.py      HF → CTranslate2 int8 (deploy) + parity check
    ├── eval_traversal.py   eval đúng-cạnh trên cây vàng
    └── validate_dataset.py oracle nghiêm (strict-parse + so node/giá trị)

resources/
├── ontology/Ontology_AcademicProcedure.owx   ontology hệ thống (Protégé; .owl RDF/XML là fallback)
├── datasets/{train,test}.jsonl               6220 mẫu (câu → cây JSON; train 4714 / test 1506)
└── e2e/cases.jsonl                            100 cây vàng (eval đúng-cạnh)

webui/   chat UI      artifacts/   model + báo cáo eval      tests/   pytest suite

dev/   (GITIGNORED — không thuộc hệ thống, giữ làm provenance)
├── dataset_construction/   khâu dựng dataset (catalog/Codex/oracle/merge) + phase4/
├── ontology_build/         build_ontology.py + nguồn v8 (cách dựng nhãn/alias)
└── phase8_prototypes/      BGE-M3 reranker + bm25s/model2vec (benchmark, chưa tích hợp)
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
| `uv run pytest` | Bộ test (65 pass) |
| `uv run --extra inference python -m ontchatbot.scripts.eval_traversal` | Eval đúng-cạnh trên cây vàng (100%) |
| `uv run --extra inference python -m ontchatbot.scripts.validate_dataset` | Oracle nghiêm trên cases.jsonl (100/100) |
| `uv run --extra train python -m ontchatbot.scripts.train` | Train BARTpho (GPU; bf16 + adamw_8bit, vừa 6GB) |
| `uv run --extra train python -m ontchatbot.scripts.evaluate` | Eval 2 mức (cấu-trúc-cây ⊕ đầu-cuối) |
| `uv run --extra train python -m ontchatbot.scripts.convert_ct2` | HF → CTranslate2 int8 + parity check |
| `uv run --extra inference python -m ontchatbot.scripts.serve` | FastAPI tại <http://127.0.0.1:8000> |

Script dev (dựng dataset, build ontology) chạy từ `dev/`: vd
`PYTHONPATH=dev uv run --extra inference python -m dataset_construction.merge_dataset`.

## Trạng thái

Lõi (ontology + duyệt + render), dataset (6220 mẫu), model BARTpho (train + eval 2 mức) và
deploy CTranslate2 int8 **đã xong & verify**: eval đầu-cuối F1 micro ~0.94 (truy vấn ~0.96),
gate pytest 65 / eval_traversal 100% / oracle 100/100. `/chat` chạy thật trên CT2.
Còn lại: benchmark ontology vs CSDL phẳng (Phase 8), deploy lightning.ai (Phase 7), và một
thao tác thủ công — mở ontology trong Protégé Save-As **OWL/XML** để có `.owx` thuần (runtime
đã tự ưu tiên `.owx` nếu có, hiện chạy `.owl` RDF/XML).

## Tham khảo

- BARTpho: <https://github.com/VinAIResearch/BARTpho>
- owlready2: <https://owlready2.readthedocs.io/>
- CTranslate2: <https://github.com/OpenNMT/CTranslate2>
