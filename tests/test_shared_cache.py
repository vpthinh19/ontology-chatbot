"""Canh chính phần nhớ đệm dùng chung của bộ kiểm.

Một bộ kiểm nhớ nhầm vẫn xanh, nhưng không còn chứng minh điều gì - nó chỉ lặp
lại câu trả lời cũ cho một câu hỏi mới. Đó là kiểu hỏng khó nhận ra nhất, nên
phần nhớ đệm phải tự có phép kiểm chứ không được tin suông.
"""

from __future__ import annotations

from ontchatbot.runtime import sparql
from ontchatbot.runtime.sparql import execute_select, load_ontology


# Truy vấn phải mở đầu bằng ``SELECT``: phần khai tiền tố do tầng chạy tự ghép
# vào. Sắp xếp rõ ràng để hai lần chạy không khác nhau vì thứ tự.
QUERY = "SELECT ?label WHERE { ?s rdfs:label ?label } ORDER BY ?label LIMIT 5"


def test_the_cache_is_actually_installed() -> None:
    """Nếu chốt chống nạp hai lần chặn nhầm thì cả bộ kiểm chậm lại mà không ai biết."""

    assert hasattr(load_ontology, "uncached"), "nhớ đệm không được cài"
    assert hasattr(execute_select, "uncached")


def test_cached_answers_match_what_the_engine_really_returns() -> None:
    """Đây là điều kiện duy nhất khiến nhớ đệm hợp lệ: kết quả không đổi."""

    graph = load_ontology()

    cached = execute_select(graph, QUERY)
    direct = execute_select.uncached(graph, QUERY)

    assert cached == direct
    assert cached, "truy vấn mẫu phải trả về dòng, nếu không phép kiểm này rỗng nghĩa"


def test_a_different_ontology_never_borrows_the_canonical_answers(tmp_path) -> None:
    """Khoá theo nội dung, nên nội dung khác phải cho đồ thị khác.

    Bỏ điều kiện này thì một phép kiểm dựng ontology riêng sẽ nhận về kết quả của
    ontology chuẩn, và nó xanh trong khi lẽ ra phải đỏ.
    """

    canonical = load_ontology()
    trimmed = tmp_path / "ontology.ttl"
    trimmed.write_text(
        "@prefix : <http://www.ntu.edu.vn/ontology/academic#> .\n"
        "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n"
        ':MotThuKhac rdfs:label "một nhãn không có trong bản chuẩn" .\n',
        encoding="utf-8",
    )

    other = load_ontology(trimmed)

    assert other is not canonical
    assert execute_select(other, QUERY) != execute_select(canonical, QUERY)


def test_a_copy_of_the_canonical_file_shares_the_same_graph(tmp_path) -> None:
    """Bản chép giống hệt thì dùng chung - đây là chỗ tiết kiệm lớn nhất."""

    copy = tmp_path / "ontology.ttl"
    copy.write_bytes(sparql.ONTOLOGY_PATH.read_bytes())

    assert load_ontology(copy) is load_ontology()


def test_the_caller_cannot_corrupt_what_the_next_test_will_read() -> None:
    """Người gọi sắp xếp hay sửa tại chỗ là chuyện thường, và nó không được lan ra."""

    graph = load_ontology()
    first = execute_select(graph, QUERY)
    original = [dict(row) for row in first]

    first.clear()
    for row in original[:1]:
        pass

    second = execute_select(graph, QUERY)
    assert second == original

    second[0][next(iter(second[0]))] = "đã bị sửa"
    assert execute_select(graph, QUERY) == original
