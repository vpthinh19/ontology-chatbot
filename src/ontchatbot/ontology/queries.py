"""Per-class SPARQL queries against the loaded ontology.

Each NER tag has its own ``fetch_*`` function returning a flat record dict.
A single generic SPARQL pattern would either over-fetch (because individual
classes expose disjoint property sets) or miss class-specific fields, so we
maintain one focused query per class.

Owlready2's SPARQL engine struggles with multiple ``OPTIONAL`` clauses sharing
a common subject (its SQL translator emits malformed joins), so each property
is queried with a small single-pattern SELECT. The resulting queries are tiny
and cached at the SQLite layer, keeping latency negligible.
"""

from __future__ import annotations

import logging

from owlready2 import default_world

from .loader import load_ontology

log = logging.getLogger(__name__)

_PREFIXES = """
PREFIX : <http://www.ntu.edu.vn/ontology/academic#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
"""


def _sparql(query: str) -> list[list]:
    """Run a SELECT against the loaded world.

    ``error_on_undefined_entities=False`` lets us probe IRIs that may have been
    proposed by fuzzy matching but were filtered out of the ontology — the
    query simply returns an empty result set instead of raising.
    """
    load_ontology()
    return list(default_world.sparql(_PREFIXES + query,
                                     error_on_undefined_entities=False))


def _name(node) -> str:
    return getattr(node, "name", str(node)) if node is not None else ""


def _str(node) -> str | None:
    s = str(node).strip() if node is not None else ""
    return s or None


def _scalar(local: str, predicate: str) -> str | None:
    """First literal value of ``local <predicate> ?x`` or ``None``."""
    triple = (f":{local} {predicate} ?x" if predicate.startswith("rdfs:")
              else f":{local} :{predicate} ?x")
    rows = _sparql(f"SELECT ?x WHERE {{ {triple} }}")
    return _str(rows[0][0]) if rows else None


def _linked(local: str, prop: str) -> list[dict]:
    """All ``local prop ?x`` together with each ``?x`` rdfs:label and formUrl."""
    rows = _sparql(f"""
    SELECT ?x ?lbl ?url WHERE {{
      :{local} :{prop} ?x .
      OPTIONAL {{ ?x rdfs:label ?lbl }}
      OPTIONAL {{ ?x :formUrl ?url }}
    }}""")
    return [{"name": _name(r[0]), "label": _str(r[1]), "url": _str(r[2])}
            for r in rows]


# Per-class fetchers

def fetch_quy_trinh(local: str) -> dict:
    """``AcademicProcedure`` — description, decision, video, and linked entities."""
    return {
        "kind": "QuyTrinhHocVu",
        "iri": local,
        "label": _scalar(local, "rdfs:label"),
        "description": _scalar(local, "procedureDescription"),
        "decision": _scalar(local, "appliedDecision"),
        "video_url": _scalar(local, "videoURL"),
        "fee_note": _scalar(local, "feeNote"),
        "handled_by": _linked(local, "handledBy"),
        "executed_via": _linked(local, "executedVia"),
        "based_on": _linked(local, "basedOnRegulation"),
        "conditions": _linked(local, "hasCondition"),
        "documents": _linked(local, "requiresDocument"),
        "outputs": _linked(local, "hasOutput"),
        "steps": _linked(local, "hasStep"),
        "fees": _linked(local, "hasFeeCategory"),
        "payments": _linked(local, "hasPaymentMethod"),
    }


def fetch_phong_ban(local: str) -> dict:
    """``AdministrativeOffice`` — contact card."""
    return {
        "kind": "PhongBanHanhChinh",
        "iri": local,
        "label": _scalar(local, "rdfs:label"),
        "head": _scalar(local, "headOfOffice"),
        "email": _scalar(local, "officeEmail"),
        "location": _scalar(local, "officeLocation"),
        "phone": _scalar(local, "officePhoneNumber"),
        "website": _scalar(local, "officeWebsite"),
    }


def fetch_tai_lieu(local: str) -> dict:
    """``Document`` — downloadable form."""
    return {
        "kind": "TaiLieuBieuMau",
        "iri": local,
        "label": _scalar(local, "rdfs:label"),
        "form_url": _scalar(local, "formUrl"),
    }


def fetch_dinh_muc(local: str) -> dict:
    """``FeeCategory`` — fee per credit, target programmes, decision."""
    fee = _scalar(local, "feePerCredit")
    return {
        "kind": "DinhMucHocPhi",
        "iri": local,
        "label": _scalar(local, "rdfs:label"),
        "fee_per_credit": int(fee) if fee and fee.lstrip("-").isdigit() else None,
        "decision": _scalar(local, "appliedDecision"),
        "target": _scalar(local, "appliesToTarget"),
        "based_on": _linked(local, "basedOnRegulation"),
    }


def fetch_phuong_thuc(local: str) -> dict:
    """``PaymentMethod`` — label-only individuals."""
    return {
        "kind": "PhuongThucThanhToan",
        "iri": local,
        "label": _scalar(local, "rdfs:label"),
    }


FETCHERS = {
    "QuyTrinhHocVu": fetch_quy_trinh,
    "PhongBanHanhChinh": fetch_phong_ban,
    "TaiLieuBieuMau": fetch_tai_lieu,
    "DinhMucHocPhi": fetch_dinh_muc,
    "PhuongThucThanhToan": fetch_phuong_thuc,
}


def _exists(individual: str) -> bool:
    """True iff ``individual`` is asserted in the ontology."""
    onto = load_ontology()
    return onto[individual] is not None


def fetch(tag: str, individual: str) -> dict | None:
    fn = FETCHERS.get(tag)
    if not fn:
        log.warning("[fetch] unknown tag=%s", tag)
        return None
    if not _exists(individual):
        log.warning("[fetch] individual not found tag=%s iri=%s", tag, individual)
        return None
    rec = fn(individual)
    log.info("[fetch] tag=%s iri=%s keys=%s",
             tag, individual, sorted(k for k, v in rec.items() if v))
    return rec
