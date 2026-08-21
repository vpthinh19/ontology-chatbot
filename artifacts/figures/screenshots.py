"""Chụp ảnh giao diện từ lượt trò chuyện thật với máy chủ đang chạy."""
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:8811/"
RA = Path("docs/images")
CAU = [("giao-dien.png", "học lại môn bị rớt thì làm sao ạ"),
       ("giao-dien-tu-choi.png", "tối nay ăn gì ngon nhỉ?")]

with sync_playwright() as p:
    trinh = p.chromium.launch(channel="chrome", headless=True)
    for ten, cau in CAU:
        trang = trinh.new_page(viewport={"width": 1120, "height": 700}, device_scale_factor=2)
        trang.goto(URL, wait_until="networkidle")
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
    trinh.close()
