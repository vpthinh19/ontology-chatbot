"""Benchmark Phase 8 — ontology (duyệt cấu trúc) vs phẳng (truy hồi BGE) — 2 TẦNG metric.

    uv run --extra train --extra benchmark python -m ontchatbot.baseline.benchmark \
        [--ontology-source model|gold] [--limit N] [--variants concise,denorm]

**Tầng 1 — TRUY HỒI (cùng đơn vị: tập IRI):**
* Ontology trả ĐÚNG TẬP → precision/recall/F1 (micro) + exact-set.
* Phẳng trả danh sách xếp hạng → recall@k / precision@k / full@k (k=1/3/5, **headline @3**).
  Ưu-ái phẳng: chỉ cần IRI gold lọt top-k; ontology phải trả khít. So head-to-head công bằng
  ở khả năng "tìm đúng tài liệu" (Codex review #1).
**Tầng 2 — ĐÁP-ÁN-CUỐI (chỉ truy vấn data):**
* Ontology: chọn đúng field + value (doc_hit ∧ field_hit ∧ value_exact).
* Phẳng: **N/A** (retrieval-only — không trích field/value; ghi trung thực, không trộn với tầng 1).

Gold suy từ cây-vàng-đã-qua-oracle (xem :mod:`.gold`) và được materialize ra ``gold.jsonl``.
Ontology end-to-end = text→model(generate)→cây→traverse (đo trọng số HF thật, không CT2). Phẳng
nhận **câu gốc** (chuẩn IR, không tách thực thể). Staging: chạy xong phía ontology (giải phóng
model) rồi mới tới phía phẳng (BGE) — vừa GPU 6GB.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

from ..config import EVAL_ARTIFACTS_DIR, TEST_PATH
from ..ontology import Ontology
from ..preprocess import clean
from ..tree import parse
from . import retrieval
from .docstore import VARIANTS, build_corpus
from .gold import AnswerSpec, answer_spec

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

_KS = (1, 3, 5)
_FLAT_KEYS = tuple(f"{m}@{k}" for k in _KS for m in ("recall", "precision", "full"))


def _versions() -> dict:
    """Phiên bản package để audit/tái lập (Codex review #8) — đọc metadata, không import."""
    import importlib.metadata as md
    out = {}
    for pkg in ("torch", "transformers", "FlagEmbedding", "scikit-learn", "ctranslate2"):
        try:
            out[pkg] = md.version(pkg)
        except md.PackageNotFoundError:
            out[pkg] = None
    return out


# ── Nạp + materialize gold ───────────────────────────────────────────────────

def _load_rows(limit: int) -> list[dict]:
    rows = [json.loads(l) for l in TEST_PATH.read_text(encoding="utf-8").splitlines() if l.strip()]
    return rows[:limit] if limit else rows


def _build_gold(rows: list[dict], ont: Ontology) -> list[tuple[dict, AnswerSpec]]:
    """Mỗi row → (row, gold AnswerSpec). Giữ LẠI mọi row (kể cả nonretrievable) để báo cáo;
    lọc khi chấm phẳng. Gold suy từ cây-vàng-đã-qua-oracle theo ngữ nghĩa ontology (tất định);
    vật-chất-hoá ra gold.jsonl để AUDIT (Codex review #1 — không tự nhận 'load tĩnh' vì vẫn
    tính lại mỗi lần, nhưng kết quả tất định nên file = ảnh chụp kiểm chứng được)."""
    out = [(r, answer_spec(parse(r["tree"]), ont)) for r in rows]
    EVAL_ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    with (EVAL_ARTIFACTS_DIR / "gold.jsonl").open("w", encoding="utf-8") as f:
        for r, g in out:
            f.write(json.dumps({"text": r["text"], "category": r.get("category"),
                                "kind": g.kind, "iris": sorted(g.iris),
                                "fields": [[p, list(v)] for p, v in g.fields]},
                               ensure_ascii=False) + "\n")
    return out


# ── Phía ontology (end-to-end hoặc gold-sanity) ──────────────────────────────

def _ontology_preds(rows: list[dict], ont: Ontology, source: str, model_dir: str,
                    num_beams: int, batch_size: int) -> list[AnswerSpec]:
    if source == "gold":
        return [answer_spec(parse(r["tree"]), ont) for r in rows]   # sanity: phải ≈ trùng gold
    from ..scripts.evaluate import _generate, _resolve_model_dir
    import torch
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

    mdir = _resolve_model_dir(model_dir)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[bench] ontology end-to-end: model={mdir} device={device}")
    tok = AutoTokenizer.from_pretrained(mdir)
    model = AutoModelForSeq2SeqLM.from_pretrained(mdir).to(device).eval()
    preds = _generate(model, tok, [clean(r["text"]) for r in rows], device, num_beams, batch_size)
    specs = [answer_spec(p.tree, ont) for p in preds]
    del model, tok                                   # giải phóng trước khi nạp BGE (staging VRAM)
    import gc; gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    return specs


# ── Chấm điểm ────────────────────────────────────────────────────────────────

def _f1(p: float, r: float) -> float:
    return 2 * p * r / (p + r) if (p + r) else 0.0


def _flat_metrics(gold: frozenset[str], ranked: list[str]) -> dict:
    """recall@k / precision@k / full@k cho một câu (gold != rỗng)."""
    m = {}
    for k in _KS:
        topk = set(ranked[:k])
        inter = len(gold & topk)
        m[f"recall@{k}"] = inter / len(gold)
        m[f"precision@{k}"] = inter / k
        m[f"full@{k}"] = 1.0 if gold <= topk else 0.0
    return m


def run(args: argparse.Namespace) -> int:
    import numpy as np
    np.random.seed(0)
    try:
        import torch
        torch.manual_seed(0)
    except Exception:
        pass

    variants = [v.strip() for v in args.variants.split(",") if v.strip()]
    assert all(v in VARIANTS for v in variants), f"variants ∈ {VARIANTS}"

    ont = Ontology()
    rows = _load_rows(args.limit)
    gold = _build_gold(rows, ont)
    retr = [(r, g) for r, g in gold if g.kind in ("node", "data")]   # phẳng chỉ chấm truy-hồi-được
    print(f"[bench] n_total={len(rows)} n_retrievable={len(retr)} variants={variants} "
          f"source={args.ontology_source}")

    # Ontology end-to-end (trên TẤT CẢ rows để báo cả non-retrievable nếu muốn; ta chấm trên retr).
    ont_specs = _ontology_preds([r for r, _ in gold], ont, args.ontology_source,
                                args.model_dir, args.num_beams, args.batch_size)
    spec_by_text = {id(r): s for (r, _), s in zip(gold, ont_specs)}

    # Phẳng: dựng corpus + rank (câu GỐC, chuẩn IR). Chạy sau khi ontology đã nhả VRAM.
    texts = [r["text"] for r, _ in retr]
    flat_ranked: dict[str, list[list[str]]] = {}
    for v in variants:
        corpus = build_corpus(ont, v)
        print(f"[bench] flat[{v}] corpus={len(corpus)} docs → rank {len(texts)} queries…")
        flat_ranked[v] = retrieval.rank_all(corpus, texts)

    # ── Gom số liệu per-category ──
    cats = defaultdict(lambda: {
        "n": 0, "ont_inter": 0, "ont_npred": 0, "ont_ngold": 0, "ont_exact": 0,
        "data_n": 0, "ont_field_hit": 0, "ont_value_exact": 0,
        "flat": {v: defaultdict(float) for v in variants},
    })
    details = []
    for i, (r, g) in enumerate(retr):
        cat = r.get("category", "?")
        c = cats[cat]
        c["n"] += 1
        ps = spec_by_text[id(r)]
        inter = len(ps.iris & g.iris)
        c["ont_inter"] += inter
        c["ont_npred"] += len(ps.iris)
        c["ont_ngold"] += len(g.iris)
        c["ont_exact"] += int(ps.iris == g.iris)
        if g.kind == "data":
            c["data_n"] += 1
            gprops = {p for p, _ in g.fields}
            pprops = {p for p, _ in ps.fields}
            c["ont_field_hit"] += int(bool(gprops) and gprops <= pprops and ps.iris == g.iris)
            c["ont_value_exact"] += int(set(g.fields) == set(ps.fields) and ps.iris == g.iris)
        det = {"text": r["text"], "category": cat, "kind": g.kind,
               "gold": sorted(g.iris), "ont_pred": sorted(ps.iris)}
        for v in variants:
            fm = _flat_metrics(g.iris, flat_ranked[v][i])
            for key, val in fm.items():
                c["flat"][v][key] += val
            det[f"flat_{v}_top5"] = flat_ranked[v][i][:5]
        details.append(det)

    _report(cats, variants, details, args)
    return 0


# ── Báo cáo ──────────────────────────────────────────────────────────────────

def _report(cats: dict, variants: list[str], details: list[dict],
            args: argparse.Namespace) -> None:
    def agg_ont(c):
        p = c["ont_inter"] / c["ont_npred"] if c["ont_npred"] else 0.0
        r = c["ont_inter"] / c["ont_ngold"] if c["ont_ngold"] else 0.0
        return {"precision": p, "recall": r, "f1": _f1(p, r),
                "exact_set": c["ont_exact"] / c["n"] if c["n"] else 0.0}

    print("\n=== TẦNG 1: TRUY HỒI (tìm đúng tập IRI) ===")
    hdr = f"{'query-type':16} {'n':>4} | {'ONT-P':>6}{'ONT-R':>6}{'ONT-F1':>7}{'ONT-ex':>7} |"
    for v in variants:
        hdr += f" {v[:6]+'-R@3':>11}{'R@5':>6}{'full@3':>7}"
    print(hdr); print("-" * len(hdr))

    report = {"config": {"alpha": retrieval.ALPHA, "top_k_retrieve": retrieval.TOP_K_RETRIEVE,
                         "top_k_rerank": retrieval.TOP_K_RERANK, "ks": list(_KS),
                         "ontology_source": args.ontology_source, "num_beams": args.num_beams,
                         "m3": retrieval.M3_NAME, "reranker": retrieval.RERANKER_NAME,
                         "versions": _versions(),
                         "aggregation": {"ontology": "micro (Σinter/Σpred, Σinter/Σgold)",
                                         "flat": "query-mean (trung bình recall@k/precision@k/full@k theo câu)"},
                         "metric_note": ("So 'đúng-toàn-bộ' apples-to-apples = ontology exact_set vs "
                                         "flat full@k; full@3 BẤT LỢI cơ học khi |gold|>3 (vd fee_union) "
                                         "→ đọc kèm full@5 + recall@k.")},
              "per_type": {}, "data_tier": {}}
    tot = defaultdict(float)
    for cat in sorted(cats):
        c = cats[cat]
        o = agg_ont(c)
        line = (f"{cat:16} {c['n']:>4} | {o['precision']:>6.2f}{o['recall']:>6.2f}"
                f"{o['f1']:>7.2f}{o['exact_set']:>7.0%} |")
        ftype = {}
        for v in variants:
            fa = {k: c["flat"][v][k] / c["n"] for k in c["flat"][v]}
            ftype[v] = fa
            line += f" {fa['recall@3']:>11.2f}{fa['recall@5']:>6.2f}{fa['full@3']:>7.0%}"
        print(line)
        report["per_type"][cat] = {"n": c["n"], "ontology": o, "flat": ftype}
        for k, val in (("inter", "ont_inter"), ("npred", "ont_npred"), ("ngold", "ont_ngold"),
                       ("exact", "ont_exact"), ("n", "n")):
            tot[k] += c[val]

    p = tot["inter"] / tot["npred"] if tot["npred"] else 0.0
    r = tot["inter"] / tot["ngold"] if tot["ngold"] else 0.0
    print("-" * len(hdr))
    micro = {"precision": p, "recall": r, "f1": _f1(p, r),
             "exact_set": tot["exact"] / tot["n"] if tot["n"] else 0.0}
    line = (f"{'TOTAL (micro)':16} {int(tot['n']):>4} | {p:>6.2f}{r:>6.2f}{_f1(p, r):>7.2f}"
            f"{micro['exact_set']:>7.0%} |")
    flat_overall = {}
    for v in variants:
        fa = ({k: sum(cats[cat]["flat"][v][k] for cat in cats) / tot["n"] for k in _FLAT_KEYS}
              if tot["n"] else {k: 0.0 for k in _FLAT_KEYS})
        flat_overall[v] = fa
        line += f" {fa['recall@3']:>11.2f}{fa['recall@5']:>6.2f}{fa['full@3']:>7.0%}"
    print(line)
    report["overall"] = {"ontology": micro, "flat": flat_overall}

    # ── Tầng 2: đáp-án-cuối (data) ──
    print("\n=== TẦNG 2: ĐÁP-ÁN-CUỐI (truy vấn data) — phẳng = N/A (retrieval-only) ===")
    print(f"{'query-type':16} {'data_n':>7} {'ONT field_hit':>14} {'ONT value_exact':>16} {'flat':>6}")
    for cat in sorted(cats):
        c = cats[cat]
        if not c["data_n"]:
            continue
        fh = c["ont_field_hit"] / c["data_n"]
        ve = c["ont_value_exact"] / c["data_n"]
        print(f"{cat:16} {c['data_n']:>7} {fh:>14.0%} {ve:>16.0%} {'N/A':>6}")
        report["data_tier"][cat] = {"data_n": c["data_n"], "ontology_field_hit": fh,
                                    "ontology_value_exact": ve, "flat": "N/A"}

    # Chỉ run CANONICAL (model + đủ biến thể) mới ghi đè artifact chính; run sanity/giới-hạn ghi
    # ra file có hậu tố để KHÔNG clobber kết quả thật (vd `--ontology-source gold` để kiểm harness).
    canonical = args.ontology_source == "model" and bool(variants)
    tag = "" if canonical else f"_{args.ontology_source}"
    rep_path = EVAL_ARTIFACTS_DIR / f"benchmark_report{tag}.json"
    det_path = EVAL_ARTIFACTS_DIR / f"benchmark_details{tag}.jsonl"
    EVAL_ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    rep_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    det_path.write_text("\n".join(json.dumps(d, ensure_ascii=False) for d in details) + "\n",
                        encoding="utf-8")
    print(f"\n[bench] báo cáo → {rep_path}")
    print(f"[bench] chi tiết per-query → {det_path}")


def main() -> None:
    p = argparse.ArgumentParser(description="Benchmark Phase 8: ontology vs phẳng (2 tầng metric)")
    p.add_argument("--ontology-source", choices=("model", "gold"), default="model",
                   help="model = end-to-end thật; gold = sanity (ontology từ cây vàng, ≈1.0)")
    p.add_argument("--model-dir", default=None, help="thư mục model HF (mặc định config.MODEL_DIR)")
    p.add_argument("--variants", default="concise,denorm", help="biến thể corpus phẳng")
    p.add_argument("--num-beams", type=int, default=4)
    p.add_argument("--batch-size", type=int, default=16)
    p.add_argument("--limit", type=int, default=0, help="chỉ N dòng đầu (smoke)")
    args = p.parse_args()
    if args.model_dir is None:
        from ..config import MODEL_DIR
        args.model_dir = str(MODEL_DIR)
    sys.exit(run(args))


if __name__ == "__main__":
    main()
