"""Đồng bộ nhãn của bộ câu hỏi đầu-cuối với tập dữ liệu hiện tại.

**Danh sách 85 câu là cố định.** Nó được chọn một lần bằng cách rút phân tầng theo
phong cách hỏi, rồi đóng băng trong ``questions.json``. Rút lại bằng một hạt giống
khác - hay từ một tệp nguồn khác - sẽ ra một bộ câu khác, và mọi con số đã đo trên
bộ cũ hết so sánh được. Vì vậy tệp này KHÔNG chọn lại câu; nó chỉ đọc lại nhãn.

Nhãn phải đọc lại vì đây chính là chỗ đã sai một lần: bộ câu hỏi lấy nhãn "ngoài
phạm vi" từ kết quả benchmark của một model cũ, rồi tập dữ liệu sửa nhãn mà bộ câu
hỏi thì không, nên một câu ĐỒ THỊ TRẢ LỜI ĐƯỢC vẫn bị chấm như câu phải từ chối.
Chạy tệp này sau mỗi lần sửa tập dữ liệu thì lệch đó không tái diễn.

Nhóm ``do_thi_khong_co`` viết tay và không có trong tập dữ liệu, nên giữ nguyên.
Nó phải được kiểm bằng tay với đồ thị: một câu lọt vào đây mà đồ thị trả lời được
sẽ âm thầm biến một câu trả lời ĐÚNG thành một lỗi bịa đặt.
"""
import json
from pathlib import Path

HERE = Path(__file__).parent
BO_CAU = HERE / "questions.json"
TAP = Path("resources/dataset")


def doc_tap_du_lieu() -> dict[str, dict]:
    rows = {}
    for split in ("train", "val", "test"):
        for line in (TAP / f"{split}.jsonl").read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            rows[row["id"]] = row
    return rows


def main() -> None:
    tap = doc_tap_du_lieu()
    bo = json.loads(BO_CAU.read_text(encoding="utf-8"))

    trong, ngoai = [], []
    doi_cho = []
    for nhom in ("trong_pham_vi", "ngoai_pham_vi"):
        for cau in bo[nhom]:
            row = tap.get(cau["id"])
            if row is None:
                raise SystemExit(f"{cau['id']} không còn trong tập dữ liệu")
            tra_loi_duoc = row["query_id"] != "no-information" and bool(row["target"])
            nhom_dung = "trong_pham_vi" if tra_loi_duoc else "ngoai_pham_vi"
            if nhom_dung != nhom:
                doi_cho.append((cau["id"], nhom, nhom_dung))
            if tra_loi_duoc:
                trong.append({
                    "id": cau["id"], "cau_hoi": row["input"], "register": row["register"],
                    "query_id": row["query_id"],
                    "node_dung": [t.lstrip(":") for t in row["target"]],
                })
            else:
                ngoai.append({
                    "id": cau["id"], "cau_hoi": row["input"], "register": row["register"],
                })

    bo["trong_pham_vi"], bo["ngoai_pham_vi"] = trong, ngoai
    BO_CAU.write_text(json.dumps(bo, ensure_ascii=False, indent=1), encoding="utf-8")

    for cid, cu, moi in doi_cho:
        print(f"  {cid}: {cu} -> {moi}")
    print(f"trong phạm vi {len(trong)} · ngoài phạm vi {len(ngoai)} "
          f"· đồ thị không có {len(bo['do_thi_khong_co'])} (viết tay, giữ nguyên)")


if __name__ == "__main__":
    main()
