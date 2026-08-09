import re
from pathlib import Path

from ontchatbot.catalogue import load_catalogue
from ontchatbot.settings import QUERY_CATALOGUE_MANUAL_PATH, QUERY_CATALOGUE_PATH


ROOT = Path(__file__).resolve().parents[2]

#: Tài liệu nào được phép nêu số họ truy vấn.
_CATALOGUE_DOCS = ("README.md", "docs/DATASET.md", "resources/dataset/README.md")
#: Một khẳng định về quy mô danh mục: "296 họ", "19 dạng"...
_CLAIM = re.compile(r"(\d+)\s+(?:họ|dạng)\b")


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _catalogue_sizes() -> set[int]:
    """Mọi con số hợp lệ khi tài liệu nói về quy mô danh mục truy vấn."""

    catalogue = load_catalogue(QUERY_CATALOGUE_PATH)
    manual = sum(
        1
        for line in QUERY_CATALOGUE_MANUAL_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    primary = sum(1 for spec in catalogue.values() if spec.tier == "primary")
    return {
        len(catalogue),
        manual,
        len(catalogue) - manual - 1,  # sinh tự động; trừ cả họ từ chối
        primary,
        len(catalogue) - primary,
    }


def test_public_docs_quote_the_real_catalogue_size() -> None:
    """Mọi con số về quy mô danh mục trong tài liệu phải khớp `catalogue.jsonl`.

    Bản trước chốt thẳng chuỗi ``"364 họ truy vấn"``. Khi danh mục đổi, test vẫn
    XANH vì tài liệu cũng chưa được sửa - tức là nó khoá cái sai lại thay vì phát
    hiện ra, và còn làm việc sửa tài liệu cho đúng bị đỏ. Đọc thẳng từ danh mục thì
    tài liệu và dữ liệu không thể lệch nhau mà không ai biết.

    Câu nhắc tới danh mục **cũ** được bỏ qua: chúng cố ý nói về con số lịch sử.
    """

    allowed = _catalogue_sizes()

    stale: list[tuple[str, int]] = []
    for path in _CATALOGUE_DOCS:
        for line in _read(path).splitlines():
            if "cũ" in line:
                continue
            stale.extend(
                (path, int(value))
                for value in _CLAIM.findall(line)
                if int(value) not in allowed
            )

    assert stale == [], f"tài liệu nêu số họ truy vấn không có thật: {stale}"


def test_public_docs_describe_the_evaluated_dataset() -> None:
    files = (
        "README.md",
        "docs/DATASET.md",
        "docs/TRAINING.md",
        "resources/dataset/README.md",
        "reports/README.md",
    )
    joined = "\n".join(_read(path) for path in files)

    assert "4.454 câu" in joined
    # Dataset đang được dựng lại: tài liệu công khai phải nói rõ điều đó thay vì
    # để người đọc tưởng các số liệu cũ còn hiệu lực.
    assert "không còn hợp lệ" in joined
    assert "candidate pool" not in joined
    assert "455 câu" not in joined


def test_readme_explains_the_research_to_new_readers() -> None:
    training = _read("docs/TRAINING.md")
    readme = _read("README.md")

    assert "được chọn để triển khai" in training
    assert "92,38%" in training
    assert "test không tham gia chọn checkpoint" in training
    assert "## 1. Bài toán nghiên cứu" in readme
    assert "## 2. Các khái niệm nền tảng" in readme
    assert "## 3. Phương pháp đề xuất" in readme
    assert "### 3.1. Hình dạng đầu vào và đầu ra của model" in readme
    assert "SELECT ?answer WHERE { :CourseRegistrationProcedure" in readme
    assert "Phòng Công tác Chính trị và Sinh viên" in readme
    assert "## 9. Giới hạn" in readme
    assert "resources/dataset/train.jsonl" in readme
    assert "resources/dataset/test.jsonl" in readme
    assert "resources/cases/procedure_language.jsonl" in readme
    assert "reports/models.json" in readme
    assert "uv run generate_reports" in readme
    assert "uv run train_sparql" in readme
    assert "uv run convert_sparql_model" in readme
    assert "uv run serve_sparql" in readme
    assert "docker run --rm --publish 8000:8000 vpt19/ontchatbot:0.4.1" in readme
    assert "NTUdocs" not in readme
    assert "artifacts/" not in readme
    assert "Trạng thái hiện tại" not in readme


def test_docs_connect_ontology_query_catalogue_and_dataset() -> None:
    ontology = _read("docs/ONTOLOGY.md")
    dataset = _read("docs/DATASET.md")
    readme = _read("README.md")

    assert "answer_inventory.json" in ontology
    assert "| Thủ tục học vụ | 22 |" in ontology
    assert "| Chính sách học vụ | 3 |" in ontology
    assert "cơ sở dữ liệu duy nhất" in ontology
    assert "Quyết định 1052" in readme
    assert "Quyết định 729" in readme
    assert "SPARQL" in readme
    assert "22" in readme
    assert "6.073" in ontology
    assert "4.454 câu" in dataset
    assert "được chọn để triển khai" in _read("docs/TRAINING.md")


def test_public_docs_describe_consistency_and_metric_provenance() -> None:
    files = (
        "README.md",
        "docs/CONCEPT.md",
        "docs/ONTOLOGY.md",
        "docs/DATASET.md",
        "docs/EVALUATION.md",
        "docs/MODEL_CARD.md",
        "docs/DEPLOYMENT.md",
        "reports/README.md",
    )
    joined = "\n".join(_read(path) for path in files)

    assert "danh mục khả năng trả lời" in joined
    assert "danh mục truy vấn" in joined
    assert "uv run validate_sparql_dataset" in joined
    assert "uv run generate_reports" in joined
    assert "reports/provenance.json" in joined
    assert "baseline v0.4.1" in joined
    assert "stale" in joined
    assert "procedure-dataset.json" in joined
    assert "Claude Code" not in joined
    assert "CLAUDE.md" not in joined
    assert "ai agent" not in joined.lower()
