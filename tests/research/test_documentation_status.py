from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_public_docs_describe_current_dataset_release() -> None:
    files = (
        "README.md",
        "docs/DATASET.md",
        "docs/TRAINING.md",
        "resources/dataset/main/README.md",
        "reports/README.md",
    )
    joined = "\n".join(_read(path) for path in files)

    assert "2.000 câu" in joined
    assert "51 họ truy vấn" in joined
    assert "candidate pool" not in joined
    assert "455 câu" not in joined


def test_public_docs_allow_training_only_from_the_locked_release() -> None:
    training = _read("docs/TRAINING.md")
    readme = _read("README.md")

    assert "chưa có benchmark chính thức" in training
    assert "test không tham gia chọn checkpoint" in training
    assert "ontology → inventory → catalogue → dataset" in readme
    assert "semantic index" in readme


def test_superseded_designs_point_to_current_readiness_spec() -> None:
    replacement = "2026-07-29-ontology-dataset-readiness-design.md"
    files = (
        "docs/superpowers/specs/2026-07-29-official-production-dataset-design.md",
        "docs/superpowers/plans/2026-07-29-official-production-dataset.md",
        "docs/superpowers/specs/2026-07-29-official-ontology-refactor-design.md",
        "docs/superpowers/plans/2026-07-29-official-ontology-refactor.md",
    )

    for path in files:
        assert replacement in _read(path)


def test_docs_connect_canonical_ontology_catalogue_and_dataset() -> None:
    ontology = _read("docs/ONTOLOGY.md")
    dataset = _read("docs/DATASET.md")
    readme = _read("README.md")

    assert "answer_inventory.json" in ontology
    assert "22 quy trình" in ontology
    assert "2 chính sách" in ontology
    assert "ontology canonical" in readme
    assert "51 họ truy vấn" in readme
    assert "2.953" in ontology
    assert "2.000 câu" in dataset
    assert "coverage hoàn chỉnh" in dataset
    assert "chưa có benchmark chính thức" in _read("docs/TRAINING.md")
