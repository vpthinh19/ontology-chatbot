"""Eval đúng-cạnh (DESIGN.md §7): cây JSON vàng → duyệt → so TẬP NODE với ground-truth.

    uv run --extra inference python -m ontchatbot.scripts.eval_traversal

Mỗi dòng `resources/e2e/cases.jsonl`::

    {"text", "tree": {act, entities}, "category",
     "expected": [iri...],                # tập node kỳ vọng (rỗng với greeting/ood/vague/data-leaf)
     "expected_value_contains": "..."}    # (tuỳ chọn) chuỗi con phải có trong giá trị lá data

Chấm: chạy `Ontology.traverse(parse(tree))`, so `{node.iri}` với `expected`; nếu có
`expected_value_contains` thì kiểm thêm giá trị lá. Vì cây vàng + ontology là **xác định**,
kỳ vọng 100% — đây là lưới an toàn cho thuật toán duyệt khi model ViT5 chưa về.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict

from ..config import RESOURCES
from ..ontology import Ontology
from ..tree import parse

CASES = RESOURCES / "e2e" / "cases.jsonl"


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):       # Windows console mặc định cp1252
        sys.stdout.reconfigure(encoding="utf-8")
    ont = Ontology()
    rows = [json.loads(l) for l in CASES.read_text(encoding="utf-8").splitlines() if l.strip()]
    by_cat: dict[str, list[bool]] = defaultdict(list)
    misses: list[str] = []

    for r in rows:
        kq = ont.traverse(parse(r["tree"]))
        got = {n.iri for n in kq.nodes}
        exp = set(r.get("expected", []))
        ok = got == exp and kq.vague == bool(r.get("expected_vague", False))
        for ev in r.get("expected_values", []):
            joined = " ".join(str(v) for gv in kq.values if gv.prop == ev["prop"] for v in gv.values)
            ok = ok and (ev["contains"] in joined)
        by_cat[r["category"]].append(ok)
        if not ok:
            misses.append(f"  [{r['category']}] {r['text']!r}\n"
                          f"      exp={exp or '∅'} vals={r.get('expected_values')}\n"
                          f"      got={got or '∅'} values={[gv.prop for gv in kq.values]} "
                          f"vague={kq.vague} misses={kq.misses}")

    print(f"{'category':16} {'acc':>6}  n")
    tot_ok = tot_n = 0
    for cat in sorted(by_cat):
        v = by_cat[cat]
        tot_ok += sum(v); tot_n += len(v)
        print(f"{cat:16} {sum(v) / len(v):>6.0%}  {len(v)}")
    print(f"{'TOTAL':16} {tot_ok / tot_n:>6.0%}  {tot_n}")
    if misses:
        print("\nMisses:")
        print("\n".join(misses))
    sys.exit(0 if tot_ok == tot_n else 1)


if __name__ == "__main__":
    main()
