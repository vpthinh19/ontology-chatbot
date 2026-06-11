"""Entity-resolution parity check for the new :class:`Graph` anchor.

Runs ``resources/e2e/cases.jsonl`` through ``Graph.anchor`` and reports
accuracy by category. Two columns:

* ``tagged``  — anchor with the case's gold NER tag (isolates fuzzy quality,
  the old ``resolve(span, tag)`` contract).
* ``live``    — anchor the nlu-stripped surface with no tag (cross-tag, the
  rule-based baseline's real behaviour).

Usage: ``uv run --extra inference python -m ontchatbot.scripts.eval_baseline``
"""

from __future__ import annotations

import json
from collections import defaultdict

from ..config import RESOURCES
from ..graph import Graph
from ..nlu import _anchor_surface
from ..text import clean

CASES = RESOURCES / "e2e" / "cases.jsonl"


def _ok(anc, exp_iris: set[str], exp_class_won: bool) -> bool:
    if exp_class_won:
        return anc.class_won
    if not exp_iris:                       # negative: expect nothing
        return not anc.nodes and not anc.class_won
    return {n.iri for n in anc.nodes} == exp_iris


def main() -> None:
    g = Graph()
    rows = [json.loads(l) for l in CASES.read_text(encoding="utf-8").splitlines() if l.strip()]
    by_cat: dict[str, list[bool]] = defaultdict(list)
    by_cat_live: dict[str, list[bool]] = defaultdict(list)
    misses: list[str] = []

    for r in rows:
        exp = set(r["expected_iris"])
        cw = r["expected_class_won"]
        surface = _anchor_surface(clean(r["text"]))

        tagged = g.anchor(surface, r["tag"]) if r["tag"] else g.anchor(surface)
        live = g.anchor(surface)
        ok_t, ok_l = _ok(tagged, exp, cw), _ok(live, exp, cw)
        by_cat[r["category"]].append(ok_t)
        by_cat_live[r["category"]].append(ok_l)
        if not ok_t:
            got = "CLASS" if tagged.class_won else [n.iri for n in tagged.nodes]
            misses.append(f"  [{r['category']}] {r['text'][:48]!r}\n"
                          f"      surface={surface!r} exp={exp or ('CLASS' if cw else '∅')} got={got}")

    print(f"{'category':18} {'tagged':>8} {'live':>8}  n")
    tot_t = tot_l = tot_n = 0
    for cat in sorted(by_cat):
        t, lv = by_cat[cat], by_cat_live[cat]
        n = len(t)
        tot_t += sum(t); tot_l += sum(lv); tot_n += n
        print(f"{cat:18} {sum(t)/n:>7.0%} {sum(lv)/n:>7.0%}  {n}")
    print(f"{'TOTAL':18} {tot_t/tot_n:>7.0%} {tot_l/tot_n:>7.0%}  {tot_n}")
    if misses:
        print("\nTagged misses:")
        print("\n".join(misses))


if __name__ == "__main__":
    main()
