from ontchatbot.research.dataset import load_release
from ontchatbot.research.reporting import build_dataset_report, write_public_reports
from ontchatbot.runtime.sparql import load_ontology


def test_public_dataset_report_matches_contract(tmp_path) -> None:
    report = build_dataset_report(load_release(), load_ontology())

    assert report["dataset"]["records"] == 1416
    assert report["generalization_contract"] == {
        "validation_targets_seen_in_train": 41,
        "validation_targets": 41,
        "test_targets_seen_in_train": 0,
        "test_targets": 42,
        "test_schema_terms_missing_from_train": [],
    }
    assert report["ontology"]["resources_missing_vietnamese_label"] == []
    assert report["dataset"]["query_features_by_split"]["train"] == {
        "aggregate": 76,
        "filter": 56,
        "graph_hop": 472,
        "group": 20,
        "limit": 20,
        "multi_branch": 672,
        "multi_column": 328,
        "order": 56,
        "single_branch": 412,
        "single_column": 756,
        "values": 20,
    }
    assert report["dataset"]["query_features_by_split"]["val"]["filter"] == 8
    assert report["dataset"]["query_features_by_split"]["val"]["values"] == 8
    assert report["training_readiness"] == {"ready": True, "gaps": []}

    write_public_reports(report, output_dir=tmp_path)
    assert (tmp_path / "dataset.json").is_file()
    assert (tmp_path / "figures/dataset-splits.svg").is_file()
    assert (tmp_path / "figures/registers.svg").is_file()
    assert (tmp_path / "figures/query-features.svg").is_file()
