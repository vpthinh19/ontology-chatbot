from ontchatbot.research.evaluation import evaluate_predictions
from ontchatbot.runtime.sparql import load_ontology


def _example(
    target: str,
    register: str = "neutral",
) -> dict[str, str]:
    return {
        "id": "case-1",
        "query_id": "query-0001",
        "register": register,
        "input": "phòng nào xử lý bảo lưu",
        "target": target,
    }


def test_perfect_prediction_scores_every_metric() -> None:
    target = (
        "SELECT ?answer WHERE { :AcademicLeaveProcedure :handledBy ?node . "
        "?node rdfs:label ?answer . }"
    )
    report = evaluate_predictions([_example(target)], [target], load_ontology())

    assert report["overall"] == {
        "count": 1,
        "parse_rate": 1.0,
        "execution_rate": 1.0,
        "answer_exact_rate": 1.0,
        "result_precision": 1.0,
        "result_recall": 1.0,
        "result_f1": 1.0,
        "canonical_query_exact_rate": 1.0,
    }


def test_equivalent_query_keeps_answer_metric_but_not_canonical_exact() -> None:
    target = (
        "SELECT ?answer WHERE { :AcademicLeaveProcedure :handledBy ?node . "
        "?node rdfs:label ?answer . }"
    )
    equivalent = (
        "SELECT ?answer WHERE { :AcademicLeaveProcedure :handledBy ?office . "
        "?office rdfs:label ?answer . }"
    )
    report = evaluate_predictions([_example(target)], [equivalent], load_ontology())

    assert report["overall"]["answer_exact_rate"] == 1.0
    assert report["overall"]["canonical_query_exact_rate"] == 0.0


def test_answer_metric_ignores_variable_names() -> None:
    target = "SELECT ?answer WHERE { :StudentAffairsOffice :email ?answer . }"
    equivalent = "SELECT ?email WHERE { :StudentAffairsOffice :email ?email . }"

    report = evaluate_predictions([_example(target)], [equivalent], load_ontology())

    assert report["overall"]["answer_exact_rate"] == 1.0
    assert report["overall"]["canonical_query_exact_rate"] == 0.0


def test_invalid_prediction_is_counted_without_crashing() -> None:
    target = "SELECT ?answer WHERE { :AcademicLeaveProcedure :content ?answer . }"
    report = evaluate_predictions(
        [_example(target, register="noisy")],
        ["SELECT ?answer WHERE {"],
        load_ontology(),
        include_cases=True,
    )

    assert report["overall"]["parse_rate"] == 0.0
    assert report["overall"]["execution_rate"] == 0.0
    assert report["overall"]["answer_exact_rate"] == 0.0
    assert report["overall"]["result_precision"] == 0.0
    assert report["overall"]["result_recall"] == 0.0
    assert report["overall"]["result_f1"] == 0.0
    assert report["by_register"]["noisy"]["count"] == 1
    assert report["error_counts"] == {"parse_error": 1}
    assert report["cases"][0]["error"]


def test_partial_result_reports_macro_precision_recall_and_f1() -> None:
    target = (
        "SELECT ?answer WHERE { ?node a :PaymentMethod . "
        "?node rdfs:label ?answer . }"
    )
    prediction = target + " LIMIT 1"

    report = evaluate_predictions([_example(target)], [prediction], load_ontology())

    assert report["overall"]["answer_exact_rate"] == 0.0
    assert report["overall"]["result_precision"] == 1.0
    assert 0.0 < report["overall"]["result_recall"] < 1.0
    assert 0.0 < report["overall"]["result_f1"] < 1.0


def test_result_overlap_preserves_duplicate_rows() -> None:
    target = 'SELECT ?answer WHERE { VALUES ?answer { "A" "A" } }'
    prediction = 'SELECT ?answer WHERE { VALUES ?answer { "A" } }'

    report = evaluate_predictions([_example(target)], [prediction], load_ontology())

    assert report["overall"]["result_precision"] == 1.0
    assert report["overall"]["result_recall"] == 0.5


def test_result_metrics_are_macro_averaged_per_query() -> None:
    exact = 'SELECT ?answer WHERE { VALUES ?answer { "A" } }'
    partial = 'SELECT ?answer WHERE { VALUES ?answer { "A" "B" "C" } }'
    examples = [
        {**_example(exact), "id": "case-1"},
        {**_example(partial), "id": "case-2"},
    ]
    predictions = [exact, 'SELECT ?answer WHERE { VALUES ?answer { "A" } }']

    report = evaluate_predictions(
        examples,
        predictions,
        load_ontology(),
        include_cases=True,
    )

    case_f1 = [case["result_f1"] for case in report["cases"]]
    assert report["overall"]["result_f1"] == sum(case_f1) / 2


def test_reports_overlapping_query_features_and_missing_branch() -> None:
    target = (
        "SELECT ?content ?condition WHERE { "
        ":AcademicLeaveProcedure :content ?content . "
        ":AcademicLeaveProcedure :condition ?condition . }"
    )
    prediction = (
        "SELECT ?content ?condition WHERE { "
        ":AcademicLeaveProcedure :content ?content . }"
    )
    report = evaluate_predictions(
        [_example(target)],
        [prediction],
        load_ontology(),
        include_cases=True,
    )

    assert report["by_query_feature"]["multi_column"]["count"] == 1
    assert report["by_query_feature"]["multi_branch"]["count"] == 1
    assert report["error_counts"] == {"missing_branch": 1}
    assert report["cases"][0]["error_category"] == "missing_branch"
