"""Diacritic normalisation utility used by the greeting heuristic.

Historically this module hosted a synthetic-template generator. After the
project switched to a hand-curated source corpus
(:mod:`ontchatbot.data.sources`) the module was reduced to the single Unicode
helper still consumed by :mod:`ontchatbot.core.pipeline`.
"""

from __future__ import annotations

# Vietnamese vowel groups paired with their unaccented Latin equivalent.
_GROUPS: tuple[tuple[str, str], ...] = (
    ("àáảãạâầấẩẫậăằắẳẵặ", "a"),
    ("èéẻẽẹêềếểễệ", "e"),
    ("ìíỉĩị", "i"),
    ("òóỏõọôồốổỗộơờớởỡợ", "o"),
    ("ùúủũụưừứửữự", "u"),
    ("ỳýỷỹỵ", "y"),
    ("đ", "d"),
)
_VOWELS = "".join(g for g, _ in _GROUPS)
_PLAIN = "".join(p * len(g) for g, p in _GROUPS)
assert len(_VOWELS) == len(_PLAIN), (len(_VOWELS), len(_PLAIN))
_DIACRITIC_TABLE = str.maketrans(_VOWELS + _VOWELS.upper(),
                                 _PLAIN + _PLAIN.upper())


def strip_diacritics(s: str) -> str:
    """Return ``s`` with every Vietnamese tone mark removed."""
    return s.translate(_DIACRITIC_TABLE)
