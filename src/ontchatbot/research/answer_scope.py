"""Classify ontology individuals by their role in model-facing answers."""

from __future__ import annotations

from rdflib import RDF, Graph, URIRef


SOURCE_CLASS_NAMES = frozenset(
    {
        "Article",
        "Clause",
        "Point",
        "Appendix",
        "DocumentTable",
        "DocumentTableRow",
        "Chapter",
        "AttachedRegulation",
    }
)

OPAQUE_RECORD_CLASS_NAMES = frozenset(
    {
        "CertificateConversionRule",
        "TuitionRate",
        "PaymentFeeRule",
        "AcademicPerformanceBand",
        "GraduationClassificationBand",
        "StudyYearBand",
        "DoctoralTuitionDurationRule",
    }
)


def rdf_type_names(graph: Graph, node: URIRef) -> frozenset[str]:
    """Return local RDF type names for a project resource."""

    return frozenset(
        _local_name(value)
        for value in graph.objects(node, RDF.type)
        if isinstance(value, URIRef)
    )


def is_opaque_record(graph: Graph, node: URIRef) -> bool:
    """Whether a node is an internal storage record rather than a model slot."""

    return bool(rdf_type_names(graph, node) & OPAQUE_RECORD_CLASS_NAMES)


def _local_name(node: URIRef) -> str:
    value = str(node)
    return value.rsplit("#", 1)[-1].rsplit("/", 1)[-1]
