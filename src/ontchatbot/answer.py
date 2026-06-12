"""Answer layer: :class:`Query` → ``Fact[]`` via the schema planner.

The generic path is one idea: an intent names a **target class**; the planner
BFS-finds the shortest class path from the anchor's class to it; the executor
walks that path over individuals. Forward, inverse, and multi-hop all fall out
of the same mechanism — no per-question-type handler. Adding a relation in
Protégé extends what is answerable for free.

Three cases sit *outside* the planner because they are set/▢-arithmetic, not
path-following:
* ``filter_by`` — intersect a fee set along cohort/program (v9's structured
  ``appliesToCohort``/``appliesToProgram`` make the intersection exact).
* ``reason`` — ELIGIBILITY threshold check over v9's structured Condition
  (``cpa 5.2 >= 5.5`` → a real pass/fail verdict, not prose).
* ``COMPARE`` — two anchors set side by side.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from .graph import Graph, Node
from .nlu import ASK_OVERVIEW, GREETING, Query

log = logging.getLogger(__name__)


@dataclass
class Fact:
    """One answer unit ≈ one triple. ``subject``/``predicate`` empty for a
    self-description or a class listing; ``verdict``/``note`` carry reasoning."""
    subject: Node | None
    predicate: str
    objects: list[Node] = field(default_factory=list)
    intent: str = ""
    cls: str = ""                 # listing class
    verdict: bool | None = None   # eligibility outcome (None = undecidable in v8)
    note: str = ""


# intent → (target class to reach, human predicate label). Class IRIs are the
# v9 Vietnamese names — kept here, in render._CLASS_LABEL and label_map.json as
# the only three places a future class rename must touch.
INTENT_TARGET: dict[str, tuple[str, str]] = {
    "ASK_CONDITION":  ("DieuKien", "Điều kiện"),
    "ASK_DOCUMENT":   ("TaiLieuBieuMau", "Biểu mẫu cần nộp"),
    "ASK_OFFICE":     ("PhongBanHanhChinh", "Phòng phụ trách"),
    "ASK_FEE":        ("DinhMucHocPhi", "Học phí"),
    "ASK_PAYMENT":    ("PhuongThucThanhToan", "Phương thức thanh toán"),
    "ASK_OUTPUT":     ("KetQuaDauRa", "Kết quả"),
    "ASK_REGULATION": ("QuyDinh", "Căn cứ quy định"),
    "ASK_PROCEDURE":  ("QuyTrinhHocVu", "Thủ tục phụ trách"),
    "ASK_STEP":       ("QuyTrinhHocVu", "Các bước thực hiện"),
}

# intent → class the anchor most likely belongs to (first-pass resolution bias).
# Procedure is the hub, so relation-from-procedure intents bias to it.
INTENT_ANCHOR: dict[str, str] = {
    "ASK_CONDITION": "QuyTrinhHocVu", "ASK_STEP": "QuyTrinhHocVu",
    "ASK_OUTPUT": "QuyTrinhHocVu", "ASK_REGULATION": "QuyTrinhHocVu",
    "ASK_OVERVIEW": "QuyTrinhHocVu", "ELIGIBILITY": "QuyTrinhHocVu",
    "COMPARE": "QuyTrinhHocVu",
    "ASK_FEE": "DinhMucHocPhi", "ASK_PAYMENT": "PhuongThucThanhToan",
    "ASK_OFFICE": "PhongBanHanhChinh", "ASK_PROCEDURE": "PhongBanHanhChinh",
    "ASK_DOCUMENT": "TaiLieuBieuMau",
}


def answer(query: Query, graph: Graph) -> list[Fact]:
    """Plan + execute a :class:`Query`. Empty list ⇒ greeting/out-of-domain
    (the renderer decides the wording)."""
    if query.intent == GREETING or not query.entities:
        return []

    ent = query.entities[0]
    anc = graph.anchor(ent.surface, ent.tag,
                        prefer_cls=INTENT_ANCHOR.get(query.intent, ""))

    if query.is_listing or anc.class_won:
        cls = anc.cls or graph.class_of_tag(ent.tag)
        nodes = graph.instances(cls)
        return [Fact(subject=None, predicate="", objects=nodes,
                     intent=query.intent, cls=cls)] if nodes else []

    if not anc.nodes:
        return []                       # → out-of-domain

    anchors = anc.nodes
    if query.intent == "ELIGIBILITY":
        return _reason(graph, anchors, query.slots)
    if query.intent == "COMPARE":
        return _compare(graph, anchors)
    if query.intent == "ASK_FEE":
        # Dimensions beat fuzzy: a cohort code and/or a program name select the
        # fee set structurally. Fuzzy can't tell "K67 (Marketing, …)" from
        # another cohort's fee (the long label drags the score to the floor),
        # and it has no notion of *intersection*. With both a cohort and a
        # program, ``filter_by`` returns the single fee at their intersection.
        cohort = query.slots.get("cohort", "")
        program = graph.resolve_program(query.text)
        if cohort or program:
            fees = graph.filter_by(graph.instances("DinhMucHocPhi"),
                                   cohort=cohort, program=program)
            if fees:
                anchors = fees

    target_cls, predicate = INTENT_TARGET.get(query.intent, (None, ""))
    if query.intent == ASK_OVERVIEW or target_cls is None:
        target_cls = anchors[0].cls     # describe the anchor itself

    # Self-target: the answer *is* the anchored set (its own data) — one Fact.
    if anchors[0].cls == target_cls:
        return [Fact(subject=None, predicate=predicate, objects=anchors,
                     intent=query.intent)]

    # Relation-target: walk the planned path from each anchor.
    facts: list[Fact] = []
    for a in anchors:
        steps = graph.plan(a.cls, target_cls)
        if steps is None:
            log.info("[answer] no path %s→%s; overview fallback", a.cls, target_cls)
            facts.append(Fact(subject=None, predicate="", objects=[a],
                              intent=ASK_OVERVIEW))
            continue
        objs = graph.walk(a, steps)
        log.info("[answer] %s --%s--> %d", a.iri, steps, len(objs))
        facts.append(Fact(subject=a, predicate=predicate, objects=objs,
                          intent=query.intent))
    return facts


# Special handlers — set / threshold arithmetic the planner does not express.

# Comparator symbol → predicate. v9 conditions carry structured thresholds.
_COMPARATORS = {
    ">=": lambda a, b: a >= b, ">": lambda a, b: a > b,
    "<=": lambda a, b: a <= b, "<": lambda a, b: a < b,
    "==": lambda a, b: a == b,
}


def _reason(graph: Graph, anchors: list[Node], slots: dict) -> list[Fact]:
    """ELIGIBILITY. v9 conditions are structured (metric/comparator/threshold),
    so a supplied CPA yields a real verdict (``5.2 >= 5.5`` → fail) instead of
    the old prose dump. Qualitative conditions are still listed to self-verify."""
    provided = {"CPA": slots["cpa"]} if slots.get("cpa") is not None else {}
    facts: list[Fact] = []
    for a in anchors:
        steps = graph.plan(a.cls, "DieuKien")
        conds = graph.walk(a, steps) if steps is not None else []
        verdict, note = _evaluate(conds, provided)
        facts.append(Fact(subject=a, predicate="Điều kiện", objects=conds,
                          intent="ELIGIBILITY", verdict=verdict, note=note))
    return facts


def _evaluate(conds: list[Node], provided: dict) -> tuple[bool | None, str]:
    """Check each quantitative condition whose metric the student supplied.

    Returns ``(False, gaps)`` if any fails, ``(True, …)`` if at least one was
    checked and all passed, ``(None, …)`` if nothing could be decided (no
    matching metric) — the renderer words each case."""
    failed: list[str] = []
    checked = 0
    for c in conds:
        if c.data.get("isQuantitative") is not True:
            continue
        metric, comp = c.data.get("metric"), str(c.data.get("comparator", ">="))
        thr, op = c.data.get("thresholdValue"), _COMPARATORS.get(comp)
        if metric not in provided or op is None or thr is None:
            continue
        checked += 1
        if not op(float(provided[metric]), float(thr)):
            failed.append(f"{metric} cần {comp} {_num(thr)} "
                          f"(hiện {_num(provided[metric])})")
    if not checked:
        return None, "Cần đối chiếu các điều kiện sau"
    if failed:
        return False, "Chưa đủ điều kiện — " + "; ".join(failed)
    return True, "Đạt các điều kiện định lượng; hãy xác nhận các điều kiện còn lại"


def _num(v) -> str:
    f = float(v)
    return str(int(f)) if f.is_integer() else str(f)


def _compare(graph: Graph, anchors: list[Node]) -> list[Fact]:
    """COMPARE. Baseline lays the anchored set side by side; multi-entity
    parsing arrives with the trained NLU."""
    return [Fact(subject=None, predicate="So sánh", objects=anchors,
                 intent="COMPARE", note="So sánh các mục")]
