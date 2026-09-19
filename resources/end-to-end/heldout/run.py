"""Hỏi chatbot toàn bộ bộ đề giữ kín, lưu câu trả lời và dữ liệu công cụ của từng câu.

Chatbot được dựng đúng như máy chủ phục vụ: cùng lời hướng dẫn, cùng mô hình ngôn ngữ, cùng bộ máy tìm
kiếm trả 5 mục mỗi lần tra. Chỗ khác duy nhất là công cụ tra cứu được bọc để ghi lại từ khoá, mục trả
về, thời gian và nguyên văn dữ liệu của từng lần gọi. Script không chấm: câu trả lời được chấm riêng,
so với đáp án gốc trong ``questions.json``.

    set -a; . ./.env; set +a
    uv run python resources/end-to-end/heldout/run.py --luot 1            # ghi results-1.json
    CHAY_BU=1 uv run python resources/end-to-end/heldout/run.py --luot 1  # chỉ hỏi lại câu bị lỗi
    uv run python resources/end-to-end/heldout/run.py --luot 1 --bo-de <thư mục>  # bộ đề khác
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import time
from datetime import date
from pathlib import Path

import httpx

from ontchatbot.runtime.agent import MODEL_REQUEST_TIMEOUT_SECONDS, AgentLoop, build_instructions, read_vocabulary
from ontchatbot.runtime.api import MAX_MODEL_STEPS, MODEL_TURN_TIMEOUT_SECONDS
from ontchatbot.runtime.llm import LightningBusyError, LightningClient
from ontchatbot.runtime.lookup import bound_keywords, render_response
from ontchatbot.search import SearchEngine, TriGFileSource
from ontchatbot.settings import DEFAULT_LLM_BASE_URL, ONTOLOGY_PATH

HERE = Path(__file__).parent
TOP_K = 5
#: Số lần hỏi một câu khi khoá API bị giới hạn tốc độ.
SO_LAN_THU = 6
#: Nghỉ giữa hai câu, để lượt đo không tự đẩy khoá API vào giới hạn tốc độ.
NGHI_GIUA_CAU = float(os.environ.get("NGHI_GIUA_CAU", "4"))


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
            "ms": round((time.perf_counter() - bat_dau) * 1000, 2),
            "du_lieu": du_lieu,
        })
        return du_lieu


async def mot_luot(agent: AgentLoop, cau_hoi: str) -> tuple[str, list[str]]:
    tra_loi, danh_dau = "", []
    async for event in agent.stream([{"role": "user", "content": cau_hoi}]):
        if event.kind == "completed":
            tra_loi, danh_dau = event.content, list(event.marks)
    return tra_loi.strip(), danh_dau


def cho_khi_bi_gioi_han(exc: LightningBusyError, lan: int) -> float:
    """Số giây chờ khi dịch vụ vẫn quá tải sau các lần gọi lại của LightningClient: chờ
    theo lời dịch vụ, và không dưới 30 giây nhân số lần đã thử."""

    return max(exc.retry_after, 30.0 * (lan + 1))


async def hoi(agent: AgentLoop, cong_cu: CongCuCoVet, cau: dict) -> dict:
    # Lỗi 429 là giới hạn tốc độ của khoá API dùng cho lượt đo, không phải lỗi chatbot: chờ rồi hỏi
    # lại cả câu. Lỗi khác ghi nguyên như người dùng gặp, không che đi.
    for lan in range(SO_LAN_THU):
        cong_cu.vet.clear()
        bat_dau = time.perf_counter()
        try:
            (tra_loi, danh_dau), loi = await asyncio.wait_for(mot_luot(agent, cau["cau_hoi"]), MODEL_TURN_TIMEOUT_SECONDS), None
        except LightningBusyError as exc:
            tra_loi, danh_dau, loi = "", [], f"{type(exc).__name__}: {exc}"
            if lan + 1 < SO_LAN_THU:
                cho = cho_khi_bi_gioi_han(exc, lan)
                print(f"  {cau['id']} bị giới hạn tốc độ, chờ {cho:.0f}s rồi hỏi lại", flush=True)
                await asyncio.sleep(cho)
                continue
        except Exception as exc:
            tra_loi, danh_dau, loi = "", [], f"{type(exc).__name__}: {exc}"
        break
    giay = time.perf_counter() - bat_dau

    vet = list(cong_cu.vet)
    print(f"  {cau['id']} {giay:5.1f}s  goi={len(vet)}  {'OK' if not loi else loi[:60]}", flush=True)
    return {
        "id": cau["id"], "cau_hoi": cau["cau_hoi"], "tra_loi": tra_loi, "danh_dau": danh_dau, "loi": loi,
        "giay": round(giay, 2),
        "so_lan_goi": len(vet),
        "tu_khoa": [goi["tu_khoa"] for goi in vet],
        "node_lay_ve": sorted({n for goi in vet for n in goi["node"]}),
        "nhan_lay_ve": sorted({x for goi in vet for x in goi["nhan"]}),
        "ms_cong_cu": [goi["ms"] for goi in vet],
        # Giữ nguyên văn dữ liệu công cụ để người chấm đối chiếu trích dẫn với đúng dữ liệu của lượt đó.
        "du_lieu": "\n".join(goi["du_lieu"] for goi in vet),
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--luot", type=int, required=True, help="số thứ tự lượt chạy")
    parser.add_argument("--bo-de", type=Path, default=HERE,
                        help="thư mục chứa questions.json; kết quả và run-info.json ghi vào cùng thư mục")
    args = parser.parse_args()
    cau_hoi = json.loads((args.bo_de / "questions.json").read_text(encoding="utf-8"))
    ket_qua = args.bo_de / f"results-{args.luot}.json"
    thong_tin_tep = args.bo_de / "run-info.json"
    luot = ket_qua.stem.removeprefix("results-")

    model = os.environ.get("ONTCHATBOT_LLM_MODEL")
    key = os.environ.get("ONTCHATBOT_LLM_API_KEY")
    if not model or not key:
        raise SystemExit("đặt ONTCHATBOT_LLM_MODEL và ONTCHATBOT_LLM_API_KEY trước khi chạy")
    base_url = os.environ.get("ONTCHATBOT_LLM_BASE_URL", DEFAULT_LLM_BASE_URL).rstrip("/") + "/"

    engine = SearchEngine.open(TriGFileSource(ONTOLOGY_PATH), top_k=TOP_K)
    cong_cu = CongCuCoVet(engine)
    co_san = build_instructions(read_vocabulary(engine.ontology))

    cu = {}
    if ket_qua.is_file() and os.environ.get("CHAY_BU"):
        cu = {r["id"]: r for r in json.loads(ket_qua.read_text(encoding="utf-8")) if not r["loi"]}
        print(f"giữ lại {len(cu)} câu đã có câu trả lời, hỏi lại phần còn lại")

    phien_ban = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                               cwd=HERE).stdout.strip()
    thong_tin = json.loads(thong_tin_tep.read_text(encoding="utf-8")) if thong_tin_tep.is_file() else {}
    thong_tin[luot] = {"mo_hinh": model, "ngay": date.today().isoformat(), "commit": phien_ban,
                       "top_k": TOP_K, "so_buoc_toi_da": MAX_MODEL_STEPS}
    thong_tin_tep.write_text(json.dumps(thong_tin, ensure_ascii=False, indent=1), encoding="utf-8")

    ban_ghi: list[dict] = []
    bat_dau = time.perf_counter()
    async with httpx.AsyncClient(
        base_url=base_url,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        timeout=MODEL_REQUEST_TIMEOUT_SECONDS,
    ) as http:
        agent = AgentLoop(LightningClient(http, model=model), cong_cu, instructions=co_san, max_steps=MAX_MODEL_STEPS)
        for cau in cau_hoi:
            if cau["id"] in cu:
                ban_ghi.append(cu[cau["id"]])
                continue
            ban_ghi.append(await hoi(agent, cong_cu, cau))
            await asyncio.sleep(NGHI_GIUA_CAU)
            # Ghi sau mỗi câu: lượt đo bị ngắt giữa chừng thì CHAY_BU hỏi tiếp phần còn lại.
            ket_qua.write_text(json.dumps(ban_ghi, ensure_ascii=False, indent=1), encoding="utf-8")
    loi = sum(1 for r in ban_ghi if r["loi"])
    print(f"\nxong {len(ban_ghi)} câu trong {time.perf_counter() - bat_dau:.0f}s, {loi} lỗi → {ket_qua}")


if __name__ == "__main__":
    asyncio.run(main())
