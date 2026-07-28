"""Source normalization chỉ bung whitelist, vẫn giữ ngôn ngữ nói."""

from __future__ import annotations

from ontchatbot.runtime.text import normalize_model_input


def test_normalize_tone_position_for_bartpho() -> None:
    assert normalize_model_input("khóa thủy") == "khoá thuỷ"
    assert normalize_model_input("Khóa Thủy") == "Khoá Thuỷ"


def test_expand_unambiguous_academic_abbreviations() -> None:
    source = "  tui   rớt môn, hc lại sao; sắp đi nvqs  "

    assert normalize_model_input(source) == (
        "tui rớt môn, học lại sao; sắp đi nghĩa vụ quân sự"
    )


def test_expand_entity_and_compact_numeric_abbreviations() -> None:
    source = "CNTT k65 đóng 1tc bao nhiêu, hỏi CTSV ở đâu"

    assert normalize_model_input(source) == (
        "công nghệ thông tin khoá 65 đóng 1 tín chỉ bao nhiêu, "
        "hỏi công tác sinh viên ở đâu"
    )


def test_preserve_ambiguous_abbreviations_and_token_boundaries() -> None:
    source = "timestamp svx hcmc"

    assert normalize_model_input(source) == source


def test_expand_additional_academic_abbreviations() -> None:
    source = "đk hp, ĐKHP, dkmh, CTDT, cvht, GDTC, gdqp, GPA, KQHT, MH, BL, PDT"

    assert normalize_model_input(source) == (
        "đăng ký học phần, đăng ký học phần, đăng ký môn học, "
        "chương trình đào tạo, cố vấn học tập, giáo dục thể chất, "
        "giáo dục quốc phòng, điểm trung bình, kết quả học tập, "
        "môn học, bảo lưu, phòng đào tạo"
    )


def test_expand_conservative_chat_spellings() -> None:
    source = "khong bik đc hp lam thnao, bjo hoc, trc do vs ai, cx rui"

    assert normalize_model_input(source) == (
        "không biết được học phần làm thế nào, bao giờ học, "
        "trước do với ai, cũng rồi"
    )


def test_preserve_excluded_ambiguous_tokens() -> None:
    source = "bn hk bg m h v g ng nh ck"

    assert normalize_model_input(source) == "bao nhiêu hk bg m h v g ng nh ck"


def test_expand_domain_labels_and_common_acronyms() -> None:
    source = "HBKK cho NNA, NTTS với GDTQ xét ntn"

    assert normalize_model_input(source) == (
        "học bổng khuyến khích học tập cho ngôn ngữ Anh, "
        "nuôi trồng thuỷ sản với giáo dục tổng quát xét như thế nào"
    )


def test_expand_noisy_chat_abbreviations() -> None:
    source = "sv mun tăng CPA r thì lm s, cần vb j"

    assert normalize_model_input(source) == (
        "sinh viên muốn tăng điểm trung bình tích luỹ rồi thì làm sao, "
        "cần văn bản gì"
    )


def test_expand_compact_cohort_and_credit_spellings() -> None:
    assert normalize_model_input("khoa63 giá 1tin bnhiu") == (
        "khoá 63 giá 1 tín chỉ bao nhiêu"
    )


def test_normalization_is_idempotent() -> None:
    source = "đóng tiền hc sao, tui học CNTT khoá 65"

    once = normalize_model_input(source)

    assert normalize_model_input(once) == once
