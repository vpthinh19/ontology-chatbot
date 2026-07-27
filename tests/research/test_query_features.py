from ontchatbot.research.query_features import extract_query_features


OBJECT_PROPERTIES = frozenset(
    {"handledBy", "hasDocument", "basedOnRegulation", "supportsPaymentMethod"}
)


def test_extracts_single_column_direct_query() -> None:
    query = "SELECT ?answer WHERE { :AcademicLeaveProcedure :content ?answer . }"

    assert extract_query_features(query, object_properties=OBJECT_PROPERTIES) == {
        "output_columns": 1,
        "triple_patterns": 1,
        "graph_hop": False,
        "aggregate": False,
        "filter": False,
        "group": False,
        "order": False,
        "limit": False,
        "values": False,
    }


def test_extracts_multiple_columns_and_object_property_hop() -> None:
    query = (
        "SELECT ?content ?office WHERE { "
        ":AcademicLeaveProcedure :content ?content . "
        ":AcademicLeaveProcedure :handledBy ?node . "
        "?node rdfs:label ?office . }"
    )

    features = extract_query_features(query, object_properties=OBJECT_PROPERTIES)

    assert features["output_columns"] == 2
    assert features["triple_patterns"] == 3
    assert features["graph_hop"] is True


def test_counts_aggregate_alias_as_one_output_column() -> None:
    query = (
        "SELECT ?office (COUNT(DISTINCT ?itemNode) AS ?count) WHERE { "
        "?itemNode :handledBy ?office . } GROUP BY ?office"
    )

    features = extract_query_features(query, object_properties=OBJECT_PROPERTIES)

    assert features["output_columns"] == 2
    assert features["aggregate"] is True
    assert features["group"] is True


def test_counts_only_outer_projection_for_nested_subquery() -> None:
    query = (
        "SELECT ?count ?answer WHERE { { "
        "SELECT (COUNT(DISTINCT ?node) AS ?count) WHERE { "
        "?node a :PaymentMethod . } } "
        "?item a :PaymentMethod . ?item rdfs:label ?answer . }"
    )

    features = extract_query_features(query, object_properties=OBJECT_PROPERTIES)

    assert features["output_columns"] == 2
    assert features["aggregate"] is True
    assert features["triple_patterns"] == 3


def test_detects_semicolon_filter_order_and_limit() -> None:
    query = (
        "SELECT ?answer WHERE { ?rate :cohortCode ?cohort ; "
        ":tuitionPerCredit ?answer . FILTER ( ?answer > 500000 ) } "
        "ORDER BY DESC ( ?answer ) LIMIT 2"
    )

    features = extract_query_features(query, object_properties=OBJECT_PROPERTIES)

    assert features["triple_patterns"] == 2
    assert features["filter"] is True
    assert features["order"] is True
    assert features["limit"] is True


def test_detects_values_as_multi_entity_binding() -> None:
    query = (
        "SELECT ?method WHERE { VALUES ?node { "
        ":BankCounterPayment :OnlinePayment } "
        "?node rdfs:label ?method . } ORDER BY ?method"
    )

    features = extract_query_features(query, object_properties=OBJECT_PROPERTIES)

    assert features["values"] is True


def test_detects_filter_not_exists() -> None:
    query = (
        "SELECT ?rate WHERE { ?node :tuitionPerCredit ?rate . "
        "FILTER NOT EXISTS { ?other :tuitionPerCredit ?rate . } }"
    )

    features = extract_query_features(query, object_properties=OBJECT_PROPERTIES)

    assert features["filter"] is True
