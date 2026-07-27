from ontchatbot.research.dataset import load_release
from ontchatbot.research.reporting import build_dataset_report, write_public_reports
from ontchatbot.runtime.sparql import load_ontology


def test_public_dataset_report_matches_contract(tmp_path) -> None:
    report = build_dataset_report(load_release(), load_ontology())

    assert report["dataset"]["records"] == 1176
    assert report["generalization_contract"] == {
        "validation_targets_seen_in_train": 35,
        "validation_targets": 35,
        "test_targets_seen_in_train": 0,
        "test_targets": 39,
        "test_schema_terms_missing_from_train": [],
    }
    assert report["ontology"]["resources_missing_vietnamese_label"] == []

    write_public_reports(report, output_dir=tmp_path)
    assert (tmp_path / "dataset.json").is_file()
    assert (tmp_path / "figures/dataset-splits.svg").is_file()
    assert (tmp_path / "figures/query-shapes.svg").is_file()
