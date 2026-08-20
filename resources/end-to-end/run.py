"""Đo trợ lý đầu-cuối: hỏi bằng câu người dùng thật, chấm bằng dữ liệu công cụ trả về.

Không chấm bằng cảm nhận. Bốn phép đếm, tất cả kiểm được lại:
  1. gọi công cụ        - câu học vụ có tra cứu trước khi trả lời không
  2. lấy đúng mục       - trong những mục công cụ lấy về, có mục mà câu hỏi nhắm tới không
  3. bám dữ liệu        - số và tên viết tắt trong câu trả lời có mặt trong dữ liệu trả về không
  4. từ chối đúng       - câu ngoài phạm vi có bị chặn không, câu đồ thị thiếu có nói thiếu không
"""
from __future__ import annotations

import asyncio, contextvars, json, os, re, sys, time
from pathlib import Path

sys.path.insert(0, str(Path("src").resolve()))

from ontchatbot.research.evaluation import _query_anchor_nodes
from ontchatbot.runtime.agent import build_agent
from ontchatbot.runtime.model import CTranslate2Generator, QueryGenerationError
from ontchatbot.runtime.pipeline import MARKER, OntologyChatbot
from ontchatbot.runtime.render import render_batch
from ontchatbot.runtime.sparql import SparqlError

HERE = Path(__file__).parent
CAU_HOI = json.loads((HERE / "questions.json").read_text())
KET_QUA = HERE / "results.json"
SONG_SONG = int(os.environ.get("SONG_SONG", "3"))

luot = contextvars.ContextVar("luot")


class ChatbotCoVet(OntologyChatbot):
    """Y hệt đường chạy thật, nhưng ghi lại từ khoá, truy vấn và mục lấy được."""

    def answer_many(self, questions):
        wanted = [q for q in dict.fromkeys(q.strip() for q in questions) if q]
        vet = luot.get(None)
        if not wanted:
            raise SparqlError("no keyword to look up")
        try:
            outputs = self.generator.generate_many(wanted)
        except QueryGenerationError:
            outputs = [MARKER] * len(wanted)

        rows, seen, missed, nodes = [], set(), [], []
        for question, output in zip(wanted, outputs):
            output = output.strip()
            if output and output != MARKER:
                nodes += [n for n in _query_anchor_nodes(output, self.graph)]
            found = self._rows_for(output)
            if not found:
                missed.append(question)
                continue
            for row in found:
                key = tuple(sorted(row.items(), key=lambda kv: kv[0]))
                if key not in seen:
                    seen.add(key)
                    rows.append(row)
        ket_qua = render_batch(rows, missed=missed)
        if vet is not None:
            vet["goi"].append({"tu_khoa": wanted, "node": nodes, "so_dong": len(rows)})
            vet["du_lieu"].append(ket_qua)
        return ket_qua


# Số có từ hai chữ số, phần trăm, và chữ viết tắt in hoa: đây là chỗ mô hình bịa
# ra thứ nghe như dữ kiện. Số một chữ số bỏ qua vì nó trùng với số thứ tự.
SO = re.compile(r"\d[\d.,]*\d|\d+%")
VIET_TAT = re.compile(r"\b[A-Z]{2,}\d*\b")
_BO_QUA = {"II", "III", "IV", "VI", "VII", "VIII", "IX", "XI", "XII"}


def khong_bam_du_lieu(tra_loi: str, du_lieu: str) -> list[str]:
    """Những số và viết tắt xuất hiện trong câu trả lời mà dữ liệu không hề nói."""

    nen_co = {m.group() for m in SO.finditer(tra_loi)}
    nen_co |= {m.group() for m in VIET_TAT.finditer(tra_loi) if m.group() not in _BO_QUA}
    return sorted(t for t in nen_co if t not in du_lieu)


TU_CHOI = ("không tìm thấy", "không có thông tin", "ngoài phạm vi", "không thuộc",
           "không nằm trong", "chưa có", "không có dữ liệu", "không hỗ trợ",
           "không liên quan", "không thể trả lời", "không chứa", "không đề cập",
           "không quản lý", "không cung cấp", "không có trong")


def co_noi_la_thieu(tra_loi: str) -> bool:
    thap = tra_loi.lower()
    return any(cum in thap for cum in TU_CHOI)


async def hoi(agent, cau: dict, nhom: str, sem) -> dict:
    from agents import Runner

    async with sem:
        vet = {"goi": [], "du_lieu": []}
        luot.set(vet)
        loi = None
        for lan in range(6):
            vet["goi"].clear(); vet["du_lieu"].clear()
            bat_dau = time.perf_counter()
            try:
                ket = await Runner.run(agent, cau["cau_hoi"], max_turns=12)
                tra_loi, loi = (ket.final_output or "").strip(), None
                break
            except Exception as exc:
                tra_loi, loi = "", f"{type(exc).__name__}: {exc}"
                if "RateLimit" not in type(exc).__name__:
                    break
                await asyncio.sleep(20 * (lan + 1))
        giay = time.perf_counter() - bat_dau

    du_lieu = "\n".join(vet["du_lieu"])
    node = sorted({n for goi in vet["goi"] for n in goi["node"]})
    ban_ghi = {
        "id": cau["id"], "nhom": nhom, "cau_hoi": cau["cau_hoi"],
        "tra_loi": tra_loi, "loi": loi, "giay": round(giay, 2),
        "so_lan_goi": len(vet["goi"]),
        "tu_khoa": [k for goi in vet["goi"] for k in goi["tu_khoa"]],
        "node_lay_ve": node,
        "so_dong_du_lieu": sum(goi["so_dong"] for goi in vet["goi"]),
        "bia_dat": khong_bam_du_lieu(tra_loi, du_lieu) if tra_loi else [],
        "noi_la_thieu": co_noi_la_thieu(tra_loi),
    }
    if nhom == "trong_pham_vi":
        ban_ghi["node_dung"] = cau["node_dung"]
        ban_ghi["lay_dung_muc"] = bool(set(cau["node_dung"]) & set(node))
        ban_ghi["register"] = cau["register"]
        ban_ghi["query_id"] = cau["query_id"]
    print(f"  {ban_ghi['id']:<16} {nhom:<16} {giay:5.1f}s  goi={ban_ghi['so_lan_goi']}"
          f"  {'OK' if not loi else loi[:40]}", flush=True)
    return ban_ghi


async def main() -> None:
    generator = CTranslate2Generator.load(Path("artifacts/serving-models/t5gemma2-int8"), device="cpu",
                                          compute_type="int8")
    agent = build_agent(ChatbotCoVet(generator), model=os.environ["ONTCHATBOT_LLM_MODEL"])
    sem = asyncio.Semaphore(SONG_SONG)
    gioi_han = int(os.environ.get("GIOI_HAN", "0"))

    cu = {}
    if KET_QUA.is_file() and os.environ.get("CHAY_BU"):
        cu = {r["id"]: r for r in json.loads(KET_QUA.read_text()) if not r["loi"]}
        print(f"giữ lại {len(cu)} câu đã đo được, hỏi lại phần còn thiếu")

    viec = []
    for nhom in ("trong_pham_vi", "ngoai_pham_vi", "do_thi_khong_co"):
        rows = CAU_HOI[nhom]
        if gioi_han:
            rows = rows[:gioi_han]
        viec += [hoi(agent, cau, nhom, sem) for cau in rows if cau["id"] not in cu]

    bat_dau = time.perf_counter()
    ban_ghi = list(cu.values()) + list(await asyncio.gather(*viec))
    KET_QUA.write_text(json.dumps(ban_ghi, ensure_ascii=False, indent=1))
    print(f"\nxong {len(ban_ghi)} câu trong {time.perf_counter()-bat_dau:.0f}s → {KET_QUA}")


if __name__ == "__main__":
    asyncio.run(main())
