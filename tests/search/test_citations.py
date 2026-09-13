"""Trích dẫn trên ontology thật: mỗi câu nằm đúng chỗ văn bản nói ra nó.

Dữ liệu cũ chỉ ghi nguồn cho cả thực thể, và bộ chuyển đổi từng chép mọi câu của
thực thể vào mọi túi của nó: "4 tín chỉ" bị dẫn sang bảng không có cột tín chỉ,
"nộp tiền mặt tại quầy" bị dẫn sang phương thức quét mã QR. Các phép kiểm dưới đây
bắt đúng dấu vết mà lỗi đó để lại.
"""

from __future__ import annotations

import re
from collections import defaultdict

import pyoxigraph as oxi
import pytest

from ontchatbot.settings import ONTOLOGY_NS, ONTOLOGY_PATH

RDF_TYPE = oxi.NamedNode("http://www.w3.org/1999/02/22-rdf-syntax-ns#type")
DIA_CHI_TRICH_DAN = oxi.NamedNode(ONTOLOGY_NS + "DiaChiTrichDan")
TOA_DO = oxi.NamedNode(ONTOLOGY_NS + "toaDo")
THUOC_NGUON = oxi.NamedNode(ONTOLOGY_NS + "thuocNguon")


@pytest.fixture(scope="module")
def store() -> oxi.Store:
    store = oxi.Store()
    store.load(path=str(ONTOLOGY_PATH), format=oxi.RdfFormat.TRIG)
    return store


@pytest.fixture(scope="module")
def dia_chi(store) -> dict[oxi.NamedNode, tuple[str, str]]:
    """Địa chỉ trích dẫn -> (nguồn, toạ độ)."""

    ra = {}
    for quad in store.quads_for_pattern(None, RDF_TYPE, DIA_CHI_TRICH_DAN, None):
        nguon = next(store.quads_for_pattern(quad.subject, THUOC_NGUON, None, None)).object.value
        toa_do = next(store.quads_for_pattern(quad.subject, TOA_DO, None, None)).object.value
        ra[quad.subject] = (nguon, toa_do)
    return ra


def _ten(term) -> str:
    return term.value.rsplit("#", 1)[-1] if isinstance(term, oxi.NamedNode) else term.value


def test_every_citation_address_cites_something(store, dia_chi) -> None:
    """Địa chỉ không chứa câu nào là bộ máy chết: nó chỉ còn vì một thực thể từng dẫn tới."""

    co_cau = {quad.graph_name for quad in store.quads_for_pattern(None, None, None, None)}
    rong = sorted(f"{toa_do} ({_ten(oxi.NamedNode(nguon))})"
                  for iri, (nguon, toa_do) in dia_chi.items() if iri not in co_cau)
    assert not rong, f"địa chỉ trích dẫn rỗng: {rong}"


def test_no_two_addresses_name_the_same_place(dia_chi) -> None:
    dem = defaultdict(list)
    for iri, cho in dia_chi.items():
        dem[cho].append(_ten(iri))
    trung = {cho: ten for cho, ten in dem.items() if len(ten) > 1}
    assert not trung, f"một chỗ trong văn bản bị dựng thành nhiều địa chỉ: {trung}"


def test_a_document_states_each_fact_in_one_place(store, dia_chi) -> None:
    """Một câu nằm ở hai chỗ của CÙNG một văn bản gần như luôn là câu bị chép sang chỗ
    không nói ra nó. Hai văn bản độc lập cùng nêu một điều thì được phép."""

    theo_cau = defaultdict(list)
    for quad in store.quads_for_pattern(None, None, None, None):
        if quad.graph_name in dia_chi:
            theo_cau[(quad.subject, quad.predicate, quad.object)].append(dia_chi[quad.graph_name])
    lap = sorted(
        f"{_ten(s)} · {_ten(p)} · {_ten(o)[:40]} → {sorted(toa for _, toa in cho)}"
        for (s, p, o), cho in theo_cau.items()
        if len({nguon for nguon, _ in cho}) < len(cho)
    )
    assert not lap, "câu lặp trong cùng một văn bản:\n" + "\n".join(lap)


def test_a_whole_article_is_cited_only_when_nothing_finer_exists(dia_chi) -> None:
    """Dẫn "Điều 24" trong khi đã có "khoản 3 Điều 24" là dấu hiệu câu được gán theo
    nguồn của cả thực thể, chứ không theo khoản thật sự nói ra nó."""

    theo_nguon = defaultdict(set)
    for nguon, toa_do in dia_chi.values():
        theo_nguon[nguon].add(toa_do)
    tho = sorted(
        f"{toa_do} ({_ten(oxi.NamedNode(nguon))})"
        for nguon, cac_toa_do in theo_nguon.items()
        for toa_do in cac_toa_do
        if re.fullmatch(r"Điều \d+", toa_do)
        and any(khac.endswith(" " + toa_do) for khac in cac_toa_do)
    )
    assert not tho, f"trích dẫn cả điều dù có địa chỉ mịn hơn: {tho}"


def test_a_coordinate_reads_as_a_finished_phrase(dia_chi) -> None:
    lung = sorted(toa_do for _, toa_do in dia_chi.values()
                  if toa_do != toa_do.strip() or toa_do.endswith((",", ";")))
    assert not lung, f"toạ độ đọc lửng: {lung}"
