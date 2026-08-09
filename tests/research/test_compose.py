"""Ba trục ghép thành câu hỏi: cách gọi × khung ý định × phong cách."""

from __future__ import annotations

import random
import re

import pytest

from ontchatbot.catalogue import load_catalogue
from ontchatbot.research.compose import (
    question_variants,
    REGISTERS,
    choose_mention,
    decorate,
    load_frames,
)
from ontchatbot.research.generate_dataset import HELD_OUT_FRAMES
from ontchatbot.runtime.text import normalize_model_input
from ontchatbot.settings import DATASET_DIR, QUERY_CATALOGUE_PATH

FRAMES_PATH = DATASET_DIR / "frames.jsonl"


@pytest.fixture(scope="module")
def catalogue():
    return load_catalogue(QUERY_CATALOGUE_PATH)


@pytest.fixture(scope="module")
def frames(catalogue):
    return load_frames(FRAMES_PATH, catalogue)


def test_every_frame_uses_exactly_the_slots_its_family_declares(frames, catalogue) -> None:
    """Khung phải có đúng bộ chỗ trống mà họ truy vấn khai.

    Họ hỏi theo tên thực thể cần ``{anchor}``; họ so ngưỡng cần ``{score}``; họ
    ràng buộc theo lớp thì không có chỗ trống nào. Sai bộ chỗ trống nghĩa là câu
    hỏi sinh ra không khớp truy vấn đi kèm - lỗi âm thầm và rất khó thấy về sau.
    """

    assert frames
    wrong = [
        (query_id, frame.text)
        for query_id, items in frames.items()
        for frame in items
        if frame.slots != frozenset(catalogue[query_id].slots)
    ]

    assert wrong == []


def test_every_answerable_family_has_frames(frames, catalogue) -> None:
    """Mọi họ primary phải có khung, trừ họ từ chối.

    Họ ``no-information`` lấy câu hỏi từ nguồn khác (cách gọi mơ hồ, ghép sai
    neo, câu ngoài miền) nên không có khung theo nghĩa này.
    """

    need = {
        query_id
        for query_id, spec in catalogue.items()
        if spec.tier == "primary" and spec.domain != "out-of-domain"
    }

    assert sorted(need - set(frames)) == []
    assert sorted(set(frames) - need) == []


def test_every_family_has_enough_frames_to_split(frames) -> None:
    """Sàn khung để chia tập theo KHUNG mà vẫn học được.

    Chia theo khung là cách duy nhất đo được "hiểu cách hỏi mới": vài khung cho
    train, ``HELD_OUT_FRAMES`` cho validation và bấy nhiêu cho test. Thiếu khung
    thì train chỉ thấy một cách hỏi, hoặc test phải dùng lại khung đã dạy - điểm
    số sẽ đẹp giả.

    Ràng buộc là TỈ LỆ GIẤU, không phải con số tuyệt đối. Bản trước chốt
    ``HELD_OUT_FRAMES >= 2``, mà với 8 khung mỗi họ thì đó là **giấu 50%** - đo
    hậu quả là những khung bị giấu sai 100%, tức là model chưa từng thấy
    lối nói đó nên phép đo thành đo cách hỏi lạ chứ không đo năng lực. Thông lệ
    là 10-20%.

    Nỗi lo "một khung mỗi bên quá mỏng" chỉ đúng khi đọc TỪNG HỌ. Số tổng gộp mọi
    họ nên vẫn còn hàng chục khung chưa từng thấy mỗi bên - canh thẳng con số đó.
    """

    floor = 2 * HELD_OUT_FRAMES + 2
    thin = sorted(query_id for query_id, items in frames.items() if len(items) < floor)
    assert thin == []

    total = sum(len(items) for items in frames.values())
    held_out = HELD_OUT_FRAMES * len(frames)
    share = held_out / total
    assert 0.10 <= share <= 0.25, f"giấu {share:.0%} khung, ngoài khoảng 10-20% thông lệ"
    assert held_out >= 30, f"chỉ {held_out} khung chấm trên toàn bộ dataset"


def test_noisy_questions_survive_the_runtime_normaliser() -> None:
    """Câu noisy KHÔNG được bị chuẩn hoá hoàn tác về câu sạch.

    Đây là cái bẫy đã ghi trong kế hoạch. ``normalize_model_input`` bung một danh
    sách viết tắt cố định; nếu bộ sinh noisy chỉ dùng đúng những viết tắt đó thì
    sau chuẩn hoá câu noisy trở lại y hệt câu sạch - nhóm "có lỗi viết" thành vô
    nghĩa, model không học được gì, mà lỗi gõ thật ngoài whitelist vẫn hỏng.

    Nhóm noisy vốn là nhóm khó nhất, nên đây là chỗ phải canh chặt.
    """

    rng = random.Random(7)
    questions = [
        "bảo lưu nộp ở đâu",
        "các bước của đăng ký học phần",
        "điều kiện của chuyển ngành là gì",
        "thời hạn của xin hoãn thi là bao lâu",
        "ai quyết định thôi học",
    ]

    undone = 0
    total = 0
    for question in questions:
        clean = normalize_model_input(question)
        for _ in range(20):
            total += 1
            if normalize_model_input(decorate(question, "noisy", rng)) == clean:
                undone += 1

    assert undone / total < 0.1, f"{undone}/{total} câu noisy bị chuẩn hoá hoàn tác"


@pytest.mark.parametrize("register", REGISTERS)
def test_decoration_keeps_the_question_non_empty(register) -> None:
    rng = random.Random(3)

    for _ in range(20):
        assert decorate("bảo lưu nộp ở đâu", register, rng).strip()


def test_formal_and_colloquial_reach_for_different_names() -> None:
    """Trang trọng dùng tên chính thức, khẩu ngữ dùng tên ngắn.

    Ghép ngẫu nhiên hai thứ sẽ sinh ra câu không ai nói ("ê Được điều động vào
    lực lượng vũ trang v?"), và bỏ mất một tín hiệu thật: cùng một thực thể có
    nhiều tên tuỳ ngữ cảnh.
    """

    available = (
        "Thủ tục nghỉ học tạm thời",
        "bảo lưu",
        "bảo lưu kết quả học tập",
        "tạm nghỉ học",
    )
    rng = random.Random(11)

    formal = [choose_mention(available, "formal", rng) for _ in range(40)]
    colloquial = [choose_mention(available, "colloquial", rng) for _ in range(40)]

    assert "Thủ tục nghỉ học tạm thời" in formal
    assert "Thủ tục nghỉ học tạm thời" not in colloquial
    assert "bảo lưu" in colloquial


def test_a_single_name_is_used_by_every_register() -> None:
    """Phần lớn neo chỉ có đúng một cách gọi; không được rơi vào nhánh rỗng."""

    rng = random.Random(5)

    for register in REGISTERS:
        assert choose_mention(("Điều 24",), register, rng).casefold() == "điều 24"


def test_every_name_is_seen_both_capitalised_and_lower_case() -> None:
    """Chữ hoa là trục phong cách, không phải chính tả cố định của tên.

    Nhãn ontology viết hoa vì đó là tên chính thức trong công văn. Chèn nguyên
    trạng thì tên nào cũng chỉ tồn tại một dạng, trong khi runtime không hạ chữ
    thường và người dùng gõ chat gần như luôn viết thường - thực thể rơi thẳng ra
    ngoài phân bố đã học.
    """

    rng = random.Random(11)
    official = "Chính sách buộc thôi học"

    seen = {choose_mention((official,), register, rng) for register in REGISTERS}

    assert official in seen
    assert official.casefold() in seen


def test_interrogatives_expand_into_natural_variants() -> None:
    """Một khung soạn tay tự nhân lên vài cách hỏi mà không phải viết thêm."""

    assert "bảo lưu nộp chỗ nào" in question_variants("bảo lưu nộp ở đâu")
    assert "bảo lưu làm sao" in question_variants("bảo lưu làm như thế nào")
    assert "hạn nộp bảo lưu là bao giờ" in question_variants(
        "hạn nộp bảo lưu là khi nào"
    )


def test_substitution_never_leaves_a_repeated_word() -> None:
    """"làm" + "làm sao" phải thành "làm sao", không phải "làm làm sao"."""

    assert "bảo lưu làm làm sao" not in question_variants("bảo lưu làm như thế nào")


def test_only_one_synonym_group_applies_per_question() -> None:
    """Chồng nhiều phép thay sinh ra câu lệch nghĩa mà vẫn mang đích cũ.

    "bảo lưu là gì" được nhóm "là gì" xử lý; nếu nhóm "gì" cũng áp lên thì ra
    "bảo lưu là những gì" - câu hỏi khác hẳn nhưng vẫn gắn đáp án cũ.
    """

    assert "bảo lưu là những gì" not in question_variants("bảo lưu là gì")


def test_an_opener_is_never_stacked_on_a_template_that_has_one() -> None:
    """Mẫu câu tự mang từ dẫn thì chỉ nhận đuôi, không nhận thêm đầu.

    Mẫu soạn tay "cho hỏi {anchor} làm thế nào, tiện thể…" gặp tiền tố trang
    trọng đã sinh ra "Xin cho biết cho hỏi …" trong 14 dòng của bản trước.
    """

    stacked = re.compile(
        r"(?i)^\W*(cho hỏi|cho tôi hỏi|xin cho biết|mình muốn hỏi|đề nghị hướng dẫn|cho hoi)"
        r"\s+(cho hỏi|cho tôi hỏi|xin cho biết|mình muốn hỏi|đề nghị hướng dẫn|cho hoi)"
    )
    rng = random.Random(3)

    for register in REGISTERS:
        for _ in range(60):
            text = decorate("cho hỏi bảo lưu làm thế nào", register, rng)
            assert not stacked.match(text), text
