from ontchatbot.evaluation import evaluate_predictions
from ontchatbot.query_engine import load_ontology


def _example(target: str, register: str = "neutral") -> dict[str, str]:
    return {
        "id": "case-1",
        "family_id": "family-1",
        "split": "validation",
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
    assert report["by_register"]["noisy"]["count"] == 1
    assert report["cases"][0]["error"]
