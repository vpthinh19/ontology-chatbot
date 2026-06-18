"""Chấm một LÔ (text, tree) do Codex sinh — máy chấm tự động Phase 4.

    uv run --extra inference python -m ontchatbot.scripts.validate_batch <batch.jsonl>

Mỗi dòng lô = ``{catalog_id, style, text, tree}``. Cách chấm (neo + oracle nghiêm):

1. Tra ``catalog_id`` trong ``catalog.jsonl`` → lấy ``expected`` (đáp án biết trước).
2. ``validate_case_strict(text, tree, **expected)`` — pin TOÀN BỘ outcome của cây:
   strict-parse + act + nodes/values/vague/misses == expected + trace đủ mạnh, không tie.
3. Khử trùng theo text đã chuẩn hoá (trong lô + có thể so với lô đã nhận trước).

Cặp PASS → ``accepted/<batch>.jsonl`` (kèm ``catalog_id/category/style`` để split sau).
Cặp FAIL → ``<batch>.rejected.jsonl`` kèm lý do (để chỉnh prompt Codex hoặc loại).

KHÔNG kiểm text↔nghĩa ở đây (oracle chỉ thấy ``tree``) — đó là việc của round-trip
(``roundtrip``) + review tay. Tầng này đảm bảo: cây ĐÚNG CẤU TRÚC và RA ĐÚNG ĐÁP ÁN.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field

from ..config import ACCEPTED_DIR, CATALOG_PATH
from ..ontology import Ontology
from ..preprocess import normalize_for_match
from .validate_dataset import case_kwargs, validate_case_strict


@dataclass
class BatchReport:
    accepted: list[dict] = field(default_factory=list)
    rejected: list[dict] = field(default_factory=list)   # {row, errors}

    @property
    def n(self) -> int:
        return len(self.accepted) + len(self.rejected)


def load_catalog() -> dict[str, dict]:
    rows = [json.loads(l) for l in CATALOG_PATH.read_text(encoding="utf-8").splitlines() if l.strip()]
    return {r["id"]: r for r in rows}


def _coerce_tree(tree: object) -> object:
    """Codex đôi khi trả ``tree`` dạng chuỗi JSON — nới lỏng thành dict."""
    if isinstance(tree, str):
        try:
            return json.loads(tree)
        except json.JSONDecodeError:
            return tree
    return tree


def validate_batch(rows: list[dict], catalog: dict[str, dict], ont: Ontology,
                   *, seen: set[str] | None = None) -> BatchReport:
    """Chấm từng cặp. ``seen`` = text đã chuẩn hoá đã nhận (khử trùng xuyên-lô)."""
    rep = BatchReport()
    seen = set() if seen is None else seen
    for row in rows:
        errs: list[str] = []
        cid = row.get("catalog_id")
        entry = catalog.get(cid)
        text = row.get("text")
        tree = _coerce_tree(row.get("tree"))

        if entry is None:
            errs.append(f"catalog_id lạ: {cid!r}")
        if not isinstance(text, str) or not text.strip():
            errs.append("thiếu/empty text")
        if errs:
            rep.rejected.append({"row": row, "errors": errs})
            continue

        norm = normalize_for_match(text)
        if norm in seen:
            rep.rejected.append({"row": row, "errors": ["trùng text (đã có)"]})
            continue

        result = validate_case_strict(text, tree, ontology=ont, **case_kwargs(entry))
        if not result.ok:
            rep.rejected.append({"row": row, "errors": result.errors})
            continue

        seen.add(norm)
        rep.accepted.append({
            "text": text.strip(),
            "tree": tree,
            "catalog_id": cid,
            "category": entry["category"],
            "group": entry["group"],
            "style": row.get("style", "unspecified"),
        })
    return rep


def load_batch(path) -> list[dict]:
    raw = path.read_text(encoding="utf-8").strip()
    # Hỗ trợ cả JSONL lẫn {"pairs":[...]} / [...] (Codex output-schema).
    if raw.startswith("{") and '"pairs"' in raw[:200]:
        return json.loads(raw)["pairs"]
    if raw.startswith("["):
        return json.loads(raw)
    return [json.loads(l) for l in raw.splitlines() if l.strip()]


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) < 2:
        print("dùng: validate_batch <batch.jsonl|batch.json>")
        sys.exit(2)
    from pathlib import Path
    path = Path(sys.argv[1])
    catalog = load_catalog()
    ont = Ontology()
    rep = validate_batch(load_batch(path), catalog, ont)

    out = ACCEPTED_DIR / (path.stem + ".accepted.jsonl")
    rej = path.with_suffix(".rejected.jsonl")
    ACCEPTED_DIR.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        for a in rep.accepted:
            fh.write(json.dumps(a, ensure_ascii=False) + "\n")
    with rej.open("w", encoding="utf-8") as fh:
        for r in rep.rejected:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    rate = 100.0 * len(rep.accepted) / rep.n if rep.n else 0.0
    print(f"[validate_batch] {path.name}: {len(rep.accepted)}/{rep.n} PASS ({rate:.0f}%)")
    print(f"    accepted → {out}")
    if rep.rejected:
        print(f"    rejected → {rej}  ({len(rep.rejected)} cặp)")
        # gộp lý do để chỉnh prompt
        from collections import Counter
        reasons = Counter(e.split(":")[0] for r in rep.rejected for e in r["errors"])
        for reason, c in reasons.most_common():
            print(f"      {c:4d}× {reason}")


if __name__ == "__main__":
    main()
