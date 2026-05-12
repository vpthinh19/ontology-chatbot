"""End-to-end precision/recall/F1 benchmark for the fuzzy matcher.

Sweeps :data:`FUZZY_MIN_SCORE` across a range; reports macro-averaged
precision, recall, and F1 over the hand-curated test set. NER outputs are
pre-computed once per case so the sweep itself only re-runs the rapidfuzz
call.

Per-case scoring on URI sets:

* TP = ``|pred ∩ expected|``
* FP = ``|pred - expected|``
* FN = ``|expected - pred|``
* ``pred=expected=∅`` is treated as a perfect rejection (P=R=F1=1) —
  covers negative + class-listing cases where class-win produces ``pred=[]``.

Outputs (under ``artifacts/fuzzy_bench/``):

* ``curve.png``  — precision, recall, F1 vs τ
* ``report.md``  — summary table

Usage::

    uv run python -m ontchatbot.scripts.bench_fuzzy
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless: don't open a Tk window
import matplotlib.pyplot as plt

from ..config import ARTIFACTS_DIR, FUZZY_MIN_SCORE, RESOURCES
from ..ner_model import Entity
from ..pipeline import Pipeline, PipelineContext

CASES_PATH = RESOURCES / "e2e" / "cases.jsonl"
OUT_DIR = ARTIFACTS_DIR / "fuzzy_bench"
PLOT_PATH = OUT_DIR / "curve.png"
REPORT_PATH = OUT_DIR / "report.md"

TAU_SWEEP: list[int] = list(range(50, 100, 2))


def _load_cases(path: Path) -> list[dict]:
    out: list[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                out.append(json.loads(line))
    return out


def _precompute_ner(pipeline: Pipeline,
                    cases: list[dict]) -> list[list[Entity]]:
    """Run preprocess + NER once per case so the τ-sweep can re-use spans."""
    cache: list[list[Entity]] = []
    for case in cases:
        ctx = PipelineContext(query=case["text"])
        ctx = pipeline._preprocess(ctx)
        ctx = pipeline._ner(ctx)
        cache.append(list(ctx.spans))
    return cache


def _score_case(pred: set[str], exp: set[str]) -> tuple[float, float, float]:
    """Per-case (precision, recall, F1) on URI sets.

    Convention: empty pred AND empty exp is a perfect rejection — score 1.0
    across the board. Any other ``zero_division`` situation scores 0.0,
    matching :func:`sklearn.metrics.precision_recall_fscore_support`.
    """
    if not pred and not exp:
        return 1.0, 1.0, 1.0
    tp = len(pred & exp)
    fp = len(pred - exp)
    fn = len(exp - pred)
    p = tp / (tp + fp) if (tp + fp) else 0.0
    r = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * p * r / (p + r) if (p + r) else 0.0
    return p, r, f1


def _metrics(pipeline: Pipeline,
             ner_cache: list[list[Entity]],
             cases: list[dict],
             tau: float) -> tuple[float, float, float]:
    """Macro-averaged (precision, recall, F1) at the given τ."""
    pipeline.onto._min_score = tau
    p_sum = r_sum = f1_sum = 0.0
    for case, spans in zip(cases, ner_cache):
        pred: set[str] = set()
        for span in spans:
            m = pipeline.onto.resolve(span.surface, span.tag)
            if not m.class_won:
                pred.update(m.individuals)
        p, r, f1 = _score_case(pred, set(case["expected_iris"]))
        p_sum += p
        r_sum += r
        f1_sum += f1
    n = len(cases)
    return p_sum / n, r_sum / n, f1_sum / n


def _plot(scores: dict[int, tuple[float, float, float]], path: Path) -> None:
    taus = sorted(scores)
    best = max(taus, key=lambda t: scores[t][2])  # best by F1
    cur = int(FUZZY_MIN_SCORE)

    precision = [scores[t][0] for t in taus]
    recall = [scores[t][1] for t in taus]
    f1 = [scores[t][2] for t in taus]

    plt.figure(figsize=(9, 5))
    plt.plot(taus, precision, marker="o", label="Precision (macro)", linewidth=1.5)
    plt.plot(taus, recall, marker="s", label="Recall (macro)", linewidth=1.5)
    plt.plot(taus, f1, marker="D", label="F1 (macro)", linewidth=2.5, color="black")
    plt.axvline(x=cur, linestyle="--", color="grey", alpha=0.5,
                label=f"Current τ={cur}")
    plt.axvline(x=best, linestyle=":", color="red", alpha=0.7,
                label=f"Best τ={best} (F1={scores[best][2]:.3f})")
    plt.xlabel("FUZZY_MIN_SCORE (τ)")
    plt.ylabel("Score")
    plt.title("Fuzzy matcher precision/recall/F1 vs threshold (end-to-end)")
    plt.legend(loc="lower center", fontsize=9, ncol=2)
    plt.ylim(0, 1.05)
    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(path, dpi=120)
    plt.close()


def _report(scores: dict[int, tuple[float, float, float]],
            n_cases: int,
            n_expected: int,
            path: Path) -> None:
    taus = sorted(scores)
    best = max(taus, key=lambda t: scores[t][2])  # best by F1
    cur = int(FUZZY_MIN_SCORE)
    step = taus[1] - taus[0]

    lines = [
        "# Fuzzy matcher benchmark (precision / recall / F1)",
        "",
        f"- Cases: **{n_cases}**",
        f"- Total expected URIs: **{n_expected}**",
        f"- τ sweep: **{taus[0]} → {taus[-1]} step {step}**",
        "- Metric: macro-averaged P/R/F1 on URI sets per case",
        "",
        "## Headline",
        "",
        "| | τ | Precision | Recall | F1 |",
        "|---|---|---|---|---|",
    ]
    for label, t in (("Current", cur), ("Best (by F1)", best)):
        if t in scores:
            p, r, f1 = scores[t]
            lines.append(f"| **{label}** | {t} | {p:.3f} | {r:.3f} | {f1:.3f} |")

    if cur in scores:
        delta = scores[best][2] - scores[cur][2]
        lines.append("")
        lines.append(f"Δ F1 by retuning τ={cur} → τ={best}: **{delta:+.3f}**")

    lines += [
        "",
        "## Sweep",
        "",
        "| τ | Precision | Recall | F1 |",
        "|---|---|---|---|",
    ]
    for t in taus:
        p, r, f1 = scores[t]
        lines.append(f"| {t} | {p:.3f} | {r:.3f} | {f1:.3f} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    if not CASES_PATH.exists():
        print(f"[bench] {CASES_PATH} not found", file=sys.stderr)
        sys.exit(1)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cases = _load_cases(CASES_PATH)
    n_expected = sum(len(c["expected_iris"]) for c in cases)
    print(f"[bench] loaded {len(cases)} cases ({n_expected} expected URIs)")
    print("[bench] loading pipeline (warming ONNX session)…")
    pipeline = Pipeline.get()
    print("[bench] pre-computing NER per case…")
    ner_cache = _precompute_ner(pipeline, cases)
    hit = sum(1 for spans in ner_cache if spans)
    print(f"[bench] NER hit on {hit}/{len(cases)} cases ({hit / len(cases):.1%})")

    print(f"[bench] sweeping τ ∈ {TAU_SWEEP[0]}..{TAU_SWEEP[-1]} step {TAU_SWEEP[1] - TAU_SWEEP[0]}")
    scores = {tau: _metrics(pipeline, ner_cache, cases, float(tau))
              for tau in TAU_SWEEP}

    _plot(scores, PLOT_PATH)
    _report(scores, len(cases), n_expected, REPORT_PATH)
    print(f"[bench] wrote plot   → {PLOT_PATH}")
    print(f"[bench] wrote report → {REPORT_PATH}")

    best = max(scores, key=lambda t: scores[t][2])
    cur = int(FUZZY_MIN_SCORE)
    bp, br, bf = scores[best]
    print()
    print(f"  Best τ={best} (by F1) → P={bp:.3f} R={br:.3f} F1={bf:.3f}")
    if cur in scores:
        cp, cr, cf = scores[cur]
        print(f"  Cur  τ={cur}             → P={cp:.3f} R={cr:.3f} F1={cf:.3f}  "
              f"Δ F1 = {bf - cf:+.3f}")


if __name__ == "__main__":
    main()
