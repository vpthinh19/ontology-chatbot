"""Cắt bỏ khoảng nền trống giữa câu trả lời và thanh nhập liệu."""
import subprocess, sys
from pathlib import Path

def cao_noi_dung(tep: Path) -> int:
    """Dòng cuối cùng còn khác màu nền, tính từ trên xuống."""
    ra = subprocess.run(["magick", str(tep), "-colorspace", "Gray", "-scale", "1x!",
                         "-depth", "8", "txt:-"], capture_output=True, text=True).stdout
    # bỏ qua, dùng cách khác bên dưới
    return 0

for ten, ket_thuc, bat_dau_thanh in [("giao-dien.png", 1080, 1150),
                                     ("giao-dien-tu-choi.png", 400, 1090),
                                     ("giao-dien-tra-cuu.png", 330, 1560)]:
    tep = Path("docs/images") / ten
    if not tep.is_file():
        continue
    w = int(subprocess.run(["magick", "identify", "-format", "%w", str(tep)],
                           capture_output=True, text=True).stdout)
    h = int(subprocess.run(["magick", "identify", "-format", "%h", str(tep)],
                           capture_output=True, text=True).stdout)
    tren, duoi = f"/tmp/tren-{ten}", f"/tmp/duoi-{ten}"
    subprocess.run(["magick", str(tep), "-crop", f"{w}x{ket_thuc}+0+0", "+repage", tren], check=True)
    subprocess.run(["magick", str(tep), "-crop", f"{w}x{h-bat_dau_thanh}+0+{bat_dau_thanh}",
                    "+repage", duoi], check=True)
    subprocess.run(["magick", tren, duoi, "-append", str(tep)], check=True)
    print(" ", ten, subprocess.run(["magick", "identify", "-format", "%wx%h", str(tep)],
                                   capture_output=True, text=True).stdout)
