"""Đóng băng bộ kiểm tra tra cứu từ kết quả chạy thật.

Bộ này là mốc đối chiếu cho toàn bộ đợt tái cấu trúc ontology. Nó **không gọi mô
hình ngôn ngữ**: từ khoá đã được một lần chạy thật sinh ra và ghi lại trong
``results.json``, nên chạy lại chỉ tốn vài giây và cho cùng một kết quả.

Mỗi câu ghi cả IRI lẫn nhãn của mục đúng. IRI sẽ đổi khi ontology chuyển sang tên
tiếng Việt; nhãn thì không, nên bài kiểm vẫn chạy được xuyên qua lần đổi tên đó.

Chạy lại tệp này chỉ khi muốn đóng băng lại bộ câu - ví dụ sau khi sửa nhãn mục
đúng. Đổi bộ câu là mọi con số đã đo hết so sánh được.
"""

from __future__ import annotations

import json
from pathlib import Path

from rdflib import Graph
from rdflib.namespace import RDFS

from ontchatbot.search.vocabulary import ACADEMIC, local_name
from ontchatbot.settings import ONTOLOGY_PATH

HERE = Path(__file__).parent
KET_QUA = HERE / "results.json"
BO_KIEM = HERE / "retrieval.json"


def nhan_cua(graph: Graph, ten_cuc_bo: str) -> str:
    """Nhãn hiển thị của một mục, đọc từ ontology lúc đóng băng."""

    nhan = sorted(str(value) for value in graph.objects(ACADEMIC[ten_cuc_bo], RDFS.label))
    return nhan[0] if nhan else ten_cuc_bo


def main() -> None:
    graph = Graph()
    graph.parse(ONTOLOGY_PATH, format="turtle")

    ban_ghi = json.loads(KET_QUA.read_text(encoding="utf-8"))
    cau_hoi = []
    bo_qua = []
    for row in ban_ghi:
        if row["nhom"] != "trong_pham_vi":
            continue
        tu_khoa = [k.strip() for k in row["tu_khoa"] if k.strip()]
        node_dung = [n.lstrip(":") for n in row["node_dung"]]
        if not tu_khoa or not node_dung:
            bo_qua.append(row["id"])
            continue
        cau_hoi.append({
            "id": row["id"],
            "cau_hoi": row["cau_hoi"],
            "tu_khoa": tu_khoa,
            "node_dung": node_dung,
            "nhan_dung": [nhan_cua(graph, n) for n in node_dung],
        })

    BO_KIEM.write_text(
        json.dumps({"cau_hoi": cau_hoi}, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8",
    )
    print(f"đóng băng {len(cau_hoi)} câu vào {BO_KIEM.name}")
    if bo_qua:
        print(f"bỏ qua {len(bo_qua)} câu thiếu từ khoá hoặc mục đúng: {bo_qua}")
    thieu_nhan = [c["id"] for c in cau_hoi if any(n == d for n, d in zip(c["nhan_dung"], c["node_dung"]))]
    if thieu_nhan:
        print(f"⚠ {len(thieu_nhan)} câu có mục đúng không tìm thấy nhãn trong ontology: {thieu_nhan}")


if __name__ == "__main__":
    main()
