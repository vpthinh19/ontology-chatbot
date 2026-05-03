"""Generate train/test JSONL for PhoBERT NER from ontology + templates.

Pipeline
--------
1. Load all ontology individuals together with their ``rdfs:label`` and every
   ``hasAlias`` literal — these become the pool of *surface forms* for each tag.
2. For every ``(template, surface)`` pair render a word-segmented token
   sequence and assign BIO tags by tracking the entity slot's position. Both
   the surrounding text and the entity surface are word-segmented separately
   (``underthesea``) and then concatenated, so BIO alignment is exact without
   char-offset bookkeeping.
3. Add greeting and out-of-domain samples (all ``O``) for non-entity coverage.
4. Stitch a configurable number of *multi-entity* samples by joining two
   single-entity sentences with a Vietnamese conversational connector.
5. Apply mild surface noise to a fraction of samples.
6. Stratify-split by leading-tag distribution into train/test JSONL files.

Each output line: ``{"tokens": [...], "ner_tags": [...]}``.
"""

from __future__ import annotations

import argparse
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

from underthesea import word_tokenize

from ..config import MAX_LENGTH, OUT_DIR, SEED, TEST_PATH, TRAIN_PATH
from ..ontology.loader import (
    class_local,
    iter_individuals,
    load_ontology,
    ontology_tags,
    primary_label,
    short_name,
)
from ..viz.distributions import plot_label_distribution, plot_length_distribution
from .templates import CONNECTORS, GREETINGS, OUT_OF_DOMAIN, TEMPLATES, perturb


def segment(text: str) -> list[str]:
    """Word-segment with underthesea, returning underscore-joined tokens."""
    out = word_tokenize(text, format="text")
    out = out if isinstance(out, str) else " ".join(out)
    return [t for t in out.split() if t]


def collect_surfaces() -> dict[str, list[str]]:
    """Per-tag pool of surface forms: ``rdfs:label`` + ``hasAlias`` + humanised name.

    For ``DinhMucHocPhi`` we additionally synthesise short forms (``k65``,
    ``hp k65``…) since the user often abbreviates fee-bracket queries.
    """
    load_ontology()
    pool: dict[str, list[str]] = defaultdict(list)
    for tag in ontology_tags():
        for ind in iter_individuals(class_local(tag)):
            forms: set[str] = {short_name(ind).replace("_", " "), primary_label(ind)}
            for a in getattr(ind, "hasAlias", None) or []:
                forms.add(str(a))
            for v in getattr(ind, "label", None) or []:
                forms.add(str(v))
            if tag == "DinhMucHocPhi":
                base = short_name(ind)
                for piece in base.split("_"):
                    if len(piece) >= 2 and piece[0] in "Kk" and piece[1:].isdigit():
                        forms.update({piece.lower(), f"hp {piece.lower()}",
                                      f"học phí {piece.lower()}"})
            pool[tag].extend(sorted({f.strip() for f in forms if f and f.strip()}))
    return pool


def render_single(template: str, tag: str, surface: str) -> dict:
    """Render a one-entity sentence into ``{tokens, ner_tags}``."""
    left, right = template.split("{E}", 1)
    l_toks = segment(left.strip())
    r_toks = segment(right.strip())
    e_toks = segment(surface)
    if not e_toks:
        e_toks = [surface]
    tokens = l_toks + e_toks + r_toks
    tags = (
        ["O"] * len(l_toks)
        + [f"B-{tag}"] + [f"I-{tag}"] * (len(e_toks) - 1)
        + ["O"] * len(r_toks)
    )
    return {"tokens": tokens, "ner_tags": tags}


def stitch(a: dict, b: dict, connector: str) -> dict:
    """Concatenate two single-entity samples with a connector phrase."""
    conn = segment(connector.strip())
    return {
        "tokens": a["tokens"] + conn + b["tokens"],
        "ner_tags": a["ner_tags"] + ["O"] * len(conn) + b["ner_tags"],
    }


def _sample_no_entity(text: str) -> dict:
    toks = segment(text)
    return {"tokens": toks, "ner_tags": ["O"] * len(toks)}


def _apply_noise(sample: dict, rng: random.Random) -> dict:
    raw = " ".join(t.replace("_", " ") for t in sample["tokens"])
    noisy = perturb(raw, rng)
    new_toks = segment(noisy)
    return {**sample, "tokens": new_toks} if len(new_toks) == len(sample["tokens"]) else sample


def _leading_tag(sample: dict) -> str:
    """First non-``O`` tag (used as stratification key); ``O`` if entity-free."""
    for t in sample["ner_tags"]:
        if t != "O":
            return t.split("-", 1)[1]
    return "O"


def build(
    *,
    n_per_tag: int = 240,
    n_multi: int = 220,
    n_greeting: int = 140,
    n_ood: int = 180,
    test_ratio: float = 0.2,
    noise_ratio: float = 0.4,
    seed: int = SEED,
) -> tuple[list[dict], list[dict]]:
    rng = random.Random(seed)
    pool = collect_surfaces()
    samples: list[dict] = []

    # Single-entity
    for tag, templates in TEMPLATES.items():
        if not pool.get(tag):
            continue
        for _ in range(n_per_tag):
            samples.append(render_single(rng.choice(templates), tag,
                                         rng.choice(pool[tag])))

    # Multi-entity (60% cross-class, 40% same-class for hard cases like "hp k65, k67")
    tags = list(TEMPLATES.keys())
    for _ in range(n_multi):
        if rng.random() < 0.6:
            t1, t2 = rng.sample(tags, 2)
        else:
            t1 = t2 = rng.choice(tags)
        a = render_single(rng.choice(TEMPLATES[t1]), t1, rng.choice(pool[t1]))
        b = render_single(rng.choice(TEMPLATES[t2]), t2, rng.choice(pool[t2]))
        samples.append(stitch(a, b, rng.choice(CONNECTORS)))

    # Non-entity intents
    for _ in range(n_greeting):
        samples.append(_sample_no_entity(rng.choice(GREETINGS)))
    for _ in range(n_ood):
        samples.append(_sample_no_entity(rng.choice(OUT_OF_DOMAIN)))

    # Surface noise
    samples = [_apply_noise(s, rng) if rng.random() < noise_ratio else s
               for s in samples]
    rng.shuffle(samples)

    # Stratified split by leading tag
    grouped: dict[str, list[dict]] = defaultdict(list)
    for s in samples:
        grouped[_leading_tag(s)].append(s)
    train: list[dict] = []
    test: list[dict] = []
    for items in grouped.values():
        cut = int(len(items) * (1.0 - test_ratio))
        train.extend(items[:cut])
        test.extend(items[cut:])
    rng.shuffle(train)
    rng.shuffle(test)
    return train, test


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def _summary(rows: list[dict]) -> str:
    leading = Counter(_leading_tag(r) for r in rows)
    return f"n={len(rows)} leading_tags={dict(leading)}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n-per-tag", type=int, default=240)
    parser.add_argument("--n-multi", type=int, default=220)
    parser.add_argument("--n-greeting", type=int, default=140)
    parser.add_argument("--n-ood", type=int, default=180)
    parser.add_argument("--test-ratio", type=float, default=0.2)
    parser.add_argument("--noise-ratio", type=float, default=0.4)
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()

    train, test = build(
        n_per_tag=args.n_per_tag,
        n_multi=args.n_multi,
        n_greeting=args.n_greeting,
        n_ood=args.n_ood,
        test_ratio=args.test_ratio,
        noise_ratio=args.noise_ratio,
        seed=args.seed,
    )
    write_jsonl(TRAIN_PATH, train)
    write_jsonl(TEST_PATH, test)
    print(f"[train] {_summary(train)}")
    print(f"[test ] {_summary(test)}")

    viz_dir = OUT_DIR / "dataset"
    plot_label_distribution({"train": train, "test": test},
                            str(viz_dir / "label_distribution.png"))
    plot_length_distribution({"train": train, "test": test},
                             str(viz_dir / "length_distribution.png"),
                             max_length=MAX_LENGTH)
    print(f"[viz  ] {viz_dir}")


if __name__ == "__main__":
    main()
