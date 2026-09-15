"""Dữ kiện trong ontology gần nhất với đáp án gốc của từng câu, để đánh dấu "ontology có dữ liệu không".

Không dùng bộ máy tìm kiếm của hệ thống: so trực tiếp chữ và con số của câu hỏi cùng đáp án gốc với
mọi phát biểu trong tệp TriG (kể cả giá trị, thứ mà chỉ mục tìm kiếm không chứa).

    uv run python resources/end-to-end/heldout/generation/coverage.py resources/end-to-end/heldout/generation/out-*.json
"""
import json
import math
import re
import sys
import unicodedata
from pathlib import Path

import pyoxigraph as ox

ROOT = Path(__file__).resolve().parents[4]
ONTOLOGY = ROOT / "resources" / "ontology" / "ontology.trig"
NS = "http://www.ntu.edu.vn/ontology/academic#"
RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
RDFS_LABEL = "http://www.w3.org/2000/01/rdf-schema#label"
SOURCE_LAYER = {NS + "Nguon", NS + "DiaChiTrichDan"}
STOP = set(("là gì nào ai đâu ở bao nhiêu thế sao như của và các những cho có được thì mà để với khi nếu về "
            "tại không phải một trong từ đến theo đối này đó sinh viên em văn bản quy định").split())


def words(text: str) -> set[str]:
    return {w for w in re.findall(r"\w+", unicodedata.normalize("NFC", text).lower()) if w not in STOP}


def numbers(text: str) -> set[str]:
    found = set()
    for token in re.findall(r"\d[\d.,]*\d|\d", text):
        digits = re.sub(r"[.,]", "", token)
        if len(digits) >= 2:
            found.add(digits.lstrip("0") or "0")
    return found


store = ox.Store()
store.load(path=str(ONTOLOGY), format=ox.RdfFormat.TRIG)
label, types = {}, {}
for q in store.quads_for_pattern(None, None, None, None):
    if q.predicate.value == RDFS_LABEL:
        label.setdefault(q.subject.value, q.object.value)
    elif q.predicate.value == RDF_TYPE:
        types.setdefault(q.subject.value, set()).add(q.object.value)

facts = []
for q in store.quads_for_pattern(None, None, None, None):
    s, p, o = q.subject.value, q.predicate.value, q.object
    if p in (RDF_TYPE, RDFS_LABEL) or types.get(s, set()) & SOURCE_LAYER:
        continue
    obj = o.value if isinstance(o, ox.Literal) else label.get(o.value, o.value.rsplit("#", 1)[-1])
    if obj.startswith("http"):
        continue
    text = f"{label.get(s, s.rsplit('#', 1)[-1])} | {label.get(p, p.rsplit('#', 1)[-1])} | {obj}"
    facts.append((text, words(text), numbers(text)))

for path in sys.argv[1:]:
    model = Path(path).stem.removeprefix("out-")
    for i, item in enumerate(json.loads(Path(path).read_text(encoding="utf-8"))["cau_hoi"]):
        if item["loai"] == "ngoai_hoc_vu":
            continue
        probe = item["cau_hoi"] + " " + " ".join(item["y_chinh"])
        pw, pn = words(probe), numbers(" ".join(item["y_chinh"]))
        scored = sorted(((len(pw & fw) + 3 * len(pn & fn)) / math.sqrt(len(fw) + 1), text)
                        for text, fw, fn in facts)[-3:]
        print(f"[{model} #{i}] {item['loai'][:8]} | {item['cau_hoi'][:90]}")
        print(f"   gốc: {' / '.join(item['y_chinh'])[:170]}")
        for score, text in reversed(scored):
            print(f"   {score:4.1f} {text[:170]}")
