"""Generate train/test JSONL for PhoBERT NER from ontology + templates.

Pipeline
--------
1. Load every individual of every NER class together with its alias literals.
2. For each (template, entity) pair, render a word-segmented token sequence and
   assign BIO tags by tracking the entity span position. Word segmentation is
   applied to template fragments and entity surfaces independently; the final
   sentence is the space-join of segmented tokens, so BIO alignment is exact
   without char-offset bookkeeping.
3. Add greeting and out-of-domain samples (label-wide ``O``) to balance the
   non-entity intent distribution.
4. Apply mild surface noise to a fraction of samples to model conversational
   distortions (diacritic loss, casing, punctuation drop, vowel stretching).
5. Stratify-split into train/test JSONL.

Each output line: ``{"tokens": [...], "ner_tags": [...], "intent": "..."}``.
``intent`` records the high-level label of the sample (one of the seven label
map keys) and is used for stratification and analysis only — the model is
trained on ``ner_tags`` exclusively.
"""

from __future__ import annotations

import argparse
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

from underthesea import word_tokenize

from ..config import LABEL_MAP_PATH, SEED, TEST_PATH, TRAIN_PATH
from ..ontology.loader import iter_individuals, load_ontology, ontology_tags, tag_to_class_local
from .templates import (
    GREETINGS,
    MULTI_TEMPLATES,
    OUT_OF_DOMAIN,
    TEMPLATES,
    perturb,
)


def _seg(text: str) -> list[str]:
    """Word-segment with underthesea, returning a list of underscore-joined tokens."""
    out = word_tokenize(text, format="text")
    out = out if isinstance(out, str) else " ".join(out)
    return [t for t in out.split() if t]


def _humanize(name: str) -> str:
    return name.replace("_", " ")


def collect_surfaces() -> dict[str, list[str]]:
    """For each NER tag, collect canonical names + alias literals as surface forms."""
    load_ontology()
    surfaces: dict[str, list[str]] = defaultdict(list)
    for tag in ontology_tags():
        cls_local = tag_to_class_local(tag)
        for ind in iter_individuals(cls_local):
            forms: set[str] = {_humanize(getattr(ind, "name", str(ind)))}
            for a in getattr(ind, "hasAlias", None) or []:
                if isinstance(a, str) and a.strip():
                    forms.add(a.strip())
            # FeeCategory ranges — synthesise ``hp k65``, ``k67`` short forms
            if tag == "DinhMucHocPhi":
                base = getattr(ind, "name", "")
                # Phi_K65_550k -> "k65"
                parts = base.split("_")
                for p in parts:
                    if len(p) >= 2 and p[0] in "Kk" and p[1:].isdigit():
                        forms.add(p.lower())
                        forms.add(f"hp {p.lower()}")
                        forms.add(f"học phí {p.lower()}")
            # PaymentMethod: humanise CamelCase
            if tag == "PhuongThucThanhToan":
                base = getattr(ind, "name", "")
                if base == "BankTransfer":
                    forms.update(["chuyển khoản", "chuyen khoan", "ck ngân hàng"])
                if base == "PayOnline":
                    forms.update(["thanh toán online", "online", "qr code"])
            surfaces[tag].extend(sorted(forms))
    return surfaces


def render_single(template: str, tag: str, surface: str) -> tuple[list[str], list[str], str]:
    """Render a single-entity template, returning (tokens, ner_tags, plain_text)."""
    left, right = template.split("{E}", 1)
    left_toks = _seg(left.strip())
    right_toks = _seg(right.strip())
    ent_toks = _seg(surface)
    tokens = left_toks + ent_toks + right_toks
    tags = (
        ["O"] * len(left_toks)
        + [f"B-{tag}"] + [f"I-{tag}"] * (len(ent_toks) - 1)
        + ["O"] * len(right_toks)
    )
    plain = " ".join(tokens)
    return tokens, tags, plain


def render_multi(
    template: str, tag1: str, surface1: str, tag2: str, surface2: str
) -> tuple[list[str], list[str], str]:
    """Render a two-entity template."""
    parts = template.split("{E1}")
    head = parts[0]
    rest = parts[1].split("{E2}")
    mid, tail = rest[0], rest[1]
    head_toks = _seg(head.strip())
    mid_toks = _seg(mid.strip())
    tail_toks = _seg(tail.strip())
    e1 = _seg(surface1)
    e2 = _seg(surface2)
    tokens = head_toks + e1 + mid_toks + e2 + tail_toks
    tags = (
        ["O"] * len(head_toks)
        + [f"B-{tag1}"] + [f"I-{tag1}"] * (len(e1) - 1)
        + ["O"] * len(mid_toks)
        + [f"B-{tag2}"] + [f"I-{tag2}"] * (len(e2) - 1)
        + ["O"] * len(tail_toks)
    )
    return tokens, tags, " ".join(tokens)


def _apply_noise(sample: dict, rng: random.Random) -> dict:
    """Re-segment after applying surface noise on the joined sentence; tags realign
    only when token count is preserved, otherwise the original sample is kept."""
    raw = " ".join(t.replace("_", " ") for t in sample["tokens"])
    noisy = perturb(raw, rng)
    new_toks = _seg(noisy)
    if len(new_toks) == len(sample["tokens"]):
        return {**sample, "tokens": new_toks}
    return sample


def build(
    n_per_tag: int = 240,
    n_multi: int = 200,
    n_greeting: int = 140,
    n_ood: int = 180,
    test_ratio: float = 0.2,
    noise_ratio: float = 0.4,
    seed: int = SEED,
) -> tuple[list[dict], list[dict]]:
    rng = random.Random(seed)
    surfaces = collect_surfaces()
    samples: list[dict] = []

    for tag, templates in TEMPLATES.items():
        pool = surfaces.get(tag, [])
        if not pool:
            continue
        for _ in range(n_per_tag):
            tpl = rng.choice(templates)
            surf = rng.choice(pool)
            tokens, tags, _ = render_single(tpl, tag, surf)
            samples.append({"tokens": tokens, "ner_tags": tags, "intent": tag})

    multi_tags = list(TEMPLATES.keys())
    for _ in range(n_multi):
        tpl = rng.choice(MULTI_TEMPLATES)
        # 60% cross-class pairs, 40% same-class pairs (e.g. "hp k65 ... k67 nữa")
        if rng.random() < 0.6:
            t1, t2 = rng.sample(multi_tags, 2)
        else:
            t1 = t2 = rng.choice(multi_tags)
        s1 = rng.choice(surfaces[t1])
        s2 = rng.choice([s for s in surfaces[t2] if s != s1] or surfaces[t2])
        tokens, tags, _ = render_multi(tpl, t1, s1, t2, s2)
        samples.append({"tokens": tokens, "ner_tags": tags, "intent": "Multi"})

    for _ in range(n_greeting):
        text = rng.choice(GREETINGS)
        toks = _seg(text)
        samples.append({"tokens": toks, "ner_tags": ["O"] * len(toks), "intent": "ChaoHoi"})

    for _ in range(n_ood):
        text = rng.choice(OUT_OF_DOMAIN)
        toks = _seg(text)
        samples.append({"tokens": toks, "ner_tags": ["O"] * len(toks), "intent": "NgoaiLe"})

    # Surface noise
    samples = [
        _apply_noise(s, rng) if rng.random() < noise_ratio else s
        for s in samples
    ]
    rng.shuffle(samples)

    # Stratified split by intent so every label is represented in test
    by_intent: dict[str, list[dict]] = defaultdict(list)
    for s in samples:
        by_intent[s["intent"]].append(s)

    train, test = [], []
    for items in by_intent.values():
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
    intents = Counter(r["intent"] for r in rows)
    tag_counts: Counter[str] = Counter()
    for r in rows:
        for t in r["ner_tags"]:
            if t != "O":
                tag_counts[t.split("-", 1)[1]] += 1
    return f"intents={dict(intents)}, entity_tokens={dict(tag_counts)}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n-per-tag", type=int, default=240)
    parser.add_argument("--n-multi", type=int, default=200)
    parser.add_argument("--n-greeting", type=int, default=140)
    parser.add_argument("--n-ood", type=int, default=180)
    parser.add_argument("--test-ratio", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()

    train, test = build(
        n_per_tag=args.n_per_tag,
        n_multi=args.n_multi,
        n_greeting=args.n_greeting,
        n_ood=args.n_ood,
        test_ratio=args.test_ratio,
        seed=args.seed,
    )
    write_jsonl(TRAIN_PATH, train)
    write_jsonl(TEST_PATH, test)
    print(f"[train] n={len(train)} {_summary(train)}")
    print(f"[test ] n={len(test)}  {_summary(test)}")
    print(f"label_map: {LABEL_MAP_PATH}")


if __name__ == "__main__":
    main()
