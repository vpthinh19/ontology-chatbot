"""Sinh câu hỏi cho bộ đề giữ kín bằng Codex CLI, lần lượt từng mô hình.

Mỗi mô hình nhận cùng lời nhắc ``prompt.md``, cộng danh sách câu phải tránh: các câu hỏi thử đã dùng khi phát
triển hệ thống (``--tranh``, mỗi dòng một câu, giữ ngoài repo) và các câu mà mô hình chạy trước đã sinh. Codex
chỉ được đọc một thư mục chép riêng các văn bản chính thức, đặt ngoài repo; lời nhắc đầy đủ và nhật ký của từng
mô hình ghi cạnh thư mục đó.

    uv run python resources/end-to-end/heldout/v2/generation/generate.py --nguon <thư mục ngoài repo> [--tranh <tệp>]
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).parent
ROOT = Path(__file__).resolve().parents[5]
VAN_BAN = ["Qd1052.md", "Qd1965.md", "Qd729.md", "Qd1314.md", "huong_dan_dong_hoc_phi.md",
           "DongHocPhi_VCB_2021.md", "Qd317.md", "tieu-chuan-hoc-bong.txt", "Qd626.md", "Qd753.md"]
MO_HINH = ["sol", "terra", "luna"]
MUC_TRANH = "\n## Các câu đã có"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--nguon", type=Path, required=True, help="thư mục chép văn bản cho Codex đọc")
    parser.add_argument("--tranh", type=Path, help="tệp câu hỏi phải tránh, mỗi dòng một câu")
    args = parser.parse_args()
    args.nguon.mkdir(parents=True, exist_ok=True)
    for ten in VAN_BAN:
        shutil.copy2(ROOT / "references" / ten, args.nguon / ten)

    tranh = [d.strip() for d in args.tranh.read_text(encoding="utf-8").splitlines() if d.strip()] if args.tranh else []
    goc = (HERE / "prompt.md").read_text(encoding="utf-8")
    for mo_hinh in MO_HINH:
        dau_ra = HERE / f"out-{mo_hinh}.json"
        if dau_ra.is_file():
            print(f"{mo_hinh}: đã có {dau_ra.name}, bỏ qua", flush=True)
        else:
            if tranh:
                loi_nhac = goc.rstrip() + "\n\n" + "\n".join(f"- {c}" for c in tranh) + "\n"
            else:
                loi_nhac = goc.split(MUC_TRANH)[0].rstrip() + "\n"
            (args.nguon.parent / f"prompt-{mo_hinh}.md").write_text(loi_nhac, encoding="utf-8")
            print(f"{mo_hinh}: đang sinh", flush=True)
            # Codex treo khi stdin không phải TTY, nên stdin luôn là DEVNULL.
            with open(args.nguon.parent / f"log-{mo_hinh}.txt", "w", encoding="utf-8") as log:
                ket_thuc = subprocess.run(
                    ["codex", "exec", "--skip-git-repo-check", "--sandbox", "read-only", "-C", str(args.nguon),
                     "-m", f"gpt-5.6-{mo_hinh}", "-c", 'model_reasoning_effort="high"',
                     "--output-schema", str(HERE / "schema.json"), "-o", str(dau_ra), loi_nhac],
                    stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, timeout=1500,
                )
            if ket_thuc.returncode or not dau_ra.is_file():
                raise SystemExit(f"{mo_hinh}: codex dừng với mã {ket_thuc.returncode}, xem log-{mo_hinh}.txt")
        tranh += [c["cau_hoi"] for c in json.loads(dau_ra.read_text(encoding="utf-8"))["cau_hoi"]]
        print(f"{mo_hinh}: xong, danh sách tránh có {len(tranh)} câu", flush=True)


if __name__ == "__main__":
    main()
