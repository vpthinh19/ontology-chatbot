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
    # Danh mục thủ công là tuỳ chọn. Nhánh này tính các mục của nó khi có để tài
    # liệu luôn phản ánh cả danh mục sinh tự động lẫn mục khai tay.
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

    Quy mô hợp lệ được suy ra từ danh mục để tài liệu và dữ liệu dùng cùng phạm
    vi. Các câu mô tả danh mục lịch sử được bỏ qua.
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

    assert total in readme
    # Canh con số, không canh đơn vị: "6.308 dòng" và "6.308 câu" nói cùng một điều.
    assert total in dataset
    assert all(value in dataset for value in splits.values())
    assert all(value in resource for value in splits.values())
    assert "candidate pool" not in "\n".join((readme, dataset, resource))


def test_readme_explains_the_research_to_new_readers() -> None:
    """README viết cho người chưa biết gì và không mở mã nguồn.

    Canh những gì người đọc đó CẦN, không canh cách trình bày: đánh số mục hay
    dán một truy vấn mẫu là lựa chọn biên tập, còn việc nói rõ mô hình nhận gì
    và trả gì thì không.
    """

    readme = _read("README.md")
    metrics_file = ROOT / "artifacts/entity-linking/benchmark-metrics.json"

    # Người đọc phải trả lời được: hệ thống giải bài gì, dữ liệu đi qua những
    # hình dạng nào, nội dung lấy từ đâu, đo bằng cách nào, và nó chưa làm được
    # gì. Canh chủ đề chứ không canh cách đánh số hay thứ tự mục.
    for topic in (
        "Bài toán",
        "Hình dạng dữ liệu",
        "Ontology",
        "Tập dữ liệu",
        "Thiết lập thực nghiệm",
        "Hạn chế",
        "Hướng cải tiến",
    ):
        assert topic in readme, topic

    # Đầu ra chỉ có hai dạng, và đó là ràng buộc quan trọng nhất của công cụ.
    assert "không có thông tin" in readme
    # Số liệu của tầng sinh truy vấn KHÔNG phải chất lượng của trợ lý hoàn
    # chỉnh, nên README phải báo cáo riêng một phép đo chạy hết cả đường - và
    # phải nói rõ hai con số đó chênh nhau. Canh ý chứ không canh câu chữ.
    assert "end-to-end" in readme
    # Canh HÌNH DẠNG chứ không canh giá trị: yêu cầu là "phải báo cáo tỷ lệ trên
    # nhóm câu học vụ và đặt cạnh phép đo từng phần". Mẫu số đọc từ chính bộ câu
    # hỏi chứ không ghi cứng - sửa một nhãn sai là nhóm đổi kích thước, và một
    # con số ghim trong phép kiểm sẽ biến việc sửa đúng thành phép kiểm đỏ.
    trong_pham_vi = len(json.loads(
        (ROOT / "resources/end-to-end/questions.json").read_text(encoding="utf-8")
    )["trong_pham_vi"])
    assert re.search(rf"\d+/{trong_pham_vi}\b", readme), (
        f"thiếu tỷ lệ end-to-end trên {trong_pham_vi} câu học vụ")
    assert "phép đo từng phần" in readme

    # Sơ đồ thay cho mô tả bằng lời: một cho luồng xử lý, một cho luồng dữ liệu.
    # Ảnh dựng sẵn chứ không phải sơ đồ dựng lúc hiển thị, vì tài liệu này còn đi
    # ra ngoài kho mã, nơi không có bộ dựng sơ đồ nào chạy.
    images = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", readme)
    assert len(images) >= 2, images
    assert "```mermaid" not in readme
    for image in images:
        assert (ROOT / image).is_file(), image

    # Mỗi accuracy công bố trong README phải có mặt trong artifact chỉ số. Canh
    # chiều này vì lỗi nguy hiểm là tài liệu giữ lại một con số không còn nguồn,
    # chứ không phải artifact có con số tài liệu chưa nhắc.
    if metrics_file.is_file():
        published = {
            f"{100 * m['accuracy']:.1f}%".replace(".", ",")
            for m in json.loads(metrics_file.read_text(encoding="utf-8"))["metrics"].values()
        }
        assert published <= set(_PERCENTAGE.findall(readme)), published
    assert "NTUdocs" not in readme
    # README không được dẫn người đọc tới rác của một lượt chạy cục bộ.
    assert "artifacts/" not in readme
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
    # Ontology là nguồn nội dung duy nhất - không có kho dữ liệu song song nào
    # để hai chỗ nói hai điều khác nhau về cùng một quy định.
    assert "cơ sở dữ liệu nội dung duy nhất" in ontology
    # Người đọc phải biết dữ kiện đến từ văn bản nào, nếu không thì không có
    # cách nào đối chiếu lại điều công cụ nói.
    assert "Quyết định 1052" in readme
    assert "Quyết định 317" in readme
    assert "SPARQL" in readme
    assert _vi_number(supported) in ontology
    assert _vi_number(records) in dataset


def test_public_docs_describe_consistency_and_metric_provenance() -> None:
    files = (
        "README.md",
        "docs/ONTOLOGY.md",
        "docs/DATASET.md",
        "resources/reports/README.md",
    )
    joined = "\n".join(_read(path) for path in files)
    provenance = _json("resources/reports/provenance.json")
    baseline = provenance["baseline_release"]

    assert "khả năng trả lời" in joined
    assert "khuôn truy vấn" in joined
    assert "uv run validate_sparql_dataset" in joined
    assert "uv run generate_reports" in joined
    assert "resources/reports/provenance.json" in joined
    assert f"baseline {baseline}" in joined
    assert provenance["model_metrics"]["status"] in joined
    assert provenance["deployment_metrics"]["status"] in joined
    assert "procedure-dataset.json" in joined
    assert ("models.json" in joined) == (REPORTS_DIR / "models.json").is_file()
    assert "Claude Code" not in joined
    assert "CLAUDE.md" not in joined
    assert "ai agent" not in joined.lower()
