"""Validate catalogue coverage against the canonical answer inventory."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Mapping

from rdflib import OWL, RDF, Graph, Namespace, URIRef

from .graph import validate_select
from ..settings import ONTOLOGY_NS
from .answer_scope import is_opaque_record, rdf_type_names
from ..catalogue import CoverageSelector, QuerySpec

ACADEMIC = Namespace(ONTOLOGY_NS)


class CatalogueValidationError(ValueError):
    """The query catalogue does not faithfully cover the answer inventory."""


def validate_catalogue(
    graph: Graph,
    inventory: Mapping[str, object],
    catalogue: Mapping[str, QuerySpec],
) -> dict[str, object]:
    """Validate selectors, model-facing slots, and complete supported coverage."""

    raw_entries = inventory.get("entries")
    if not isinstance(raw_entries, list):
        raise CatalogueValidationError("inventory entries must be a list")
    supported = [
        entry
        for entry in raw_entries
        if isinstance(entry, dict) and entry.get("status") == "supported"
    ]
    if not supported:
        raise CatalogueValidationError("inventory has no supported entries")

    coverage: dict[str, list[str]] = defaultdict(list)
    domains: Counter[str] = Counter()
    for query_id, spec in catalogue.items():
        domains[spec.domain] += 1
        if spec.domain == "out-of-domain":
            if spec.coverage:
                raise CatalogueValidationError(
                    f"{query_id}: rejection query cannot declare coverage"
                )
            continue
        if not spec.coverage:
            raise CatalogueValidationError(f"{query_id}: declares no coverage")

        _validate_template(spec)
        _validate_slots(graph, query_id, spec)
        for selector_index, selector in enumerate(spec.coverage, 1):
            _validate_selector(graph, query_id, selector_index, selector)
            for path in selector.paths:
                matched = [
                    entry
                    for entry in supported
                    if _selector_matches(graph, selector, path, entry)
                ]
                if not matched:
                    raise CatalogueValidationError(
                        f"{query_id}: coverage selector {selector_index} path "
                        f"{'/'.join(path)} matches no supported entry"
                    )
                for entry in matched:
                    coverage[str(entry["id"])].append(query_id)

    uncovered = sorted(
        str(entry["id"])
        for entry in supported
        if str(entry["id"]) not in coverage
    )
    if uncovered:
        raise CatalogueValidationError(
            f"uncovered supported inventory entries: {uncovered[:10]}"
        )

    overlaps = {
        entry_id: sorted(set(query_ids))
        for entry_id, query_ids in sorted(coverage.items())
        if len(set(query_ids)) > 1
    }
    return {
        "supported_entries": len(supported),
        "covered_entries": len(coverage),
        "uncovered_entries": [],
        "overlapping_entries": overlaps,
        "families": len(catalogue),
        "domains": dict(sorted(domains.items())),
    }


def _validate_template(spec: QuerySpec) -> None:
    target = spec.target_template
    for name, slot in spec.slots.items():
        value = slot.values[0] if slot.kind == "iri" else "0"
        target = target.replace(f"${{{name}}}", value)
    try:
        validate_select(target)
    except ValueError as exc:
        raise CatalogueValidationError(
            f"{spec.query_id}: invalid target template: {exc}"
        ) from exc


def _validate_slots(graph: Graph, query_id: str, spec: QuerySpec) -> None:
    for slot_name, slot in spec.slots.items():
        if slot.kind != "iri":
            continue
        for value in slot.values:
            node = ACADEMIC[value[1:]]
            if not any(graph.triples((node, None, None))):
                raise CatalogueValidationError(
                    f"{query_id}.{slot_name}: {value} does not exist in ontology"
                )
            if is_opaque_record(graph, node):
                raise CatalogueValidationError(
                    f"{query_id}.{slot_name}: {value} is an opaque record IRI"
                )


def _validate_selector(
    graph: Graph,
    query_id: str,
    selector_index: int,
    selector: CoverageSelector,
) -> None:
    for class_name in selector.anchor_classes:
        class_node = ACADEMIC[class_name]
        if (class_node, RDF.type, OWL.Class) not in graph:
            raise CatalogueValidationError(
                f"{query_id}: selector {selector_index} class {class_name} does not exist"
            )
    accepted_types = set(selector.anchor_classes)
    for anchor_name in selector.anchors:
        anchor = ACADEMIC[anchor_name]
        if not any(graph.triples((anchor, None, None))):
            raise CatalogueValidationError(
                f"{query_id}: selector {selector_index} anchor {anchor_name} does not exist"
            )
        if not (rdf_type_names(graph, anchor) & accepted_types):
            raise CatalogueValidationError(
                f"{query_id}: selector {selector_index} anchor {anchor_name} "
                f"does not belong to {sorted(accepted_types)}"
            )


def _selector_matches(
    graph: Graph,
    selector: CoverageSelector,
    path: tuple[str, ...],
    entry: Mapping[str, object],
) -> bool:
    anchor_name = entry.get("anchor")
    raw_path = entry.get("path")
    if not isinstance(anchor_name, str) or not isinstance(raw_path, list):
        return False
    if tuple(raw_path) != path:
        return False
    if selector.anchors and anchor_name not in selector.anchors:
        return False
    return bool(
        rdf_type_names(graph, ACADEMIC[anchor_name]) & set(selector.anchor_classes)
    )
