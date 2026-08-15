"""Ghép ba trục thành một câu hỏi: cách gọi tên × khung ý định × phong cách.

Liệt kê paraphrase tiếng Việt là việc vô hạn - riêng "như thế nào" đã có "như
nào", "sao", "làm sao", "ra sao", "thế nào nhỉ", "sao ta"... Cách duy nhất mở
rộng được là **sinh theo tổ hợp**: viết 5 khung ý định và 8 đuôi phong cách thay
vì ngồi viết 40 câu.

Ba trục cố ý tách rời nhau:

* **cách gọi tên** (``mentions.py``) - suy từ ontology, không bịa;
* **khung ý định** (``resources/dataset/frames.jsonl``) - soạn tay, quyết định
  chatbot hiểu ý định nào;
* **phong cách** (module này) - thuần hình thức, không đụng tới nghĩa.

Chia tập phải cắt theo **khung**, không theo dòng: sinh tổ hợp rồi chia ngẫu
nhiên thì test chỉ là hoán vị của train, và điểm số sẽ đẹp giả một lần nữa.
"""

from __future__ import annotations

import json
import random
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

REGISTERS = ("formal", "neutral", "colloquial", "noisy")

#: Mở đầu và kết thúc theo phong cách. Chỉ đổi hình thức, giữ nguyên ý.
_DECORATIONS: dict[str, tuple[tuple[str, str], ...]] = {
    "formal": (
        ("Xin cho biết ", "."),
        ("Cho tôi hỏi ", "."),
        ("", "?"),
        ("Đề nghị hướng dẫn ", "."),
    ),
    "neutral": (("", "?"), ("Cho hỏi ", "?"), ("", " ạ?"), ("Mình muốn hỏi ", "?")),
    "colloquial": (
        ("", " nhỉ?"),
        ("", " vậy ta?"),
        ("", " thế ạ?"),
        ("cho hỏi ", " với ạ?"),
        ("ê ", " v?"),
        ("", " sao giờ?"),
        ("tui muốn biết ", " á?"),
        ("", " ta?"),
        ("", " hả?"),
        ("", " zậy?"),
        ("mn ơi ", " với?"),
        ("", " đây ta?"),
        ("ai biết ", " không?"),
    ),
    "noisy": (("", "?"), ("", ""), ("cho hoi ", "?"), ("", " z?")),
}

#: Gõ nhầm phím lân cận trên bàn phím QWERTY tiếng Việt.
_NEIGHBOURS = {"a": "s", "s": "a", "o": "p", "e": "r", "i": "u", "n": "m", "t": "y"}


#: Chỗ trống trong khung, đặt tên trùng slot của họ truy vấn: {anchor}, {score}...
_PLACEHOLDER = re.compile(r"\{([a-z][a-z0-9_]*)\}")


@dataclass(frozen=True)
class Frame:
    query_id: str
    text: str
    short: bool = False

    def fill(self, values: dict[str, str]) -> str:
        text = self.text
        for name, value in values.items():
            text = text.replace(f"{{{name}}}", value)
        return text

    @property
    def slots(self) -> frozenset[str]:
        return frozenset(_PLACEHOLDER.findall(self.text))


def load_frames(
    path: Path,
    catalogue: Mapping[str, object] | None = None,
) -> dict[str, tuple[Frame, ...]]:
    """Khung ý định theo họ truy vấn, giữ nguyên thứ tự khai báo.

    Khi truyền ``catalogue``, mỗi khung bị bắt buộc dùng **đúng** bộ chỗ trống mà
    họ truy vấn khai: họ hỏi theo tên thực thể phải có ``{anchor}``, họ so ngưỡng
    phải có ``{score}``, họ ràng buộc theo lớp thì không có chỗ trống nào. Sai bộ
    chỗ trống nghĩa là câu hỏi không khớp truy vấn nó sinh ra.
    """

    frames: dict[str, list[Frame]] = {}
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        payload = json.loads(line)
        query_id = payload["query_id"]
        if query_id in frames:
            raise ValueError(f"dòng {number}: khung trùng cho {query_id}")
        texts = payload["frames"]
        short_texts = payload.get("short_frames", [])
        if not texts:
            raise ValueError(f"dòng {number}: {query_id} không có khung nào")
        items = [Frame(query_id, text) for text in texts]
        items.extend(Frame(query_id, text, short=True) for text in short_texts)
        if catalogue is not None:
            spec = catalogue.get(query_id)
            if spec is None:
                raise ValueError(f"dòng {number}: {query_id} không có trong danh mục")
            expected = frozenset(spec.slots)  # type: ignore[attr-defined]
            wrong = [frame.text for frame in items if frame.slots != expected]
            if wrong:
                raise ValueError(
                    f"dòng {number}: {query_id} cần đúng chỗ trống {sorted(expected)}; "
                    f"sai ở {wrong[:2]}"
                )
        frames[query_id] = items
    return {query_id: tuple(items) for query_id, items in frames.items()}


#: Từ dẫn mà module này KHÔNG tự sinh ra nhưng mẫu câu soạn tay có thể mở đầu
#: bằng chúng. Thiếu chúng thì luật chống chồng bỏ lọt: "cho hoi Xin hỏi Trường
#: Đại học Nha Trang…".
_EXTRA_OPENERS = ("xin hỏi", "tôi cần", "tôi muốn hỏi", "mình hỏi", "em hỏi")

#: Mọi từ dẫn mà một câu có thể mở đầu, dùng để KHÔNG khoác chồng.
_OPENERS = tuple(
    sorted(
        {
            prefix.strip().casefold()
            for pairs in _DECORATIONS.values()
            for prefix, _ in pairs
            if prefix.strip()
        }
        | set(_EXTRA_OPENERS),
        key=len,
        reverse=True,
    )
)


def decorate(
    question: str,
    register: str,
    rng: random.Random,
    *,
    short: bool = False,
) -> str:
    """Khoác phong cách lên một câu hỏi đã ghép xong.

    Câu vốn đã mở đầu bằng một từ dẫn thì chỉ nhận đuôi, không nhận thêm đầu:
    mẫu câu soạn tay *"cho hỏi {anchor} làm thế nào, tiện thể…"* gặp tiền tố
    trang trọng đã sinh ra *"Xin cho biết cho hỏi …"* trong 14 dòng.

    ``short=True`` giữ câu ngắn: chỉ nhận đuôi, không nhận từ dẫn nào. Người thật
    gõ *"chuyển ngành"*, và khoác lên thành *"Đề nghị hướng dẫn chuyển ngành."*
    là biến nó trở lại thành câu dài - đúng thứ đang cần chữa. Bốn phong cách đều
    có ít nhất một lựa chọn đuôi-trần nên không phong cách nào bị mất.
    """

    options = _DECORATIONS[register]
    lowered = question.lstrip().casefold()
    if short or any(lowered.startswith(opener) for opener in _OPENERS):
        options = tuple(pair for pair in options if not pair[0].strip()) or options
    prefix, suffix = rng.choice(options)
    text = f"{prefix}{question}{suffix}"
    if register == "formal":
        text = text[:1].upper() + text[1:]
    elif register == "noisy":
        text = _noisy(text, rng)
    return re.sub(r"\s+", " ", text).strip()


def _noisy(text: str, rng: random.Random) -> str:
    """Lỗi gõ thật, cố ý NẰM NGOÀI whitelist viết tắt của runtime.

    Bẫy đã được ghi trong kế hoạch: nếu sinh câu noisy bằng chính các viết tắt mà
    ``normalize_model_input`` biết bung ra, thì sau chuẩn hoá câu noisy trở lại y
    hệt câu sạch - model không học được gì, mà lỗi chính tả thật ngoài whitelist
    vẫn hỏng. Ba phép dưới đây đều không có trong whitelist đó.
    """

    choice = rng.random()
    if choice < 0.45:
        return _strip_diacritics(text)
    if choice < 0.75:
        return _drop_spaces(text, rng)
    return _typo(text, rng)


def _strip_diacritics(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return stripped.replace("đ", "d").replace("Đ", "D")


def _drop_spaces(text: str, rng: random.Random) -> str:
    words = text.split(" ")
    if len(words) < 3:
        return text
    cut = rng.randrange(len(words) - 1)
    return " ".join(words[:cut] + [words[cut] + words[cut + 1]] + words[cut + 2 :])


def _typo(text: str, rng: random.Random) -> str:
    positions = [i for i, ch in enumerate(text) if ch.lower() in _NEIGHBOURS]
    if not positions:
        return text
    index = rng.choice(positions)
    return text[:index] + _NEIGHBOURS[text[index].lower()] + text[index + 1 :]


def choose_mention(
    available: tuple[str, ...],
    register: str,
    rng: random.Random,
) -> str:
    """Chọn cách gọi hợp với phong cách đang dùng.

    Người viết trang trọng dùng tên chính thức - *"Thủ tục nghỉ học tạm thời"*;
    người nói khẩu ngữ dùng tên ngắn - *"bảo lưu"*. Ghép ngẫu nhiên hai thứ sẽ ra
    những câu không ai nói, kiểu *"ê Được điều động vào lực lượng vũ trang v?"*.

    Tương quan này không phải trang trí: nó đúng với cách người ta thật sự nói, và
    nó dạy model rằng cùng một thực thể có nhiều tên tuỳ ngữ cảnh.
    """

    if len(available) == 1:
        return _cased(available[0], register, rng)
    ordered = sorted(available, key=lambda text: (len(text.split()), text))
    half = max(1, len(ordered) // 2)
    if register == "formal":
        return _cased(rng.choice(ordered[-half:]), register, rng)
    if register in ("colloquial", "noisy"):
        return _cased(rng.choice(ordered[:half]), register, rng)
    return _cased(rng.choice(ordered), register, rng)


#: Xác suất giữ nguyên chữ hoa của tên chính thức, theo phong cách.
#:
#: Là xác suất chứ không phải luật cứng, vì tên chính thức DÀI chỉ được giọng
#: trang trọng chọn - đặt luật cứng theo phong cách thì đúng những cái tên dài
#: đó vĩnh viễn không bao giờ được nhìn thấy ở dạng chữ thường.
_KEEPS_OFFICIAL_CASE = {
    "formal": 0.85,
    "neutral": 0.5,
    "colloquial": 0.12,
    "noisy": 0.08,
}


def _cased(mention: str, register: str, rng: random.Random) -> str:
    """Viết hoa hay không cũng là một trục phong cách, không phải chính tả.

    Nhãn trong ontology viết hoa vì đó là tên chính thức trong công văn. Chèn
    nguyên trạng thì **313 trong 335 tên viết hoa chưa từng một lần xuất hiện ở
    dạng chữ thường** trong cả dataset - trong khi runtime KHÔNG hạ chữ thường,
    và người dùng thật gõ chat gần như luôn viết thường.

    Tệ hơn cả lệch phân bố: tỉ lệ viết hoa giảm dần theo phong cách (60% trang
    trọng, 35% cẩu thả), nên chữ hoa trở thành tín hiệu chỉ ranh giới thực thể
    mà model bám vào được thay vì hiểu nội dung.

    Chỉ HẠ chữ thường, không bao giờ viết hoa lên: nhãn vốn viết thường trong
    ontology ("bảo lưu") là tên khẩu ngữ, viết hoa nó lên là bịa.
    """

    if mention[:1].isupper() and rng.random() >= _KEEPS_OFFICIAL_CASE[register]:
        return mention.casefold()
    return mention


#: Nhóm từ để hỏi thay thế được cho nhau trong tiếng Việt.
#:
#: Đây là trục thứ tư, và là trục rẻ nhất: một khung soạn tay tự nhân lên vài
#: biến thể mà không phải viết thêm câu nào. Đúng thứ người dùng chỉ ra - riêng
#: "như thế nào" đã có "như nào", "thế nào", "ra sao", "làm sao".
#:
#: Các nhóm phải là từ đồng nghĩa THẬT trong ngữ cảnh câu hỏi. Không gộp
#: "bao nhiêu" với "bao lâu" (một hỏi số lượng, một hỏi thời gian), không gộp
#: "gì" với "nào" (một hỏi vật, một hỏi lựa chọn) - thay bừa sẽ sinh ra câu sai
#: nghĩa mà vẫn gắn đích cũ, tức là dạy model một liên kết sai.
_SYNONYMS: tuple[tuple[str, ...], ...] = (
    ("như thế nào", "như nào", "thế nào", "ra sao", "làm sao"),
    ("ở đâu", "chỗ nào", "tại đâu"),
    ("bao nhiêu", "mấy"),
    ("là gì", "là cái gì"),
    ("những gì", "gì"),
    ("khi nào", "lúc nào", "bao giờ"),
    ("do ai", "do người nào"),
    ("gồm", "bao gồm"),
)


def question_variants(question: str) -> tuple[str, ...]:
    """Các biến thể của một câu hỏi khi đổi từ để hỏi.

    Biến thể của CÙNG một khung phải nằm CÙNG một tập khi chia train/val/test:
    "X ở đâu" và "X chỗ nào" quá giống nhau để tính là "cách hỏi chưa từng thấy".
    Trục này làm giàu bên trong một tập, không phải trục để chia tập.
    """

    found: dict[str, None] = {question: None}
    lowered = question.lower()
    for group in _SYNONYMS:
        source = next((item for item in group if item in lowered), None)
        if source is None:
            continue
        start = lowered.index(source)
        for target in group:
            if target != source:
                variant = question[:start] + target + question[start + len(source) :]
                found.setdefault(_collapse_repeats(variant), None)
        # Chỉ áp MỘT nhóm cho mỗi câu. Chồng nhiều phép thay lên nhau sinh ra
        # những câu lệch nghĩa ("bảo lưu là những gì") mà vẫn mang đích cũ.
        break
    return tuple(found)


def _collapse_repeats(text: str) -> str:
    """Bỏ từ lặp liền kề do phép thay tạo ra: "làm làm sao" -> "làm sao"."""

    words = text.split()
    cleaned = [
        word
        for index, word in enumerate(words)
        if index == 0 or word.lower() != words[index - 1].lower()
    ]
    return " ".join(cleaned)
