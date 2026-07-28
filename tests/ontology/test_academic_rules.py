from decimal import Decimal

from rdflib import RDF


def _rules(graph, class_):
    return set(graph.subjects(RDF.type, class_))


def _by_result(graph, academic, class_, result):
    return next(
        rule
        for rule in graph.subjects(RDF.type, class_)
        if str(graph.value(rule, academic.resultLabel)) == result
    )


def test_academic_performance_bands_match_article_18(ontology_graph, academic) -> None:
    bands = _rules(ontology_graph, academic.AcademicPerformanceBand)
    assert len(bands) == 6
    expected = {
        "Xuất sắc": (Decimal("9.00"), Decimal("10")),
        "Giỏi": (Decimal("8.00"), Decimal("8.99")),
        "Khá": (Decimal("7.00"), Decimal("7.99")),
        "Trung bình": (Decimal("5.00"), Decimal("6.99")),
        "Yếu": (Decimal("4.00"), Decimal("4.99")),
        "Kém": (Decimal("0.00"), Decimal("3.99")),
    }
    for result, (minimum, maximum) in expected.items():
        band = _by_result(ontology_graph, academic, academic.AcademicPerformanceBand, result)
        assert ontology_graph.value(band, academic.minimumValue).toPython() == minimum
        assert ontology_graph.value(band, academic.maximumValue).toPython() == maximum
        assert ontology_graph.value(band, academic.minimumInclusive).toPython() is True
        assert ontology_graph.value(band, academic.maximumInclusive).toPython() is True


def test_study_year_bands_preserve_source_boundaries(ontology_graph, academic) -> None:
    bands = _rules(ontology_graph, academic.StudyYearBand)
    assert len(bands) == 4
    fourth_year = _by_result(ontology_graph, academic, academic.StudyYearBand, "Sinh viên năm thứ tư")
    assert ontology_graph.value(fourth_year, academic.minimumValue).toPython() == Decimal("105")
    assert ontology_graph.value(fourth_year, academic.minimumInclusive).toPython() is False
    assert ontology_graph.value(fourth_year, academic.maximumValue) is None
    third_year = _by_result(ontology_graph, academic, academic.StudyYearBand, "Sinh viên năm thứ ba")
    assert ontology_graph.value(third_year, academic.minimumValue).toPython() == Decimal("70")
    assert ontology_graph.value(third_year, academic.maximumValue).toPython() == Decimal("105")
    assert ontology_graph.value(third_year, academic.maximumInclusive).toPython() is False


def test_graduation_classification_bands_match_article_23(
    ontology_graph, academic
) -> None:
    bands = _rules(ontology_graph, academic.GraduationClassificationBand)
    assert len(bands) == 4
    average = _by_result(ontology_graph, academic, academic.GraduationClassificationBand, "Trung bình")
    assert ontology_graph.value(average, academic.minimumValue).toPython() == Decimal("5.50")
    assert ontology_graph.value(average, academic.maximumValue).toPython() == Decimal("6.99")


def test_class_size_rules_keep_numeric_limits_and_source_wildcards(
    ontology_graph, academic
) -> None:
    rules = _rules(ontology_graph, academic.ClassSizeRule)
    assert len(rules) == 14
    without_maximum = {
        rule for rule in rules if ontology_graph.value(rule, academic.maximumValue) is None
    }
    assert len(without_maximum) == 2
    assert all("*" in str(ontology_graph.value(rule, academic.criterionText)) for rule in without_maximum)
    cnc = next(rule for rule in rules if "CNC" in str(ontology_graph.value(rule, academic.criterionText)))
    assert ontology_graph.value(cnc, academic.minimumValue).toPython() == Decimal("10")
    assert ontology_graph.value(cnc, academic.maximumValue).toPython() == Decimal("15")


def test_every_academic_rule_is_traceable(ontology_graph, academic) -> None:
    classes = {
        academic.AcademicPerformanceBand,
        academic.StudyYearBand,
        academic.GraduationClassificationBand,
        academic.ClassSizeRule,
    }
    for class_ in classes:
        for rule in ontology_graph.subjects(RDF.type, class_):
            assert (rule, academic.sourceDocument, academic.Decision1052) in ontology_graph
            assert ontology_graph.value(rule, academic.sourceProvision) is not None
            criterion = ontology_graph.value(rule, academic.criterionText)
            assert criterion is not None and criterion.language == "vi"
