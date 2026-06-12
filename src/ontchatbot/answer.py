"""Answer layer: :class:`Query` → ``Fact[]`` — execute the query graph.

The whole layer is three fixed mechanisms (docs/redesign/03), no
per-question-type handler:

* **DNF builder** — order the constraints into *decision groups* with the
  same-class-substitution rule: a constraint of a class already present in
  the current group *replaces* it and opens a new group that inherits
  everything that preceded the replaced one. Two same-dimension values can
  never intersect to anything, so substitution is the only meaningful
  reading; separator words need no special handling.
* **shadow projection** — within a group, every constraint casts its
  *shadow* onto the subject class: ``walk(c, plan(cls(c) → subject))``.
  The planner supplies direction and hop count from the schema; a constraint
  whose class is the subject's own shadows to itself (empty plan), which is
  how self-description falls out of the same formula.
* **set algebra** — intersect the shadows inside a group (faceted search),
  union the groups (one Fact block each). Empty intersection degrades
  honestly: a note plus each dimension's own set, never a guess.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from .graph import Graph, Node
from .nlu import GREETING, Query

log = logging.getLogger(__name__)


@dataclass
class Fact:
    """One reply block. ``cls`` set ⇒ class listing; otherwise ``objects``
    are the nodes a decision group resolved to, ``heading`` names the group."""
    objects: list[Node] = field(default_factory=list)
    heading: str = ""
    cls: str = ""
    note: str = ""


def answer(query: Query, graph: Graph) -> list[Fact]:
    """Execute a :class:`Query`. Empty list ⇒ greeting/out-of-domain
    (the renderer decides the wording)."""
    if query.act == GREETING:
        return []

    constraints = [n for n in (graph.node(m.iri) for m in query.constraints)
                   if n is not None]
    subject = query.subject_cls or (constraints[0].cls if constraints else "")
    if not subject:
        return []                                   # → out-of-domain

    if not constraints:
        if not query.subject_listable:
            return []                               # bare interrogative → OOD
        nodes = graph.instances(subject)
        return [Fact(objects=nodes, cls=subject)] if nodes else []

    facts: list[Fact] = []
    groups = build_groups(constraints)
    plain = len(groups) == 1 and len(groups[0]) == 1 \
        and groups[0][0].cls == subject             # pure self-description
    for group in groups:
        facts.extend(_execute(graph, subject, group, plain=plain))
    log.info("[answer] subject=%s groups=%s facts=%d",
             subject, [[c.iri for c in g] for g in groups], len(facts))
    return facts


def build_groups(constraints: list[Node]) -> list[list[Node]]:
    """Same-class-substitution DNF. ``[k65, cntt, k67]`` → ``[[k65, cntt],
    [k67]]``; ``[cntt, k65, k67]`` → ``[[cntt, k65], [cntt, k67]]`` — the new
    value inherits what preceded the one it replaces."""
    groups: list[list[Node]] = [[]]
    cur = groups[0]
    for c in constraints:
        idx = next((i for i in range(len(cur) - 1, -1, -1)
                    if cur[i].cls == c.cls), None)
        if idx is None:
            cur.append(c)
        else:
            cur = cur[:idx] + [c]
            groups.append(cur)
    return groups


def _execute(graph: Graph, subject: str, group: list[Node],
             *, plain: bool) -> list[Fact]:
    """One decision group → one block (or honest degradation blocks)."""
    shadows: list[tuple[Node, list[Node]]] = []
    dropped: list[Node] = []
    for c in group:
        steps = graph.plan(c.cls, subject)
        if steps is None:
            dropped.append(c)
            continue
        shadows.append((c, graph.walk(c, steps)))
    note = ("Không xét: " + ", ".join(f"«{c.label}»" for c in dropped) +
            " (không liên quan tới chủ đề hỏi)." if dropped else "")
    if not shadows:
        return [Fact(note=note or "Chưa có dữ liệu phù hợp.")]

    heading = "" if plain else _heading(graph, subject, group)
    inter = _intersect([s for _, s in shadows])
    if inter:
        return [Fact(objects=inter, heading=heading, note=note)]
    if all(not s for _, s in shadows):
        return [Fact(heading=heading, note=(note + " " if note else "") +
                     "Chưa có dữ liệu cho mục này.")]
    # Honest degradation: no node satisfies every dimension at once — say so
    # and show each dimension's own set instead of guessing.
    facts = [Fact(heading=heading, note=(note + " " if note else "") +
                  "Không có mục nào khớp đồng thời các tiêu chí; "
                  "dữ liệu theo từng tiêu chí:")]
    for c, shadow in shadows:
        if shadow:
            facts.append(Fact(objects=shadow,
                              heading=f"Theo «{c.label}»"))
    return facts


def _heading(graph: Graph, subject: str, group: list[Node]) -> str:
    crit = " × ".join(c.label for c in group)
    return f"{graph.class_label(subject)} — {crit}"


def _intersect(shadows: list[list[Node]]) -> list[Node]:
    """Ordered intersection: keep the first shadow's order."""
    if not shadows:
        return []
    keep = set.intersection(*({n.iri for n in s} for s in shadows))
    return [n for n in shadows[0] if n.iri in keep]
