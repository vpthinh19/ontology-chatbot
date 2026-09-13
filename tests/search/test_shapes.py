"""Dữ liệu thật phải khớp cấu trúc khai báo trong shapes.ttl.

shapes.ttl nói mỗi loại thông tin có những ô nào, ô nào bắt buộc, nhận mấy giá trị, là
chữ hay trỏ tới loại nào. Trang quản trị sẽ sinh form và kiểm dữ liệu nhập từ cùng tệp
này, nên mọi đợt nhập dữ liệu bằng script cũng phải qua đây trước khi commit.
"""

from __future__ import annotations

import pyoxigraph as oxi
import pyshacl
import pytest
from rdflib import Dataset, Graph, Literal, Namespace, URIRef

from ontchatbot.settings import ONTOLOGY_NS, ONTOLOGY_PATH

SHAPES_PATH = ONTOLOGY_PATH.with_name("shapes.ttl")
SH = Namespace("http://www.w3.org/ns/shacl#")
RDF_TYPE = oxi.NamedNode("http://www.w3.org/1999/02/22-rdf-syntax-ns#type")


@pytest.fixture(scope="module")
def shapes() -> Graph:
    return Graph().parse(SHAPES_PATH, format="turtle")


def test_data_conforms_to_the_shapes(shapes) -> None:
    dataset = Dataset()
    dataset.parse(ONTOLOGY_PATH, format="trig")
    data = Graph()
    for s, p, o, _ in dataset.quads((None, None, None, None)):
        data.add((s, p, o))
    conforms, _, report = pyshacl.validate(data, shacl_graph=shapes, inference="none")
    assert conforms, report


def test_sourced_properties_sit_in_a_citation_bag(shapes) -> None:
    """Ô đánh dấu :batBuocNguon true không được có câu nằm ngoài mọi túi trích dẫn."""

    store = oxi.Store()
    store.load(path=str(ONTOLOGY_PATH), format=oxi.RdfFormat.TRIG)
    bat_buoc = URIRef(ONTOLOGY_NS + "batBuocNguon")
    khong_nguon = []
    for shape, lop in shapes.subject_objects(SH.targetClass):
        for prop in shapes.objects(shape, SH.property):
            if shapes.value(prop, bat_buoc) != Literal(True):
                continue
            path = oxi.NamedNode(str(shapes.value(prop, SH.path)))
            for kieu in store.quads_for_pattern(None, RDF_TYPE, oxi.NamedNode(str(lop)), oxi.DefaultGraph()):
                for cau in store.quads_for_pattern(kieu.subject, path, None, oxi.DefaultGraph()):
                    khong_nguon.append(f"{cau.subject.value.rsplit('#', 1)[-1]} · {path.value.rsplit('#', 1)[-1]}")
    assert not khong_nguon, khong_nguon
