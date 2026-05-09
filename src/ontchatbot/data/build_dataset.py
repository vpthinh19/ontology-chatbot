"""Compile the hand-curated source corpus into static train / test JSONL.

The dataset itself is *static* — it lives in :mod:`ontchatbot.data.sources`
as an explicit Python list of ``(text, [(surface, tag), …])`` tuples. This
compiler does only deterministic, reproducible work:

1. word-segment each text via ``underthesea`` (PhoBERT was pre-trained on
   word-segmented Vietnamese);
2. align each annotated surface to a contiguous run of tokens, emitting BIO
   tags with strict no-overlap accounting;
3. split deterministically into train / test via a content-hash so the
   partition is stable across re-compiles even if the source list grows.

There is no randomness, no template expansion, no stochastic noise: the
JSONL produced here is a faithful one-to-one materialisation of the
human-authored source.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from ..core.config import MAX_LENGTH, ARTIFACTS_DIR, TEST_PATH, TRAIN_PATH
from ..ner.preprocessing import Preprocessor
from ..viz.distributions import plot_label_distribution, plot_length_distribution
from .sources import SAMPLES, Sample

# All text passes through the singleton Preprocessor — same code path used
# by the inference pipeline, modulo the abbrev/teen-code expansion which is
# inference-only (training samples are already authored in expanded form).
_PRE = Preprocessor.get()


def _normalize(text: str) -> str:
    """Light NFC + underthesea normalisation. The full ``clean()`` path
    (URL strip, sticky-acronym splitting, teen-code expansion) is **not**
    applied here — training data is hand-curated in already-expanded form,
    so character-level alignment of authored surfaces still works."""
    return _PRE.normalize(text)


def _segment(text: str) -> list[str]:
    """Word-segment with underthesea; returns underscore-joined tokens."""
    return Preprocessor.segment(text)


def _char_spans(text: str, tokens: list[str]) -> list[tuple[int, int]]:
    """Return ``[(start, end)]`` of each token's character range in ``text``.

    The underscore in an underthesea token represents a space in the source
    text, so we walk the source linearly looking up each token's readable
    form. This gives us a precise character-level index that downstream
    alignment can use even when the segmenter glues unrelated words
    together (e.g. ``có_học``) — a frequent edge case in conversational
    Vietnamese.
    """
    spans: list[tuple[int, int]] = []
    pos = 0
    for tok in tokens:
        readable = tok.replace("_", " ")
        idx = text.find(readable, pos)
        if idx < 0:
            raise ValueError(
                f"token {tok!r} not locatable from pos={pos} in {text!r}"
            )
        spans.append((idx, idx + len(readable)))
        pos = idx + len(readable)
    return spans


def align(sample: Sample) -> dict:
    """Render one ``(text, entities)`` source row into ``{tokens, ner_tags}``.

    Alignment is *character-driven*: for each annotated surface we find its
    character span in the source text (case-insensitive, monotonic cursor),
    then mark every token whose character range overlaps that span. This
    handles segmenter idiosyncrasies — when ``underthesea`` glues an
    unrelated leading word into a multi-syllable token, the resulting
    multi-word token is still tagged correctly at word granularity.
    """
    raw_text, entities = sample
    text = _normalize(raw_text)
    tokens = _segment(text)
    spans = _char_spans(text, tokens)
    tags = ["O"] * len(tokens)
    text_l = text.lower()
    used_token_idx: set[int] = set()
    used_char_spans: list[tuple[int, int]] = []
    for surface, label in entities:
        surface = _normalize(surface)
        target = surface.lower()
        # Iterate every occurrence and pick the first that does not collide
        # with a previously annotated span — this lets the source list
        # annotations in any order while still rejecting accidental overlaps.
        idx = -1
        search_from = 0
        while True:
            cand = text_l.find(target, search_from)
            if cand < 0:
                break
            cand_end = cand + len(surface)
            if not any(s < cand_end and e > cand for s, e in used_char_spans):
                idx = cand
                break
            search_from = cand + 1
        if idx < 0:
            raise ValueError(
                f"entity surface {surface!r} ({label}) not found in {text!r} "
                f"or all occurrences already used"
            )
        end = idx + len(surface)
        hit = [i for i, (s, e) in enumerate(spans) if s < end and e > idx]
        if not hit:
            raise ValueError(
                f"entity {surface!r} ({label}) overlaps no token in {text!r}"
            )
        if any(i in used_token_idx for i in hit):
            raise ValueError(
                f"entity {surface!r} ({label}) overlaps an earlier annotation in {text!r}"
            )
        tags[hit[0]] = f"B-{label}"
        for j in hit[1:]:
            tags[j] = f"I-{label}"
        used_token_idx.update(hit)
        used_char_spans.append((idx, end))
    return {"tokens": tokens, "ner_tags": tags}


def _stable_bucket(text: str) -> int:
    """Map a sample to ``[0, 100)`` deterministically by SHA-1 of its text."""
    h = hashlib.sha1(text.encode("utf-8")).digest()
    return int.from_bytes(h[:4], "big") % 100


def split(samples: list[Sample], *, test_pct: int = 20) -> tuple[list[Sample], list[Sample]]:
    """Hash-based split — adding new samples does not reshuffle existing ones."""
    train: list[Sample] = []
    test: list[Sample] = []
    for s in samples:
        (test if _stable_bucket(s[0]) < test_pct else train).append(s)
    return train, test


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def _summary(rows: list[dict]) -> str:
    leading: Counter[str] = Counter()
    for r in rows:
        tag = next((t.split("-", 1)[1] for t in r["ner_tags"] if t != "O"), "O")
        leading[tag] += 1
    return f"n={len(rows)} leading_tags={dict(leading)}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--test-pct", type=int, default=20)
    args = parser.parse_args()

    # Validate uniqueness — duplicates in the source corrupt train/test isolation.
    seen: dict[str, int] = {}
    for i, (text, _) in enumerate(SAMPLES):
        if text in seen:
            raise ValueError(f"duplicate source text at index {i} (also at {seen[text]}): {text!r}")
        seen[text] = i

    aligned = [align(s) for s in SAMPLES]

    train_src, test_src = split(SAMPLES, test_pct=args.test_pct)
    train = [align(s) for s in train_src]
    test = [align(s) for s in test_src]

    write_jsonl(TRAIN_PATH, train)
    write_jsonl(TEST_PATH, test)
    print(f"[corpus] {_summary(aligned)}")
    print(f"[train ] {_summary(train)}")
    print(f"[test  ] {_summary(test)}")

    viz_dir = ARTIFACTS_DIR / "dataset"
    plot_label_distribution({"train": train, "test": test},
                            str(viz_dir / "label_distribution.png"))
    plot_length_distribution({"train": train, "test": test},
                             str(viz_dir / "length_distribution.png"),
                             max_length=MAX_LENGTH)
    print(f"[viz   ] {viz_dir}")


if __name__ == "__main__":
    main()
