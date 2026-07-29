"""Build the machine-readable inventory of answerable ontology paths."""

from __future__ import annotations

import json
from pathlib import Path

from rdflib import OWL, RDF, RDFS, SKOS, Graph, Literal, Namespace, URIRef

from ..runtime.sparql import load_ontology
from ..settings import ANSWER_INVENTORY_PATH, ONTOLOGY_NS
from .answer_scope import SOURCE_CLASS_NAMES, is_opaque_record, rdf_type_names

ACADEMIC = Namespace(ONTOLOGY_NS)
PROVISION_PROPERTIES = (
    "sourceProvision",
    "instructionProvision",
    "eligibilityProvision",
    "deadlineProvision",
    "resultProvision",
    "paymentInstructionProvision",
)
LABEL_PROPERTIES = (
    "requiresForm",
    "submittedTo",
    "reviewedBy",
    "decidedBy",
    "supportsPaymentMethod",
    "supportsBank",
    "appliesToProgram",
    "appliesToCourseCategory",
    "appliesToEducationLevel",
    "appliesToCertificate",
    "mapsToCompetencyLevel",
    "grantsCourseExemption",
    "belongsToDisciplineGroup",
)
EXCLUSIONS = (
    {
        "id": "ClassAbsenceRequestProcedure-resultProvision",
        "anchor": "ClassAbsenceRequestProcedure",
        "answer_kind": "literal",
        "path": [],
        "provenance": ["Decision1052Article17Clause01PointB"],
        "status": "excluded",
        "reason": "Provision mô tả việc xem xét, không bảo đảm một kết quả.",
    },
    {
        "id": "SickLeaveProcedure-submittedTo",
        "anchor": "SickLeaveProcedure",
        "answer_kind": "label",
        "path": [],
        "provenance": ["Decision1052Article30"],
        "status": "excluded",
        "reason": "Hai nhánh nghỉ ốm không có một đơn vị nhận hồ sơ chung rõ ràng.",
    },
    {
        "id": "ArticulationStudyProcedure-requiresForm",
        "anchor": "ArticulationStudyProcedure",
        "answer_kind": "label",
        "path": [],
        "provenance": ["Decision1052Article29"],
        "status": "excluded",
        "reason": "Điều 29 không quy định biểu mẫu cụ thể.",
    },
)


def resolve_answer_path(
    graph: Graph,
    anchor: str,
    path: list[str],
) -> list[Literal]:
    """Follow a declared path and require literal terminal values."""

    nodes: set[object] = {ACADEMIC[anchor]}
    for index, component in enumerate(path):
        predicate = RDFS.label if component == "rdfs:label" else ACADEMIC[component]
        nodes = {
            value
            for node in nodes
            if isinstance(node, URIRef)
            for value in graph.objects(node, predicate)
        }
        if not nodes:
            return []
        if index < len(path) - 1 and any(
            not isinstance(node, URIRef) for node in nodes
        ):
            return []
    if any(not isinstance(node, Literal) for node in nodes):
        return []
    return sorted(nodes, key=lambda value: (str(value), value.language or ""))


def build_answer_inventory(graph: Graph) -> dict[str, object]:
    """Derive supported answer paths and append explicit exclusions."""

    entries: list[dict[str, object]] = []
    for anchor in _semantic_individuals(graph):
        anchor_name = _local_name(anchor)
        literal_predicates = {
            predicate
            for predicate, value in graph.predicate_objects(anchor)
            if isinstance(value, Literal) and predicate != SKOS.altLabel
        }
        for predicate in sorted(literal_predicates, key=str):
            component = "rdfs:label" if predicate == RDFS.label else _local_name(predicate)
            if predicate == RDFS.label and is_opaque_record(graph, anchor):
                entries.append(
                    {
                        "id": f"{anchor_name}-rdfs-label",
                        "anchor": anchor_name,
                        "answer_kind": "label",
                        "path": ["rdfs:label"],
                        "provenance": _provenance(
                            graph,
                            anchor_name,
                            ["rdfs:label"],
                        ),
                        "status": "excluded",
                        "reason": (
                            "Nhãn của bản ghi kỹ thuật nội bộ; truy vấn bằng "
                            "điều kiện nghiệp vụ thay vì IRI của bản ghi."
                        ),
                    }
                )
                continue
            _append_supported(graph, entries, anchor_name, [component])
        for property_name in PROVISION_PROPERTIES:
            _append_supported(
                graph,
                entries,
                anchor_name,
                [property_name, "officialText"],
            )
        for property_name in LABEL_PROPERTIES:
            _append_supported(
                graph,
                entries,
                anchor_name,
                [property_name, "rdfs:label"],
            )

    entries.extend(dict(entry) for entry in EXCLUSIONS)
    entries.sort(key=lambda item: str(item["id"]))
    return {
        "schema_version": 1,
        "ontology_namespace": ONTOLOGY_NS,
        "entries": entries,
    }


def write_answer_inventory(graph: Graph, path: Path = ANSWER_INVENTORY_PATH) -> None:
    """Write the deterministic inventory JSON."""

    Path(path).write_text(
        json.dumps(build_answer_inventory(graph), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _semantic_individuals(graph: Graph) -> list[URIRef]:
    individuals = {
        subject
        for subject in graph.subjects(RDF.type, OWL.NamedIndividual)
        if isinstance(subject, URIRef)
        and str(subject).startswith(ONTOLOGY_NS)
        and not (rdf_type_names(graph, subject) & SOURCE_CLASS_NAMES)
    }
    return sorted(individuals, key=str)


def _append_supported(
    graph: Graph,
    entries: list[dict[str, object]],
    anchor: str,
    path: list[str],
) -> None:
    values = resolve_answer_path(graph, anchor, path)
    if not values:
        return
    entries.append(
        {
            "id": "-".join([anchor, *[part.replace(":", "-") for part in path]]),
            "anchor": anchor,
            "answer_kind": "label" if path[-1] == "rdfs:label" else "literal",
            "path": path,
            "provenance": _provenance(graph, anchor, path),
            "status": "supported",
        }
    )


def _provenance(graph: Graph, anchor: str, path: list[str]) -> list[str]:
    subject = ACADEMIC[anchor]
    first = path[0]
    if first in PROVISION_PROPERTIES:
        nodes = set(graph.objects(subject, ACADEMIC[first]))
    else:
        nodes = set(graph.objects(subject, ACADEMIC.sourceProvision))
        if not nodes:
            nodes = set(graph.objects(subject, ACADEMIC.sourceDocument))
        if not nodes:
            nodes = {subject}
    return sorted(_local_name(node) for node in nodes if isinstance(node, URIRef))


def _local_name(node: URIRef) -> str:
    value = str(node)
    if not value.startswith(ONTOLOGY_NS):
        raise ValueError(f"resource is outside the ontology namespace: {value}")
    return value[len(ONTOLOGY_NS) :]


def main() -> None:
    write_answer_inventory(load_ontology())


if __name__ == "__main__":
    main()
