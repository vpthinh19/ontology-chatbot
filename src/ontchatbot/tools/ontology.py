"""Build ontology v11 from v10 with an auditable, lossless migration."""

from __future__ import annotations

import json
from pathlib import Path

from rdflib import BNode, Graph, Literal, Namespace, RDF, RDFS
from rdflib.collection import Collection
from rdflib.namespace import OWL, SKOS

ACADEMIC = Namespace("http://www.ntu.edu.vn/ontology/academic#")
ONTOLOGY_IRI = Namespace("http://www.ntu.edu.vn/ontology/").academic

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "resources/ontology/ontology_v10.ttl"
TARGET = ROOT / "resources/ontology/ontology_v11.ttl"
MANIFEST = ROOT / "resources/ontology/ontology_v10_to_v11.json"

FLATTENED_PROPERTIES = (
    (ACADEMIC.hasCondition, ACADEMIC.Condition, ACADEMIC.condition, "điều kiện", "yêu cầu"),
    (ACADEMIC.hasOutcome, ACADEMIC.Outcome, ACADEMIC.outcome, "kết quả", "đầu ra"),
)

# These values describe questions or overly broad words, not alternate names.
REMOVED_ALIASES = (
    (ACADEMIC.AcademicLeaveProcedure, "điều kiện bảo lưu"),
    (ACADEMIC.appliesTuitionRate, "học phí"),
    (ACADEMIC.documentUrl, "tải biểu mẫu"),
    (ACADEMIC.handledBy, "xử lý"),
    (ACADEMIC.hasDocument, "đơn"),
    (ACADEMIC.headName, "phụ trách"),
    (ACADEMIC.location, "ở đâu"),
)


def _local_name(value: object) -> str:
    return str(value).rsplit("#", maxsplit=1)[-1]


def _replace_regulation_domain(graph: Graph) -> None:
    """Remove the retired Condition class from basedOnRegulation's union."""

    domains = list(graph.objects(ACADEMIC.basedOnRegulation, RDFS.domain))
    if len(domains) != 1:
        raise ValueError("basedOnRegulation must have exactly one domain")

    old_domain = domains[0]
    heads = list(graph.objects(old_domain, OWL.unionOf))
    if len(heads) != 1:
        raise ValueError("basedOnRegulation domain must be an owl:unionOf")

    old_members = set(Collection(graph, heads[0]))
    expected = {ACADEMIC.AcademicProcedure, ACADEMIC.Condition, ACADEMIC.TuitionRate}
    if old_members != expected:
        raise ValueError(f"unexpected basedOnRegulation domain: {old_members}")

    Collection(graph, heads[0]).clear()
    graph.remove((old_domain, None, None))
    graph.remove((ACADEMIC.basedOnRegulation, RDFS.domain, old_domain))

    new_domain = BNode()
    new_head = BNode()
    graph.add((ACADEMIC.basedOnRegulation, RDFS.domain, new_domain))
    graph.add((new_domain, RDF.type, OWL.Class))
    graph.add((new_domain, OWL.unionOf, new_head))
    Collection(graph, new_head, [ACADEMIC.AcademicProcedure, ACADEMIC.TuitionRate])


def migrate(source: Path = SOURCE, target: Path = TARGET, manifest_path: Path = MANIFEST) -> dict:
    graph = Graph().parse(source, format="turtle")
    source_triples = len(graph)
    records: list[dict[str, str]] = []

    # Validate and replace this union before removing the Condition class,
    # otherwise deleting references to the class also mutates the RDF list.
    _replace_regulation_domain(graph)

    for old_property, old_class, new_property, label, alias in FLATTENED_PROPERTIES:
        pairs = sorted(graph.subject_objects(old_property), key=lambda pair: (str(pair[0]), str(pair[1])))
        if not pairs:
            raise ValueError(f"{_local_name(old_property)} has no values")

        for parent, wrapper in pairs:
            labels = list(graph.objects(wrapper, RDFS.label))
            if len(labels) != 1 or labels[0].language != "vi":
                raise ValueError(f"{_local_name(wrapper)} must have one Vietnamese label")

            incoming = set(graph.subject_predicates(wrapper))
            if incoming != {(parent, old_property)}:
                raise ValueError(f"{_local_name(wrapper)} is not a private wrapper: {incoming}")

            extras = set(graph.predicate_objects(wrapper)) - {
                (RDF.type, old_class),
                (RDF.type, OWL.NamedIndividual),
                (RDFS.label, labels[0]),
            }
            for predicate, value in extras:
                if predicate != ACADEMIC.basedOnRegulation or (parent, predicate, value) not in graph:
                    raise ValueError(f"non-redundant data on {_local_name(wrapper)}: {(predicate, value)}")

            graph.add((parent, new_property, labels[0]))
            records.append(
                {
                    "source": _local_name(parent),
                    "old_property": _local_name(old_property),
                    "removed_wrapper": _local_name(wrapper),
                    "new_property": _local_name(new_property),
                    "value": str(labels[0]),
                    "language": labels[0].language or "",
                }
            )
            graph.remove((wrapper, None, None))

        graph.remove((None, old_property, None))
        graph.remove((old_property, None, None))
        graph.remove((old_class, None, None))
        graph.remove((None, None, old_class))

        graph.add((new_property, RDF.type, OWL.DatatypeProperty))
        graph.add((new_property, RDFS.label, Literal(label, lang="vi")))
        graph.add((new_property, RDFS.domain, ACADEMIC.AcademicProcedure))
        graph.add((new_property, RDFS.range, RDF.langString))
        graph.add((new_property, SKOS.altLabel, Literal(alias, lang="vi")))

    removed_aliases: list[dict[str, str]] = []
    for resource, value in REMOVED_ALIASES:
        literal = Literal(value, lang="vi")
        if (resource, SKOS.altLabel, literal) not in graph:
            raise ValueError(f"missing alias scheduled for removal: {_local_name(resource)} -> {value}")
        graph.remove((resource, SKOS.altLabel, literal))
        removed_aliases.append({"resource": _local_name(resource), "value": value, "language": "vi"})

    old_versions = list(graph.objects(ONTOLOGY_IRI, OWL.versionInfo))
    if old_versions != [Literal("10")]:
        raise ValueError(f"unexpected source version: {old_versions}")
    graph.set((ONTOLOGY_IRI, OWL.versionInfo, Literal("11")))

    graph.bind("", ACADEMIC)
    graph.bind("owl", OWL)
    graph.bind("rdf", RDF)
    graph.bind("rdfs", RDFS)
    graph.bind("skos", SKOS)

    manifest = {
        "source": source.name,
        "target": target.name,
        "source_triples": source_triples,
        "target_triples": len(graph),
        "flattened_values": records,
        "removed_aliases": removed_aliases,
        "notes": [
            "content is preserved unchanged",
            "Condition and Outcome wrappers were private and are replaced by repeated Vietnamese literals",
            "two wrapper regulation links were redundant with their parent procedures",
            "object properties remain graph connectors and are not flattened",
        ],
    }

    target.parent.mkdir(parents=True, exist_ok=True)
    turtle = graph.serialize(format="turtle")
    target.write_text(turtle.rstrip() + "\n", encoding="utf-8")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    manifest = migrate()
    print(
        f"created {manifest['target']}: "
        f"{manifest['source_triples']} -> {manifest['target_triples']} triples, "
        f"{len(manifest['flattened_values'])} values flattened"
    )


if __name__ == "__main__":
    main()
