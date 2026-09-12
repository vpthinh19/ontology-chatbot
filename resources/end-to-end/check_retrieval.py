"""Chạy bộ kiểm tra tra cứu và so với mốc đã ghi.

Không gọi mô hình ngôn ngữ: từ khoá lấy từ ``retrieval.json`` đã đóng băng, chỉ
chạy engine tìm kiếm. Dùng làm lưới an toàn cho cả đợt tái cấu trúc ontology -
mỗi bước sửa dữ liệu xong thì chạy lại, câu nào đang đạt mà tụt là biết ngay.

    python resources/end-to-end/check_retrieval.py            # chạy và so mốc
    python resources/end-to-end/check_retrieval.py --ghi-moc  # ghi lại mốc mới

Khớp mục đúng theo IRI trước, không được thì theo nhãn. Nhờ vậy bài kiểm vẫn chạy
sau khi ontology đổi sang IRI tiếng Việt.
"""

from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from pathlib import Path

from ontchatbot.search import SearchEngine, TurtleFileSource
from ontchatbot.settings import ONTOLOGY_PATH

HERE = Path(__file__).parent
BO_KIEM = HERE / "retrieval.json"
MOC = HERE / "retrieval-baseline.json"


def chuan_hoa(text: str) -> str:
    return unicodedata.normalize("NFC", text).casefold().strip()


def thu_hang(ket_qua, node_dung: list[str], nhan_dung: list[str]) -> int | None:
    """Vị trí của mục đúng trong danh sách trả về, đếm từ 1; None nếu không có."""

    can_node = {n.lstrip(":") for n in node_dung}
    can_nhan = {chuan_hoa(n) for n in nhan_dung}
    for vi_tri, result in enumerate(ket_qua, start=1):
        if result.node.lstrip(":") in can_node or chuan_hoa(result.label) in can_nhan:
            return vi_tri
    return None


def chay(engine: SearchEngine) -> dict:
    cau_hoi = [c for c in json.loads(BO_KIEM.read_text(encoding="utf-8"))["cau_hoi"]
               if not c.get("ngoai_pham_vi")]
    dat, truot, thu_hang_dat = [], [], []
    for cau in cau_hoi:
        response = engine.search(cau["tu_khoa"])
        vi_tri = thu_hang(response.results, cau["node_dung"], cau["nhan_dung"])
        if vi_tri:
            dat.append(cau["id"])
            thu_hang_dat.append(vi_tri)
        else:
            truot.append((cau, [r.label for r in response.results]))
    return {"dat": dat, "truot": truot, "thu_hang": thu_hang_dat, "tong": len(cau_hoi)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ghi-moc", action="store_true", help="ghi lại mốc theo kết quả lần chạy này")
    args = parser.parse_args()

    engine = SearchEngine.open(TurtleFileSource(ONTOLOGY_PATH))
    kq = chay(engine)
    dau_bang = sum(1 for v in kq["thu_hang"] if v == 1)

    print(f"tìm ra mục đúng : {len(kq['dat'])}/{kq['tong']}   (đứng đầu: {dau_bang})")
    print(f"trượt           : {len(kq['truot'])}\n")
    for cau, duoc in kq["truot"]:
        print(f"  {cau['cau_hoi'][:60]}")
        print(f"      cần  : {', '.join(cau['nhan_dung'])}")
        print(f"      được : {', '.join(duoc) if duoc else '(không có kết quả)'}")

    if args.ghi_moc:
        MOC.write_text(
            json.dumps({"tong": kq["tong"], "dat": sorted(kq["dat"])}, ensure_ascii=False, indent=1) + "\n",
            encoding="utf-8",
        )
        print(f"\nđã ghi mốc: {len(kq['dat'])}/{kq['tong']} câu đạt")
        return 0

    if not MOC.exists():
        print("\nchưa có mốc; chạy lại với --ghi-moc để ghi")
        return 0

    moc = set(json.loads(MOC.read_text(encoding="utf-8"))["dat"])
    tut = sorted(moc - set(kq["dat"]))
    them = sorted(set(kq["dat"]) - moc)
    print(f"\nso với mốc: {len(them)} câu mới đạt, {len(tut)} câu tụt")
    for cid in tut:
        print(f"  ⚠ tụt: {cid}")
    return 1 if tut else 0


if __name__ == "__main__":
    sys.exit(main())
