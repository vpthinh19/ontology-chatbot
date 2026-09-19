"""IRI dùng chung, cách viết gọn chúng, và nạp tệp TriG."""

from __future__ import annotations

from pathlib import Path

import pyoxigraph as oxi

from .settings import ONTOLOGY_NS

RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
RDFS = "http://www.w3.org/2000/01/rdf-schema#"
SKOS = "http://www.w3.org/2004/02/skos/core#"
XSD = "http://www.w3.org/2001/XMLSchema#"
SH = "http://www.w3.org/ns/shacl#"

RDF_TYPE = oxi.NamedNode(RDF + "type")
RDFS_LABEL = oxi.NamedNode(RDFS + "label")
SKOS_ALT_LABEL = oxi.NamedNode(SKOS + "altLabel")
#: Câu nằm ngoài mọi túi trích dẫn: danh tính, tầng nguồn, điều dự án tự khẳng định.
OUTSIDE = oxi.DefaultGraph()


def local_name(iri: str) -> str:
    """Phần sau dấu # (hoặc dấu / cuối) của IRI, ví dụ ``nopTai``."""

    text = str(iri)
    return text.rsplit("#", 1)[-1] if "#" in text else text.rsplit("/", 1)[-1]


def local_id(iri: str) -> str:
    """IRI trong namespace học vụ thành định danh ``TenCucBo``; IRI khác giữ nguyên."""

    return str(iri).removeprefix(ONTOLOGY_NS)


def compact(iri: str) -> str:
    """IRI trong namespace học vụ thành ``:TenCucBo``; IRI khác giữ nguyên."""

    text = str(iri)
    return ":" + text[len(ONTOLOGY_NS):] if text.startswith(ONTOLOGY_NS) else text


def expand(text: str) -> str:
    """Ngược lại của ``compact``."""

    return ONTOLOGY_NS + text[1:] if text.startswith(":") else text


def term(local: str) -> oxi.NamedNode:
    """NamedNode của định danh ``local`` trong namespace học vụ."""

    return oxi.NamedNode(ONTOLOGY_NS + local)


def load_trig(path: Path | str) -> oxi.Store:
    store = oxi.Store()
    store.load(path=str(path), format=oxi.RdfFormat.TRIG)
    return store
