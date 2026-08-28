import json
import hashlib
from collections import Counter

from ontchatbot.catalogue import QuerySpec, SlotSpec
from ontchatbot.research.evaluation import (
    evaluate_predictions as _evaluate_predictions,
    evaluate_query_id_expectations,
)
from ontchatbot.runtime.cards import Card, CardLookup
from ontchatbot.research.graph import load_ontology
from ontchatbot.settings import TEST_DATASET_PATH, VAL_DATASET_PATH


def _example(
    target: str,
    register: str = "neutral",
) -> dict[str, object]:
    marker = target == "không có thông tin"
    anchor = ":Test" + hashlib.sha256(target.encode()).hexdigest()[:16]
    return {
        "id": "case-1",
        "query_id": "no-information" if marker else "query-0001",
        "register": register,
        "input": "phòng nào xử lý bảo lưu",
        "target": [] if marker else [anchor],
        "_query": target,
    }


def evaluate_predictions(examples, predictions, graph, **kwargs):
    """Feed SPARQL-focused fixtures through the dataset's new label format."""

    supplied_lookup = kwargs.pop("lookup", None)
    cards = []
    cleaned = []
    for example in examples:
        row = dict(example)
        query = row.pop("_query", None)
        if query is not None:
            cards.append(
                Card(
                    row["query_id"],
                    tuple(row["target"]),
                    "test",
                    query,
                )
            )
        cleaned.append(row)
    lookup = supplied_lookup or (CardLookup(cards) if cards else None)
    return _evaluate_predictions(
        cleaned, predictions, graph, lookup=lookup, **kwargs
    )


V3_CATALOGUE = {
    "node-facts": QuerySpec(
        "node-facts",
        "procedure",
        "SELECT ?answer WHERE { ${anchor} rdfs:label ?answer . }",
        {"anchor": SlotSpec("iri", (":AcademicAdvisor", ":CourseLecturer"))},
    ),
    "no-information": QuerySpec(
        "no-information", "out-of-domain", "không có thông tin", {}
    ),
}


V3_LOOKUP = CardLookup(
    [
        Card(
            "node-facts",
            (anchor,),
            "test",
            V3_CATALOGUE["node-facts"].target_template.replace("${anchor}", anchor),
        )
        for anchor in (":AcademicAdvisor", ":CourseLecturer")
    ]
    + [Card("no-information", (), "test", "không có thông tin")]
)


def _v3_example(identifier: str, query_id: str, target: list[str]) -> dict[str, object]:
    return {
        "id": identifier,
        "query_id": query_id,
        "register": "neutral",
        "input": identifier,
        "target": target,
    }


def test_held_out_splits_carry_both_kinds_of_row() -> None:
    """Val và test đều phải có dòng dump node và dòng từ chối.

    Công cụ hoặc truy xuất dữ kiện hoặc trả ``không có thông tin``. Phép kiểm
    xác nhận trực tiếp sự hiện diện của cả hai loại dòng thay vì suy ra một loại
    từ tổng số dòng.
    """

    for path in (VAL_DATASET_PATH, TEST_DATASET_PATH):
        rows = [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        query_ids = Counter(row["query_id"] for row in rows)

        assert rows
        assert query_ids["no-information"] > 0
        assert len(rows) - query_ids["no-information"] > 0


def test_perfect_prediction_scores_every_metric() -> None:
    target = (
        "SELECT ?answer WHERE { :TemporaryAcademicLeaveProcedure :submittedTo ?node . "
        "?node rdfs:label ?answer . }"
    )
    report = evaluate_predictions([_example(target)], [target], load_ontology())

    assert report["overall"]["count"] == 1
    assert report["overall"]["parse_rate"] == 1.0
    assert report["overall"]["execution_rate"] == 1.0
    assert report["overall"]["answer_exact_rate"] == 1.0
    assert report["overall"]["result_f1"] == 1.0
    assert report["in_domain"]["count"] == 1
    assert report["out_of_domain"]["count"] == 0


def test_equivalent_query_keeps_answer_metric_but_not_canonical_exact() -> None:
    target = (
        "SELECT ?answer WHERE { :TemporaryAcademicLeaveProcedure :submittedTo ?node . "
        "?node rdfs:label ?answer . }"
    )
    equivalent = (
        "SELECT ?answer WHERE { :TemporaryAcademicLeaveProcedure :submittedTo ?office . "
        "?office rdfs:label ?answer . }"
    )
    report = evaluate_predictions([_example(target)], [equivalent], load_ontology())

    assert report["overall"]["answer_exact_rate"] == 1.0
    assert report["overall"]["canonical_query_exact_rate"] == 0.0


def test_answer_metric_ignores_variable_names() -> None:
    target = "SELECT ?answer WHERE { :StudentAffairsOffice rdfs:label ?answer . }"
    equivalent = "SELECT ?label WHERE { :StudentAffairsOffice rdfs:label ?label . }"

    report = evaluate_predictions([_example(target)], [equivalent], load_ontology())

    assert report["overall"]["answer_exact_rate"] == 1.0
    assert report["overall"]["canonical_query_exact_rate"] == 0.0


def test_invalid_prediction_is_counted_without_crashing() -> None:
    target = "SELECT ?answer WHERE { :TemporaryAcademicLeaveProcedure :hasStep ?part . ?part :stepText ?answer . }"
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
        "SELECT ?content ?document WHERE { "
        ":TemporaryAcademicLeaveProcedure :hasStep ?part . "
        "?part :stepText ?content . "
        ":TemporaryAcademicLeaveProcedure :requiresForm ?form . "
        "?form rdfs:label ?document . }"
    )
    prediction = (
        "SELECT ?content ?document WHERE { "
        ":TemporaryAcademicLeaveProcedure :hasStep ?part . "
        "?part :officialText ?content . }"
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


def test_marker_prediction_is_scored_without_sparql_parsing() -> None:
    example = {
        **_example("không có thông tin", register="colloquial"),
        "query_id": "no-information",
        "input": "xin chào nha",
    }

    report = evaluate_predictions(
        [example], ["không có thông tin"], load_ontology(), include_cases=True
    )

    assert report["overall"]["answer_exact_rate"] == 1.0
    assert report["out_of_domain"]["count"] == 1
    assert report["out_of_domain"]["marker_exact_rate"] == 1.0
    assert report["out_of_domain"]["false_acceptance_rate"] == 0.0
    assert report["out_of_domain"]["safe_rejection_rate"] == 1.0
    assert report["overall"]["system_answer_exact_rate"] == 1.0
    assert report["cases"][0]["parse"] is False


def test_executable_select_for_marker_is_false_acceptance() -> None:
    example = {
        **_example("không có thông tin"),
        "query_id": "no-information",
        "input": "thời tiết hôm nay",
    }
    prediction = 'SELECT ?answer WHERE { VALUES ?answer { "trời nắng" } }'

    report = evaluate_predictions([example], [prediction], load_ontology())

    assert report["out_of_domain"]["answer_exact_rate"] == 0.0
    assert report["out_of_domain"]["false_acceptance_rate"] == 1.0
    assert report["out_of_domain"]["safe_rejection_rate"] == 0.0
    assert report["overall"]["system_answer_exact_rate"] == 0.0


def test_empty_select_for_marker_is_a_safe_system_rejection() -> None:
    example = {
        **_example("không có thông tin"),
        "query_id": "no-information",
        "input": "mốc điểm không tồn tại",
    }
    prediction = (
        "SELECT ?answer WHERE { :TemporaryAcademicLeaveProcedure "
        ":minimumValue ?answer . }"
    )

    report = evaluate_predictions(
        [example], [prediction], load_ontology(), include_cases=True
    )

    assert report["overall"]["answer_exact_rate"] == 0.0
    assert report["overall"]["system_answer_exact_rate"] == 1.0
    assert report["out_of_domain"]["safe_rejection_rate"] == 1.0
    assert report["cases"][0]["safe_rejection"] is True
    assert report["cases"][0]["system_answer_exact"] is True


def test_marker_for_supported_query_is_a_false_rejection() -> None:
    target = (
        "SELECT ?answer WHERE { :TemporaryAcademicLeaveProcedure "
        ":submittedTo ?node . ?node rdfs:label ?answer . }"
    )

    report = evaluate_predictions(
        [_example(target)],
        ["không có thông tin"],
        load_ontology(),
        include_cases=True,
    )

    assert report["overall"]["system_answer_exact_rate"] == 0.0
    assert report["error_counts"] == {"false_rejection": 1}
    assert report["cases"][0]["error_category"] == "false_rejection"


def test_v3_metrics_are_separate_and_account_for_every_group() -> None:
    node_target = V3_CATALOGUE["node-facts"].target_template.replace(
        "${anchor}", ":AcademicAdvisor"
    )
    examples = [
        _v3_example("node", "node-facts", [":AcademicAdvisor"]),
        _v3_example("rejection", "no-information", []),
    ]

    report = evaluate_predictions(
        examples,
        [node_target, "không có thông tin"],
        load_ontology(),
        catalogue=V3_CATALOGUE,
        lookup=V3_LOOKUP,
    )

    assert report["primary_metrics"] == {
        "node_selection": {"count": 1, "correct": 1, "rate": 1.0},
        "query_shape": {"count": 1, "correct": 1, "rate": 1.0},
        "rejection_decision": {"count": 2, "correct": 2, "rate": 1.0},
    }
    assert report["coverage_accounting"] == {
        "total": 2,
        "accounted_for": 2,
        "groups": {
            "node_queries": {
                "count": 1,
                "scored_by": [
                    "node_selection",
                    "query_shape",
                    "rejection_decision",
                ],
            },
            "out_of_domain": {
                "count": 1,
                "scored_by": ["rejection_decision"],
            },
        },
    }


def test_node_metric_accepts_another_explicit_syntax_but_shape_does_not() -> None:
    target = V3_CATALOGUE["node-facts"].target_template.replace(
        "${anchor}", ":AcademicAdvisor"
    )
    equivalent = (
        "SELECT ?answer WHERE { VALUES ?entity { :AcademicAdvisor } "
        "?entity rdfs:label ?answer . }"
    )

    report = evaluate_predictions(
        [_v3_example("node", "node-facts", [":AcademicAdvisor"])],
        [equivalent],
        load_ontology(),
        catalogue=V3_CATALOGUE,
        lookup=V3_LOOKUP,
        include_cases=True,
    )

    assert report["primary_metrics"]["node_selection"]["rate"] == 1.0
    assert report["primary_metrics"]["query_shape"]["rate"] == 0.0
    assert report["cases"][0]["expected_nodes"] == ["AcademicAdvisor"]
    assert report["cases"][0]["predicted_nodes"] == ["AcademicAdvisor"]


def test_invalid_sparql_is_wrong_in_every_applicable_v3_metric() -> None:
    target = V3_CATALOGUE["node-facts"].target_template.replace(
        "${anchor}", ":AcademicAdvisor"
    )

    report = evaluate_predictions(
        [_v3_example("node", "node-facts", [":AcademicAdvisor"])],
        ["SELECT ?answer WHERE {"],
        load_ontology(),
        catalogue=V3_CATALOGUE,
        lookup=V3_LOOKUP,
    )

    assert report["primary_metrics"] == {
        "node_selection": {"count": 1, "correct": 0, "rate": 0.0},
        "query_shape": {"count": 1, "correct": 0, "rate": 0.0},
        "rejection_decision": {"count": 1, "correct": 0, "rate": 0.0},
    }


def test_real_user_questions_are_scored_separately_by_query_id() -> None:
    node_target = V3_CATALOGUE["node-facts"].target_template.replace(
        "${anchor}", ":AcademicAdvisor"
    )
    expectations = [
        {"question": "cố vấn học tập", "expected_query_id": "node-facts"},
        {"question": "thời tiết", "expected_query_id": "no-information"},
    ]

    report = evaluate_query_id_expectations(
        expectations,
        [node_target, "SELECT ?answer WHERE {"],
        catalogue=V3_CATALOGUE,
        include_cases=True,
    )

    assert report["count"] == 2
    assert report["correct"] == 1
    assert report["query_id_accuracy"] == 0.5
    assert report["mixed_into_generated_benchmark"] is False
    assert report["cases"][1]["predicted_query_id"] is None
