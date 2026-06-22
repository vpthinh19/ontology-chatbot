"""Benchmark — ontology (duyệt cấu trúc) vs PHẲNG (truy hồi BGE) — 2 TẦNG metric.

    uv run --extra train python -m ontchatbot.baseline.benchmark \
        [--ontology-source model|gold] [--limit N]
    uv run --extra inference python -m ontchatbot.baseline.benchmark --reaggregate

Phân loại theo **NHÓM NĂNG LỰC** (:mod:`.groups`) hợp đề tài quy trình, KHÔNG theo miền học phí.
Chỉ MỘT kho phẳng → người đọc chỉ thấy "ontology vs phẳng".

**Tầng 1 — TRUY HỒI (cùng đơn vị: tập IRI):**
* Ontology trả ĐÚNG TẬP → precision/recall/F1 (micro) + exact-set.
* Phẳng trả danh sách xếp hạng → recall@k / precision@k / full@k (k=1/3/5, **headline @3**).
**Tầng 2 — ĐÁP-ÁN-CUỐI (chỉ truy vấn data):** ontology chọn đúng field+value; phẳng **N/A**.

``--reaggregate`` đọc lại ``benchmark_details.jsonl`` (per-query gold/ont_pred/flat_top5) + lấy
tầng-2 từ report cũ → dựng lại report+nhóm mà KHÔNG chạy BGE/model (tất định, dùng khi đổi cách
gom nhóm). Gold suy từ cây-vàng-đã-qua-oracle (:mod:`.gold`). Ontology end-to-end = HF thật.
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
from .docstore import build_corpus, load_flat_db
from .gold import AnswerSpec, answer_spec
from .groups import GROUP_KEYS, GROUP_LABEL, group_of

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

_KS = (1, 3, 5)
_FLAT_KEYS = tuple(f"{m}@{k}" for k in _KS for m in ("recall", "precision", "full"))


def _versions() -> dict:
    """Phiên bản package để audit/tái lập — đọc metadata, không import."""
    import importlib.metadata as md
    out = {}
    for pkg in ("torch", "transformers", "FlagEmbedding", "scikit-learn", "ctranslate2"):
        try:
            out[pkg] = md.version(pkg)
        except md.PackageNotFoundError:
            out[pkg] = None
    return out


def _new_cat() -> dict:
    return {"n": 0, "ont_inter": 0, "ont_npred": 0, "ont_ngold": 0, "ont_exact": 0,
            "data_n": 0, "ont_field_hit": 0, "ont_value_exact": 0,
            "flat": defaultdict(float)}


# ── Nạp + materialize gold ───────────────────────────────────────────────────

def _load_rows(limit: int) -> list[dict]:
    rows = [json.loads(l) for l in TEST_PATH.read_text(encoding="utf-8").splitlines() if l.strip()]
    return rows[:limit] if limit else rows


def _build_gold(rows: list[dict], ont: Ontology) -> list[tuple[dict, AnswerSpec]]:
    """Mỗi row → (row, gold AnswerSpec); vật-chất-hoá ra gold.jsonl để AUDIT (tất định)."""
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


def _accumulate(c: dict, gold: frozenset[str], ont_iris: frozenset[str], ranked: list[str]) -> None:
    """Cộng tầng-1 (ontology micro + flat recall@k/full@k) cho một câu vào nhóm ``c``."""
    c["n"] += 1
    c["ont_inter"] += len(ont_iris & gold)
    c["ont_npred"] += len(ont_iris)
    c["ont_ngold"] += len(gold)
    c["ont_exact"] += int(ont_iris == gold)
    for key, val in _flat_metrics(gold, ranked).items():
        c["flat"][key] += val


def run(args: argparse.Namespace) -> int:
    import numpy as np
    np.random.seed(0)
    try:
        import torch
        torch.manual_seed(0)
    except Exception:
        pass

    ont = Ontology()
    rows = _load_rows(args.limit)
    gold = _build_gold(rows, ont)
    retr = [(r, g) for r, g in gold if g.kind in ("node", "data")]   # phẳng chỉ chấm truy-hồi-được
    print(f"[bench] n_total={len(rows)} n_retrievable={len(retr)} source={args.ontology_source}")

    ont_specs = _ontology_preds([r for r, _ in gold], ont, args.ontology_source,
                                args.model_dir, args.num_beams, args.batch_size)
    spec_by_text = {id(r): s for (r, _), s in zip(gold, ont_specs)}

    # Phẳng: MỘT corpus, rank câu GỐC (chuẩn IR). Chạy sau khi ontology đã nhả VRAM.
    texts = [r["text"] for r, _ in retr]
    corpus = load_flat_db()                      # ưu tiên artifact đã vật chất hoá (peer của ontology)
    if corpus is None:
        print("[bench] ⚠️ chưa có artifact kho phẳng — dựng tạm; chạy scripts.build_flat_db để vật chất hoá")
        corpus = build_corpus(ont)
    print(f"[bench] phẳng corpus={len(corpus)} docs → rank {len(texts)} queries…")
    flat_ranked = retrieval.rank_all(corpus, texts)

    cats: dict[str, dict] = defaultdict(_new_cat)
    details = []
    for i, (r, g) in enumerate(retr):
        grp = group_of(r.get("category", "?"))
        c = cats[grp]
        ps = spec_by_text[id(r)]
        _accumulate(c, g.iris, ps.iris, flat_ranked[i])
        if g.kind == "data":
            c["data_n"] += 1
            gprops = {p for p, _ in g.fields}
            pprops = {p for p, _ in ps.fields}
            c["ont_field_hit"] += int(bool(gprops) and gprops <= pprops and ps.iris == g.iris)
            c["ont_value_exact"] += int(set(g.fields) == set(ps.fields) and ps.iris == g.iris)
        details.append({"text": r["text"], "category": r.get("category", "?"), "group": grp,
                        "kind": g.kind, "gold": sorted(g.iris), "ont_pred": sorted(ps.iris),
                        "flat_top5": flat_ranked[i][:5]})

    _report(cats, details, args, _live_config(args))
    return 0


def _live_config(args) -> dict:
    return {"alpha": retrieval.ALPHA, "top_k_retrieve": retrieval.TOP_K_RETRIEVE,
            "top_k_rerank": retrieval.TOP_K_RERANK, "ks": list(_KS),
            "ontology_source": args.ontology_source, "num_beams": args.num_beams,
            "m3": retrieval.M3_NAME, "reranker": retrieval.RERANKER_NAME, "versions": _versions(),
            "aggregation": {"ontology": "micro (Σinter/Σpred, Σinter/Σgold)",
                            "flat": "query-mean (trung bình recall@k/precision@k/full@k theo câu)"},
            "metric_note": ("So 'đúng-toàn-bộ' apples-to-apples = ontology exact_set vs flat full@k; "
                            "full@3 BẤT LỢI cơ học khi |gold|>3 → đọc kèm full@5 + recall@k. Trục phân "
                            "loại = NHÓM NĂNG LỰC (groups.py).")}


# ── Tái-gom từ details (không chạy BGE/model) ────────────────────────────────

def reaggregate() -> int:
    """Dựng lại report+details theo nhóm năng lực TỪ details cũ (per-query) + tầng-2 report cũ."""
    det_path = EVAL_ARTIFACTS_DIR / "benchmark_details.jsonl"
    rep_path = EVAL_ARTIFACTS_DIR / "benchmark_report.json"
    recs = [json.loads(l) for l in det_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    old = json.loads(rep_path.read_text(encoding="utf-8")) if rep_path.exists() else {}

    cats: dict[str, dict] = defaultdict(_new_cat)
    new_details = []
    for rec in recs:
        grp = group_of(rec.get("category", "?"))
        ranked = rec.get("flat_top5") or []
        _accumulate(cats[grp], frozenset(rec["gold"]), frozenset(rec["ont_pred"]), ranked)
        new_details.append({"text": rec["text"], "category": rec.get("category", "?"),
                            "group": grp, "kind": rec.get("kind"), "gold": rec["gold"],
                            "ont_pred": rec["ont_pred"], "flat_top5": ranked[:5]})

    # Tầng 2: regroup data_tier per-category cũ (field_hit/value_exact theo data_n) → nhóm.
    for cat, d in (old.get("data_tier") or {}).items():
        grp = group_of(cat)
        dn = d.get("data_n", 0)
        cats[grp]["data_n"] += dn
        cats[grp]["ont_field_hit"] += round(d.get("ontology_field_hit", 0) * dn)
        cats[grp]["ont_value_exact"] += round(d.get("ontology_value_exact", 0) * dn)

    det_path.write_text("\n".join(json.dumps(d, ensure_ascii=False) for d in new_details) + "\n",
                        encoding="utf-8")
    cfg = old.get("config", {})
    cfg["metric_note"] = ("Trục phân loại = NHÓM NĂNG LỰC (groups.py); báo cáo re-gom từ details "
                          "per-query (tất định, không chạy lại BGE).")
    _report(cats, None, _ReaggArgs(), cfg)
    return 0


class _ReaggArgs:
    ontology_source = "model"


# ── Báo cáo ──────────────────────────────────────────────────────────────────

def _report(cats: dict, details, args, config: dict) -> None:
    def agg_ont(c):
        p = c["ont_inter"] / c["ont_npred"] if c["ont_npred"] else 0.0
        r = c["ont_inter"] / c["ont_ngold"] if c["ont_ngold"] else 0.0
        return {"precision": p, "recall": r, "f1": _f1(p, r),
                "exact_set": c["ont_exact"] / c["n"] if c["n"] else 0.0}

    order = [g for g in GROUP_KEYS if g in cats] + [g for g in cats if g not in GROUP_KEYS]
    print("\n=== TẦNG 1: TRUY HỒI (tìm đúng tập IRI) — theo NHÓM NĂNG LỰC ===")
    hdr = (f"{'nhóm năng lực':20} {'n':>4} | {'ONT-P':>6}{'ONT-R':>6}{'ONT-F1':>7}{'ONT-ex':>7} | "
           f"{'PHẲNG-R@3':>10}{'R@5':>6}{'full@3':>7}")
    print(hdr); print("-" * len(hdr))

    report = {"config": config, "per_type": {}, "data_tier": {}}
    tot = defaultdict(float)
    for grp in order:
        c = cats[grp]
        o = agg_ont(c)
        fa = {k: c["flat"][k] / c["n"] for k in c["flat"]} if c["n"] else {}
        print(f"{GROUP_LABEL.get(grp, grp):20} {c['n']:>4} | {o['precision']:>6.2f}{o['recall']:>6.2f}"
              f"{o['f1']:>7.2f}{o['exact_set']:>7.0%} | "
              f"{fa.get('recall@3', 0):>10.2f}{fa.get('recall@5', 0):>6.2f}{fa.get('full@3', 0):>7.0%}")
        report["per_type"][grp] = {"label": GROUP_LABEL.get(grp, grp), "n": c["n"],
                                   "ontology": o, "flat": fa}
        for k, val in (("inter", "ont_inter"), ("npred", "ont_npred"), ("ngold", "ont_ngold"),
                       ("exact", "ont_exact"), ("n", "n")):
            tot[k] += c[val]

    p = tot["inter"] / tot["npred"] if tot["npred"] else 0.0
    r = tot["inter"] / tot["ngold"] if tot["ngold"] else 0.0
    micro = {"precision": p, "recall": r, "f1": _f1(p, r),
             "exact_set": tot["exact"] / tot["n"] if tot["n"] else 0.0}
    flat_overall = ({k: sum(cats[g]["flat"][k] for g in cats) / tot["n"] for k in _FLAT_KEYS}
                    if tot["n"] else {k: 0.0 for k in _FLAT_KEYS})
    print("-" * len(hdr))
    print(f"{'TỔNG (micro)':20} {int(tot['n']):>4} | {p:>6.2f}{r:>6.2f}{_f1(p, r):>7.2f}"
          f"{micro['exact_set']:>7.0%} | "
          f"{flat_overall['recall@3']:>10.2f}{flat_overall['recall@5']:>6.2f}{flat_overall['full@3']:>7.0%}")
    report["overall"] = {"ontology": micro, "flat": flat_overall}

    # ── Tầng 2: đáp-án-cuối (data) ──
    print("\n=== TẦNG 2: ĐÁP-ÁN-CUỐI (truy vấn data) — phẳng = N/A (retrieval-only) ===")
    for grp in order:
        c = cats[grp]
        if not c["data_n"]:
            continue
        fh = c["ont_field_hit"] / c["data_n"]
        ve = c["ont_value_exact"] / c["data_n"]
        print(f"{GROUP_LABEL.get(grp, grp):20} data_n={c['data_n']:>4} field_hit={fh:>5.0%} value_exact={ve:>5.0%}")
        report["data_tier"][grp] = {"label": GROUP_LABEL.get(grp, grp), "data_n": c["data_n"],
                                    "ontology_field_hit": fh, "ontology_value_exact": ve, "flat": "N/A"}

    canonical = getattr(args, "ontology_source", "model") == "model"
    tag = "" if canonical else f"_{args.ontology_source}"
    rep_path = EVAL_ARTIFACTS_DIR / f"benchmark_report{tag}.json"
    EVAL_ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    rep_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[bench] báo cáo → {rep_path}")
    if details is not None:
        det_path = EVAL_ARTIFACTS_DIR / f"benchmark_details{tag}.jsonl"
        det_path.write_text("\n".join(json.dumps(d, ensure_ascii=False) for d in details) + "\n",
                            encoding="utf-8")
        print(f"[bench] chi tiết per-query → {det_path}")


def main() -> None:
    p = argparse.ArgumentParser(description="Benchmark: ontology vs phẳng (2 tầng metric)")
    p.add_argument("--ontology-source", choices=("model", "gold"), default="model")
    p.add_argument("--model-dir", default=None)
    p.add_argument("--num-beams", type=int, default=4)
    p.add_argument("--batch-size", type=int, default=16)
    p.add_argument("--limit", type=int, default=0, help="chỉ N dòng đầu (smoke)")
    p.add_argument("--reaggregate", action="store_true",
                   help="dựng lại report theo nhóm TỪ details cũ, KHÔNG chạy BGE/model")
    args = p.parse_args()
    if args.reaggregate:
        sys.exit(reaggregate())
    if args.model_dir is None:
        from ..config import MODEL_DIR
        args.model_dir = str(MODEL_DIR)
    sys.exit(run(args))


if __name__ == "__main__":
    main()
