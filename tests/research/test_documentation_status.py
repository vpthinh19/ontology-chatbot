from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_public_docs_describe_current_dataset_release() -> None:
    files = (
        "README.md",
        "docs/DATASET.md",
        "docs/TRAINING.md",
        "resources/dataset/README.md",
        "reports/README.md",
    )
    joined = "\n".join(_read(path) for path in files)

    assert "4.454 câu" in joined
    assert "51 họ truy vấn" in joined
    assert "candidate pool" not in joined
    assert "455 câu" not in joined


def test_readme_explains_the_research_to_new_readers() -> None:
    training = _read("docs/TRAINING.md")
    readme = _read("README.md")

    assert "T5Gemma2 được chọn cho runtime" in training
    assert "92,38%" in training
    assert "test không tham gia chọn checkpoint" in training
    assert "## 1. Bài toán nghiên cứu" in readme
    assert "## 2. Các khái niệm nền tảng" in readme
    assert "## 3. Phương pháp đề xuất" in readme
    assert "## 9. Giới hạn" in readme
    assert "NTUdocs" not in readme
    assert "artifacts/" not in readme
    assert "Trạng thái hiện tại" not in readme


def test_docs_connect_canonical_ontology_catalogue_and_dataset() -> None:
    ontology = _read("docs/ONTOLOGY.md")
    dataset = _read("docs/DATASET.md")
    readme = _read("README.md")

    assert "answer_inventory.json" in ontology
    assert "22 quy trình" in ontology
    assert "2 chính sách" in ontology
    assert "Quyết định 1052" in readme
    assert "Quyết định 729" in readme
    assert "SPARQL" in readme
    assert "22" in readme
    assert "2.953" in ontology
    assert "4.454 câu" in dataset
    assert "coverage hoàn chỉnh" in dataset
    assert "T5Gemma2 được chọn cho runtime" in _read("docs/TRAINING.md")
