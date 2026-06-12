"""NLU: raw text → :class:`Query` (mentions split into subject + constraints).

This is the rule-based **baseline** stand-in for the XLM-R two-head model.
Step 3 swaps the *recognition* for one ONNX forward (token head: spans with
class tags; sentence head: GREETING/QUERY/OOD); the :class:`Query` contract
and everything downstream stay.

The mechanism mirrors the target architecture exactly:

* **scan** — longest-match, left-to-right, non-overlapping matching of the
  normalised text against the graph's *lexicon* (danh bạ). A row that names a
  **class** ("học phí", "phòng ban") yields a SUBJECT mention; a row that
  names an **individual** ("k65", "bảo lưu") yields a CONSTRAINT mention.
  Ties at equal length: class beats individual ("học phí" reads as the fee
  class, not the fee-payment procedure's alias; "đóng học phí" is longer and
  picks the procedure naturally).
* **interrogatives** — a small closed table of pure question phrases
  ("phụ trách gì" → QuyTrinhHocVu). They are subject mentions the trained
  model will tag from context; the table is baseline-only and is *never*
  extended per edge case (misses become test rows for step 3, not new rules).
* **subject choice** — one subject per query (scope decision 2026-06-13):
  a cue-marked mention (interrogative, or a class mention right before a
  question word) wins over a plain class mention; first occurrence wins
  within a rank. Leftover subject classes are reported for the
  "ask separately" notice. No subject mention at all → the first
  constraint's own class (self-description), else out-of-domain.

There is no fuzzy scoring, no threshold, no intent table and no slot regex —
those died with the query-graph redesign (docs/redesign/03).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from .text import clean, normalize_for_match

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Mention:
    """One linked span. ``kind`` is ``subject`` (names a class — an open
    variable) or ``constraint`` (names an individual — a constant)."""
    surface: str
    cls: str
    kind: str
    iri: str = ""
    cue: bool = False     # subject carried interrogative force
    listable: bool = False  # subject backed by a real class-label row


@dataclass
class Query:
    """An understood question threaded into the answer layer."""
    text: str
    act: str                                    # GREETING | QUERY
    subject_cls: str = ""
    subject_listable: bool = False
    constraints: list[Mention] = field(default_factory=list)
    extra_subjects: list[str] = field(default_factory=list)  # class labels


GREETING = "GREETING"
QUERY = "QUERY"


_GREETING_KEYS = (
    "xin chao", "chao ", " chao", "hello", " hi ", "hey", "alo",
    "cam on", "thanks", "tks", "tam biet", "bye",
    "haha", "hihi", "hehe", "huhu",
)

# Closed interrogative table (folded) — pure question phrases the trained NER
# will tag from context. Policy: NEVER grown per edge case.
_INTERROGATIVES: dict[str, str] = {
    "phu trach gi": "QuyTrinhHocVu",
    "phu trach nhung gi": "QuyTrinhHocVu",
    "xu ly gi": "QuyTrinhHocVu",
    "xu ly nhung gi": "QuyTrinhHocVu",
    "nop o dau": "PhongBanHanhChinh",
    "nop o phong nao": "PhongBanHanhChinh",
    "nop phong nao": "PhongBanHanhChinh",
    "nop cho ai": "PhongBanHanhChinh",
    "lien he ai": "PhongBanHanhChinh",
    "gap ai": "PhongBanHanhChinh",
    "duoc khong": "DieuKien",
    "du dieu kien": "DieuKien",
    "can gi": "DieuKien",
    "can nhung gi": "DieuKien",
    "bao nhieu": "DinhMucHocPhi",
    "duoc gi": "KetQuaDauRa",
    "nhan duoc gi": "KetQuaDauRa",
    "can cu nao": "QuyDinh",
    "quyet dinh nao": "QuyDinh",
}

# Question words that mark the class mention right before them as the asked
# thing ("cần giấy tờ GÌ" → giấy tờ is the subject even if another class
# mention came first).
_CUE_TOKENS = frozenset(("gi", "nao", "dau", "sao", "nhieu", "khong", "may"))
_CUE_WINDOW = 2


def understand(text: str, lexicon) -> Query:
    """Raw user text → :class:`Query`.

    ``lexicon`` is any iterable of rows with ``phrase/kind/cls/iri``
    attributes (duck-typed so this module never imports the graph — the
    dependency arrow stays text → nlu → graph → answer).
    """
    cleaned = clean(text)
    folded = normalize_for_match(cleaned)
    if not folded:
        return Query(text="", act=GREETING)
    if _is_greeting(folded):
        return Query(text=cleaned, act=GREETING)

    mentions = _scan(folded, lexicon)
    subject, listable, extras = _choose_subject(mentions)
    constraints = [m for m in mentions if m.kind == "constraint"]
    q = Query(text=cleaned, act=QUERY,
              subject_cls=subject, subject_listable=listable,
              constraints=constraints, extra_subjects=extras)
    log.info("[nlu] subject=%s listable=%s constraints=%s extras=%s",
             subject, listable, [(m.surface, m.cls) for m in constraints],
             extras)
    return q


def _is_greeting(folded: str) -> bool:
    padded = f" {folded} "
    return any(k in padded for k in _GREETING_KEYS)


# Scanning — longest-match, left-to-right, non-overlapping.

def _scan(folded: str, lexicon) -> list[Mention]:
    index, max_len = _index(lexicon)
    tokens = folded.split()
    out: list[Mention] = []
    i = 0
    while i < len(tokens):
        hit = None
        for ln in range(min(max_len, len(tokens) - i), 0, -1):
            phrase = " ".join(tokens[i:i + ln])
            entry = index.get(phrase)
            if entry is not None:
                hit = (entry, ln)
                break
        if hit is None:
            i += 1
            continue
        entry, ln = hit
        kind, cls, iri, listable = entry
        cue = kind == "subject" and iri == "?"          # interrogative row
        if kind == "subject" and not cue:
            nxt = tokens[i + ln:i + ln + _CUE_WINDOW]
            cue = any(t in _CUE_TOKENS for t in nxt)
        out.append(Mention(surface=phrase, cls=cls, kind=kind,
                           iri="" if kind == "subject" else iri,
                           cue=cue, listable=listable))
        i += ln
    return out


def _index(lexicon) -> tuple[dict, int]:
    """phrase → (kind, cls, iri, listable). Precedence on duplicate phrases:
    interrogative > class > individual."""
    rank = {"interrog": 2, "class": 1, "individual": 0}
    best: dict[str, tuple[int, tuple]] = {}

    def put(phrase: str, src: str, row: tuple) -> None:
        cur = best.get(phrase)
        if cur is None or rank[src] > cur[0]:
            best[phrase] = (rank[src], row)

    for e in lexicon:
        if e.kind == "class":
            put(e.phrase, "class", ("subject", e.cls, "", True))
        else:
            put(e.phrase, "individual", ("constraint", e.cls, e.iri, False))
    for phrase, cls in _INTERROGATIVES.items():
        put(phrase, "interrog", ("subject", cls, "?", False))

    index = {p: row for p, (_r, row) in best.items()}
    max_len = max((p.count(" ") + 1 for p in index), default=1)
    return index, max_len


# Subject choice — one per query.

def _choose_subject(mentions: list[Mention]) -> tuple[str, bool, list[str]]:
    subs = [m for m in mentions if m.kind == "subject"]
    if not subs:
        return "", False, []
    ranked = [m for m in subs if m.cue] + [m for m in subs if not m.cue]
    chosen = ranked[0]
    # Listing needs a real class-label mention of the chosen class — a bare
    # interrogative ("bao nhiêu?") must not unleash a full class dump.
    listable = any(m.listable and m.cls == chosen.cls for m in subs)
    constraint_classes = {m.cls for m in mentions if m.kind == "constraint"}
    extras: list[str] = []
    for m in subs:
        if m.cls != chosen.cls and m.cls not in constraint_classes \
                and m.cls not in extras:
            extras.append(m.cls)
    return chosen.cls, listable, extras
