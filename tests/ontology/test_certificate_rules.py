from decimal import Decimal

from rdflib import RDF


EXPECTED_LANGUAGE_CERTIFICATES = {
    "TOEICCertificate",
    "TOEFLIBTCertificate",
    "IELTSCertificate",
    "LinguaskillCertificate",
    "AptisGeneralCertificate",
    "CambridgeEnglishScaleCertificate",
    "HSKCertificate",
    "TOCFLCertificate",
    "JLPTCertificate",
    "JPTCertificate",
    "TRKICertificate",
    "DELFCertificate",
    "TCFCertificate",
    "TOPIKCertificate",
    "KLPTCertificate",
}

EXPECTED_RULES = {
    "StandardEnglishCertificateTable": 26,
    "StandardOtherLanguageCertificateTable": 46,
    "SpecialProgramEnglishCertificateTable": 36,
    "SpecialProgramOtherLanguageCertificateTable": 48,
    "EnglishMajorOtherLanguageCertificateTable": 47,
    "ComputerCertificateTable": 9,
}


def _rules_for_table(graph, academic, table_name):
    table = academic[table_name]
    rows = set(graph.objects(table, academic.hasPart))
    return {
        rule
        for rule in graph.subjects(RDF.type, academic.CertificateConversionRule)
        if graph.value(rule, academic.sourceProvision) in rows
    }


def test_certificate_catalogue_and_learner_contexts(ontology_graph, academic) -> None:
    language = set(ontology_graph.subjects(RDF.type, academic.LanguageCertificate))
    computer = set(ontology_graph.subjects(RDF.type, academic.ComputerCertificate))
    contexts = set(ontology_graph.subjects(RDF.type, academic.LearnerCategory))
    assert language == {academic[name] for name in EXPECTED_LANGUAGE_CERTIFICATES}
    assert computer == {academic.IC3Certificate, academic.ICDLCertificate, academic.MOSCertificate}
    assert contexts == {
        academic.StandardProgramNonLanguageMajorStudent,
        academic.SpecialProgramNonLanguageMajorStudent,
        academic.EnglishLanguageMajorStudent,
    }


def test_every_meaningful_certificate_cell_becomes_one_rule(
    ontology_graph, academic
) -> None:
    for table_name, expected_count in EXPECTED_RULES.items():
        assert len(_rules_for_table(ontology_graph, academic, table_name)) == expected_count


def test_every_certificate_rule_is_sourced_and_contextualized(
    ontology_graph, academic
) -> None:
    rules = set(ontology_graph.subjects(RDF.type, academic.CertificateConversionRule))
    assert len(rules) == sum(EXPECTED_RULES.values())
    for rule in rules:
        assert (rule, academic.sourceDocument, academic.Decision1052) in ontology_graph
        assert ontology_graph.value(rule, academic.sourceProvision) is not None
        assert ontology_graph.value(rule, academic.appliesToCertificate) is not None
        assert set(ontology_graph.objects(rule, academic.appliesToLearnerCategory))
        criterion = ontology_graph.value(rule, academic.criterionText)
        assert criterion is not None and criterion.language == "vi"


def test_special_program_rules_reference_the_six_official_programs(
    ontology_graph, academic
) -> None:
    expected_programs = {
        academic.InformationTechnology,
        academic.Accounting,
        academic.FinanceAndBanking,
        academic.HotelManagement,
        academic.BusinessAdministration,
        academic.TourismAndTravelServiceManagement,
    }
    rules = _rules_for_table(ontology_graph, academic, "SpecialProgramEnglishCertificateTable")
    assert {ontology_graph.value(rule, academic.appliesToProgram) for rule in rules} == expected_programs


def test_computer_certificates_have_three_inclusive_score_bands(
    ontology_graph, academic
) -> None:
    rules = _rules_for_table(ontology_graph, academic, "ComputerCertificateTable")
    assert len(rules) == 9
    grades = {
        ontology_graph.value(rule, academic.convertedGrade).toPython() for rule in rules
    }
    assert grades == {Decimal("8"), Decimal("9"), Decimal("10")}
    assert all(ontology_graph.value(rule, academic.minimumScore) is not None for rule in rules)
    assert all(ontology_graph.value(rule, academic.maximumScore) is not None for rule in rules)
    assert all(ontology_graph.value(rule, academic.minimumInclusive).toPython() is True for rule in rules)
    assert all(ontology_graph.value(rule, academic.maximumInclusive).toPython() is True for rule in rules)


def test_ambiguous_multi_threshold_cells_remain_unsplit(ontology_graph, academic) -> None:
    rules = _rules_for_table(ontology_graph, academic, "StandardEnglishCertificateTable")
    toeic_b1 = next(
        rule
        for rule in rules
        if ontology_graph.value(rule, academic.appliesToCertificate) == academic.TOEICCertificate
        and "400" in str(ontology_graph.value(rule, academic.criterionText))
        and "500" in str(ontology_graph.value(rule, academic.criterionText))
    )
    assert ontology_graph.value(toeic_b1, academic.minimumScore) is None
    assert ontology_graph.value(toeic_b1, academic.maximumScore) is None
