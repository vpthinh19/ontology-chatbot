import json
import re
from pathlib import Path

from ontchatbot.catalogue import load_catalogue
from ontchatbot.research.dataset import load_release
from ontchatbot.settings import (
    QUERY_CATALOGUE_MANUAL_PATH,
    QUERY_CATALOGUE_PATH,
    REPORTS_DIR,
)


ROOT = Path(__file__).resolve().parents[2]

#: Tài liệu nào được phép nêu số họ truy vấn.
_CATALOGUE_DOCS = ("README.md", "docs/DATASET.md", "resources/dataset/README.md")
#: Một khẳng định về quy mô danh mục: "296 họ", "19 dạng"...
_CLAIM = re.compile(r"(\d+)\s+(?:họ|dạng)\b")
_PERCENTAGE = re.compile(r"\d+(?:[.,]\d+)?%")


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _json(path: str) -> dict:
    return json.loads(_read(path))


def _vi_number(value: int) -> str:
    return f"{value:,}".replace(",", ".")


def _metric_percentages(payload: object) -> set[str]:
    """Các phần trăm được sinh từ artifact metric hiện hành."""

    found: set[str] = set()
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key.endswith("_rate") and isinstance(value, (int, float)):
                found.add(f"{value * 100:.2f}%".replace(".", ","))
            else:
                found.update(_metric_percentages(value))
    elif isinstance(payload, list):
        for value in payload:
            found.update(_metric_percentages(value))
    return found


def _catalogue_sizes() -> set[int]:
    """Mọi con số hợp lệ khi tài liệu nói về quy mô danh mục truy vấn."""

    catalogue = load_catalogue(QUERY_CATALOGUE_PATH)
    # Tệp khai tay đã bị XOÁ cùng họ "liệt kê năng lực" (2026-08-14) - nó chỉ
    # chứa đúng họ đó. Giữ nhánh này để tài liệu vẫn nói đúng nếu sau có ai khai
    # tay một họ mới, nhưng không được vỡ khi tệp không tồn tại.
    manual = (
        sum(
            1
            for line in QUERY_CATALOGUE_MANUAL_PATH.read_text(
                encoding="utf-8"
            ).splitlines()
            if line.strip()
        )
        if QUERY_CATALOGUE_MANUAL_PATH.exists()
        else 0
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
    release = load_release()
    total = _vi_number(sum(map(len, release.values())))
    splits = {
        split: _vi_number(len(rows)) for split, rows in release.items()
    }
    readme = _read("README.md")
    dataset = _read("docs/DATASET.md")
    resource = _read("resources/dataset/README.md")

    assert f"{total} câu" in readme
    assert f"{total} câu" in dataset
    assert all(value in dataset for value in splits.values())
    assert all(value in resource for value in splits.values())
    assert "candidate pool" not in "\n".join((readme, dataset, resource))


def test_readme_explains_the_research_to_new_readers() -> None:
    training = _read("docs/TRAINING.md")
    readme = _read("README.md")
    model_report = REPORTS_DIR / "models.json"

    assert "test không tham gia chọn checkpoint" in training
    assert "## 1. Bài toán nghiên cứu" in readme
    assert "## 2. Các khái niệm nền tảng" in readme
    assert "## 3. Phương pháp đề xuất" in readme
    assert "### 3.1. Hình dạng đầu vào và đầu ra của model" in readme
    assert "SELECT ?thuoctinh ?giatri ?nguon ?duongdan WHERE" in readme
    assert "TemporaryAcademicLeaveProcedure" in readme
    assert "## 9. Giới hạn" in readme
    assert "resources/dataset/train.jsonl" in readme
    assert "resources/dataset/test.jsonl" in readme
    assert "uv run generate_reports" in readme
    assert ".venv/bin/python -m ontchatbot.research.inventory" in readme
    assert ".venv/bin/python -m ontchatbot.cli.validate_data" in readme
    assert "không sinh lại nữa" in readme
    assert "điều phối tool-calling hoàn chỉnh chưa được tích hợp" in readme
    if model_report.is_file():
        documented = set(_PERCENTAGE.findall(training))
        assert _metric_percentages(json.loads(model_report.read_text())) <= documented
    else:
        # Không có artifact metric thì tài liệu không được công bố một
        # phần trăm model như thể đó là kết quả hiện hành.
        assert _PERCENTAGE.findall(training) == []
    assert "NTUdocs" not in readme
    # README không được dẫn người đọc tới rác của một lượt chạy cục bộ. Ngoại lệ
    # DUY NHẤT là ``artifacts/reports/``: từ khi mọi thứ sinh ra dồn về
    # ``artifacts/``, đó là chỗ ở của bản đối chứng nằm trong git, nên nhắc tới
    # nó là đúng - còn ``artifacts/run-...`` thì vẫn không.
    assert re.sub(r"artifacts/reports/", "", readme).find("artifacts/") == -1
    assert "Trạng thái hiện tại" not in readme


def test_docs_connect_ontology_query_catalogue_and_dataset() -> None:
    ontology = _read("docs/ONTOLOGY.md")
    dataset = _read("docs/DATASET.md")
    readme = _read("README.md")
    inventory = _json("resources/ontology/answer_inventory.json")
    supported = sum(
        entry["status"] == "supported" for entry in inventory["entries"]
    )
    records = sum(map(len, load_release().values()))

    assert "answer_inventory.json" in ontology
    assert "cơ sở dữ liệu duy nhất" in ontology
    assert "Quyết định 1052" in readme
    assert "Quyết định 317" in readme
    assert "SPARQL" in readme
    assert "1052" in readme
    assert f"{_vi_number(supported)} khả năng trả lời" in ontology
    assert f"{_vi_number(records)} câu" in dataset


def test_public_docs_describe_consistency_and_metric_provenance() -> None:
    files = (
        "README.md",
        "docs/CONCEPT.md",
        "docs/ONTOLOGY.md",
        "docs/DATASET.md",
        "docs/EVALUATION.md",
        "docs/MODEL_CARD.md",
        "docs/DEPLOYMENT.md",
        "artifacts/reports/README.md",
    )
    joined = "\n".join(_read(path) for path in files)
    provenance = _json("artifacts/reports/provenance.json")
    baseline = provenance["baseline_release"]

    assert "danh mục khả năng trả lời" in joined
    assert "danh mục truy vấn" in joined
    assert "uv run validate_sparql_dataset" in joined
    assert "uv run generate_reports" in joined
    assert "artifacts/reports/provenance.json" in joined
    assert f"baseline {baseline}" in joined
    assert provenance["model_metrics"]["status"] in joined
    assert provenance["deployment_metrics"]["status"] in joined
    assert "procedure-dataset.json" in joined
    assert ("models.json" in joined) == (REPORTS_DIR / "models.json").is_file()
    assert "Claude Code" not in joined
    assert "CLAUDE.md" not in joined
    assert "ai agent" not in joined.lower()
