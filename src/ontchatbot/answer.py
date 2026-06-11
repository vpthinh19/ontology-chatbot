"""Answer layer: :class:`Query` → ``Fact[]`` via the schema planner.

The generic path is one idea: an intent names a **target class**; the planner
BFS-finds the shortest class path from the anchor's class to it; the executor
walks that path over individuals. Forward, inverse, and multi-hop all fall out
of the same mechanism — no per-question-type handler. Adding a relation in
Protégé extends what is answerable for free.

Three cases sit *outside* the planner because they are set/▢-arithmetic, not
path-following:
* ``filter_by`` — intersect a fee set along cohort/program (full power needs
  the v9 remodel; v8 narrows by substring).
* ``reason`` — ELIGIBILITY threshold check (needs v9's structured Condition;
  v8 can only enumerate the conditions to verify).
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


# intent → (target class to reach, human predicate label).
INTENT_TARGET: dict[str, tuple[str, str]] = {
    "ASK_CONDITION":  ("Condition", "Điều kiện"),
    "ASK_DOCUMENT":   ("Document", "Biểu mẫu cần nộp"),
    "ASK_OFFICE":     ("AdministrativeOffice", "Phòng phụ trách"),
    "ASK_FEE":        ("FeeCategory", "Học phí"),
    "ASK_PAYMENT":    ("PaymentMethod", "Phương thức thanh toán"),
    "ASK_OUTPUT":     ("OutputResult", "Kết quả"),
    "ASK_REGULATION": ("Regulation", "Căn cứ quy định"),
    "ASK_PROCEDURE":  ("AcademicProcedure", "Thủ tục phụ trách"),
    "ASK_STEP":       ("AcademicProcedure", "Các bước thực hiện"),
}

# intent → class the anchor most likely belongs to (first-pass resolution bias).
# Procedure is the hub, so relation-from-procedure intents bias to it.
INTENT_ANCHOR: dict[str, str] = {
    "ASK_CONDITION": "AcademicProcedure", "ASK_STEP": "AcademicProcedure",
    "ASK_OUTPUT": "AcademicProcedure", "ASK_REGULATION": "AcademicProcedure",
    "ASK_OVERVIEW": "AcademicProcedure", "ELIGIBILITY": "AcademicProcedure",
    "COMPARE": "AcademicProcedure",
    "ASK_FEE": "FeeCategory", "ASK_PAYMENT": "PaymentMethod",
    "ASK_OFFICE": "AdministrativeOffice", "ASK_PROCEDURE": "AdministrativeOffice",
    "ASK_DOCUMENT": "Document",
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
        # A cohort code is the only reliable signal in v8 — fuzzy can't tell
        # "K67 (Marketing, …)" from another cohort's fee (its long label drags
        # the score down to the noise floor). So with a cohort we take the
        # whole cohort *set* from the class, not the fuzzy-anchored subset.
        # The v9 remodel adds structured Cohort/Program for true set GIAO.
        cohort = query.slots.get("cohort", "")
        if cohort:
            cohort_fees = graph.filter_by(graph.instances("FeeCategory"),
                                          cohort=cohort)
            if cohort_fees:
                anchors = cohort_fees

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

def _reason(graph: Graph, anchors: list[Node], slots: dict) -> list[Fact]:
    """ELIGIBILITY. v8 Conditions are prose-only (no metric/threshold), so we
    enumerate them for the student to verify; the v9 remodel turns this into a
    real ``cpa >= threshold`` verdict."""
    facts: list[Fact] = []
    cpa = slots.get("cpa")
    note = (f"Với CPA {cpa}, hãy đối chiếu các điều kiện sau"
            if cpa is not None else "Cần đối chiếu các điều kiện sau")
    for a in anchors:
        steps = graph.plan(a.cls, "Condition")
        conds = graph.walk(a, steps) if steps is not None else []
        facts.append(Fact(subject=a, predicate="Điều kiện", objects=conds,
                          intent="ELIGIBILITY", verdict=None, note=note))
    return facts


def _compare(graph: Graph, anchors: list[Node]) -> list[Fact]:
    """COMPARE. Baseline lays the anchored set side by side; multi-entity
    parsing arrives with the trained NLU."""
    return [Fact(subject=None, predicate="So sánh", objects=anchors,
                 intent="COMPARE", note="So sánh các mục")]
