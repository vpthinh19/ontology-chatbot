import re

from rdflib import OWL, RDF
from rdflib.namespace import XSD


CLAUSE_LINE = re.compile(r"(?m)^(\d+)\.\s")
POINT_LINE = re.compile(r"(?m)^([a-zđ])\)\s")


def _vi_texts(graph, subject, predicate):
    return [value for value in graph.objects(subject, predicate) if value.language == "vi"]


def _identifiers(graph, parent, academic):
    return {
        str(graph.value(child, academic.identifier))
        for child in graph.objects(parent, academic.hasPart)
        if graph.value(child, academic.identifier) is not None
    }


def test_decision_1052_metadata_and_structure(ontology_graph, academic) -> None:
    decision = academic.Decision1052
    assert (decision, RDF.type, OWL.NamedIndividual) in ontology_graph
    assert (decision, RDF.type, academic.Decision) in ontology_graph
    assert (decision, academic.documentNumber, None) in ontology_graph
    assert str(ontology_graph.value(decision, academic.documentNumber)) == "1052/QĐ-ĐHNT"
    assert ontology_graph.value(decision, academic.issueDate).datatype == XSD.date
    assert str(ontology_graph.value(decision, academic.issueDate)) == "2025-07-17"
    assert str(ontology_graph.value(decision, academic.effectiveFromAcademicYear)) == "2025-2026"
    assert not any("1051" in str(value) for value in ontology_graph.objects(decision, None))

    enactment_articles = {
        academic[f"Decision1052EnactmentArticle{index:02d}"] for index in range(1, 4)
    }
    chapters = {academic[f"Decision1052Chapter{index:02d}"] for index in range(1, 6)}
    articles = {academic[f"Decision1052Article{index:02d}"] for index in range(1, 33)}
    appendices = {academic[f"Decision1052Appendix{index:02d}"] for index in range(1, 4)}

    for article in enactment_articles:
        assert (article, RDF.type, academic.Article) in ontology_graph
        assert (article, academic.partOf, decision) in ontology_graph
    assert (academic.Decision1052Regulation, RDF.type, academic.AttachedRegulation) in ontology_graph
    assert (academic.Decision1052Regulation, academic.partOf, decision) in ontology_graph
    for chapter in chapters:
        assert (chapter, RDF.type, academic.Chapter) in ontology_graph
        assert (chapter, academic.partOf, academic.Decision1052Regulation) in ontology_graph
    for article in articles:
        assert (article, RDF.type, academic.Article) in ontology_graph
        assert ontology_graph.value(article, academic.partOf) in chapters
        assert (article, academic.sourceDocument, decision) in ontology_graph
        assert _vi_texts(ontology_graph, article, academic.officialText)
    for appendix in appendices:
        assert (appendix, RDF.type, academic.Appendix) in ontology_graph
        assert (appendix, academic.partOf, academic.Decision1052Regulation) in ontology_graph


def test_decision_1052_clauses_points_and_tables_are_traceable(
    ontology_graph, academic
) -> None:
    clauses = set(ontology_graph.subjects(RDF.type, academic.Clause))
    points = set(ontology_graph.subjects(RDF.type, academic.Point))
    rows = {
        row
        for row in ontology_graph.subjects(RDF.type, academic.DocumentTableRow)
        if (row, academic.sourceDocument, academic.Decision1052) in ontology_graph
    }
    assert clauses
    assert points
    assert rows
    for part in clauses | points | rows:
        assert ontology_graph.value(part, academic.partOf) is not None
        assert (part, academic.sourceDocument, academic.Decision1052) in ontology_graph
        assert _vi_texts(ontology_graph, part, academic.officialText)

    assert (
        academic.Decision1052Article24Clause03,
        academic.partOf,
        academic.Decision1052Article24,
    ) in ontology_graph
    assert (
        academic.Decision1052Article25Clause01PointA,
        academic.partOf,
        academic.Decision1052Article25Clause01,
    ) in ontology_graph


def test_decision_1052_numbered_children_match_parent_text(
    ontology_graph, academic
) -> None:
    for index in range(1, 33):
        article = academic[f"Decision1052Article{index:02d}"]
        text = str(ontology_graph.value(article, academic.officialText))
        expected = {f"Khoản {number}" for number in CLAUSE_LINE.findall(text)}
        actual = {
            value
            for value in _identifiers(ontology_graph, article, academic)
            if value.startswith("Khoản ")
        }
        assert actual == expected, article

    for clause in ontology_graph.subjects(RDF.type, academic.Clause):
        text = str(ontology_graph.value(clause, academic.officialText))
        expected = {f"Điểm {letter}" for letter in POINT_LINE.findall(text)}
        if not expected:
            continue
        actual = {
            value
            for value in _identifiers(ontology_graph, clause, academic)
            if value.startswith("Điểm ")
        }
        assert actual == expected, clause


def test_article_20_clauses_are_separated_without_duplicate_points(
    ontology_graph, academic
) -> None:
    clause_1 = academic.Decision1052Article20Clause01
    clause_2 = academic.Decision1052Article20Clause02
    assert _identifiers(
        ontology_graph, academic.Decision1052Article20, academic
    ) == {"Khoản 1", "Khoản 2", "Khoản 3"}
    assert _identifiers(ontology_graph, clause_1, academic) == {
        "Điểm a",
        "Điểm b",
        "Điểm c",
    }
    assert _identifiers(ontology_graph, clause_2, academic) == {
        "Điểm a",
        "Điểm b",
    }
    assert "buộc thôi học" not in str(
        ontology_graph.value(clause_1, academic.officialText)
    ).casefold()
    assert "buộc thôi học" in str(
        ontology_graph.value(clause_2, academic.officialText)
    ).casefold()
    for point in ontology_graph.objects(clause_1, academic.hasPart):
        assert len(list(ontology_graph.objects(point, academic.officialText))) == 1
        assert len(list(ontology_graph.objects(point, academic.orderIndex))) == 1


def test_decision_1052_does_not_invent_missing_appendix_4(ontology_graph, academic) -> None:
    assert not list(
        ontology_graph.triples((academic.Decision1052Appendix04, None, None))
    )


def test_decision_729_metadata_and_structure(ontology_graph, academic) -> None:
    decision = academic.Decision729
    assert (decision, RDF.type, OWL.NamedIndividual) in ontology_graph
    assert (decision, RDF.type, academic.Decision) in ontology_graph
    assert str(ontology_graph.value(decision, academic.documentNumber)) == "729/QĐ-ĐHNT"
    assert str(ontology_graph.value(decision, academic.issueDate)) == "2025-05-28"
    assert str(ontology_graph.value(decision, academic.effectiveFromAcademicYear)) == "2025-2026"
    assert str(ontology_graph.value(decision, academic.effectiveFromSemester)) == "Học kỳ I"
    assert ontology_graph.value(decision, academic.validUntilSuperseded).toPython() is True
    for index in range(1, 4):
        article = academic[f"Decision729EnactmentArticle{index:02d}"]
        assert (article, RDF.type, academic.Article) in ontology_graph
        assert (article, academic.partOf, decision) in ontology_graph
    for index in range(1, 3):
        appendix = academic[f"Decision729Appendix{index:02d}"]
        assert (appendix, RDF.type, academic.Appendix) in ontology_graph
        assert (appendix, academic.partOf, decision) in ontology_graph
