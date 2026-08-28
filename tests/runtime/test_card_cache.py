"""Bảng thẻ nướng sẵn phải giống hệt bản dựng, và không bao giờ được dùng nhầm."""

from __future__ import annotations

import json
import shutil

import pytest

from ontchatbot.runtime.cards import (
    CARD_CACHE_VERSION,
    bake_cards,
    build_cards,
    load_cards,
)
from ontchatbot.runtime.sparql import load_ontology
from ontchatbot.settings import ONTOLOGY_PATH, QUERY_CATALOGUE_PATH


@pytest.fixture(scope="module")
def store():
    return load_ontology()


@pytest.fixture(scope="module")
def built(store):
    return build_cards(store)


@pytest.fixture
def baked(tmp_path):
    """Tệp nướng sẵn cùng hai tệp nguồn của nó, chép sang thư mục tạm."""

    ontology = tmp_path / "ontology.ttl"
    catalogue = tmp_path / "catalogue.jsonl"
    shutil.copy(ONTOLOGY_PATH, ontology)
    shutil.copy(QUERY_CATALOGUE_PATH, catalogue)
    cache = tmp_path / "cards.json"
    bake_cards(cache, ontology_path=ontology, catalogue_path=catalogue)
    return cache, ontology, catalogue


def _loaded(baked, store):
    cache, ontology, catalogue = baked
    return load_cards(
        store, ontology_path=ontology, catalogue_path=catalogue, cache_path=cache
    )


def test_the_baked_table_is_identical_to_the_one_built_from_the_graph(baked, store, built):
    """Đây là điều bước nướng chịu trách nhiệm: ghi ra rồi đọc lại không rơi gì."""
    assert _loaded(baked, store) == built


def test_a_missing_file_falls_back_to_building(tmp_path, store, built):
    """Thiếu tệp thì chậm hơn, không được hỏng."""
    assert load_cards(store, cache_path=tmp_path / "không-có.json") == built


@pytest.mark.parametrize(
    "damage",
    (
        pytest.param(lambda text: "{ đây không phải JSON", id="tệp hỏng"),
        pytest.param(lambda text: json.dumps({}), id="thiếu khoá"),
        pytest.param(
            lambda text: json.dumps(
                {**json.loads(text), "version": CARD_CACHE_VERSION + 1}
            ),
            id="phiên bản khác",
        ),
        pytest.param(
            lambda text: json.dumps({**json.loads(text), "fingerprint": "0" * 64}),
            id="vân tay khác",
        ),
    ),
)
def test_an_unusable_file_falls_back_to_building(baked, store, built, damage):
    """Mọi kiểu hỏng đều dẫn về việc dựng lại, không kiểu nào làm dịch vụ chết."""
    cache, _ontology, _catalogue = baked
    cache.write_text(damage(cache.read_text(encoding="utf-8")), encoding="utf-8")

    assert _loaded(baked, store) == built


def test_editing_the_ontology_retires_the_baked_table(baked, store, built):
    """Sửa ontology mà quên nướng lại thì bảng cũ bị bỏ, chứ không phục vụ tiếp.

    Đây là chỗ nguy hiểm nhất của mọi bộ nhớ đệm: nó vẫn đọc được, vẫn đúng định
    dạng, chỉ là nói về một ontology không còn tồn tại.

    Nên phép kiểm này cấy một thẻ đánh dấu vào tệp. Không có nó thì bảng nướng
    bằng đúng bảng dựng, và phép kiểm sẽ xanh dù tệp cũ có bị dùng nhầm hay không.
    """

    cache, ontology, catalogue = baked
    payload = json.loads(cache.read_text(encoding="utf-8"))
    payload["cards"].append(["dấu-đánh-riêng", [], "chữ", "SELECT ?x WHERE { }"])
    cache.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    marked = _loaded(baked, store)
    assert [card.query_id for card in marked].count("dấu-đánh-riêng") == 1, (
        "tệp nướng sẵn phải đang được dùng thật thì phép kiểm sau mới có nghĩa"
    )

    ontology.write_text(
        ontology.read_text(encoding="utf-8")
        + "\n:ThucTheMoi a <http://www.w3.org/2002/07/owl#NamedIndividual> .\n",
        encoding="utf-8",
    )

    after = _loaded(baked, store)
    assert "dấu-đánh-riêng" not in [card.query_id for card in after]
    assert after == built
