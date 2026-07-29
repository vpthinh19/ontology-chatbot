from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_public_docs_call_current_dataset_candidate() -> None:
    files = (
        "README.md",
        "docs/DATASET.md",
        "docs/TRAINING.md",
        "resources/dataset/main/README.md",
        "reports/README.md",
    )
    joined = "\n".join(_read(path) for path in files)

    assert "candidate pool" in joined
    assert "Release hiện có 456 câu" not in joined
    assert "# Dataset production" not in joined
    assert "release chính thức này" not in joined


def test_public_docs_block_official_training_until_readiness_gates_pass() -> None:
    training = _read("docs/TRAINING.md")
    readme = _read("README.md")

    assert "không được full fine-tune" in training
    assert "ontology → catalogue → dataset" in readme
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


def test_docs_separate_canonical_ontology_from_candidate_dataset() -> None:
    ontology = _read("docs/ONTOLOGY.md")
    dataset = _read("docs/DATASET.md")
    readme = _read("README.md")

    assert "answer_inventory.json" in ontology
    assert "22 quy trình" in ontology
    assert "2 chính sách" in ontology
    assert "ontology canonical" in readme
    assert "candidate pool" in dataset
    assert "không được full fine-tune" in _read("docs/TRAINING.md")
