"""Kiểm dataset theo bốn điều kiện chất lượng.

Chạy:  .venv/bin/python -m ontchatbot.cli.check_conditions

1. Sample chỉ có hai dạng: truy vấn thông tin, hoặc "không có thông tin".
2. Sample trả thông tin phải dẫn nguồn kèm mốc thời gian, và nguồn phải chuẩn của
   chính thông tin đó.
3. Nguồn là công văn hoặc web chính chủ Đại học Nha Trang.
4. Mỗi loại thông tin cần nhiều sắc thái prompt, nhiều độ dài.

Mỗi truy vấn được chạy trên đồ thị. Biểu thức ngày tháng và các phép kiểm đối
chiếu dữ liệu được thực hiện trên giá trị đã phân tích.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlsplit

from ontchatbot.runtime.sparql import PREFIXES, load_ontology
from ontchatbot.settings import DATASET_DIR, QUERY_CATALOGUE_PATH, REPORTS_DIR

DATASET = DATASET_DIR
MARKER = "không có thông tin"


def main(destination: str | None = None) -> None:
    """Chạy trọn cuộc kiểm và ghi báo cáo.

    Hàm chỉ được gọi tường minh vì nó ghi tệp báo cáo.
    """

    if destination is None and len(sys.argv) > 1:
        destination = sys.argv[1]
    rows = []
    for split in ("train", "val", "test"):
        for line in (DATASET / f"{split}.jsonl").read_text(encoding="utf-8").splitlines():
            if line.strip():
                item = json.loads(line)
                item["split"] = split
                rows.append(item)

    catalogue = {}
    for line in (QUERY_CATALOGUE_PATH).read_text(encoding="utf-8").splitlines():
        if line.strip():
            spec = json.loads(line)
            catalogue.setdefault(spec["query_id"], []).append(spec)

    report: dict[str, object] = {"tong_dong": len(rows)}
    print(f"Đã nạp {len(rows)} dòng, {len(catalogue)} họ trong danh mục.\n")

    # ---------------------------------------------------------------- ĐIỀU KIỆN 1
    # Chỉ hai dạng: truy vấn thông tin, hoặc đúng chuỗi "không có thông tin".
    dk1_bad = []
    shapes = Counter()
    for r in rows:
        target = r["target"].strip()
        if target == MARKER:
            shapes["tu_choi"] += 1
            if r["query_id"] != "no-information":
                dk1_bad.append((r["id"], "đích là câu từ chối nhưng họ không phải no-information"))
        elif target.upper().startswith("SELECT"):
            shapes["truy_van"] += 1
            if r["query_id"] == "no-information":
                dk1_bad.append((r["id"], "họ no-information nhưng đích là SELECT"))
        else:
            shapes["DANG_LA"] += 1
            dk1_bad.append((r["id"], f"dạng thứ ba: {target[:60]!r}"))

    print("== ĐK1 — chỉ hai dạng ==")
    print(f"  truy vấn thông tin : {shapes['truy_van']}")
    print(f"  không có thông tin : {shapes['tu_choi']}")
    print(f"  dạng lạ            : {shapes['DANG_LA']}")
    print(f"  VI PHẠM            : {len(dk1_bad)}")
    for bad in dk1_bad[:10]:
        print("   ", bad)
    report["dk1"] = {"shapes": dict(shapes), "vi_pham": dk1_bad}

    # ------------------------------------------------------- ĐIỀU KIỆN 2 và 3
    print("\n== ĐK2/ĐK3 — chạy thật từng truy vấn ==")
    graph = load_ontology()
    print("  đã nạp ontology")

    DATE_RE = re.compile(r"\b(?:ngày\s*)?\d{1,2}[/-]\d{1,2}[/-]\d{4}\b|\bnăm\s*\d{4}\b|\b\d{4}\b")

    cache: dict[str, dict] = {}
    no_rows, no_source, no_link, source_without_date = [], [], [], []
    hosts = Counter()
    all_links: set[str] = set()

    info_rows = [r for r in rows if r["target"].strip() != MARKER]
    for index, r in enumerate(info_rows, 1):
        target = r["target"].strip()
        if target not in cache:
            try:
                result = list(graph.query(PREFIXES + target))
            except Exception as exc:  # noqa: BLE001
                cache[target] = {"error": str(exc)}
                continue
            names = [str(v) for v in (result[0].labels if result else [])] if result else []
            recs = [
                {str(k): (str(v) if v is not None else "") for k, v in zip(names, row)}
                for row in result
            ]
            cache[target] = {"rows": recs}
        entry = cache[target]
        if "error" in entry:
            no_rows.append((r["id"], "LỖI CHẠY: " + entry["error"][:80]))
            continue
        recs = entry["rows"]
        if not recs:
            no_rows.append((r["id"], "truy vấn trả 0 dòng"))
            continue
        missing_source = [x for x in recs if not x.get("nguon", "").strip()]
        missing_link = [x for x in recs if not x.get("duongdan", "").strip()]
        if missing_source:
            no_source.append((r["id"], f"{len(missing_source)}/{len(recs)} dòng thiếu ?nguon"))
        if missing_link:
            no_link.append((r["id"], f"{len(missing_link)}/{len(recs)} dòng thiếu ?duongdan"))
        for x in recs:
            citation = x.get("nguon", "").strip()
            if citation and not DATE_RE.search(citation):
                source_without_date.append((r["id"], citation[:90]))
            link = x.get("duongdan", "").strip()
            if link:
                all_links.add(link)
                hosts[urlsplit(link).netloc.lower()] += 1
        if index % 500 == 0:
            print(f"  ...{index}/{len(info_rows)}")

    print(f"  truy vấn riêng biệt đã chạy: {len(cache)}")
    print(f"\n  [ĐK2] dòng trả VỀ RỖNG hoặc lỗi : {len(no_rows)}")
    for bad in no_rows[:10]:
        print("   ", bad)
    print(f"  [ĐK2] dòng THIẾU nguồn          : {len(no_source)}")
    for bad in no_source[:10]:
        print("   ", bad)
    print(f"  [ĐK2] dòng THIẾU đường dẫn      : {len(no_link)}")
    for bad in no_link[:10]:
        print("   ", bad)

    uniq_undated = sorted({c for _, c in source_without_date})
    print(f"  [ĐK2] trích dẫn KHÔNG CÓ MỐC THỜI GIAN: {len(source_without_date)} lượt, {len(uniq_undated)} chuỗi riêng")
    for c in uniq_undated[:20]:
        print("    -", c)

    print(f"\n  [ĐK3] tên miền của mọi ?duongdan ({len(all_links)} URL riêng):")
    for host, n in hosts.most_common():
        flag = "" if host.endswith("ntu.edu.vn") else "   <-- KHÔNG PHẢI ntu.edu.vn"
        print(f"    {n:6}  {host}{flag}")

    report["dk2"] = {
        "rong_hoac_loi": no_rows,
        "thieu_nguon": no_source,
        "thieu_duong_dan": no_link,
        "trich_dan_khong_ngay": uniq_undated,
    }
    report["dk3"] = {"hosts": dict(hosts), "urls": sorted(all_links)}

    # ---------------------------------------------------------------- ĐIỀU KIỆN 4
    print("\n== ĐK4 — sắc thái prompt cho mỗi loại thông tin ==")


    def anchors(target: str) -> tuple[str, ...]:
        return tuple(sorted(set(re.findall(r"(?<![\w:])(:[A-Z][A-Za-z0-9_]*)", target))))


    by_type: dict[tuple, list] = defaultdict(list)
    for r in info_rows:
        by_type[(r["query_id"], anchors(r["target"]))].append(r)

    reg_hist = Counter(len({x["register"] for x in v}) for v in by_type.values())
    len_hist = Counter(len(v) for v in by_type.values())
    print(f"  tổng loại thông tin (họ + neo): {len(by_type)}")
    print(f"  số phong cách mỗi loại: {dict(sorted(reg_hist.items()))}")
    print(f"  số dòng mỗi loại (rút gọn): {dict(sorted(len_hist.items())[:8])} ...")

    thin = []
    for key, group in by_type.items():
        regs = {x["register"] for x in group}
        lengths = [len(x["input"].split()) for x in group]
        if len(regs) < 3 or len(group) < 3 or (max(lengths) - min(lengths)) < 4:
            thin.append(
                {
                    "query_id": key[0],
                    "anchors": list(key[1]),
                    "dong": len(group),
                    "phong_cach": sorted(regs),
                    "dai_min": min(lengths),
                    "dai_max": max(lengths),
                }
            )

    by_family = Counter(t["query_id"] for t in thin)
    print(f"\n  LOẠI THÔNG TIN MỎNG (dưới 3 phong cách, hoặc dưới 3 dòng, hoặc biên độ dài <4 từ): {len(thin)}")
    for fam, n in by_family.most_common():
        total = sum(1 for k in by_type if k[0] == fam)
        print(f"    {n:4}/{total:<4} {fam}")
    report["dk4"] = {"tong_loai": len(by_type), "mong": thin, "theo_ho": dict(by_family)}

    # Đường ra có thể truyền từ ngoài; mặc định nằm trong thư mục báo cáo.
    out = Path(destination or REPORTS_DIR / "audit-bon-dieu-kien.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nBáo cáo đầy đủ: {out}")


if __name__ == "__main__":
    main()
