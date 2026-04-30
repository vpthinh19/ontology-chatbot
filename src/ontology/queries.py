"""SPARQL queries tailored per ontology class.

Each ontology class exposes a different set of properties and object relations.
A single generic SPARQL pattern would either over-fetch or miss class-specific
fields, so we maintain a focused query per class. All queries return JSON-like
dictionaries to decouple downstream rendering from RDF specifics.
"""

from __future__ import annotations

from typing import Any

from owlready2 import default_world

from ..config import ONTOLOGY_NS
from .loader import load_ontology

NS = ONTOLOGY_NS
PREFIXES = f"PREFIX : <{NS}>\nPREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>\n"


def _q(sparql: str) -> list[list[Any]]:
    """Run a SPARQL SELECT against the loaded world."""
    load_ontology()
    return list(default_world.sparql(PREFIXES + sparql))


def _lit(values, default=None):
    """Pick the first non-empty literal from a SPARQL result row column."""
    for v in values or []:
        if v is not None and str(v).strip():
            return str(v)
    return default


def _name(ind) -> str:
    return getattr(ind, "name", str(ind))


# Per-class fetch functions. Each receives the local name of the individual
# (e.g. ``QuyTrinh_BaoLuu``) and returns a flat dict of fields.

def fetch_quy_trinh(local: str) -> dict:
    """AcademicProcedure: description, regulation, channel, office, conditions, docs, outputs, steps, fees."""
    rows = _q(f"""
    SELECT ?desc ?dec ?vid WHERE {{
      OPTIONAL {{ :{local} :procedureDescription ?desc }}
      OPTIONAL {{ :{local} :appliedDecision ?dec }}
      OPTIONAL {{ :{local} :videoURL ?vid }}
    }}""")
    desc = dec = vid = None
    if rows:
        desc, dec, vid = rows[0]

    def linked(prop: str) -> list[str]:
        r = _q(f"SELECT ?x WHERE {{ :{local} :{prop} ?x }}")
        return [_name(row[0]) for row in r if row[0] is not None]

    return {
        "kind": "QuyTrinhHocVu",
        "iri": local,
        "description": str(desc) if desc else None,
        "decision": str(dec) if dec else None,
        "video_url": str(vid) if vid else None,
        "handled_by": linked("handledBy"),
        "executed_via": linked("executedVia"),
        "based_on": linked("basedOnRegulation"),
        "conditions": linked("hasCondition"),
        "documents": linked("requiresDocument"),
        "outputs": linked("hasOutput"),
        "steps": linked("hasStep"),
        "fees": linked("hasFeeCategory"),
        "payments": linked("hasPaymentMethod"),
    }


def fetch_phong_ban(local: str) -> dict:
    """AdministrativeOffice: contact details."""
    rows = _q(f"""
    SELECT ?head ?email ?loc ?phone ?web WHERE {{
      OPTIONAL {{ :{local} :headOfOffice ?head }}
      OPTIONAL {{ :{local} :officeEmail ?email }}
      OPTIONAL {{ :{local} :officeLocation ?loc }}
      OPTIONAL {{ :{local} :officePhoneNumber ?phone }}
      OPTIONAL {{ :{local} :officeWebsite ?web }}
    }}""")
    head = email = loc = phone = web = None
    if rows:
        head, email, loc, phone, web = rows[0]
    return {
        "kind": "PhongBanHanhChinh",
        "iri": local,
        "head": str(head) if head else None,
        "email": str(email) if email else None,
        "location": str(loc) if loc else None,
        "phone": str(phone) if phone else None,
        "website": str(web) if web else None,
    }


def fetch_tai_lieu(local: str) -> dict:
    """Document: form download URL."""
    rows = _q(f"SELECT ?url WHERE {{ :{local} :formUrl ?url }}")
    url = rows[0][0] if rows else None
    return {"kind": "TaiLieuBieuMau", "iri": local, "form_url": str(url) if url else None}


def fetch_dinh_muc(local: str) -> dict:
    """FeeCategory: fee per credit, target programmes, applied decision."""
    rows = _q(f"""
    SELECT ?fee ?dec ?tgt ?note WHERE {{
      OPTIONAL {{ :{local} :feePerCredit ?fee }}
      OPTIONAL {{ :{local} :appliedDecision ?dec }}
      OPTIONAL {{ :{local} :appliesToTarget ?tgt }}
      OPTIONAL {{ :{local} :feeNote ?note }}
    }}""")
    fee = dec = tgt = note = None
    if rows:
        fee, dec, tgt, note = rows[0]
    return {
        "kind": "DinhMucHocPhi",
        "iri": local,
        "fee_per_credit": int(fee) if fee is not None else None,
        "decision": str(dec) if dec else None,
        "target": str(tgt) if tgt else None,
        "note": str(note) if note else None,
    }


def fetch_phuong_thuc(local: str) -> dict:
    """PaymentMethod: identifier-only individuals; humanised name suffices."""
    return {"kind": "PhuongThucThanhToan", "iri": local}


FETCHERS = {
    "QuyTrinhHocVu": fetch_quy_trinh,
    "PhongBanHanhChinh": fetch_phong_ban,
    "TaiLieuBieuMau": fetch_tai_lieu,
    "DinhMucHocPhi": fetch_dinh_muc,
    "PhuongThucThanhToan": fetch_phuong_thuc,
}


def fetch(tag: str, individual_local: str) -> dict | None:
    """Dispatch to the per-class fetcher and return a normalised record."""
    fn = FETCHERS.get(tag)
    return fn(individual_local) if fn else None
