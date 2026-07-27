from ontchatbot.research.dataset import load_release
from ontchatbot.research.reporting import build_dataset_report, write_public_reports
from ontchatbot.runtime.sparql import load_ontology


def test_public_dataset_report_matches_contract(tmp_path) -> None:
    report = build_dataset_report(load_release(), load_ontology())

    assert report["dataset"]["records"] == 1336
    assert report["generalization_contract"] == {
        "validation_targets_seen_in_train": 35,
        "validation_targets": 35,
        "test_targets_seen_in_train": 0,
        "test_targets": 39,
        "test_schema_terms_missing_from_train": [],
    }
    assert report["ontology"]["resources_missing_vietnamese_label"] == []
    assert report["dataset"]["query_features_by_split"]["train"] == {
        "aggregate": 68,
        "filter": 40,
        "graph_hop": 472,
        "group": 12,
        "limit": 12,
        "multi_branch": 632,
        "multi_column": 308,
        "order": 12,
        "single_branch": 408,
        "single_column": 732,
    }
    assert "filter" not in report["dataset"]["query_features_by_split"]["val"]
    assert report["training_readiness"] == {
        "ready": False,
        "gaps": [
            {
                "code": "insufficient_train_feature_targets",
                "minimum": 5,
                "features": {"group": 3, "limit": 3, "order": 3},
            },
            {
                "code": "missing_validation_features",
                "minimum_families": 2,
                "features": {"filter": 0, "group": 0, "limit": 0, "order": 0},
            },
            {
                "code": "under_supported_test_terms",
                "minimum_train_families": 2,
                "terms": {
                    "BankCounterPayment": 1,
                    "OnlinePayment": 1,
                    "PaymentMethod": 1,
                    "PlanningAndFinanceOffice": 1,
                },
            },
        ],
    }

    write_public_reports(report, output_dir=tmp_path)
    assert (tmp_path / "dataset.json").is_file()
    assert (tmp_path / "figures/dataset-splits.svg").is_file()
    assert (tmp_path / "figures/registers.svg").is_file()
    assert (tmp_path / "figures/query-features.svg").is_file()
