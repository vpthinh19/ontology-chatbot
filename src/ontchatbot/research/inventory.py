"""Build the machine-readable inventory of answerable ontology paths."""

from __future__ import annotations

import json
from pathlib import Path

from rdflib import OWL, RDF, RDFS, SKOS, Graph, Literal, Namespace, URIRef

from ..runtime.sparql import SOURCE_PROJECTION_PREDICATES, load_ontology
from ..settings import ANSWER_INVENTORY_PATH, ONTOLOGY_NS
from .answer_scope import (
    INTERNAL_CLASS_NAMES,
    SOURCE_CLASS_NAMES,
    is_opaque_record,
    rdf_type_names,
)

ACADEMIC = Namespace(ONTOLOGY_NS)

#: Bước cuối hợp lệ của từng quan hệ.
#:
#: Mỗi quan hệ chỉ có các đầu cuối mang ý nghĩa trả lời tương ứng.
RELATION_TERMINALS = {
    # Căn cứ gồm nội dung, trích dẫn và liên kết tới văn bản nguồn.
    "basedOn": ("citationLabel", "officialText", "documentUrl"),
    "hasStep": ("stepText",),
    "hasRequirement": ("requirementText",),
    "hasDeadline": ("deadlineText",),
    "hasOutcome": ("outcomeText",),
    "hasConsequence": ("consequenceText",),
    "hasResolution": ("conditionText",),
    "appliesToCase": ("rdfs:label", "caseText"),
    "nextProcedure": ("rdfs:label", "summaryText"),
    "hasCatalogueEntry": ("rdfs:label", "listedTitle", "downloadUrl"),
    "catalogueEntryForForm": ("rdfs:label",),
}
#: Quan hệ không khai ở trên chỉ dẫn tới tên gọi của node đích.
DEFAULT_TERMINALS = ("rdfs:label",)


def object_properties(graph: Graph) -> tuple[str, ...]:
    """Mọi object property đã khai báo, theo thứ tự ổn định.

    Suy từ lược đồ thay vì liệt kê tay: lược đồ đã khai báo đầy đủ, nên thêm
    một quan hệ mới là danh mục khả năng trả lời tự biết tới nó.
    """

    return tuple(
        sorted(
            _local_name(subject)
            for subject in graph.subjects(RDF.type, OWL.ObjectProperty)
            if isinstance(subject, URIRef) and str(subject).startswith(ONTOLOGY_NS)
        )
    )
#: Khả năng trả lời bị loại, kèm lý do.
EXCLUSIONS = (
    {
        "id": "ArticulationStudyProcedure-requiresForm",
        "anchor": "ArticulationStudyProcedure",
        "answer_kind": "label",
        "path": [],
        "provenance": ["Decision1052Article29"],
        "status": "excluded",
        "reason": "Điều 29 không quy định biểu mẫu cụ thể cho việc học liên thông.",
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
    relations = object_properties(graph)
    for anchor in _semantic_individuals(graph):
        anchor_name = _local_name(anchor)
        # Chỉ nhận thuộc tính của chính dự án (và rdfs:label). Chú thích biên
        # tập bằng từ vựng ngoài không phải dữ liệu trả lời cho người dùng.
        literal_predicates = {
            predicate
            for predicate, value in graph.predicate_objects(anchor)
            if isinstance(value, Literal)
            and predicate != SKOS.altLabel
            and predicate not in SOURCE_PROJECTION_PREDICATES
            and (predicate == RDFS.label or str(predicate).startswith(ONTOLOGY_NS))
        }
        for predicate in sorted(literal_predicates, key=str):
            component = "rdfs:label" if predicate == RDFS.label else _local_name(predicate)
            table_types = {"DocumentTable", "CertificateConversionTable"}
            if component == "officialText" and (
                rdf_type_names(graph, anchor) & table_types
            ):
                entries.append(
                    {
                        "id": f"{anchor_name}-officialText",
                        "anchor": anchor_name,
                        "answer_kind": "literal",
                        "path": ["officialText"],
                        "provenance": _provenance(
                            graph,
                            anchor_name,
                            ["officialText"],
                        ),
                        "status": "excluded",
                        "reason": (
                            "Bản phẳng cũ làm mất vị trí ô rỗng; bảng chỉ trả "
                            "verbatimTableText giữ nguyên cột từ nguồn."
                        ),
                    }
                )
                continue
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
        for property_name in relations:
            for terminal in RELATION_TERMINALS.get(property_name, DEFAULT_TERMINALS):
                _append_supported(
                    graph,
                    entries,
                    anchor_name,
                    [property_name, terminal],
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
    """Mọi neo mà một câu hỏi có thể nhắm tới.

    Node nội bộ của quy trình được hỏi qua quy trình chứa chúng; các phần văn
    bản vẫn là neo trả lời trực tiếp.
    """

    individuals = {
        subject
        for subject in graph.subjects(RDF.type, OWL.NamedIndividual)
        if isinstance(subject, URIRef)
        and str(subject).startswith(ONTOLOGY_NS)
        and not (rdf_type_names(graph, subject) & INTERNAL_CLASS_NAMES)
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
    """Căn cứ của một đường đi: phần văn bản mà chính neo dẫn nguồn tới."""

    subject = ACADEMIC[anchor]
    nodes = set(graph.objects(subject, ACADEMIC.basedOn)) or {subject}
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
