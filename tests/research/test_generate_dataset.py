from __future__ import annotations

from rdflib import RDF, Graph, URIRef

from ontchatbot.catalogue import QuerySpec, SlotSpec, load_catalogue
from ontchatbot.research.generate_dataset import (
    build_bindings,
    name_teaching_cases,
)
from ontchatbot.runtime.sparql import execute_select, load_ontology
from ontchatbot.settings import ONTOLOGY_NS, QUERY_CATALOGUE_PATH


def test_certificate_families_return_the_six_source_tables_as_whole_nodes() -> None:
    graph = load_ontology()
    catalogue = load_catalogue(QUERY_CATALOGUE_PATH)

    def ns(local: str) -> URIRef:
        return URIRef(ONTOLOGY_NS + local)

    expected = {
        "certificate-conversion-table-english-language-major-student": {
            "SecondLanguageConversionTableEnglishMajor",
        },
        "certificate-conversion-table-special-program-non-language-major-student": {
            "EnglishRequirementTableSpecialProgram",
            "OtherLanguageRequirementTableSpecialProgram",
        },
        "certificate-conversion-table-standard-program-non-language-major-student": {
            "EnglishConversionTableStandardProgram",
            "OtherLanguageConversionTableStandardProgram",
        },
        "certificate-conversion-table-moi-doi-tuong": {
            "ComputerCertificateConversionTable",
        },
    }

    assert set(catalogue) & set(expected) == set(expected)
    assert not set(graph.subjects(RDF.type, ns("CertificateConversionRule")))
    for query_id, table_names in expected.items():
        spec = catalogue[query_id]
        assert spec.slots == {}
        rows = execute_select(graph, spec.target_template, max_rows=100)
        returned = {
            str(row["giatri"])
            for row in rows
            if str(row["thuoctinh"]) == "nguyên văn bảng"
        }
        table_texts = {
            str(next(graph.objects(ns(table_name), ns("verbatimTableText"))))
            for table_name in table_names
        }
        assert returned == table_texts
        assert len(rows) == 6 * len(table_names)
        assert {str(row["thuoctinh"]) for row in rows} == {
            "nhãn tiếng Việt",
            "nguyên văn bảng",
            "trích dẫn",
            "đường dẫn văn bản gốc",
            "thuộc tài liệu",
            "nằm trong phần",
        }
        assert all(row.get("nguon") and row.get("duongdan") for row in rows)

    document_anchors = set(catalogue["document-part-facts"].slots["anchor"].values)
    assert not document_anchors & {
        f":{table_name}" for table_names in expected.values() for table_name in table_names
    }


def test_independent_iri_slots_still_form_a_cartesian_product() -> None:
    query_id = "independent-slots"
    catalogue = {
        query_id: QuerySpec(
            query_id,
            "academic-rule",
            "SELECT ?x WHERE { ${left} ?p ?x FILTER (${right} = ${right}) }",
            {
                "left": SlotSpec("iri", (":Left1", ":Left2")),
                "right": SlotSpec("iri", (":Right1", ":Right2")),
            },
        )
    }

    bindings = build_bindings(
        Graph(store="Oxigraph"),
        catalogue,
        {query_id: ()},
        article_numbers=(),
        clause_numbers=(),
    )[query_id]

    assert bindings == [
        {"left": ":Left1", "right": ":Right1"},
        {"left": ":Left1", "right": ":Right2"},
        {"left": ":Left2", "right": ":Right1"},
        {"left": ":Left2", "right": ":Right2"},
    ]


def test_name_teaching_cases_enumerate_every_label_without_a_seed() -> None:
    spec = QuerySpec(
        "named-family",
        "procedure",
        "SELECT * WHERE { ${anchor} ?p ?x }",
        {"anchor": SlotSpec("iri", (":One", ":Two"))},
    )
    bindings = [{"anchor": ":One"}, {"anchor": ":Two"}]
    mentions = {"One": ("Tên chính", "tên phụ"), "Two": ("Tên thứ hai",)}

    assert name_teaching_cases(spec, bindings, mentions) == [
        ({"anchor": ":One"}, "anchor", "Tên chính"),
        ({"anchor": ":One"}, "anchor", "tên phụ"),
        ({"anchor": ":Two"}, "anchor", "Tên thứ hai"),
    ]
