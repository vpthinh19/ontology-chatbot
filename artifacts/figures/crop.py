"""Cắt bỏ khoảng nền trống giữa câu trả lời và thanh nhập liệu.

Ảnh chụp ở khung cố định 1120x700 nên câu trả lời ngắn để lại một vệt rỗng kéo dài
tới thanh nhập liệu ở đáy. Vệt đó không nói lên điều gì, mà lại đẩy phần chữ nhỏ đi
khi ảnh được thu vào trang tài liệu.

Ranh giới được dò từ chính ảnh chứ không ghi cứng. Trang có hai màu nền khác nhau -
khung trò chuyện một màu, nền trang một màu - nên không thể tìm khoảng rỗng bằng
cách so với "màu nền". Thay vào đó tìm dải đồng màu dài nhất ở nửa dưới ảnh: chỗ
nào kéo dài mà không đổi màu thì chỗ đó không có gì để xem.
"""
import subprocess
from pathlib import Path

# Nhiễu nén làm mức xám của cùng một vùng phẳng chênh nhau một hai mức; ngưỡng này
# coi chúng là cùng màu mà vẫn tách được các khối nội dung.
NGUONG = 2
# Chừa lại một vành nền ở hai đầu vết cắt để ảnh không bị cắt sát chữ.
VANH = 40


def do_sang_tung_dong(tep: Path) -> list[int]:
    """Hạ ảnh xuống một cột để lấy độ sáng trung bình của từng dòng."""
    ra = subprocess.run(
        ["magick", str(tep), "-colorspace", "Gray", "-resize", "1x!", "-depth", "8", "txt:-"],
        capture_output=True, text=True, check=True,
    ).stdout
    return [int(d.split("gray(")[1].rstrip(")")) for d in ra.splitlines()[1:]]


def dai_phang_nhat(muc: list[int]) -> tuple[int, int]:
    """Dải dòng đồng màu dài nhất kéo xuống tới nửa dưới ảnh.

    Xét theo chỗ dải KẾT THÚC chứ không phải chỗ nó bắt đầu: khoảng rỗng cần cắt
    thường mở ra ngay dưới câu trả lời - có khi còn ở nửa trên - rồi chạy dài
    xuống tận thanh nhập liệu. Còn dải phẳng ở mép trên ảnh thì kết thúc sớm nên
    không lọt vào.
    """
    giua = len(muc) // 2
    dai = (0, 0)
    dau = 0
    for i in range(1, len(muc) + 1):
        if i < len(muc) and abs(muc[i] - muc[dau]) <= NGUONG:
            continue
        if i >= giua and i - dau > dai[1] - dai[0]:
            dai = (dau, i)
        dau = i
    return dai


def cat(tep: Path) -> str:
    muc = do_sang_tung_dong(tep)
    dau, cuoi = dai_phang_nhat(muc)
    if cuoi - dau < 3 * VANH:
        return "không có khoảng rỗng đáng cắt"

    ket_thuc, bat_dau_thanh = dau + VANH, cuoi - VANH
    w = int(subprocess.run(["magick", "identify", "-format", "%w", str(tep)],
                           capture_output=True, text=True, check=True).stdout)
    h = len(muc)
    tren, duoi = f"/tmp/tren-{tep.name}", f"/tmp/duoi-{tep.name}"
    subprocess.run(["magick", str(tep), "-crop", f"{w}x{ket_thuc}+0+0", "+repage", tren], check=True)
    subprocess.run(["magick", str(tep), "-crop", f"{w}x{h - bat_dau_thanh}+0+{bat_dau_thanh}",
                    "+repage", duoi], check=True)
    subprocess.run(["magick", tren, duoi, "-append", str(tep)], check=True)
    return subprocess.run(["magick", "identify", "-format", "%wx%h", str(tep)],
                          capture_output=True, text=True, check=True).stdout


if __name__ == "__main__":
    for ten in ("giao-dien.png", "giao-dien-tu-choi.png", "giao-dien-tra-cuu.png"):
        tep = Path("docs/images") / ten
        if tep.is_file():
            print(f"  {ten}: {cat(tep)}")
