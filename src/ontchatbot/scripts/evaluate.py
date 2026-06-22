"""Đánh giá BARTpho tree-model ở 2 MỨC.

    uv run --extra train python -m ontchatbot.scripts.evaluate \
        [--model-dir artifacts/models/bartpho_tree] [--limit N] [--num-beams 4]

Vì sao 2 mức: **eval-loss KHÔNG đủ** chứng minh đúng — hai chuỗi JSON lệch 1 token vẫn loss gần
nhau nhưng ``traverse`` ra node SAI. Nên tách:

* **Mức 1 — cấu trúc cây (cô lập BART):** model sinh JSON. Đo: JSON hợp lệ (``json_valid``); chuỗi
  có đúng HỢP ĐỒNG cây nghiêm không (``strict_ok`` = ``tree.parse_strict`` không raise — chống
  ``parse`` khoan dung "vá" lỗi rồi che đi); ``act`` đúng (``act_acc``); và cây khớp gold sau khi
  chuẩn hoá nhãn + **bất biến thứ tự anh-em** (``tree_norm``, chỉ tính trên gold-query); ``shape``
  = đúng cấu trúc kể cả nhãn sai (chẩn đoán, chỉ trên gold-query).
* **Mức 2 — đầu-cuối:** ``text → model → cây → traverse`` so với đáp-án-chuẩn = ``traverse(gold_tree)``.
  Quy đáp án về tập **đơn vị đáp án** (answer atom — đơn vị nhỏ nhất để so theo TẬP, cho điểm phần):
  ``("node", iri)`` cho mỗi cá thể, ``("data", prop, value)`` cho lá data ("đúng phiếu sai field =
  SAI"), ``("miss", nhãn)`` cho nhánh không khớp (phân biệt "không có thông tin về X" với "về Y"),
  ``("vague",)`` / ``("act", x)`` cho mơ hồ/chào/ood. Báo Precision / Recall / F1 (micro) + tỷ lệ
  trùng-khít-tập **theo 5 NHÓM NĂNG LỰC** (``capabilities.group_of``: tra-cứu / đi-một-quan-hệ /
  đi-nhiều-bước / nhiều-thuộc-tính / lọc — KHÔNG theo miền học phí), macro trung bình trên 5 nhóm;
  các loại phi-truy-vấn (vague/ood/greeting/kiểm-âm) báo riêng, không tính vào macro.

⚠️ HẠN CHẾ ĐÃ BIẾT (báo cáo trung thực): atom data là ``(prop, value)`` KHÔNG kèm subject IRI vì
``Result.DataValue`` không lưu chủ thể — nếu hai cá thể khác nhau có cùng (field, value) thì model
trả sai chủ thể vẫn được tính đúng (hiếm: giá trị thường phân biệt). Khắc phục triệt để cần đổi
``ontology.DataValue`` (việc core, ngoài phạm vi script này).

Model nạp = checkpoint HF (torch ``generate``); deploy dùng CTranslate2 — eval này đo TRỌNG SỐ đã
train, không phải đường inference triển khai. Source = ``preprocess.clean(text)`` ĐỒNG BỘ với train
(train.py dùng cùng hàm) để khỏi lệch phân phối.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from ..config import (
    EVAL_ARTIFACTS_DIR,
    MAX_SOURCE_LENGTH,
    MAX_TARGET_LENGTH,
    MODEL_DIR,
    TEST_PATH,
)
from ..ontology import Ontology, Result
from ..preprocess import clean, normalize_for_match
from ..tree import QUERY, VAGUE, StrictParseError, Tree, TreeNode, from_model_json, parse, parse_strict
from ..capabilities import GROUP_KEYS, GROUP_LABEL, group_of

if hasattr(sys.stdout, "reconfigure"):           # Windows console mặc định cp1252
    sys.stdout.reconfigure(encoding="utf-8")

# category mà đáp án ĐÚNG vốn là "không trả node" — để sanity-check gold không nhầm là drift.
_NEGATIVE_CATS = frozenset({"neg_child_miss", "neg_root_vague", "vague", "ood", "greeting"})


# ── Mức 1: so cấu trúc cây (chuẩn hoá nhãn, bất biến thứ tự anh-em) ───────────

def _canon(node: TreeNode) -> tuple:
    """Dạng chuẩn của một node để so cây: (kind, nhãn-chuẩn-hoá, multiset con đã sort).

    Sort con → bất biến thứ tự anh-em (anh-em = nhánh độc lập §5, ``k65>cntt`` ≡ ``cntt>k65``).
    Nhãn chuẩn hoá bằng ``normalize_for_match`` — đúng phép chuẩn hoá mà bộ khớp dùng, nên hai
    nhãn coi-là-bằng ở đây cũng resolve y hệt; không che lỗi chọn-sai-từ (vd học phí≠học bổng)."""
    return (node.kind, normalize_for_match(node.label),
            tuple(sorted(_canon(c) for c in node.children)))


def _tree_canon(t: Tree) -> tuple:
    """Cả cây về dạng chuẩn: (act, canon(root)|None)."""
    return (t.act, _canon(t.root) if t.root is not None else None)


def _shape(node: TreeNode) -> tuple:
    """Như ``_canon`` nhưng BỎ nhãn — chỉ kind + cấu trúc (chẩn đoán: BART đúng SHAPE chưa)."""
    return (node.kind, tuple(sorted(_shape(c) for c in node.children)))


# ── Mức 2: quy đáp án về tập "answer atoms" ──────────────────────────────────

def _atoms(act: str, res: Result) -> set:
    """Tập **đơn vị đáp án** (answer atom) mô tả đáp án thực mà người dùng nhận.

    * vague (act=vague HOẶC gốc trỏ class/quan-hệ) → ``("vague",)``. Gộp hai đường vì cùng cho
      "Không hiểu câu hỏi" — khớp đúng điều kiện ``render`` dùng (``act == VAGUE or result.vague``),
      nếu không model trả lời đúng vẫn bị chấm sai chỉ vì khác đường nội bộ.
    * greeting/ood → ``("act", act)`` (mỗi loại một câu trả lời riêng, không tra cứu).
    * còn lại: mỗi node terminal → ``("node", iri)``; mỗi giá trị lá data → ``("data", prop, str(v))``
      (gói cả ``prop`` ⇒ sai field = atom khác = SAI); mỗi nhánh không khớp → ``("miss", nhãn)``
      (phân biệt "không có thông tin về X/Y" và chống empty≡empty ăn điểm — Codex review H4).
    """
    if act == VAGUE or res.vague:
        return {("vague",)}
    if act != QUERY:
        return {("act", act)}
    out: set = {("node", n.iri) for n in res.nodes}
    for dv in res.values:
        for v in dv.values:
            out.add(("data", dv.prop, str(v)))
    for label in res.misses:
        out.add(("miss", normalize_for_match(label)))
    return out


def _prf(inter: int, npred: int, ngold: int) -> tuple[float, float, float]:
    """Precision / Recall / F1 từ tổng giao / |pred| / |gold| (micro-aggregate được)."""
    p = inter / npred if npred else (1.0 if ngold == 0 else 0.0)
    r = inter / ngold if ngold else (1.0 if npred == 0 else 0.0)
    f = 2 * p * r / (p + r) if (p + r) else 0.0
    return p, r, f


# ── Sinh cây từ model (torch generate, theo lô) ──────────────────────────────

@dataclass
class _Pred:
    raw: str            # chuỗi model sinh (để soi khi sai)
    json_ok: bool       # json.loads thành công?
    strict_ok: bool     # chuỗi đúng hợp đồng cây nghiêm (parse_strict không raise)?
    tree: Tree          # cây đã parse KHOAN DUNG (json hỏng → Tree(VAGUE), khớp production)


def _generate(model, tokenizer, texts: list[str], device, num_beams: int, batch_size: int
              ) -> list[_Pred]:
    """text (đã clean) → list[_Pred]. JSON hỏng → ``parse`` khoan dung trả vague (như pipeline thật)."""
    import torch

    preds: list[_Pred] = []
    for i in range(0, len(texts), batch_size):
        chunk = texts[i:i + batch_size]
        enc = tokenizer(chunk, return_tensors="pt", padding=True, truncation=True,
                        max_length=MAX_SOURCE_LENGTH).to(device)
        with torch.no_grad():
            out = model.generate(**enc, num_beams=num_beams, max_length=MAX_TARGET_LENGTH)
        for s in tokenizer.batch_decode(out, skip_special_tokens=True):
            try:
                obj = from_model_json(s)                 # bỏ pad + items→entities → dict cây chuẩn
            except (json.JSONDecodeError, TypeError):
                preds.append(_Pred(raw=s, json_ok=False, strict_ok=False, tree=Tree(act="vague")))
                continue
            try:
                parse_strict(obj)
                strict_ok = True
            except StrictParseError:
                strict_ok = False
            preds.append(_Pred(raw=s, json_ok=True, strict_ok=strict_ok, tree=parse(obj)))
    return preds


# ── Gom số liệu ──────────────────────────────────────────────────────────────

@dataclass
class _Bucket:
    """Thống kê tích luỹ cho một query-type (micro). ``n_query`` = số gold act==query
    (mẫu số cho tree_norm/shape — hai metric này vô nghĩa với non-query, Codex review M4)."""
    n: int = 0
    n_query: int = 0
    json_ok: int = 0
    strict_ok: int = 0
    act_ok: int = 0
    tree_norm: int = 0
    shape_ok: int = 0
    e2e_exact: int = 0
    inter: int = 0
    npred: int = 0
    ngold: int = 0

    def add(self, other: "_Bucket") -> None:
        for f in self.__dataclass_fields__:
            setattr(self, f, getattr(self, f) + getattr(other, f))


def _resolve_model_dir(raw: str) -> str:
    """Trả thư mục có weight để nạp (đường TUYỆT ĐỐI cho local — transformers nhận chắc). Nếu ``raw``
    chưa lưu model cuối (chỉ có ``checkpoint-*``, train chưa xong) → chọn checkpoint bước CAO NHẤT +
    cảnh báo (Codex review H1). Không phải local model dir → trả nguyên (có thể là HF repo id)."""
    p = Path(raw)
    if (p / "config.json").exists():
        return str(p.resolve())
    ckpts = sorted([d for d in p.glob("checkpoint-*") if (d / "config.json").exists()],
                   key=lambda d: int(d.name.split("-")[-1]) if d.name.split("-")[-1].isdigit() else -1)
    if ckpts:
        print(f"[eval] ⚠️ {raw} chưa có model cuối — dùng checkpoint mới nhất: {ckpts[-1].name} "
              f"(train xong sẽ có model ở thư mục cha)")
        return str(ckpts[-1].resolve())
    if p.exists():
        print(f"[eval] ⚠️ {raw} tồn tại nhưng không có config.json/checkpoint-* — để HF xử lý")
    return raw                                   # HF repo id hoặc để HF báo lỗi rõ


def _gold_sanity(rows: list[dict], ont: Ontology) -> None:
    """Tripwire chống 'gold drift': gold phải qua parse_strict; gold-query (không phải negative)
    KHÔNG được ra misses/vague. Chỉ CẢNH BÁO (không chặn eval) — Codex review H3."""
    bad_parse, bad_traverse = [], []
    for r in rows:
        try:
            parse_strict(r["tree"])
        except StrictParseError as e:
            bad_parse.append(f"{r.get('category')}: {r['text']!r} — {e}")
            continue
        if r.get("category") in _NEGATIVE_CATS:
            continue
        res = ont.traverse(parse(r["tree"]))
        if res.vague or res.misses:
            bad_traverse.append(f"{r.get('category')}: {r['text']!r} "
                                f"vague={res.vague} misses={res.misses}")
    if bad_parse or bad_traverse:
        print(f"[eval] ⚠️ GOLD ĐÁNG NGỜ — strict-parse lỗi: {len(bad_parse)}, "
              f"traverse bất thường: {len(bad_traverse)} (eval vẫn chạy, nhưng nên rà):")
        for line in (bad_parse + bad_traverse)[:8]:
            print(f"        {line}")


def evaluate(args: argparse.Namespace) -> int:
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
    import torch

    rows = [json.loads(l) for l in TEST_PATH.read_text(encoding="utf-8").splitlines() if l.strip()]
    if args.limit:
        rows = rows[:args.limit]

    model_dir = _resolve_model_dir(args.model_dir)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[eval] model_dir={model_dir} device={device} n={len(rows)} beams={args.num_beams}")
    tokenizer = AutoTokenizer.from_pretrained(model_dir)
    model = AutoModelForSeq2SeqLM.from_pretrained(model_dir, dtype=torch.bfloat16).to(device).eval()
    gc = model.config                            # log cấu hình generate để soi bẫy mBART (Codex M5)
    print(f"[eval] tokenizer={type(tokenizer).__name__} "
          f"decoder_start={getattr(gc, 'decoder_start_token_id', None)} "
          f"bos={getattr(gc, 'bos_token_id', None)} eos={getattr(gc, 'eos_token_id', None)} "
          f"pad={getattr(gc, 'pad_token_id', None)} forced_bos={getattr(gc, 'forced_bos_token_id', None)}")

    ont = Ontology()
    _gold_sanity(rows, ont)
    texts = [clean(r["text"]) for r in rows]                 # ĐỒNG BỘ source với train
    preds = _generate(model, tokenizer, texts, device, args.num_beams, args.batch_size)

    buckets: dict[str, _Bucket] = defaultdict(_Bucket)
    mismatches: list[dict] = []
    act_conf: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))  # gold act → pred act → đếm

    for r, pred in zip(rows, preds):
        gold_tree = parse(r["tree"])
        gold_res, pred_res = ont.traverse(gold_tree), ont.traverse(pred.tree)
        gold_atoms, pred_atoms = _atoms(gold_tree.act, gold_res), _atoms(pred.tree.act, pred_res)
        is_query = gold_tree.act == QUERY

        b = buckets[group_of(r.get("category", "?"))]
        b.n += 1
        b.n_query += is_query
        b.json_ok += pred.json_ok
        b.strict_ok += pred.strict_ok
        b.act_ok += (pred.tree.act == gold_tree.act)
        act_conf[gold_tree.act][pred.tree.act] += 1       # ma trận nhầm lẫn act (cho Hình 10)
        if is_query:                             # tree_norm/shape chỉ có nghĩa khi gold là cây
            b.tree_norm += (_tree_canon(pred.tree) == _tree_canon(gold_tree))
            b.shape_ok += (pred.tree.root is not None
                           and _shape(pred.tree.root) == _shape(gold_tree.root))

        inter = len(pred_atoms & gold_atoms)
        b.inter += inter
        b.npred += len(pred_atoms)
        b.ngold += len(gold_atoms)
        exact = pred_atoms == gold_atoms
        b.e2e_exact += exact
        if not exact:
            mismatches.append({
                "text": r["text"], "category": r.get("category", "?"),
                "gold_act": gold_tree.act, "pred_act": pred.tree.act,
                "json_ok": pred.json_ok, "strict_ok": pred.strict_ok,
                "gold": sorted(map(str, gold_atoms)), "pred": sorted(map(str, pred_atoms)),
                "gold_misses": gold_res.misses, "pred_misses": pred_res.misses,
                "pred_raw": pred.raw,
            })

    _report(buckets, mismatches, model_dir, args, act_conf)
    overall = sum(b.e2e_exact for b in buckets.values())
    total = sum(b.n for b in buckets.values())
    return 0 if overall == total else 1


# ── In bảng + lưu báo cáo ────────────────────────────────────────────────────

def _report(buckets: dict[str, _Bucket], mismatches: list[dict], model_dir: str,
            args: argparse.Namespace, act_conf: dict[str, dict[str, int]] | None = None) -> None:
    hdr = (f"{'query-type':16} {'n':>4} {'json':>5} {'strict':>6} {'act':>5} {'tree':>5} "
           f"{'shape':>6} {'P':>5} {'R':>5} {'F1':>5} {'exact':>6}")
    print("\n" + hdr)
    print("-" * len(hdr))

    q_tot, nq_tot = _Bucket(), _Bucket()
    cap_f1s, cap_exacts = [], []
    cap_keys = [k for k in GROUP_KEYS if k in buckets]               # 5 nhóm năng lực, thứ tự khó dần
    other_keys = sorted(k for k in buckets if k not in GROUP_KEYS)   # phi-năng-lực: vague/ood/greeting + kiểm âm
    for key in cap_keys:                                            # trục CHÍNH: macro chỉ trung bình 5 nhóm này
        b = buckets[key]
        _print_row(GROUP_LABEL[key], b)
        q_tot.add(b)
        m = _bucket_metrics(b)
        cap_f1s.append(m["f1"]); cap_exacts.append(m["exact_set"])
    if other_keys:
        print("-" * len(hdr))
        for key in other_keys:
            b = buckets[key]
            _print_row(key, b)
            (q_tot if b.n_query else nq_tot).add(b)
    print("-" * len(hdr))
    if q_tot.n:
        _print_row("SUBTOTAL query", q_tot)
    if nq_tot.n:
        _print_row("SUBTOTAL nonq", nq_tot)
    all_tot = _Bucket(); all_tot.add(q_tot); all_tot.add(nq_tot)
    _print_row("TOTAL (micro)", all_tot)
    macro_f1 = sum(cap_f1s) / len(cap_f1s) if cap_f1s else 0.0
    macro_ex = sum(cap_exacts) / len(cap_exacts) if cap_exacts else 0.0
    print(f"{'MACRO (5 nhóm)':16} {'':>4} {'':>5} {'':>6} {'':>5} {'':>5} {'':>6} "
          f"{'':>5} {'':>5} {macro_f1:>5.2f} {macro_ex:>6.0%}")

    EVAL_ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    report = {
        "model_dir": model_dir, "num_beams": args.num_beams,
        "per_type": {cat: _bucket_metrics(b) for cat, b in sorted(buckets.items())},
        "subtotal_query": _bucket_metrics(q_tot),
        "subtotal_nonquery": _bucket_metrics(nq_tot),
        "overall_micro": _bucket_metrics(all_tot),
        "macro_f1": macro_f1, "macro_exact": macro_ex,
        "act_confusion": {g: dict(d) for g, d in (act_conf or {}).items()},
    }
    (EVAL_ARTIFACTS_DIR / "eval_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (EVAL_ARTIFACTS_DIR / "eval_mismatches.jsonl").write_text(
        "\n".join(json.dumps(m, ensure_ascii=False) for m in mismatches), encoding="utf-8")
    print(f"\n[eval] báo cáo → {EVAL_ARTIFACTS_DIR / 'eval_report.json'}")
    print(f"[eval] {len(mismatches)} sai E2E → {EVAL_ARTIFACTS_DIR / 'eval_mismatches.jsonl'}")


def _bucket_metrics(b: _Bucket) -> dict:
    p, r, f = _prf(b.inter, b.npred, b.ngold)
    return {
        "n": b.n, "n_query": b.n_query,
        "json_valid": b.json_ok / b.n if b.n else 0.0,
        "strict_ok": b.strict_ok / b.n if b.n else 0.0,
        "act_acc": b.act_ok / b.n if b.n else 0.0,
        "tree_norm": b.tree_norm / b.n_query if b.n_query else None,
        "shape_acc": b.shape_ok / b.n_query if b.n_query else None,
        "precision": p, "recall": r, "f1": f,
        "exact_set": b.e2e_exact / b.n if b.n else 0.0,
    }


def _pct(x) -> str:
    return "    -" if x is None else f"{x:>5.0%}"


def _print_row(name: str, b: _Bucket) -> None:
    m = _bucket_metrics(b)
    print(f"{name:16} {b.n:>4} {m['json_valid']:>5.0%} {m['strict_ok']:>6.0%} {m['act_acc']:>5.0%} "
          f"{_pct(m['tree_norm'])} {_pct(m['shape_acc']):>6} "
          f"{m['precision']:>5.2f} {m['recall']:>5.2f} {m['f1']:>5.2f} {m['exact_set']:>6.0%}")


def main() -> None:
    p = argparse.ArgumentParser(description="Eval 2 mức BARTpho tree-model (cấu trúc + đầu-cuối)")
    p.add_argument("--model-dir", default=str(MODEL_DIR),
                   help="thư mục checkpoint HF (mặc định config.MODEL_DIR; tự lùi về checkpoint-* nếu chưa có model cuối)")
    p.add_argument("--num-beams", type=int, default=4,
                   help="beam search; thử cả --num-beams 1 (greedy) để so độ ổn định JSON cho output cấu trúc")
    p.add_argument("--batch-size", type=int, default=16)
    p.add_argument("--limit", type=int, default=0, help="chỉ chạy N dòng đầu (smoke)")
    sys.exit(evaluate(p.parse_args()))


if __name__ == "__main__":
    main()
