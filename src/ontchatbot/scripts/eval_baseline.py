"""Edge-correct evaluation of the query-graph pipeline.

Runs ``resources/e2e/cases.jsonl`` through ``understand → answer`` and checks
that the set of **result node IRIs** equals the expected set — i.e. the system
reached the right nodes by the right edges, not just resolved an anchor. This
replaces the old anchor-only parity check (the fuzzy matcher it tested is gone).

A case is ``{"text", "expected": [iri…], "category"}``; an empty ``expected``
means greeting / out-of-domain (the pipeline must return no result nodes).

Usage: ``uv run --extra inference python -m ontchatbot.scripts.eval_baseline``
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict

from ..answer import answer
from ..config import RESOURCES
from ..graph import Graph
from ..nlu import understand

CASES = RESOURCES / "e2e" / "cases.jsonl"


def _result_iris(facts) -> set[str]:
    return {n.iri for f in facts for n in f.objects}


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):       # Windows console defaults to cp1252
        sys.stdout.reconfigure(encoding="utf-8")
    g = Graph()
    lex = g.lexicon()
    rows = [json.loads(l) for l in CASES.read_text(encoding="utf-8").splitlines()
            if l.strip()]
    by_cat: dict[str, list[bool]] = defaultdict(list)
    misses: list[str] = []

    for r in rows:
        exp = set(r["expected"])
        got = _result_iris(answer(understand(r["text"], lex), g))
        ok = got == exp
        by_cat[r["category"]].append(ok)
        if not ok:
            misses.append(f"  [{r['category']}] {r['text']!r}\n"
                          f"      exp={exp or '∅'}\n      got={got or '∅'}")

    print(f"{'category':18} {'acc':>6}  n")
    tot_ok = tot_n = 0
    for cat in sorted(by_cat):
        v = by_cat[cat]
        tot_ok += sum(v); tot_n += len(v)
        print(f"{cat:18} {sum(v) / len(v):>6.0%}  {len(v)}")
    print(f"{'TOTAL':18} {tot_ok / tot_n:>6.0%}  {tot_n}")
    if misses:
        print("\nMisses:")
        print("\n".join(misses))


if __name__ == "__main__":
    main()
