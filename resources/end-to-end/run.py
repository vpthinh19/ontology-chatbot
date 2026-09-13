"""Đo trợ lý đầu-cuối: hỏi bằng câu hỏi thật, chấm bằng dữ liệu công cụ đã trả về.

Trợ lý được dựng đúng như máy chủ phục vụ: cùng lời hướng dẫn, cùng mô hình ngôn ngữ, cùng
engine tìm kiếm trả 3 mục mỗi lần tra. Chỗ khác duy nhất là công cụ tra cứu được bọc để ghi
lại từ khoá, mục trả về, thời gian và nguyên văn dữ liệu của từng lần gọi.

Bốn phép đếm tất định, đều kiểm lại được:
  1. gọi công cụ   - câu học vụ có tra cứu trước khi trả lời không
  2. lấy đúng mục  - trong các mục công cụ trả về, có mục mà câu hỏi nhắm tới không
  3. bám dữ liệu   - số và chữ viết tắt trong câu trả lời có mặt trong dữ liệu trả về không
  4. từ chối đúng  - câu ngoài phạm vi và câu hỏi vào khoảng trống có được nói là không có không

    set -a; . ./.env; set +a
    uv run python resources/end-to-end/run.py             # hỏi cả 85 câu, ghi results.json
    CHAY_BU=1 uv run python resources/end-to-end/run.py   # chỉ hỏi lại những câu bị lỗi
    uv run python resources/end-to-end/run.py --cham-lai  # tính lại phép đếm từ câu trả lời đã lưu
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import time
import unicodedata
from datetime import date
from pathlib import Path

import httpx

from ontchatbot.runtime.agent import MODEL_REQUEST_TIMEOUT_SECONDS, AgentLoop, build_instructions, read_vocabulary
from ontchatbot.runtime.api import MAX_MODEL_STEPS, MODEL_TURN_TIMEOUT_SECONDS
from ontchatbot.runtime.llm import LightningClient
from ontchatbot.runtime.lookup import bound_keywords, render_response
from ontchatbot.search import SearchEngine, TriGFileSource
from ontchatbot.settings import DEFAULT_LLM_BASE_URL, ONTOLOGY_PATH

HERE = Path(__file__).parent
CAU_HOI = json.loads((HERE / "questions.json").read_text(encoding="utf-8"))
KET_QUA = HERE / "results.json"
THONG_TIN = HERE / "run-info.json"
TOP_K = 3
#: Số lần hỏi một câu khi khoá API bị giới hạn tốc độ.
SO_LAN_THU = 6
#: Nghỉ giữa hai câu, để lượt đo không tự đẩy khoá API vào giới hạn tốc độ.
NGHI_GIUA_CAU = float(os.environ.get("NGHI_GIUA_CAU", "4"))

# Số có từ hai chữ số, phần trăm, và chữ viết tắt in hoa: đây là chỗ mô hình bịa ra thứ
# nghe như dữ kiện. Số một chữ số bỏ qua vì nó trùng với số thứ tự.
SO = re.compile(r"\d[\d.,]*\d|\d+%")
VIET_TAT = re.compile(r"\b[A-Z]{2,}\d*\b")
_BO_QUA = {"II", "III", "IV", "VI", "VII", "VIII", "IX", "XI", "XII"}
TU_CHOI = ("không tìm thấy", "không có thông tin", "ngoài phạm vi", "không thuộc",
           "không nằm trong", "chưa có", "không có dữ liệu", "không hỗ trợ",
           "không liên quan", "không thể trả lời", "không chứa", "không đề cập",
           "không quản lý", "không cung cấp", "không có trong")


class CongCuCoVet:
    """Công cụ tra cứu y như khi phục vụ, cộng một cuốn sổ ghi mọi lần gọi của câu đang hỏi."""

    def __init__(self, engine: SearchEngine) -> None:
        self.engine = engine
        self.vet: list[dict] = []

    async def __call__(self, keywords) -> str:
        bounded, truncation = bound_keywords(keywords)
        bat_dau = time.perf_counter()
        response = self.engine.search(bounded)
        du_lieu = render_response(response, truncation)
        self.vet.append({
            "tu_khoa": bounded,
            "node": [result.node.lstrip(":") for result in response.results],
            "nhan": [result.label for result in response.results],
            "so_dong": sum(len(facts) for result in response.results for _, facts in result.profile.groups),
            "ms": round((time.perf_counter() - bat_dau) * 1000, 2),
            "du_lieu": du_lieu,
        })
        return du_lieu


def chuan_hoa(text: str) -> str:
    return unicodedata.normalize("NFC", text).casefold().strip()


#: Dấu phân cách hàng nghìn giữa các chữ số: "6.000.000" và "6000000" là cùng một số.
_PHAN_CACH_NGHIN = re.compile(r"(?<=\d)[.,](?=\d{3}(?!\d))")


def khong_bam_du_lieu(tra_loi: str, du_lieu: str, co_san: str, cau_hoi: str = "") -> list[str]:
    """Những số và chữ viết tắt trong câu trả lời mà dữ liệu, câu hỏi và lời hướng dẫn đều không có.

    Lời hướng dẫn kèm sẵn vài tên chủ đề lấy từ ontology; trợ lý nêu lại chúng khi mời người
    dùng hỏi rõ hơn, và số nhắc lại từ câu hỏi cũng không phải bịa. Số được so sau khi bỏ dấu
    phân cách hàng nghìn, vì trợ lý hay viết "6.000.000" cho giá trị "6000000".
    """

    co = _PHAN_CACH_NGHIN.sub("", du_lieu + cau_hoi + co_san)
    nen_co = {m.group() for m in SO.finditer(tra_loi) if _PHAN_CACH_NGHIN.sub("", m.group()) not in co}
    nen_co |= {m.group() for m in VIET_TAT.finditer(tra_loi) if m.group() not in _BO_QUA and m.group() not in co}
    return sorted(nen_co)


def co_noi_la_thieu(tra_loi: str) -> bool:
    thap = tra_loi.lower()
    return any(cum in thap for cum in TU_CHOI)


async def mot_luot(agent: AgentLoop, cau_hoi: str) -> str:
    tra_loi = ""
    async for event in agent.stream([{"role": "user", "content": cau_hoi}]):
        if event.kind == "completed":
            tra_loi = event.content
    return tra_loi.strip()


def cho_khi_bi_gioi_han(exc: httpx.HTTPStatusError, lan: int) -> float:
    """Số giây chờ sau lỗi 429: theo Retry-After nếu máy chủ gửi, không thì tăng dần."""

    retry_after = exc.response.headers.get("retry-after", "")
    return float(retry_after) if retry_after.isdigit() else 30.0 * (lan + 1)


async def hoi(agent: AgentLoop, cong_cu: CongCuCoVet, cau: dict, nhom: str, co_san: str) -> dict:
    # Lỗi 429 là giới hạn tốc độ của khoá API dùng chung cho lượt đo, không phải lỗi trợ lý:
    # chờ rồi hỏi lại cả câu. Lỗi khác ghi nguyên như người dùng gặp, không che đi.
    for lan in range(SO_LAN_THU):
        cong_cu.vet.clear()
        bat_dau = time.perf_counter()
        try:
            tra_loi, loi = await asyncio.wait_for(mot_luot(agent, cau["cau_hoi"]), MODEL_TURN_TIMEOUT_SECONDS), None
        except httpx.HTTPStatusError as exc:
            tra_loi, loi = "", f"{type(exc).__name__}: {exc}"
            if exc.response.status_code == 429 and lan + 1 < SO_LAN_THU:
                cho = cho_khi_bi_gioi_han(exc, lan)
                print(f"  {cau['id']:<16} bị giới hạn tốc độ, chờ {cho:.0f}s rồi hỏi lại", flush=True)
                await asyncio.sleep(cho)
                continue
        except Exception as exc:
            tra_loi, loi = "", f"{type(exc).__name__}: {exc}"
        break
    giay = time.perf_counter() - bat_dau

    vet = list(cong_cu.vet)
    ban_ghi = {
        "id": cau["id"], "nhom": nhom, "cau_hoi": cau["cau_hoi"],
        "tra_loi": tra_loi, "loi": loi, "giay": round(giay, 2),
        "so_lan_goi": len(vet),
        "tu_khoa": [k for goi in vet for k in goi["tu_khoa"]],
        "so_tu_khoa_moi_lan": [len(goi["tu_khoa"]) for goi in vet],
        "node_lay_ve": sorted({n for goi in vet for n in goi["node"]}),
        "nhan_lay_ve": sorted({x for goi in vet for x in goi["nhan"]}),
        "so_dong_du_lieu": sum(goi["so_dong"] for goi in vet),
        "ms_cong_cu": [goi["ms"] for goi in vet],
        # Giữ nguyên văn dữ liệu công cụ: phép chấm chất lượng đối chiếu câu trả lời với đúng
        # dữ liệu của chính lượt đó, và phép chấm lại dùng nó mà không phải hỏi lại.
        "du_lieu": "\n".join(goi["du_lieu"] for goi in vet),
    }
    dan_xuat(ban_ghi, cau, nhom, co_san)
    print(f"  {ban_ghi['id']:<16} {nhom:<16} {giay:5.1f}s  goi={ban_ghi['so_lan_goi']}"
          f"  {'OK' if not loi else loi[:60]}", flush=True)
    return ban_ghi


def dan_xuat(ban_ghi: dict, cau: dict, nhom: str, co_san: str) -> None:
    """Các trường tính từ câu trả lời đã lưu và bộ câu hỏi hiện tại, nên chấm lại không cần hỏi lại."""

    for khoa in ("register", "chuyen_nhom", "node_dung", "nhan_dung", "lay_dung_muc", "ngoai_pham_vi"):
        ban_ghi.pop(khoa, None)
    tra_loi = ban_ghi["tra_loi"]
    ban_ghi["nhom"] = nhom
    ban_ghi["bia_dat"] = khong_bam_du_lieu(tra_loi, ban_ghi["du_lieu"], co_san, cau["cau_hoi"]) if tra_loi else []
    ban_ghi["noi_la_thieu"] = co_noi_la_thieu(tra_loi)
    for khoa in ("register", "chuyen_nhom"):
        if khoa in cau:
            ban_ghi[khoa] = cau[khoa]
    if nhom == "trong_pham_vi":
        ban_ghi["node_dung"], ban_ghi["nhan_dung"] = cau["node_dung"], cau["nhan_dung"]
        if cau.get("ngoai_pham_vi"):
            ban_ghi["lay_dung_muc"], ban_ghi["ngoai_pham_vi"] = None, cau["ngoai_pham_vi"]
        else:
            can_nhan = {chuan_hoa(x) for x in cau["nhan_dung"]}
            ban_ghi["lay_dung_muc"] = bool(set(cau["node_dung"]) & set(ban_ghi["node_lay_ve"])) or any(
                chuan_hoa(x) in can_nhan for x in ban_ghi["nhan_lay_ve"])


async def main() -> None:
    engine = SearchEngine.open(TriGFileSource(ONTOLOGY_PATH), top_k=TOP_K)
    cong_cu = CongCuCoVet(engine)
    co_san = build_instructions(read_vocabulary(engine.ontology))

    if "--cham-lai" in sys.argv:
        theo_id = {cau["id"]: (cau, nhom) for nhom, rows in CAU_HOI.items() for cau in rows}
        ban_ghi = json.loads(KET_QUA.read_text(encoding="utf-8"))
        for r in ban_ghi:
            dan_xuat(r, *theo_id[r["id"]], co_san)
        thu_tu = {cau_id: i for i, cau_id in enumerate(theo_id)}
        ban_ghi.sort(key=lambda r: thu_tu[r["id"]])
        KET_QUA.write_text(json.dumps(ban_ghi, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"đã chấm lại {len(ban_ghi)} câu theo bộ câu hỏi hiện tại, không hỏi lại mô hình")
        return

    model = os.environ.get("ONTCHATBOT_LLM_MODEL")
    key = os.environ.get("ONTCHATBOT_LLM_API_KEY")
    if not model or not key:
        raise SystemExit("đặt ONTCHATBOT_LLM_MODEL và ONTCHATBOT_LLM_API_KEY trước khi chạy")
    base_url = os.environ.get("ONTCHATBOT_LLM_BASE_URL", DEFAULT_LLM_BASE_URL).rstrip("/") + "/"

    cu = {}
    if KET_QUA.is_file() and os.environ.get("CHAY_BU"):
        cu = {r["id"]: r for r in json.loads(KET_QUA.read_text(encoding="utf-8")) if not r["loi"]}
        print(f"giữ lại {len(cu)} câu đã đo được, hỏi lại phần còn lại")

    THONG_TIN.write_text(json.dumps({"mo_hinh": model, "ngay": date.today().isoformat(), "top_k": TOP_K,
                                     "so_buoc_toi_da": MAX_MODEL_STEPS}, ensure_ascii=False, indent=1),
                         encoding="utf-8")
    ban_ghi: list[dict] = []
    bat_dau = time.perf_counter()
    async with httpx.AsyncClient(
        base_url=base_url,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        timeout=MODEL_REQUEST_TIMEOUT_SECONDS,
    ) as http:
        agent = AgentLoop(LightningClient(http, model=model), cong_cu, instructions=co_san, max_steps=MAX_MODEL_STEPS)
        for nhom in ("trong_pham_vi", "ngoai_pham_vi", "do_thi_khong_co"):
            for cau in CAU_HOI[nhom]:
                if cau["id"] in cu:
                    ban_ghi.append(cu[cau["id"]])
                    continue
                ban_ghi.append(await hoi(agent, cong_cu, cau, nhom, co_san))
                await asyncio.sleep(NGHI_GIUA_CAU)
                # Ghi sau mỗi câu: lượt đo dài, bị ngắt giữa chừng thì CHAY_BU hỏi tiếp phần còn lại.
                KET_QUA.write_text(json.dumps(ban_ghi, ensure_ascii=False, indent=1), encoding="utf-8")
    loi = sum(1 for r in ban_ghi if r["loi"])
    print(f"\nxong {len(ban_ghi)} câu trong {time.perf_counter() - bat_dau:.0f}s, {loi} lỗi → {KET_QUA}")


if __name__ == "__main__":
    asyncio.run(main())
