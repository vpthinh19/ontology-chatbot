"""Chấm chất lượng từng câu trả lời thành năm mức, bằng một mô hình ngôn ngữ lớn.

Các phép dò tự động ở `score.py` chỉ đếm được những thứ mang hình dạng cố định:
có gọi công cụ không, node lấy về có trúng không, câu trả lời có nêu con số nào
ngoài dữ liệu không. Chúng không đọc được câu trả lời có thật sự trả lời câu hỏi
hay không. Phép chấm này lấp chỗ đó.

Mỗi câu trả lời được đưa kèm **đúng dữ liệu công cụ đã trả về trong chính lượt
đó**, rồi xếp vào một mức. Người chấm là mô hình chứ không phải người, nên mỗi
phán quyết buộc phải kèm một trích đoạn làm bằng chứng để kiểm lại được.

Chạy sau `run.py`, đọc `results.json`, ghi `quality.json` và `quality-log.md`.

Nhật ký gom câu hỏi, dữ liệu công cụ, câu trả lời và phán quyết vào cùng một chỗ,
xếp theo mức. Không có nó thì muốn kiểm một phán quyết phải tự ghép hai tệp JSON,
và khâu kiểm bị bỏ qua - đã bỏ qua hai lần, mỗi lần đưa ra một con số sai.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, "src")
from ontchatbot.runtime.agent import DEFAULT_BASE_URL, build_instructions

HERE = Path(__file__).parent
KET_QUA = HERE / "results.json"
DAU_RA = HERE / "quality.json"
NHAT_KY = HERE / "quality-log.md"
SONG_SONG = int(os.environ.get("SONG_SONG", "2"))

# Trợ lý được trao sẵn một danh sách chủ đề tra được trong lời hướng dẫn của nó.
# Bộ chấm phải thấy danh sách đó, nếu không mỗi lần trợ lý mời người dùng hỏi rõ
# hơn bằng cách nêu vài chủ đề sẽ bị đọc thành bịa đặt - "Mẫu số 13" thành số 13
# bịa ra. Xem cùng phép dò tương ứng ở `run.py`.
CO_SAN = build_instructions()
CO_SAN = CO_SAN[CO_SAN.index("vài chủ đề tra được:") + len("vài chủ đề tra được:"):].strip()

# Phân mức theo MỘT câu hỏi: trợ lý có trả lời được thứ được hỏi không, và nếu
# có thì trả lời đó có bám dữ liệu không.
#
# Ranh giới đáng chú ý nhất là giữa "dung" và "tu_choi". Hình dạng thường gặp
# nhất của trợ lý này là "dữ liệu không có X, nhưng có Y liên quan" - nó vừa từ
# chối vừa nêu dữ kiện. Đó là TỪ CHỐI, vì thứ được hỏi vẫn không được trả lời.
# Buộc "tu_choi" phải không nêu dữ kiện nào sẽ đẩy gần hết nhóm này sang "dung"
# và thổi phồng tỷ lệ đúng.
MUC = {
    "dung": "Đưa ra được thứ được hỏi, và mọi dữ kiện nêu ra đều có trong dữ liệu",
    "tu_choi": "KHÔNG đưa ra được thứ được hỏi, và nói rằng dữ liệu không có nó",
    "lac_de": "Không đưa ra được thứ được hỏi và cũng không nói là thiếu",
    "thieu": "Đưa ra được một phần, phần đã đưa thì đúng",
    "sai": "Có dữ kiện sai, hoặc suy diễn ra quan hệ mà dữ liệu không nói",
}

KHUON = """Bạn chấm chất lượng một câu trả lời của trợ lý học vụ.

CÂU HỎI:
{cau_hoi}

DỮ LIỆU CÔNG CỤ ĐÃ TRẢ VỀ TRONG CHÍNH LƯỢT NÀY:
{du_lieu}

DANH SÁCH CHỦ ĐỀ TRỢ LÝ LUÔN CÓ SẴN (nằm trong lời hướng dẫn của nó, không phải
kết quả tra cứu). Tên trong danh sách này là tên thật; nêu lại chúng KHÔNG phải
là bịa đặt:
{co_san}

CÂU TRẢ LỜI CỦA TRỢ LÝ:
{tra_loi}

Xếp câu trả lời vào ĐÚNG MỘT mức:
{muc}

Cách chấm, làm theo đúng thứ tự:

BƯỚC 1. Xác định câu hỏi đòi CÁI GÌ. Viết ra trong đầu một mệnh đề cụ thể, ví dụ
"mức điểm để xếp loại giỏi" hay "hạn nộp đơn". Đó là thứ duy nhất cần tìm.

BƯỚC 2. Thứ đó CÓ trong câu trả lời không?
   - Có, và đúng với dữ liệu  -> "dung"
   - Có một phần               -> "thieu"
   - Không có                  -> sang bước 3

BƯỚC 3. Trợ lý có nói rằng dữ liệu không có thứ đó không?
   - Có   -> "tu_choi"
   - Không -> "lac_de"

BƯỚC 4. Bất kể các bước trên, nếu trợ lý nêu một dữ kiện KHÔNG có trong dữ liệu,
hoặc khẳng định một quan hệ mà dữ liệu chỉ nêu hai dữ kiện rời, thì đổi thành "sai".
Liệt kê các chủ đề trong danh sách có sẵn ở trên KHÔNG phải là nêu dữ kiện: đó là
lời mời hỏi rõ hơn. Câu hỏi quá chung để tra mà trợ lý hỏi lại cho rõ, không khẳng
định điều gì, thì xếp "tu_choi" chứ không phải "sai".

⚠️ Câu rào đón KHÔNG phải căn cứ để xếp "tu_choi". Trợ lý thường viết dạng "dữ liệu
không nêu X, nhưng có Y" — nếu Y CHÍNH LÀ thứ được hỏi thì đó là "dung", không phải
"tu_choi". Chỉ xếp "tu_choi" khi thứ được hỏi thật sự KHÔNG được đưa ra.

Chỉ đối chiếu với dữ liệu ở trên. Kiến thức riêng của bạn không phải căn cứ.

Trả về đúng một đối tượng JSON, không kèm chữ nào khác:
{{"muc": "<một trong: dung, tu_choi, lac_de, thieu, sai>", "bang_chung": "<trích đúng nguyên văn một đoạn ngắn từ câu trả lời hoặc từ dữ liệu, làm căn cứ>"}}"""


async def cham(client, ban_ghi: dict, sem) -> dict:
    async with sem:
        loi_nhac = KHUON.format(
            cau_hoi=ban_ghi["cau_hoi"],
            du_lieu=(ban_ghi.get("du_lieu") or "").strip() or "(công cụ không trả về dòng nào)",
            tra_loi=ban_ghi["tra_loi"] or "(trợ lý không trả lời)",
            muc="\n".join(f"- {k}: {v}" for k, v in MUC.items()),
            co_san=CO_SAN,
        )
        for lan in range(5):
            try:
                phan_hoi = await client.chat.completions.create(
                    model=os.environ["ONTCHATBOT_LLM_MODEL"],
                    messages=[{"role": "user", "content": loi_nhac}],
                    temperature=0,
                )
                chu = (phan_hoi.choices[0].message.content or "").strip()
                chu = chu[chu.index("{") : chu.rindex("}") + 1]
                phan = json.loads(chu)
                if phan.get("muc") in MUC:
                    print(f"  {ban_ghi['id']:<16} {phan['muc']}", flush=True)
                    return {"id": ban_ghi["id"], "nhom": ban_ghi["nhom"], **phan}
            except Exception as exc:
                if lan == 4:
                    print(f"  {ban_ghi['id']:<16} LỖI {type(exc).__name__}", flush=True)
                    return {"id": ban_ghi["id"], "nhom": ban_ghi["nhom"],
                            "muc": None, "bang_chung": f"{type(exc).__name__}: {exc}"}
                await asyncio.sleep(15 * (lan + 1))
        return {"id": ban_ghi["id"], "nhom": ban_ghi["nhom"], "muc": None, "bang_chung": ""}


# Dữ liệu công cụ có lượt dài hàng chục nghìn ký tự (bảng biểu nguyên văn). Cắt
# bớt để nhật ký còn đọc được; nguyên văn vẫn nằm đủ trong `results.json`.
GIOI_HAN_DU_LIEU = 1500


def viet_nhat_ky(phan: list[dict], theo_ban_ghi: dict, nghi_ngo: dict) -> None:
    """Gom câu hỏi, dữ liệu, câu trả lời và phán quyết vào một tệp đọc được.

    Xếp theo mức để việc "xem tay vài ca ở mỗi mức" chỉ là cuộn xuống, thay vì
    phải tự ghép `quality.json` với `results.json` - khâu mà hai lượt chấm sai
    trước đây đều bỏ qua.
    """
    from collections import Counter

    dong = ["# Nhật ký chấm chất lượng câu trả lời", ""]
    dem = Counter(p["muc"] for p in phan)
    dong.append(f"{len(phan)} câu · " + " · ".join(
        f"{muc} {dem.get(muc, 0)}" for muc in MUC) + f" · đáng ngờ {len(nghi_ngo)}")
    dong.append("")
    dong.append("Mỗi mục gồm câu hỏi, dữ liệu công cụ đã trả về trong chính lượt đó, câu trả")
    dong.append("lời nguyên văn, phán quyết của bộ chấm và các tín hiệu tất định để đối chiếu.")
    dong.append("")

    for muc in MUC:
        cua_muc = [p for p in phan if p["muc"] == muc]
        if not cua_muc:
            continue
        dong += [f"## {muc} — {len(cua_muc)} câu", "", f"*{MUC[muc]}*", ""]
        for p in cua_muc:
            r = theo_ban_ghi[p["id"]]
            du_lieu = (r.get("du_lieu") or "").strip() or "(công cụ không trả về dòng nào)"
            if len(du_lieu) > GIOI_HAN_DU_LIEU:
                du_lieu = du_lieu[:GIOI_HAN_DU_LIEU] + f"\n… (còn {len(r['du_lieu']) - GIOI_HAN_DU_LIEU} ký tự)"
            dong += [f"### {p['id']} · {r['nhom']}", ""]
            if p["id"] in nghi_ngo:
                dong += [f"> ⚠️ **Đáng ngờ:** {nghi_ngo[p['id']]}", ""]
            tin_hieu = [
                f"gọi công cụ {r.get('so_lan_goi', 0)} lần",
                f"{r.get('so_dong_du_lieu', 0)} dòng dữ liệu",
            ]
            if "lay_dung_muc" in r:
                tin_hieu.append("lấy đúng mục" if r["lay_dung_muc"] else "**lấy sai mục**")
                tin_hieu.append(f"đích {', '.join(r.get('node_dung') or []) or '—'}")
            if r.get("bia_dat"):
                tin_hieu.append(f"**ngoài dữ liệu: {', '.join(r['bia_dat'])}**")
            dong += [f"**Tín hiệu tất định:** {' · '.join(tin_hieu)}", ""]
            dong += ["**Câu hỏi:** " + r["cau_hoi"], ""]
            dong += ["**Bộ chấm trích:** " + (p.get("bang_chung") or "—"), ""]
            dong += ["**Câu trả lời:**", "", "```", r["tra_loi"] or "(trợ lý không trả lời)", "```", ""]
            dong += ["<details><summary>Dữ liệu công cụ</summary>", "", "```json", du_lieu, "```", "", "</details>", ""]

    NHAT_KY.write_text("\n".join(dong), encoding="utf-8")


async def main() -> None:
    from openai import AsyncOpenAI

    client = AsyncOpenAI(
        api_key=os.environ["ONTCHATBOT_LLM_API_KEY"],
        base_url=os.environ.get("ONTCHATBOT_LLM_BASE_URL", DEFAULT_BASE_URL),
    )
    ban_ghi = json.loads(KET_QUA.read_text())
    if any("du_lieu" not in r for r in ban_ghi):
        raise SystemExit("kết quả chưa lưu dữ liệu công cụ; chạy lại run.py trước")

    # Giữ lại phán quyết đã chấm được, chỉ hỏi lại những câu chưa có mức. Máy chủ
    # mô hình chặn theo tốc độ, nên một lượt hiếm khi chấm trọn cả bộ.
    cu = {}
    if DAU_RA.is_file():
        cu = {p["id"]: p for p in json.loads(DAU_RA.read_text()) if p.get("muc")}
        if cu:
            print(f"giữ lại {len(cu)} câu đã chấm, hỏi lại {len(ban_ghi) - len(cu)} câu")

    sem = asyncio.Semaphore(SONG_SONG)
    moi = await asyncio.gather(*(cham(client, r, sem) for r in ban_ghi if r["id"] not in cu))
    theo_id = {**cu, **{p["id"]: p for p in moi}}
    phan = [theo_id[r["id"]] for r in ban_ghi]
    DAU_RA.write_text(json.dumps(phan, ensure_ascii=False, indent=1), encoding="utf-8")

    from collections import Counter

    # Đối chiếu với ba tín hiệu tất định đã ghi sẵn trong mỗi bản ghi. Phép này
    # không tốn lượt gọi nào, và nó bắt được đúng loại lỗi mà bộ chấm hay mắc:
    # xếp "từ chối" cho câu vốn đã lấy đúng mục, có dữ liệu và không bịa.
    theo_ban_ghi = {r["id"]: r for r in ban_ghi}
    nghi_ngo = {}
    for p_ in phan:
        r = theo_ban_ghi.get(p_["id"], {})
        if not p_.get("muc"):
            continue
        if (p_["muc"] == "tu_choi" and r.get("lay_dung_muc")
                and r.get("so_dong_du_lieu", 0) > 0 and not r.get("bia_dat")):
            nghi_ngo[p_["id"]] = "chấm TỪ CHỐI nhưng lấy đúng mục và có dữ liệu"
        elif p_["muc"] == "dung" and r.get("so_dong_du_lieu", 0) == 0:
            nghi_ngo[p_["id"]] = "chấm ĐÚNG nhưng công cụ trả 0 dòng"
        elif p_["muc"] == "dung" and r.get("bia_dat"):
            nghi_ngo[p_["id"]] = "chấm ĐÚNG nhưng phép dò thấy số ngoài dữ liệu"

    viet_nhat_ky(phan, theo_ban_ghi, nghi_ngo)

    tong = len(phan)
    dem = Counter(p["muc"] for p in phan)
    print("\n" + "=" * 62)
    print(f"CHẤT LƯỢNG CÂU TRẢ LỜI ({tong} câu)")
    for muc, nghia in MUC.items():
        n = dem.get(muc, 0)
        print(f"  {muc:<10} {n:>3}  ({n / tong * 100:4.1f}%)  {nghia}")

    # Tách theo nhóm câu hỏi. Gộp cả 85 câu vào một mẫu số làm con số "đúng" tụt
    # xuống mỗi khi trợ lý từ chối ĐÚNG một câu không trả lời được - với 25 câu
    # đó, từ chối mới là hành vi cần, còn "đúng" là không thể đạt theo định nghĩa.
    print("\n  Tách theo nhóm câu hỏi:")
    for nhom, muc_dung in (("trong_pham_vi", "dung"),
                           ("ngoai_pham_vi", "tu_choi"),
                           ("do_thi_khong_co", "tu_choi")):
        cua_nhom = [p_ for p_ in phan if theo_ban_ghi[p_["id"]]["nhom"] == nhom]
        if not cua_nhom:
            continue
        dat = sum(p_["muc"] == muc_dung for p_ in cua_nhom)
        khac = Counter(p_["muc"] for p_ in cua_nhom if p_["muc"] != muc_dung)
        con_lai = "  ·  " + ", ".join(f"{k} {v}" for k, v in khac.most_common()) if khac else ""
        print(f"    {nhom:<16} {muc_dung:<8} {dat:>3}/{len(cua_nhom):<3} "
              f"({dat / len(cua_nhom) * 100:5.1f}%){con_lai}")

    print(f"\n  Đối chiếu với tín hiệu tất định: {len(nghi_ngo)}/{tong} phán quyết đáng ngờ")
    for cid, ly_do in list(nghi_ngo.items())[:8]:
        print(f"    {cid}  {ly_do}")
    if len(nghi_ngo) > 8:
        print(f"    ... còn {len(nghi_ngo) - 8} câu nữa")
    if len(nghi_ngo) > tong * 0.1:
        print("  ⚠️ Quá 10% phán quyết mâu thuẫn với tín hiệu tất định — "
              "sửa luật chấm trước khi tin con số ở trên.")

    hong = dem.get(None, 0)
    if hong:
        print(f"  {'CHẤM HỎNG':<10} {hong:>3}")
    print(f"\nđã ghi {DAU_RA.relative_to(Path.cwd())} và {NHAT_KY.relative_to(Path.cwd())}")
    print("Xem tay vài ca ở MỖI mức trong nhật ký trước khi dùng các con số trên.")


if __name__ == "__main__":
    asyncio.run(main())
