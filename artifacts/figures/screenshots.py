"""Chụp ảnh giao diện từ lượt trò chuyện thật với máy chủ đang chạy."""
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:8811/"
RA = Path("docs/images")
CAU = [("giao-dien.png", "học lại môn bị rớt thì làm sao ạ"),
       ("giao-dien-tu-choi.png", "tối nay ăn gì ngon nhỉ?")]

# Ảnh thứ ba bắt trạng thái GIỮA lượt, lúc công cụ đang chạy và giao diện còn
# đang hiện các cụm từ khoá gửi đi. Trạng thái đó chỉ sống khoảng hai chục mili
# giây - chọn truy vấn mất 3,8 ms và chạy truy vấn mất 16 ms - nên không kịp chụp
# bằng cách chờ rồi bấm máy.
#
# Cách làm: gọi máy chủ thật, lấy trọn luồng sự kiện của lượt đó, rồi trả lại cho
# trang đúng phần đầu tới sự kiện tra cứu. Nội dung hiển thị vì thế là của một
# lượt có thật; chỉ có nhịp giao hàng bị giữ lại ở đúng khoảnh khắc cần chụp.
CAU_TRA_CUU = ("giao-dien-tra-cuu.png", "điều kiện xét học bổng khuyến khích học tập là gì")


def mo_trang(trinh):
    trang = trinh.new_page(viewport={"width": 1120, "height": 700}, device_scale_factor=2)
    trang.goto(URL, wait_until="networkidle")
    return trang


def den_luc_tra_cuu(than: str) -> str:
    """Cắt luồng sự kiện ngay sau sự kiện tra cứu cuối cùng."""
    khoi = than.split("\n\n")
    giu = []
    for k in khoi:
        if '"tra_cuu_xong"' in k:
            break
        giu.append(k)
    if not any('"tra_cuu"' in k for k in giu):
        raise SystemExit("lượt này không gọi công cụ, không có trạng thái tra cứu để chụp")
    return "\n\n".join(giu) + "\n\n"


with sync_playwright() as p:
    trinh = p.chromium.launch(channel="chrome", headless=True)
    for ten, cau in CAU:
        trang = mo_trang(trinh)
        trang.fill(".prompt-input", cau)
        trang.press(".prompt-input", "Enter")
        # Trang gắn lớp 'bot-responding' lên body suốt lượt trả lời; nó rời đi
        # là lúc câu trả lời viết xong.
        trang.wait_for_selector("body.bot-responding", timeout=15000)
        trang.wait_for_selector("body:not(.bot-responding)", timeout=180000)
        time.sleep(1.2)
        trang.screenshot(path=str(RA / ten), full_page=False)
        print(f"  {ten}: {len(trang.inner_text('.chats-container'))} ký tự")
        trang.close()

    ten, cau = CAU_TRA_CUU
    trang = mo_trang(trinh)

    def giu_o_tra_cuu(route):
        that = route.fetch()
        route.fulfill(
            status=200,
            headers={"Content-Type": "text/event-stream", "Cache-Control": "no-cache"},
            body=den_luc_tra_cuu(that.text()),
        )

    trang.route("**/chat", giu_o_tra_cuu)
    trang.fill(".prompt-input", cau)
    trang.press(".prompt-input", "Enter")
    trang.wait_for_function(
        "() => { const e = document.querySelector('.reply-line.status');"
        " return e && e.textContent.startsWith('Đang tra cứu:'); }",
        timeout=120000,
    )
    trang.screenshot(path=str(RA / ten), full_page=False)
    print(f"  {ten}: {trang.inner_text('.reply-line.status')!r}")
    trang.close()
    trinh.close()
