"""NLU: raw text → :class:`Query` (entities + intent + slots).

This is the rule-based **baseline** stand-in for the XLM-R two-head model
(step 3 swaps the body of :func:`understand` for one ONNX forward; the
:class:`Query` contract stays). Three jobs:

* **intent** — keyword rules over the diacritic-folded text. ``GREETING`` and
  the listing form are detected here; out-of-domain is *not* decided here —
  it emerges downstream when the anchor resolves to nothing (a query can name
  a real procedure with zero domain keywords).
* **anchor span** — interrogative fillers (``ở đâu``, ``bao nhiêu`` …) are
  stripped so the residual surface is close to the entity, which the
  rule-based matcher needs (the trained model will not).
* **slots** — cohort code (``K65``) and a CPA value, for the v9 ``filter_by``
  / ``reason`` handlers. Captured now, lightly used in v8.

Intent declares the *target relation/class*; the planner derives direction.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from .text import clean, strip_diacritics

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Entity:
    """One anchor candidate. ``tag`` empty means 'let the graph pick the
    class' — the rule-based baseline does not predict NER tags."""
    surface: str
    tag: str = ""


@dataclass
class Query:
    """An understood question threaded into the answer layer."""
    text: str                                   # cleaned, diacritics kept
    intent: str
    entities: list[Entity] = field(default_factory=list)
    slots: dict = field(default_factory=dict)
    is_listing: bool = False


# Intent vocabulary. ``ASK_*`` map to a target relation/class in answer.py;
# the three below are handled specially.
GREETING = "GREETING"
ASK_OVERVIEW = "ASK_OVERVIEW"     # describe the anchored entity (also the
                                  # fallback intent; OOD if anchor is empty)


# Keyword rules, evaluated in order — first hit wins. Keywords are matched on
# the diacritic-folded text so no-diacritic input ("dieu kien") still fires.
# Order encodes priority; document cues sit above office cues so "tải đơn …
# ở đâu" reads as a document download, while the explicit office guards in
# :func:`_classify` reclaim "… nộp phòng nào".
_GREETING = (
    "xin chao", "chao ", " chao", "hello", " hi ", "hey", "alo",
    "cam on", "thanks", "tks", "tam biet", "bye",
    "haha", "hihi", "hehe", "huhu",
)
_INTENT_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("ASK_CONDITION", ("dieu kien", "yeu cau gi", "can gi de", "can dieu kien")),
    ("ASK_PROCEDURE", ("phu trach", "xu ly gi", "lam nhung gi", "giai quyet gi")),
    ("ASK_REGULATION", ("quy dinh", "can cu", "quyet dinh nao", "van ban nao",
                        "theo qd")),
    ("ASK_OUTPUT", ("duoc gi", "nhan duoc gi", "ket qua la gi", "ket qua cua",
                    "ket qua nhan")),
    ("ASK_DOCUMENT", ("bieu mau", "mau don", "giay to", "ho so", "form",
                      "tai don", "tai bieu", "download", "don xin",
                      "don de nghi", "don gia han")),
    ("ASK_OFFICE", ("o dau", "dia chi", "lien he", "gap ai", "bo phan nao",
                    "phong nao", "email", "so dien thoai", "sdt",
                    "lam viec gio nao", "gio lam viec", "phong ban")),
    ("ASK_PAYMENT", ("thanh toan", "phuong thuc", "chuyen khoan",
                     "nop tien", "tra tien")),
    ("COMPARE", ("so sanh", "khac nhau", "khac gi", " hon ", "chenh lech")),
    ("ASK_STEP", ("cac buoc", "lam the nao", "thu tuc", "lam sao", "huong dan",
                  "tien hanh", "quy trinh", "cach ")),
)
# ASK_FEE needs "học phí/mức phí" *plus* a price marker (a cohort code also
# counts) so a bare "đóng học phí" still routes to the procedure, not a fee row.
_FEE_MARKERS = ("bao nhieu", "moi tin chi", "the nao", "ra sao", "muc")

# Fillers removed to build the anchor surface. Folded bigrams come first so a
# token that is filler *only in context* is protected elsewhere — e.g. "bao
# nhieu" drops as a pair while "bao" survives inside "bao luu" (bảo lưu); same
# for "tin chi" vs the entity word, and "the nao". Then a conservative set of
# single tokens that never appear in any entity label/alias.
_FILLER_BIGRAMS = frozenset((
    ("bao", "nhieu"), ("bao", "gio"), ("moi", "tin"), ("tin", "chi"),
    ("o", "dau"), ("the", "nao"), ("nhu", "the"), ("ra", "sao"), ("la", "gi"),
    ("cho", "hoi"), ("thong", "tin"), ("gioi", "thieu"), ("lien", "he"),
    ("co", "nhung"), ("can", "gi"), ("dia", "chi"),
))
# Only unambiguous interrogative/politeness tokens — every entry is verified
# to never appear (diacritic-folded) inside a real entity label or alias.
# Context-sensitive ones (ban=bạn/ban, co=có/cơ, de=để/đề, the=thế/thể, la, ra)
# are left to the bigram rules so the entity sense survives.
_FILLER_TOKENS = frozenset((
    "cho", "hoi", "muon", "minh", "toi", "vay", "nhi", "giup", "xem",
    "duoc", "khong", "nao", "gi", "ve", "cach", "can", "nhung",
    "san", "sao", "lam", "viec", "gio",
))

_RE_COHORT = re.compile(r"\bk\s?(\d{2})\b", re.IGNORECASE)
_RE_CPA = re.compile(r"\b(?:cpa|gpa|diem|dtb)\D{0,8}(\d(?:[.,]\d+)?)\b", re.IGNORECASE)
_RE_LISTING = (
    re.compile(r"\bnhung\b.*\b(nao|gi)\b"),
    re.compile(r"\bco\b.*\bnhung\b"),
    re.compile(r"\bnao\b.*\bco\b"),
    re.compile(r"\bco san\b"),
    re.compile(r"\bliet ke\b"),
)


def understand(text: str) -> Query:
    """Raw user text → :class:`Query`. Pure function; no model, no I/O."""
    cleaned = clean(text)
    folded = strip_diacritics(cleaned.lower())
    if not cleaned:
        return Query(text="", intent=GREETING)

    if _is_greeting(folded):
        return Query(text=cleaned, intent=GREETING)

    # Slots come from the *raw* (pre-expansion) text: teencode would rewrite
    # "cpa" → "điểm trung bình tích luỹ" and break the CPA regex.
    raw_folded = strip_diacritics((text or "").lower())
    slots: dict = {}
    if (m := _RE_COHORT.search(raw_folded)):
        slots["cohort"] = "K" + m.group(1)
    if (m := _RE_CPA.search(raw_folded)):
        slots["cpa"] = float(m.group(1).replace(",", "."))

    listing = any(p.search(folded) for p in _RE_LISTING)
    intent = ASK_OVERVIEW if listing else _classify(folded, slots)

    surface = _anchor_surface(cleaned)
    entities = [Entity(surface=surface)] if surface else []
    log.info("[nlu] intent=%s listing=%s surface=%r slots=%s",
             intent, listing, surface, slots)
    return Query(text=cleaned, intent=intent, entities=entities,
                 slots=slots, is_listing=listing)


def _is_greeting(folded: str) -> bool:
    padded = f" {folded} "
    return any(k in padded for k in _GREETING)


def _classify(folded: str, slots: dict) -> str:
    # Eligibility: a CPA value (or "đủ điều kiện") aimed at graduation.
    if "du dieu kien" in folded or (
        ("cpa" in slots) and any(k in folded for k in ("tot nghiep", "ra truong"))):
        return "ELIGIBILITY"
    # Office reclaims the document/office overlap when the focus is "which
    # office" rather than "where to download".
    if "phong nao" in folded or ("nop" in folded and "phong" in folded):
        return "ASK_OFFICE"
    # Fee needs the entity word *and* a price marker (cohort code counts).
    if ("hoc phi" in folded or "muc phi" in folded) and (
        "cohort" in slots or any(k in folded for k in _FEE_MARKERS)):
        return "ASK_FEE"
    for intent, keys in _INTENT_RULES:
        if any(k in folded for k in keys):
            return intent
    return ASK_OVERVIEW


def _anchor_surface(cleaned: str) -> str:
    """Strip interrogative fillers, leaving the entity-bearing residue.

    Folded tokens drive the decision; the original (diacritic) spelling is
    kept by mapping positionally — the fuzzy index matches better on real
    spelling. Returns the whole input if stripping would empty it.
    """
    orig = cleaned.split()
    fold = strip_diacritics(cleaned.lower()).split()
    drop = [False] * len(orig)
    for i in range(len(fold) - 1):
        if (fold[i], fold[i + 1]) in _FILLER_BIGRAMS:
            drop[i] = drop[i + 1] = True
    for i, f in enumerate(fold):
        if f in _FILLER_TOKENS:
            drop[i] = True
    kept = [orig[i] for i in range(len(orig)) if not drop[i]]
    return " ".join(kept).strip() or cleaned
