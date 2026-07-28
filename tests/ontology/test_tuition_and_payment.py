from rdflib import OWL, RDF


def _objects(graph, subject, predicate):
    return set(graph.objects(subject, predicate))


def _matching_rates(graph, academic, **criteria):
    rates = set(graph.subjects(RDF.type, academic.TuitionRate))
    for property_name, expected in criteria.items():
        predicate = academic[property_name]
        rates = {rate for rate in rates if expected in set(graph.objects(rate, predicate))}
    return rates


def test_all_41_programs_belong_to_official_discipline_groups(
    ontology_graph, academic
) -> None:
    expected_counts = {
        academic.DisciplineGroupIII: 8,
        academic.DisciplineGroupIV: 1,
        academic.DisciplineGroupV: 23,
        academic.DisciplineGroupVII: 9,
    }
    programs = set(ontology_graph.subjects(RDF.type, academic.AcademicProgram))
    assert len(programs) == 41
    for group, count in expected_counts.items():
        assert len(set(ontology_graph.subjects(academic.belongsToDisciplineGroup, group))) == count
    assert str(ontology_graph.value(academic.InformationTechnology, academic.belongsToDisciplineGroup)).endswith("DisciplineGroupV")
    assert str(ontology_graph.value(academic.EnglishLanguage, academic.belongsToDisciplineGroup)).endswith("DisciplineGroupVII")


def test_standard_tuition_rates_match_decision_729(ontology_graph, academic) -> None:
    expected = [
        ({"appliesToCourseCategory": academic.GeneralEducationCourse}, 345000),
        ({"appliesToDisciplineGroup": academic.DisciplineGroupIII, "appliesToEducationLevel": academic.UndergraduateLevel}, 500000),
        ({"appliesToDisciplineGroup": academic.DisciplineGroupV, "appliesToEducationLevel": academic.UndergraduateLevel}, 570000),
        ({"appliesToProgram": academic.EnglishLanguage, "appliesToEducationLevel": academic.UndergraduateLevel}, 460000),
        ({"appliesToProgram": academic.HotelManagement, "appliesToEducationLevel": academic.UndergraduateLevel}, 505000),
        ({"appliesToDisciplineGroup": academic.DisciplineGroupIII, "appliesToEducationLevel": academic.MasterLevel}, 785000),
        ({"appliesToDisciplineGroup": academic.DisciplineGroupIV, "appliesToEducationLevel": academic.MasterLevel}, 850000),
        ({"appliesToDisciplineGroup": academic.DisciplineGroupV, "appliesToEducationLevel": academic.MasterLevel}, 915000),
        ({"appliesToDisciplineGroup": academic.DisciplineGroupVII, "appliesToEducationLevel": academic.MasterLevel}, 785000),
        ({"appliesToDisciplineGroup": academic.DisciplineGroupIII, "appliesToEducationLevel": academic.DoctoralLevel}, 39500000),
        ({"appliesToDisciplineGroup": academic.DisciplineGroupV, "appliesToEducationLevel": academic.DoctoralLevel}, 46000000),
        ({"appliesToProgram": academic.MarineResourceEconomicsAndManagement, "appliesToEducationLevel": academic.DoctoralLevel}, 24500000),
    ]
    for criteria, amount in expected:
        rates = _matching_rates(ontology_graph, academic, **criteria)
        assert any(int(ontology_graph.value(rate, academic.amount)) == amount for rate in rates)


def test_accredited_program_rates_use_minimum_cohort(ontology_graph, academic) -> None:
    expected = [
        (academic.SeafoodProcessingTechnology, 63, 620000),
        (academic.Biotechnology, 63, 600000),
        (academic.BusinessAdministration, 65, 550000),
        (academic.InformationTechnology, 65, 620000),
        (academic.MechanicalEngineering, 66, 620000),
        (academic.EnglishLanguage, 66, 510000),
        (academic.ThermalEngineering, 67, 620000),
        (academic.Law, 67, 550000),
    ]
    for program, cohort, amount in expected:
        rates = _matching_rates(
            ontology_graph,
            academic,
            appliesToProgram=program,
            appliesToCourseCategory=academic.AccreditedFoundationAndMajorCourse,
        )
        assert any(
            int(ontology_graph.value(rate, academic.minimumCohortNumber)) == cohort
            and int(ontology_graph.value(rate, academic.amount)) == amount
            for rate in rates
        )


def test_every_tuition_rate_is_typed_and_traced(ontology_graph, academic) -> None:
    rates = set(ontology_graph.subjects(RDF.type, academic.TuitionRate))
    assert rates
    for rate in rates:
        assert (rate, RDF.type, OWL.NamedIndividual) in ontology_graph
        assert (rate, academic.sourceDocument, academic.Decision729) in ontology_graph
        assert ontology_graph.value(rate, academic.sourceProvision) is not None
        assert str(ontology_graph.value(rate, academic.currencyCode)) == "VND"
        assert ontology_graph.value(rate, academic.billingUnit) is not None


def test_doctoral_duration_rules_preserve_entry_qualification(ontology_graph, academic) -> None:
    rules = set(ontology_graph.subjects(RDF.type, academic.DoctoralTuitionDurationRule))
    assert len(rules) == 3
    durations = sorted(int(ontology_graph.value(rule, academic.durationInYears)) for rule in rules)
    assert durations == [3, 4, 4]
    assert any((rule, academic.appliesToEntryQualification, academic.MasterQualification) in ontology_graph for rule in rules)
    assert any((rule, academic.appliesToEntryQualification, academic.BachelorQualification) in ontology_graph for rule in rules)
    assert any((rule, academic.appliesToProgram, academic.MarineResourceEconomicsAndManagement) in ontology_graph for rule in rules)


def test_payment_methods_banks_fees_and_warning_match_guidance(
    ontology_graph, academic
) -> None:
    methods = set(ontology_graph.subjects(RDF.type, academic.PaymentMethod))
    banks = set(ontology_graph.subjects(RDF.type, academic.Bank))
    assert methods == {
        academic.VNPAYPayment,
        academic.QRCodePayment,
        academic.MobileOrInternetBankingPayment,
        academic.CashAtBankCounterPayment,
    }
    assert banks == {academic.Agribank, academic.VietinBank, academic.LienVietPostBank}
    fee_amounts = {
        int(amount)
        for rule in ontology_graph.subjects(RDF.type, academic.PaymentFeeRule)
        for amount in ontology_graph.objects(rule, academic.feeAmount)
    }
    assert fee_amounts == {0, 3300, 5500}
    warnings = " ".join(str(value) for value in ontology_graph.objects(academic.TuitionPaymentProcedure, academic.paymentWarningText))
    assert "MÃ SINH VIÊN" in warnings
    assert "không gửi tài khoản của trường" in warnings
    assert "cấm thi" not in warnings.lower()
