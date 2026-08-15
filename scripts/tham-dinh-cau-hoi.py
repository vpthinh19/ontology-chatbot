"""Thẩm định câu hỏi do LLM viết, trước khi cho vào dataset.

Bảy cửa. Câu nào trượt bất kỳ cửa nào cũng bị trả lại kèm lý do, để lượt viết sau
biết đường sửa. Không cửa nào dựa vào việc đọc bằng mắt.

Chạy:  .venv/bin/python scripts/tham-dinh-cau-hoi.py

Đọc ``<nháp>/cau-hoi-moi.jsonl`` và ``loai-thong-tin.jsonl``, ghi ra
``cau-hoi-dat.jsonl`` cùng ``cau-hoi-tra-lai.jsonl``. Sửa hằng số ``SP`` cho khớp
thư mục đang dùng.

⚠️ BỐN LẦN HIỆU CHỈNH ĐỂ ĐƯỢC NHƯ HIỆN TẠI - đừng viết lại từ đầu:

1. Từng loại oan câu diễn đạt lại tên node ("Hội đồng phụ trách việc xét tốt
   nghiệp" bị chê vì "xét tốt nghiệp" cũng là tên một thủ tục).
2. Từng loại oan MỌI câu chứa chữ "sinh viên" - tên chung xuất hiện ở khắp nơi.
3. Cửa dò nhập nhằng nay chỉ CẢNH BÁO, vì bắt oan nhiều hơn bắt đúng và đã có
   ``test_no_question_leaks_across_splits_even_without_diacritics`` canh chặt hơn
   ở hạ nguồn.
4. Có lúc bỏ mất bước NFD nên hết bỏ dấu, để lọt 34 cặp trùng - và chính chúng
   gây rò rỉ giữa train và tập chấm.
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, "src")

from ontchatbot.research.mentions import mention_index  # noqa: E402
from ontchatbot.runtime.sparql import PREFIXES, load_ontology  # noqa: E402
from ontchatbot.runtime.text import normalize_model_input  # noqa: E402

SP = Path(
    "/tmp/claude-1000/-home-vpt-dev-ontology-chatbot/"
    "73a09785-ec23-42bd-b785-f865900915a7/scratchpad"
)
REGISTERS = {"formal", "neutral", "colloquial", "noisy"}

#: Người hỏi KHÔNG biết có ontology, có node, có cột nào. Họ hỏi về nhà trường.
#: Lượt viết đầu để lọt nhiều câu nói về chính dữ liệu - "Thông tin này gọi giáo
#: viên chủ nhiệm như thế nào?", "... được gọi như thế nào trong dữ liệu này ạ."
#: Dạy model những câu đó là dạy một khuôn không ai gõ.
META_PHRASES = (
    "thông tin này",
    "dữ liệu này",
    "trong thông tin",
    "trong dữ liệu",
    "cơ sở dữ liệu",
    "hệ thống",
    "bản ghi",
    "trường dữ liệu",
    "thuộc tính",
    "node",
    "mục này",
)


def fold(text: str) -> str:
    """Chuẩn hoá ĐÚNG NHƯ RUNTIME, rồi bỏ dấu.

    Phải gọi ``normalize_model_input`` chứ không tự bỏ dấu: runtime MỞ VIẾT TẮT,
    nên "ha hang tn do ky luat" và "Hạ hạng tốt nghiệp do kỷ luật" là MỘT câu đối
    với model. Bản trước của hàm này thiếu bước đó và để lọt đúng một cặp như vậy
    sang hai tập khác nhau - tập chấm hết còn là held-out mà không ai thấy.
    """

    lowered = unicodedata.normalize("NFD", normalize_model_input(text).casefold())
    stripped = "".join(c for c in lowered if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", stripped.replace("đ", "d")).strip()


def main() -> int:
    types = [
        json.loads(line)
        for line in (SP / "loai-thong-tin.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    wanted = {(t["query_id"], t["anchor"]) for t in types}

    path = SP / "cau-hoi-moi.jsonl"
    if not path.is_file():
        print("chưa có tệp câu hỏi")
        return 1
    rows = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            print(f"dòng {number}: không phải JSON hợp lệ")
    print(f"nhận {len(rows)} câu cho {len(wanted)} loại thông tin\n")

    graph = load_ontology()
    catalogue = {}
    for line in Path("resources/dataset/catalogue.jsonl").read_text(
        encoding="utf-8"
    ).splitlines():
        spec = json.loads(line)
        catalogue[spec["query_id"]] = spec

    # Trừ CHÍNH KHO VIẾT TAY ra khỏi tập đối chiếu. Dataset hiện tại đã nhập
    # chúng vào, nên không trừ thì mỗi câu tự trùng với bản sao của mình và 1.847
    # câu tốt bị trả lại oan.
    written_now = set()
    resource = Path("resources/dataset/written-questions.jsonl")
    if resource.is_file():
        written_now = {
            fold(json.loads(line)["input"])
            for line in resource.read_text(encoding="utf-8").splitlines()
            if line.strip()
        }
    existing = {
        fold(json.loads(line)["input"])
        for split in ("train", "val", "test")
        for line in Path(f"resources/dataset/{split}.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    } - written_now

    anchors = tuple(sorted({a for _, a in wanted}))
    index = mention_index(graph, anchors)[0]

    # Node mang TÊN CHUNG không được tính là "gọi nhầm sang node khác". "Sinh
    # viên", "giảng viên", "khoa" xuất hiện trong gần như mọi câu hỏi học vụ tự
    # nhiên - "sinh viên đăng ký học phần thế nào" là câu về ĐĂNG KÝ HỌC PHẦN,
    # không phải câu về sinh viên. Tính chúng vào thì phép dò loại oan 31 câu tốt.
    #
    # Nhận ra chúng bằng DỮ LIỆU chứ không liệt kê tay: đó đúng là nhóm node chỉ
    # trả về mỗi ``tên gọi``, tức không khẳng định điều gì để mà hỏi riêng.
    generic = {
        t["anchor"]
        for t in types
        if [c["cot"] for c in t["cong_cu_tra_ve"]] == ["tên gọi"]
    }
    owner_of_mention: dict[str, set[str]] = defaultdict(set)
    for anchor, names in index.items():
        if anchor in generic:
            continue
        for name in names:
            owner_of_mention[fold(name)].add(anchor)

    rejected: list[tuple[str, dict]] = []
    no_name: list[dict] = []
    seen: dict[str, dict] = {}
    per_type: dict[tuple[str, str], list[dict]] = defaultdict(list)

    for row in rows:
        key = (row.get("query_id"), row.get("anchor"))
        text = row.get("input", "")

        if key not in wanted:
            rejected.append(("loại thông tin không có trong đề bài", row))
            continue
        if row.get("register") not in REGISTERS:
            rejected.append(("phong cách không hợp lệ", row))
            continue
        if not text.strip():
            rejected.append(("câu rỗng", row))
            continue

        flat = fold(text)
        meta = [p for p in META_PHRASES if fold(p) in flat]
        if meta:
            rejected.append((f"nói về dữ liệu, không phải về trường: {meta[0]!r}", row))
            continue
        if flat in existing:
            rejected.append(("trùng câu đã có trong dataset", row))
            continue
        if flat in seen:
            rejected.append(("trùng câu khác trong chính lô này", row))
            continue

        # Cửa quan trọng nhất: câu có gọi đúng thứ nó định hỏi không, và có gọi
        # nhầm sang thứ khác không.
        # Bỏ qua cụm nào NẰM TRONG chính tên của node đích. Không bỏ thì câu
        # "Hội đồng phụ trách việc xét tốt nghiệp gọi là gì" bị loại oan, vì
        # "xét tốt nghiệp" cũng là cách gọi một thủ tục - trong khi nó chỉ là một
        # mảnh của chính cái tên đang được hỏi. Người hỏi diễn đạt lại tên gọi là
        # chuyện bình thường, và đó chính là thứ ta muốn dạy.
        # Chỉ loại khi câu KHÔNG gọi tên node đích mà LẠI gọi tên node khác.
        #
        # Phải tính "có gọi tên đích không" TRƯỚC và ĐỘC LẬP. Bản trước lọc các
        # cụm của node đích ra khỏi tập "gọi tên khác" rồi mới hỏi node đích có
        # trong tập đó không - tức là xoá đúng bằng chứng mình sắp cần. Hậu quả:
        # "Nộp học phí qua Agribank được không?" bị loại oan khỏi node Agribank,
        # vì "nộp học phí" là cách gọi một thủ tục còn "agribank" thì vừa bị lọc.
        # Mất 51 câu tốt chỉ vì thứ tự hai phép tính.
        def mentioned(anchor: str) -> bool:
            return any(
                len(fold(name)) >= 4
                and re.search(rf"(?<!\w){re.escape(fold(name))}(?!\w)", flat)
                for name in index.get(anchor, ())
            )

        # CẢNH BÁO, KHÔNG LOẠI. Phép dò này đã bắt oan ba lần liên tiếp và mỗi
        # lần tôi vá lại nó theo một kiểu: "Học phần điều kiện có tính vào tín chỉ
        # không?" bị loại vì "tín chỉ" cũng là tên một khái niệm; "Nộp học phí qua
        # Agribank được không?" bị loại vì "nộp học phí" là tên một thủ tục. Chỉ
        # số cách gọi ngắn và phổ thông trong đồ thị đã đủ làm nó vô dụng.
        #
        # Có sẵn một phép kiểm MẠNH HƠN VÀ CHÍNH XÁC HƠN ở hạ nguồn:
        # ``test_no_two_questions_teach_different_targets`` so từng câu THẬT trên
        # cả dataset và bắt đúng mâu thuẫn "một câu dạy hai đích". Giữ một phép dò
        # xấp xỉ chặn trước nó là đánh đổi câu tốt lấy cảm giác an toàn.
        if not mentioned(key[1]):
            no_name.append(row)

        seen[flat] = row
        per_type[key].append(row)

    print(f"qua cửa: {len(seen)} · bị trả lại: {len(rejected)}")
    print(f"CẢNH BÁO (không loại): {len(no_name)} câu không gọi thẳng tên node đích")
    if rejected:
        reasons = Counter(reason for reason, _ in rejected)
        for reason, count in reasons.most_common():
            print(f"   {count:4}  {reason}")
        print("\nvài câu bị trả lại:")
        for reason, row in rejected[:10]:
            print(f'   [{reason}] {row.get("anchor")}: {row.get("input")}')

    print("\n=== ĐỦ SỐ VÀ TRẢI ĐỀU CHƯA ===")
    missing = [k for k in wanted if len(per_type[k]) < 10]
    print(f"loại chưa đủ 10 câu: {len(missing)}")
    for key in missing[:10]:
        print(f"   {len(per_type[key]):2}/10  {key[1]}")

    thin_register = [k for k, v in per_type.items() if len({r["register"] for r in v}) < 4]
    print(f"loại chưa đủ bốn phong cách: {len(thin_register)}")

    short_missing = [
        k
        for k, v in per_type.items()
        if sum(2 <= len(r["input"].split()) <= 6 for r in v) < 2
    ]
    long_missing = [
        k for k, v in per_type.items() if sum(len(r["input"].split()) >= 14 for r in v) < 2
    ]
    print(f"loại thiếu câu ngắn 2-6 chữ (<2): {len(short_missing)}")
    print(f"loại thiếu câu dài >=14 chữ (<2): {len(long_missing)}")

    if seen:
        lengths = [len(r["input"].split()) for r in seen.values()]
        print(f"\nđộ dài: min {min(lengths)} · trung vị {sorted(lengths)[len(lengths)//2]} · max {max(lengths)}")
        print("phong cách:", dict(Counter(r["register"] for r in seen.values())))
        heads = Counter(" ".join(r["input"].split()[:3]).lower() for r in seen.values())
        print(f"kiểu mở đầu khác nhau: {len(heads)}/{len(seen)}")
        print("  lặp nhiều nhất:", heads.most_common(5))

    (SP / "cau-hoi-dat.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in seen.values()) + "\n",
        encoding="utf-8",
    )
    (SP / "cau-hoi-tra-lai.jsonl").write_text(
        "\n".join(
            json.dumps({"ly_do": reason, **row}, ensure_ascii=False)
            for reason, row in rejected
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"\nghi ra {SP}/cau-hoi-dat.jsonl và cau-hoi-tra-lai.jsonl")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
