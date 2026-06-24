"""Hệ phẳng = truy hồi THUẦN: BGE-M3 hybrid (dense+sparse) → BGE-reranker-v2-m3.

Trả về danh sách IRI XẾP HẠNG cho mỗi câu hỏi. KHÔNG trích thuộc tính, KHÔNG chọn field,
KHÔNG giao tập - đúng bản chất "search engine" (ghi nhận trung thực ở báo cáo). Đây là baseline
MẠNH cho khâu truy hồi nhưng vẫn ở mức tài-liệu, để phơi ưu thế suy-luận-cấu-trúc của ontology.

Cấu hình: alpha=0.5, min-max normalize dense & sparse rồi cộng; rerank top-k bằng cross-encoder
(sigmoid). **Staging VRAM**:
nạp BGE-M3 → encode hết corpus + queries → GIẢI PHÓNG → nạp reranker (vừa GPU 6GB).
**Determinism:** tie-break theo IRI (chuỗi) để thứ hạng không dao động giữa các lần chạy.
"""

from __future__ import annotations

import gc

import numpy as np

ALPHA = 0.5
TOP_K_RETRIEVE = 10
TOP_K_RERANK = 10
M3_NAME = "BAAI/bge-m3"
RERANKER_NAME = "BAAI/bge-reranker-v2-m3"


def _min_max(scores: np.ndarray) -> np.ndarray:
    lo, hi = float(np.min(scores)), float(np.max(scores))
    return np.zeros_like(scores) if hi == lo else (scores - lo) / (hi - lo)


def _sparse_score(qw: dict, dw: dict) -> float:
    return float(sum(qw[k] * dw[k] for k in (qw.keys() & dw.keys())))


def _free_cuda() -> None:
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.reset_peak_memory_stats()
    except Exception:
        pass


def rank_all(corpus: dict[str, str], queries: list[str], *, alpha: float = ALPHA,
             top_k_retrieve: int = TOP_K_RETRIEVE, top_k_rerank: int = TOP_K_RERANK,
             use_fp16: bool = True) -> list[list[str]]:
    """Mỗi câu trong ``queries`` → list IRI xếp hạng (sau rerank). ``corpus`` IRI→text."""
    from FlagEmbedding import BGEM3FlagModel

    iris = list(corpus)                               # thứ tự ổn định (insertion = thứ tự ontology)
    docs = [corpus[i] for i in iris]

    # ── Stage 1: BGE-M3 encode (corpus + queries) ──
    m3 = BGEM3FlagModel(M3_NAME, use_fp16=use_fp16)
    d_out = m3.encode(docs, return_dense=True, return_sparse=True)
    q_out = m3.encode(queries, return_dense=True, return_sparse=True)
    doc_dense = np.asarray(d_out["dense_vecs"], dtype=np.float32)        # (D, dim)
    q_dense = np.asarray(q_out["dense_vecs"], dtype=np.float32)          # (Q, dim)
    doc_sparse = d_out["lexical_weights"]
    q_sparse = q_out["lexical_weights"]
    del m3, d_out, q_out
    gc.collect()
    _free_cuda()

    # ── Stage 2: hybrid score → top-k ứng viên mỗi câu ──
    from sklearn.metrics.pairwise import cosine_similarity
    dense_all = cosine_similarity(q_dense, doc_dense)                    # (Q, D)
    candidates: list[list[int]] = []
    for qi in range(len(queries)):
        sparse = np.array([_sparse_score(q_sparse[qi], dw) for dw in doc_sparse])
        hybrid = alpha * _min_max(dense_all[qi]) + (1 - alpha) * _min_max(sparse)
        # tie-break deterministic: điểm giảm dần, rồi IRI tăng dần
        order = sorted(range(len(iris)), key=lambda j: (-hybrid[j], iris[j]))
        candidates.append(order[:top_k_retrieve])

    # ── Stage 3: rerank cross-encoder top-k ──
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    dtype = torch.float16 if (use_fp16 and device.type == "cuda") else torch.float32
    tok = AutoTokenizer.from_pretrained(RERANKER_NAME)
    rer = AutoModelForSequenceClassification.from_pretrained(
        RERANKER_NAME, dtype=dtype).to(device).eval()

    ranked: list[list[str]] = []
    for qi, cand_idx in enumerate(candidates):
        pairs = [[queries[qi], docs[j]] for j in cand_idx]
        with torch.no_grad():
            enc = tok(pairs, padding=True, truncation=True, return_tensors="pt",
                      max_length=512).to(device)
            logits = rer(**enc, return_dict=True).logits.view(-1).float()
            scores = (1.0 / (1.0 + np.exp(-logits.cpu().numpy())))      # sigmoid → [0,1]
        order = sorted(range(len(cand_idx)), key=lambda j: (-scores[j], iris[cand_idx[j]]))
        ranked.append([iris[cand_idx[j]] for j in order][:top_k_rerank])

    del rer, tok
    gc.collect()
    _free_cuda()
    return ranked
