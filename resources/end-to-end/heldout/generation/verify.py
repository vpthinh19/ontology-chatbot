"""Kiểm đầu ra sinh câu hỏi: trích nguyên văn có thật không, câu nào trùng, phân bố ra sao.

    python resources/end-to-end/heldout/generation/verify.py resources/end-to-end/heldout/generation/out-*.json
"""
import collections
import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SOURCES = ROOT / "references"


def norm(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = re.sub(r"[*_#>`|]", " ", text)
    return re.sub(r"\s+", " ", text).strip().lower()


def syllables(text: str) -> set[str]:
    return set(re.findall(r"\w+", unicodedata.normalize("NFC", text).lower()))


source_text = {p.name: norm(p.read_text(encoding="utf-8")) for p in SOURCES.iterdir() if p.suffix in (".md", ".txt")}
items = []
for path in sys.argv[1:]:
    model = Path(path).stem.removeprefix("out-")
    for item in json.loads(Path(path).read_text(encoding="utf-8"))["cau_hoi"]:
        item["mo_hinh"] = model
        items.append(item)

bad_quotes = []
for i, item in enumerate(items):
    if item["loai"] != "co_dap_an":
        continue
    text = source_text.get(item["tep"] or "")
    missing = [q for q in item["trich_nguyen_van"] if text is None or norm(q) not in text]
    if text is None or not item["trich_nguyen_van"] or missing:
        bad_quotes.append((i, item["mo_hinh"], item["cau_hoi"], item["tep"], missing[:1]))

dupes = []
for a in range(len(items)):
    for b in range(a + 1, len(items)):
        sa, sb = syllables(items[a]["cau_hoi"]), syllables(items[b]["cau_hoi"])
        if sa and sb and len(sa & sb) / len(sa | sb) >= 0.6:
            dupes.append((a, b, items[a]["cau_hoi"], items[b]["cau_hoi"]))

print("tổng:", len(items))
for field in ("mo_hinh", "chu_de", "loai", "phong_cach"):
    print(field, dict(collections.Counter(it[field] for it in items)))
print(f"\ntrích nguyên văn không tìm thấy: {len(bad_quotes)}")
for i, model, question, tep, missing in bad_quotes:
    print(f"  #{i} [{model}] {question[:70]} | {tep} | {str(missing)[:90]}")
print(f"\ncặp câu gần trùng: {len(dupes)}")
for a, b, qa, qb in dupes:
    print(f"  #{a} {qa[:60]}  ~  #{b} {qb[:60]}")
