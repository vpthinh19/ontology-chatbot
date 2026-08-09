"""Mỗi luật ở đây tương ứng MỘT lỗi có thật đã tìm ra khi soát dataset.

Bộ test cũ vẫn xanh trong khi 45,6% câu hỏi dính chữ hoa lạc chỗ, 222 dòng mang
nhãn giao diện của trang web làm tên thực thể, và 165 dòng dạy chatbot từ chối
đúng câu hỏi tự nhiên nhất về biểu mẫu. Nó xanh vì nó canh **số liệu của bản phát
hành cũ** chứ không canh **tính chất của dữ liệu**.

Nguyên tắc chung: đối chiếu với artifact thật, không chốt cứng con số nào.
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

import pytest
from rdflib import RDF, URIRef

from ontchatbot.catalogue import load_catalogue
from ontchatbot.research.mentions import mention_index
from ontchatbot.runtime.sparql import load_ontology
from ontchatbot.runtime.text import normalize_model_input
from ontchatbot.settings import DATASET_DIR, ONTOLOGY_NS, QUERY_CATALOGUE_PATH

MARKER = "không có thông tin"
SPLITS = ("train", "val", "test")


def _flatten(text: str, *, fold_d: bool = False) -> str:
    """Chuẩn hoá như runtime, rồi BỎ DẤU.

    Người dùng Việt gõ chat rất hay bỏ dấu, và nhóm câu ``noisy`` cũng sinh ra
    dạng không dấu. Hai câu chỉ khác nhau ở dấu là MỘT câu đối với model.

    ``fold_d`` quy cả ``đ`` về ``d``. Chỉ bật khi dò RÒ RỈ, vì nhóm ``noisy``
    làm đúng phép thay đó. KHÔNG bật khi dò mâu thuẫn đích: *"điểm d khoản 1
    Điều 22"* và *"điểm đ khoản 1 Điều 22"* là **hai điểm luật khác nhau**, và
    ``normalize_model_input`` giữ nguyên ``đ`` nên runtime cũng phân biệt được.
    Gộp chúng lại là tự bịa ra một mâu thuẫn không có thật.
    """

    lowered = normalize_model_input(text).casefold()
    decomposed = unicodedata.normalize("NFD", lowered)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return stripped.replace("đ", "d") if fold_d else stripped


@pytest.fixture(scope="module")
def splits() -> dict[str, list[dict]]:
    return {
        split: [
            json.loads(line)
            for line in (DATASET_DIR / f"{split}.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
            if line.strip()
        ]
        for split in SPLITS
    }


@pytest.fixture(scope="module")
def rows(splits) -> list[dict]:
    return [row for split in SPLITS for row in splits[split]]


@pytest.fixture(scope="module")
def graph():
    return load_ontology()


@pytest.fixture(scope="module")
def resolved(graph):
    catalogue = load_catalogue(QUERY_CATALOGUE_PATH)
    anchors = tuple(
        sorted(
            {
                value[1:]
                for spec in catalogue.values()
                for slot in spec.slots.values()
                if slot.kind == "iri"
                for value in slot.values
            }
        )
    )
    return mention_index(graph, anchors)[0]


def test_no_two_questions_teach_different_targets(rows) -> None:
    """Cùng một câu hỏi không được vừa dạy trả lời vừa dạy từ chối.

    Đây là mâu thuẫn tệ nhất có thể có trong dataset: model nhận hai tín hiệu
    ngược nhau cho cùng một chuỗi ký tự. Nó xảy ra thật khi một khung của họ này
    ghép với tên thực thể lại dựng ra đúng chuỗi mà họ khác cũng dựng được -
    *"đơn xin chuyển trường là mẫu số mấy"* vừa là câu hỏi số hiệu biểu mẫu, vừa
    là câu hỏi biểu mẫu của thủ tục, mà hai họ trả về hai đích khác nhau.

    So sau khi BỎ DẤU, vì với người dùng thật hai dạng đó là một câu.
    """

    by_text: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        by_text[_flatten(row["input"])].add(row["target"])

    conflicts = {text: sorted(t) for text, t in by_text.items() if len(t) > 1}

    assert conflicts == {}


def test_no_question_leaks_across_splits_even_without_diacritics(splits) -> None:
    """Tập chấm phải đo cách hỏi CHƯA TỪNG THẤY, kể cả khi người ta gõ không dấu.

    Validator đã canh trùng nguyên văn. Luật này chặt hơn một bậc: *"đi Đà Lạt
    mấy tiếng"* ở train và *"di da lat may tieng"* ở test là cùng một câu.
    """

    trained = {_flatten(row["input"], fold_d=True) for row in splits["train"]}
    leaked = [
        row["input"]
        for split in ("val", "test")
        for row in splits[split]
        if _flatten(row["input"], fold_d=True) in trained
    ]

    assert leaked == []


def test_every_official_name_is_also_seen_in_lower_case(rows, resolved) -> None:
    """Tên viết hoa nào cũng phải từng xuất hiện ở dạng chữ thường.

    Nhãn trong ontology viết hoa vì đó là tên chính thức trong công văn. Chèn
    nguyên trạng thì **93% tên viết hoa chưa từng một lần** xuất hiện dạng chữ
    thường - trong khi ``normalize_model_input`` KHÔNG hạ chữ thường, và người
    dùng gõ chat gần như luôn viết thường. Thực thể rơi thẳng ra ngoài phân bố
    đã học, dù model đã nhìn thấy nó ba chục lần.

    Tệ hơn: tỉ lệ viết hoa từng giảm dần theo phong cách (60% trang trọng, 35%
    cẩu thả), nên chữ hoa thành tín hiệu chỉ ranh giới thực thể - thứ model bám
    vào được thay vì hiểu nội dung, và thứ biến mất ở runtime.
    """

    blob = "\n".join(row["input"] for row in rows)
    official = {
        text
        for texts in resolved.values()
        for text in texts
        if text[:1].isupper() and text in blob
    }

    assert official, "không nhận ra tên viết hoa nào - phép kiểm này đang rỗng"
    assert sorted(text for text in official if text.casefold() not in blob) == []


def test_no_question_stacks_two_openers(rows) -> None:
    """Không câu nào mở đầu bằng hai từ dẫn liền nhau.

    *"Xin cho biết cho hỏi xử lý vi phạm làm thế nào"* - mẫu câu soạn tay tự mang
    sẵn "cho hỏi" rồi còn bị khoác thêm tiền tố trang trọng.
    """

    opener = (
        r"(cho hỏi|cho tôi hỏi|xin hỏi|xin cho biết|mình muốn hỏi"
        r"|đề nghị hướng dẫn|cho hoi)"
    )
    stacked = re.compile(rf"(?i)^\W*{opener}\s+{opener}")

    assert [row["input"] for row in rows if stacked.match(row["input"])] == []


def test_hard_negatives_only_use_the_entity_type_their_wording_assumes(
    rows, graph, resolved
) -> None:
    """Mẫu câu bẫy chỉ được ghép với loại thực thể mà chính nó ngầm định.

    Mọi mẫu ``hard-negative`` đều giả định chỗ trống là một THỦ TỤC: *"{X} nộp ở
    đâu"*, *"học bổng cho người làm {X}"*, *"{X} thi vào ngày nào"*. Bốc thực thể
    bừa thì 80% số dòng thành câu vô nghĩa - *"học bổng cho người làm Quyết định
    1052 là bao nhiêu"*.

    Câu vô nghĩa vẫn dạy được "từ chối", nhưng dạy model nhận ra sự VÔ NGHĨA chứ
    không dạy được ranh giới thật - mà ranh giới mới là chỗ khó nhất.
    """

    checklist_path = Path("resources/cases/rejection_checklist.json")
    checklist = json.loads(checklist_path.read_text(encoding="utf-8"))
    by_id = {row["id"]: row for row in rows}

    procedures = {
        str(node).rsplit("#", 1)[-1]
        for node in graph.subjects(RDF.type, URIRef(ONTOLOGY_NS + "AcademicProcedure"))
    }
    procedural = sorted(
        {
            text.casefold()
            for name, texts in resolved.items()
            if name in procedures
            for text in texts
        },
        key=len,
        reverse=True,
    )
    every = sorted(
        {text.casefold() for texts in resolved.values() for text in texts},
        key=len,
        reverse=True,
    )

    wrong = []
    for row_id in checklist.get("hard-negative", []):
        row = by_id.get(row_id)
        if row is None:
            continue
        # Nhóm ``noisy`` cố ý gõ sai nên tên bị vỡ - luật này canh việc CHỌN
        # thực thể, không canh việc viết sai.
        if row["register"] == "noisy":
            continue
        lowered = row["input"].casefold()
        # KHÔNG bỏ qua dòng không nhận ra tên nào. Mọi mẫu hard-negative đều có
        # chỗ trống, nên dòng nào cũng phải chứa một cách gọi - bỏ qua chúng
        # chính là cách luật này từng xanh trong khi vẫn lọt câu sai loại.
        if not any(text in lowered for text in procedural):
            wrong.append(row["input"])

    assert wrong == []
    assert every, "không nạp được cách gọi nào - phép kiểm này đang rỗng"


def test_a_question_with_an_off_topic_tail_is_still_answered(rows) -> None:
    """Câu hỏi trả lời được kèm một vế ngoài lề thì vẫn phải TRẢ LỜI.

    Bản trước xếp những câu này vào nhóm từ chối, tức là dạy một luật rất mạnh:
    hễ có vế thừa thì im lặng. Người dùng viết *"đăng ký học phần thế nào ạ, em
    cảm ơn nhiều"* rơi đúng vào bẫy đó.
    """

    tails = {
        payload["class"]: payload["templates"]
        for payload in (
            json.loads(line)
            for line in (DATASET_DIR / "rejections.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
            if line.strip()
        )
    }.get("distraction", [])

    assert tails, "không còn mẫu vế ngoài lề nào - phép kiểm này đang rỗng"

    marked = [
        row["input"]
        for row in rows
        if row["target"] == MARKER
        and any(tail.strip().strip(",") in row["input"] for tail in tails)
    ]
    answered = [
        row
        for row in rows
        if row["target"] != MARKER
        and any(tail.strip().strip(",") in row["input"] for tail in tails)
    ]

    assert marked == []
    assert answered, "không sinh được câu nào có vế ngoài lề"


def test_held_out_frames_are_not_near_duplicates_of_taught_frames() -> None:
    """Khung dùng để chấm không được gần trùng khung đã dạy.

    Nếu train có *"{X} web đánh số bao nhiêu"* còn test có *"{X} trên web đánh số
    mấy"* thì tập chấm không đo "cách hỏi chưa từng thấy" nữa - nó đo trí nhớ.

    Đo trên câu ĐÃ ghép tên thực thể, vì tên đóng góp y hệt vào cả hai câu và kéo
    độ giống lên: một cặp chỉ 0,816 ở dạng khung trần đã thành 0,934 sau khi ghép.
    """

    from ontchatbot.research.compose import load_frames
    from ontchatbot.research.generate_dataset import (
        NEAR_DUPLICATE_THRESHOLD,
        _probe_grams,
        split_frames,
    )

    catalogue = load_catalogue(QUERY_CATALOGUE_PATH)
    frames = load_frames(DATASET_DIR / "frames.jsonl", catalogue)

    too_close = []
    for query_id, items in frames.items():
        parts = split_frames(items)
        grams = {frame.text: _probe_grams(frame) for frame in items}
        for left_split, right_split in (("train", "val"), ("train", "test"), ("val", "test")):
            for left in parts[left_split]:
                for right in parts[right_split]:
                    score = max(
                        len(a & b) / len(a | b)
                        for a in grams[left.text]
                        for b in grams[right.text]
                    )
                    if score >= NEAR_DUPLICATE_THRESHOLD:
                        too_close.append((round(score, 3), query_id, left.text, right.text))

    assert too_close == []


def test_rejection_classes_come_from_the_requirements_file() -> None:
    """Danh sách nhóm câu từ chối phải ĐỌC từ ``coverage.json``, không chốt cứng.

    Bản trước chốt cứng bảy nhóm trong chính tệp test, nên khi nhóm "câu hỏi pha"
    được chuyển sang câu trả lời được, test đỏ vì lý do sai: nó tưởng dataset
    hỏng, thật ra chính nó đang giữ một quyết định đã bị thay.
    """

    required = json.loads(
        (DATASET_DIR / "coverage.json").read_text(encoding="utf-8")
    )["rejection_classes"]
    checklist = json.loads(
        Path("resources/cases/rejection_checklist.json").read_text(encoding="utf-8")
    )

    assert sorted(checklist) == sorted(required)
    assert all(checklist[name] for name in required)
