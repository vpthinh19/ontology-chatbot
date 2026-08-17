#!/usr/bin/env python
"""Dựng một trang báo cáo: hình dạng ontology, phân bố dataset, kết quả model.

Chạy thẳng, không cần tham số:

    python -m ontchatbot.cli.report_page

Nó tự đọc ontology, ba tệp dataset, và mọi ``benchmark-*.json`` tìm thấy trong
``artifacts/`` rồi ghi ra ``artifacts/reports/bao-cao.html``.

Thứ tự các mục theo đúng thứ tự người ngoài nhìn vào dự án: hình dạng ontology
trước, rồi phân bố dataset, rồi model làm được gì trên dataset đó, rồi model
hỏng ở đâu. Cấu trúc web app không thuộc trang này.
"""

from __future__ import annotations

import json
import re
import statistics as st
import sys
from collections import Counter, defaultdict
from pathlib import Path

from ontchatbot.settings import PROJECT_ROOT as ROOT

from rdflib import OWL, RDF, RDFS, Graph, URIRef

DATASET = ROOT / "resources" / "dataset"
ONTOLOGY = ROOT / "resources" / "ontology" / "ontology.ttl"
NS = "http://www.ntu.edu.vn/ontology/academic#"
OUT = ROOT / "artifacts" / "reports" / "bao-cao.html"

# Ba màu đầu của bảng màu chuẩn; các nhóm nhiều hơn dùng một màu vì nhãn trục
# mang danh tính của nhóm.
SERIES = ("#2a78d6", "#eb6834", "#1baf7a")
SERIES_DARK = ("#3987e5", "#d95926", "#199e70")


def rows(split: str) -> list[dict]:
    path = DATASET / f"{split}.jsonl"
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def ontology_shape() -> dict:
    g = Graph()
    g.parse(ONTOLOGY, format="turtle")
    per_class: Counter[str] = Counter()
    labels: dict[str, str] = {}
    for cls in g.subjects(RDF.type, OWL.Class):
        name = str(cls).split("#")[-1]
        vi = [str(o) for o in g.objects(cls, RDFS.label)]
        labels[name] = vi[0] if vi else name
    for ind in g.subjects(RDF.type, OWL.NamedIndividual):
        for cls in g.objects(ind, RDF.type):
            name = str(cls).split("#")[-1]
            if name != "NamedIndividual" and str(cls).startswith(NS):
                per_class[labels.get(name, name)] += 1
    from ontchatbot.runtime.sparql import load_ontology

    return {
        # ``triples`` là số bộ ba trong tệp; ``runtime_triples`` gồm cả các bộ
        # ba dẫn xuất được dựng khi chạy.
        "triples": len(g),
        "runtime_triples": len(load_ontology()),
        "classes": sum(1 for _ in g.subjects(RDF.type, OWL.Class)),
        "individuals": sum(1 for _ in g.subjects(RDF.type, OWL.NamedIndividual)),
        "object_properties": sum(1 for _ in g.subjects(RDF.type, OWL.ObjectProperty)),
        "datatype_properties": sum(1 for _ in g.subjects(RDF.type, OWL.DatatypeProperty)),
        "per_class": per_class.most_common(14),
    }


def dataset_shape() -> dict:
    splits = {name: rows(name) for name in ("train", "val", "test")}
    allrows = [r for rs in splits.values() for r in rs]
    marker = "không có thông tin"
    positives = [r for r in allrows if r["target"].strip().casefold() != marker]
    q_len = [len(r["input"].split()) for r in allrows]
    t_len = [len(r["target"].split()) for r in positives]
    bands: Counter[str] = Counter()
    for n in q_len:
        bands["2-6" if n <= 6 else "7-9" if n <= 9 else "10-13" if n <= 13
              else "14-17" if n <= 17 else "18+"] += 1
    return {
        "splits": {k: len(v) for k, v in splits.items()},
        "total": len(allrows),
        "refusals": len(allrows) - len(positives),
        "families": len({r["query_id"] for r in allrows}),
        "registers": Counter(r["register"] for r in allrows),
        "bands": bands,
        "q_median": st.median(q_len),
        "t_median": st.median(t_len),
        "q_max": max(q_len),
        "t_max": max(t_len),
        "top_families": Counter(
            r["query_id"] for r in allrows if r["query_id"] != "no-information"
        ).most_common(12),
    }


def anchor_kind(node: str) -> str:
    if "Table" in node:
        return "bảng"
    if re.search(r"Article\d|Clause\d|Appendix|Chapter\d|Point\d", node):
        return "điều/khoản"
    return "tên có nghĩa"


def benchmarks() -> list[dict]:
    found = []
    for path in sorted((ROOT / "artifacts").glob("benchmark-*.json")):
        report = json.loads(path.read_text(encoding="utf-8"))
        by_kind: dict[str, list[bool]] = defaultdict(list)
        for case in report.get("cases", []):
            if case.get("expected_nodes"):
                by_kind[anchor_kind(case["expected_nodes"][0])].append(
                    case["query_shape_correct"]
                )
        found.append({
            "name": path.stem.replace("benchmark-", ""),
            "run": report.get("run", {}),
            "primary": report["primary_metrics"],
            "by_register": {
                k: v["canonical_query_exact_rate"]
                for k, v in report.get("by_register", {}).items()
            },
            "by_kind": {k: sum(v) / len(v) for k, v in by_kind.items() if v},
        })
    return found


# ---------------------------------------------------------------- vẽ

def bars(items, *, color=0, pct=False, width=560) -> str:
    """Thanh ngang, nhãn ghi thẳng trên từng thanh.

    Các nhóm được phân biệt bằng nhãn trên trục, không bằng màu.
    """

    if not items:
        return "<p class='muted'>không có dữ liệu</p>"
    top = max(v for _, v in items) or 1
    row_h, gap = 26, 6
    height = len(items) * (row_h + gap)
    label_w = 220
    plot = width - label_w - 70
    out = [f'<svg viewBox="0 0 {width} {height}" role="img" class="chart">']
    for i, (name, value) in enumerate(items):
        y = i * (row_h + gap)
        w = max(2, plot * value / top)
        text = f"{value:.1%}" if pct else f"{value:,}".replace(",", ".")
        out.append(
            f'<text x="0" y="{y + 17}" class="lab">{name[:34]}</text>'
            f'<rect x="{label_w}" y="{y + 4}" width="{w:.1f}" height="{row_h - 8}" '
            f'rx="4" fill="var(--s{color})"/>'
            f'<text x="{label_w + w + 8:.1f}" y="{y + 17}" class="val">{text}</text>'
        )
    out.append("</svg>")
    return "".join(out)


def tiles(pairs) -> str:
    cells = "".join(
        f'<div class="tile"><div class="tile-v">{v}</div>'
        f'<div class="tile-k">{k}</div></div>'
        for k, v in pairs
    )
    return f'<div class="tiles">{cells}</div>'


def table(headers, body) -> str:
    head = "".join(f"<th>{h}</th>" for h in headers)
    rows_html = "".join(
        "<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in body
    )
    return (
        f'<div class="scroll"><table><thead><tr>{head}</tr></thead>'
        f"<tbody>{rows_html}</tbody></table></div>"
    )


def main() -> None:
    onto = ontology_shape()
    data = dataset_shape()
    runs = benchmarks()

    vi = lambda n: f"{n:,}".replace(",", ".")

    parts = [f"""<style>
.viz-root {{ color-scheme: light;
  --surface-1:#fcfcfb; --surface-2:#f2f2ef; --line:#dcdcd6;
  --text-primary:#0b0b0b; --text-secondary:#52514e; --muted:#77766f;
  --s0:{SERIES[0]}; --s1:{SERIES[1]}; --s2:{SERIES[2]}; }}
@media (prefers-color-scheme: dark) {{ :root:where(:not([data-theme="light"])) .viz-root {{
  color-scheme: dark;
  --surface-1:#1a1a19; --surface-2:#232322; --line:#3a3a38;
  --text-primary:#ffffff; --text-secondary:#c3c2b7; --muted:#9b9a92;
  --s0:{SERIES_DARK[0]}; --s1:{SERIES_DARK[1]}; --s2:{SERIES_DARK[2]}; }} }}
:root[data-theme="dark"] .viz-root {{ color-scheme: dark;
  --surface-1:#1a1a19; --surface-2:#232322; --line:#3a3a38;
  --text-primary:#ffffff; --text-secondary:#c3c2b7; --muted:#9b9a92;
  --s0:{SERIES_DARK[0]}; --s1:{SERIES_DARK[1]}; --s2:{SERIES_DARK[2]}; }}
.viz-root {{ background:var(--surface-1); color:var(--text-primary);
  font:15px/1.6 system-ui,-apple-system,"Segoe UI",sans-serif;
  max-width:900px; margin:0 auto; padding:32px 20px 64px; }}
h1 {{ font-size:26px; margin:0 0 4px; }}
h2 {{ font-size:19px; margin:40px 0 4px; padding-top:20px; border-top:1px solid var(--line); }}
p.note {{ color:var(--text-secondary); margin:4px 0 18px; }}
.tiles {{ display:flex; flex-wrap:wrap; gap:10px; margin:16px 0 22px; }}
.tile {{ background:var(--surface-2); border-radius:8px; padding:12px 16px; min-width:104px; }}
.tile-v {{ font-size:22px; font-weight:600; }}
.tile-k {{ font-size:12px; color:var(--text-secondary); margin-top:2px; }}
.chart {{ width:100%; height:auto; margin:6px 0 20px; }}
.lab {{ fill:var(--text-secondary); font-size:12.5px; }}
.val {{ fill:var(--text-primary); font-size:12.5px; font-weight:600; }}
.scroll {{ overflow-x:auto; margin:6px 0 20px; }}
table {{ border-collapse:collapse; width:100%; font-size:13.5px; }}
th,td {{ text-align:left; padding:7px 12px 7px 0; border-bottom:1px solid var(--line); white-space:nowrap; }}
th {{ color:var(--text-secondary); font-weight:600; }}
.muted {{ color:var(--muted); }}
</style>
<div class="viz-root">
<h1>Ontology học vụ Trường Đại học Nha Trang</h1>
<p class="note">Công cụ tra cứu học vụ: nhận câu hỏi tiếng Việt, sinh một truy vấn
SPARQL thuộc danh mục, trả về trọn vẹn một node dữ kiện kèm nguồn.</p>

<h2>1 · Hình dạng ontology</h2>
<p class="note">Tầng văn bản giữ nguyên văn quy chế; tầng nghiệp vụ giữ thủ tục,
điều kiện, thời hạn. Mọi node mang dữ kiện đều phải dẫn nguồn.</p>
"""]

    parts.append(tiles([
        ("bộ ba đã biên soạn", vi(onto["triples"])),
        ("lớp", vi(onto["classes"])),
        ("cá thể", vi(onto["individuals"])),
        ("thuộc tính quan hệ", vi(onto["object_properties"])),
        ("thuộc tính dữ liệu", vi(onto["datatype_properties"])),
    ]))
    parts.append(f"<p class='note'>Lúc chạy, đồ thị dựng thêm một chiếu nguồn nên "
                 f"thành {vi(onto['runtime_triples'])} bộ ba — đó là view tiện truy vấn, "
                 f"không phải phần biên soạn thêm.</p>")
    parts.append("<p class='note'>Số cá thể theo lớp — 14 lớp lớn nhất:</p>")
    parts.append(bars(onto["per_class"], color=0))

    parts.append(f"""<h2>2 · Phân bố dataset</h2>
<p class="note">{vi(data['total'])} câu hỏi trên {data['families']} họ truy vấn.
Câu hỏi trung vị {data['q_median']:.0f} từ (dài nhất {data['q_max']}), truy vấn
đích trung vị {data['t_median']:.0f} từ (dài nhất {data['t_max']}).</p>""")
    parts.append(tiles([
        ("huấn luyện", vi(data["splits"]["train"])),
        ("kiểm định", vi(data["splits"]["val"])),
        ("kiểm tra", vi(data["splits"]["test"])),
        ("từ chối", f"{data['refusals'] / data['total']:.1%}"),
        ("họ truy vấn", str(data["families"])),
    ]))
    parts.append("<p class='note'>Theo giọng nói — bốn phong cách cân nhau có chủ đích:</p>")
    parts.append(bars(sorted(data["registers"].items()), color=1))
    parts.append("<p class='note'>Theo độ dài câu hỏi (số từ):</p>")
    parts.append(bars(
        [(k, data["bands"][k]) for k in ("2-6", "7-9", "10-13", "14-17", "18+")],
        color=2,
    ))
    parts.append("<p class='note'>12 họ truy vấn nhiều câu nhất:</p>")
    parts.append(bars(data["top_families"], color=0))

    if runs:
        parts.append("<h2>3 · Kết quả model</h2>")
        parts.append("<p class='note'>Ba chỉ số chính, không có điểm tổng hợp. "
                     "Mọi model đi qua cùng một bộ chấm trên cùng ba tập.</p>")
        parts.append(table(
            ["lượt chấm", "model", "đúng node", "đúng dạng", "từ chối đúng"],
            [[
                r["name"], r["run"].get("model", "?"),
                f"{r['primary']['node_selection']['rate']:.1%}",
                f"{r['primary']['query_shape']['rate']:.1%}",
                f"{r['primary']['rejection_decision']['rate']:.1%}",
            ] for r in runs],
        ))
        last = runs[-1]
        if last["by_kind"]:
            parts.append("<h2>4 · Model hỏng ở đâu</h2>")
            parts.append("<p class='note'>Đúng dạng theo <b>kiểu tên node</b>. "
                         "Bảng bị hỏi bằng nội dung; điều/khoản được hỏi bằng chính "
                         "toạ độ của nó. Chênh lệch giữa hai nhóm là hạn chế lớn "
                         "nhất còn lại.</p>")
            parts.append(bars(sorted(last["by_kind"].items(), key=lambda kv: -kv[1]),
                              color=1, pct=True))
        if last["by_register"]:
            parts.append("<p class='note'>Đúng dạng theo giọng nói — câu viết "
                         "nhiễu (không dấu, sai chính tả) là chỗ yếu nhất:</p>")
            parts.append(bars(sorted(last["by_register"].items(), key=lambda kv: -kv[1]),
                              color=2, pct=True))
            parts.append(table(
                ["giọng nói", "đúng dạng"],
                [[k, f"{v:.1%}"] for k, v in sorted(last["by_register"].items())],
            ))

    parts.append("</div>")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("".join(parts), encoding="utf-8")
    print(f"đã ghi {OUT.relative_to(ROOT)}")
    print(f"  ontology {vi(onto['triples'])} bộ ba · {onto['classes']} lớp · "
          f"{vi(onto['individuals'])} cá thể")
    print(f"  dataset  {vi(data['total'])} câu · {data['families']} họ")
    print(f"  model    {len(runs)} lượt chấm")


if __name__ == "__main__":
    main()
