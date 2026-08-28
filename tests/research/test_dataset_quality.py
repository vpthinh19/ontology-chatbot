"""Các luật kiểm tra tính chất của dataset sinh từ ontology và danh mục.

Phép kiểm đối chiếu với artifact hiện tại thay vì chốt cứng quy mô phát hành, để
phạm vi kiểm tra thay đổi cùng dữ liệu.
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
from ontchatbot.research.answer_scope import (
    ANSWERED_BY,
    PROCEDURE_FAMILY,
    answered_in_dump,
    dump_literals,
)
from ontchatbot.research.mentions import mention_index, overloaded_mentions
from ontchatbot.research.graph import load_ontology
from ontchatbot.runtime.cards import CardLookup
from ontchatbot.runtime.text import normalize_model_input
from ontchatbot.settings import (
    DATASET_DIR,
    FRAMES_PATH,
    ONTOLOGY_NS,
    QUERY_CATALOGUE_PATH,
    REJECTION_CHECKLIST_PATH,
    REJECTION_FRAMES_PATH,
    REJECTION_PROVENANCE_PATH,
)

MARKER = "không có thông tin"
SPLITS = ("train", "val", "test")
STATIC_SHORT_FAMILIES = {
    "academic-performance-table",
    "academic-program-catalogue-table",
    "certificate-catalogue-table",
    "certificate-conversion-table-english-language-major-student",
    "certificate-conversion-table-moi-doi-tuong",
    "certificate-conversion-table-special-program-non-language-major-student",
    "certificate-conversion-table-standard-program-non-language-major-student",
    "class-size-table",
    "graduation-classification-table",
    "language-course-assessment-table",
    "language-course-classification-table",
    "payment-fee-by-method",
    "scholarship-rate-table-special-program",
    "scholarship-rate-table-standard-program",
    "study-year-classification-table",
}


def _flatten(text: str, *, fold_d: bool = False) -> str:
    """Chuẩn hoá như runtime, rồi bỏ dấu.

    Người dùng Việt thường gõ chat không dấu, và nhóm câu ``noisy`` cũng sinh ra
    dạng đó. Hai câu chỉ khác nhau ở dấu là một câu đối với model.

    ``fold_d`` quy cả ``đ`` về ``d``. Chỉ bật khi dò rò rỉ, vì nhóm ``noisy``
    làm đúng phép thay đó. Không bật khi dò mâu thuẫn đích: *"điểm d khoản 1
    Điều 22"* và *"điểm đ khoản 1 Điều 22"* là hai điểm luật khác nhau, và
    ``normalize_model_input`` giữ nguyên ``đ`` nên runtime cũng phân biệt được.
    Gộp chúng lại là tự bịa ra một mâu thuẫn không có thật.
    """

    lowered = normalize_model_input(text).casefold()
    decomposed = unicodedata.normalize("NFD", lowered)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return stripped.replace("đ", "d") if fold_d else stripped


def _contains_phrase(text: str, phrase: str) -> bool:
    """So cụm trọn vẹn; ``Điều 1`` không được khớp ``Điều 10``."""

    return re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", text) is not None


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

    by_text: dict[str, set[tuple[str, tuple[str, ...]]]] = defaultdict(set)
    for row in rows:
        by_text[_flatten(row["input"])].add(
            (row["query_id"], tuple(row["target"]))
        )

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


@pytest.fixture(scope="module")
def provenance() -> dict[str, dict[str, str]]:
    """Khuôn và neo đã đẻ ra từng câu từ chối, do bộ sinh ghi lại."""

    path = REJECTION_PROVENANCE_PATH
    assert path.exists(), (
        "thiếu sổ khuôn câu từ chối. Bộ sinh đã gỡ khỏi mã nguồn, nên tệp "
        "này là bản ghi DUY NHẤT về khuôn đã đẻ ra từng câu từ chối - lấy lại "
        "từ lịch sử git chứ không sinh lại được."
    )
    return json.loads(path.read_text(encoding="utf-8"))


def test_rejection_provenance_covers_every_rejection_row(rows, provenance) -> None:
    """Sổ khuôn phải phủ ĐỦ câu từ chối, nếu không phép kiểm dưới soi hụt.

    Một dòng từ chối vắng mặt trong sổ là một dòng không ai canh được, và nó im
    lặng - phép kiểm vẫn xanh vì nó chỉ duyệt những dòng có trong sổ.
    """

    rejected = {row["id"] for row in rows if row["query_id"] == "no-information"}
    assert rejected, "không đọc được dòng từ chối nào"
    assert rejected - set(provenance) == set()


def test_rejection_provenance_matches_the_question_it_claims_to_explain(
    rows, provenance, resolved
) -> None:
    """Sổ khuôn phải nói THẬT: neo nó khai phải có mặt trong chính câu hỏi.

    Đây là chỗ chống "tự chấm bài mình". Ba phép kiểm kia đọc sổ để biết dòng
    nào hỏi cái gì; nếu sổ ghi sai neo, hoặc ghi neo rỗng cho một dòng có neo,
    thì chúng bỏ qua dòng đó mà vẫn xanh. Phép kiểm này đối chiếu sổ với văn bản
    câu hỏi, là thứ sổ không tự dựng ra được.

    Dùng được vì bộ sinh cố ý KHÔNG làm lỗi chính tả bên trong tên neo: phong
    cách ``noisy`` chỉ tác động phần còn lại của câu, nên cách gọi luôn còn
    nguyên văn trong câu hỏi.
    """

    text_of = {row["id"]: row["input"].casefold() for row in rows}
    anchored = {
        row_id: entry
        for row_id, entry in sorted(provenance.items())
        if entry["anchor"]
    }
    assert anchored, "sổ khuôn không ghi neo cho dòng nào"

    wrong = [
        (row_id, entry["anchor"])
        for row_id, entry in anchored.items()
        if not any(
            mention.casefold() in text_of.get(row_id, "")
            for mention in resolved.get(entry["anchor"], ())
        )
    ]

    assert wrong == []


def test_no_rejection_row_asks_a_fact_its_own_anchor_carries(
    rows, provenance, graph
) -> None:
    """Câu từ chối không được hỏi dữ kiện mà neo của nó trả lời được.

    Các họ ``*-facts`` trả toàn bộ node, nên phép kiểm chạy truy vấn dump và so
    dữ kiện được hỏi với kết quả thực tế. Cách này bao phủ cả dữ kiện nằm trong
    văn bản tự do như ``stepText``, không chỉ các thuộc tính riêng.
    """

    dumped = dump_literals(graph, load_catalogue(QUERY_CATALOGUE_PATH), PROCEDURE_FAMILY)
    wrong = [
        (row_id, entry)
        for row_id, entry in sorted(provenance.items())
        if entry["anchor"]
        and answered_in_dump(dumped.get(entry["anchor"], ""), entry["template"])
    ]

    assert wrong == []


def test_no_rejection_template_runs_out_of_valid_anchors(graph) -> None:
    """Khuôn từ chối phải còn ít nhất MỘT neo hợp lệ, nếu không nó là khuôn chết.

    Khuôn mà MỌI thủ tục đều trả lời được thì lọc bao nhiêu cũng vô nghĩa - phải
    gỡ khỏi ``rejections.jsonl``. Bốn khuôn hỏi mục đích (*"vì sao lại {anchor}"*,
    *"{anchor} sinh ra để làm gì"*...) đúng vào ca này và đã bị gỡ.

    Phép kiểm này canh chiều ngược lại của phép kiểm trên: chỗ kia bảo đảm không
    cặp nào hỏng, chỗ này bảo đảm việc loại cặp hỏng không âm thầm biến một khuôn
    thành khuôn không bao giờ sinh ra dòng nào.
    """

    dumped = dump_literals(graph, load_catalogue(QUERY_CATALOGUE_PATH), PROCEDURE_FAMILY)
    assert dumped, "không dựng được kết quả dump cho thủ tục nào"

    templates = {
        template
        for payload in (
            json.loads(line)
            for line in (REJECTION_FRAMES_PATH)
            .read_text(encoding="utf-8")
            .splitlines()
            if line.strip()
        )
        for template in payload["templates"]
        if "{anchor}" in template
    }
    assert templates, "không đọc được khuôn từ chối có chỗ trống nào"

    dead = sorted(
        template
        for template in templates
        if all(answered_in_dump(text, template) for text in dumped.values())
    )

    assert dead == []


def test_ambiguous_rejections_are_not_resolved_by_their_own_frame(
    rows, provenance, graph
) -> None:
    """Câu "mơ hồ" chỉ được từ chối khi CHÍNH KHUNG cũng không gỡ được mơ hồ.

    Cách gọi trỏ tới nhiều node là điều kiện CẦN, chưa đủ. Nếu các node đó nằm ở
    những họ khác nhau thì khung câu hỏi đã chọn hộ một họ, và câu hỏi còn đúng
    một đáp án - từ chối là từ chối oan.

    Ca thật: *"Mẫu số 13"* trỏ tới hai tờ đơn khác nhau ngoài đời, nhưng hỏi
    *"thông tin tải xuống của Mẫu số 13"* thì chỉ còn mục tải trên website.
    **15 dòng** đã bị gán từ chối oan trước khi có phép kiểm này. Ngược lại,
    *"Điều 1"* có ở cả ba tài liệu nhưng cả ba cùng một họ tra điều luật, nên
    khung không gỡ được gì và nó mơ hồ thật.
    """

    catalogue = load_catalogue(QUERY_CATALOGUE_PATH)
    by_family = {
        query_id: {
            value
            for slot in spec.slots.values()
            if slot.kind == "iri"
            for value in slot.values
        }
        for query_id, spec in catalogue.items()
    }
    anchors = tuple(sorted({value[1:] for values in by_family.values() for value in values}))
    overloaded = overloaded_mentions(graph, anchors)
    text_of = {row["id"]: _flatten(row["input"]) for row in rows}

    wrong = []
    for row_id, entry in sorted(provenance.items()):
        if entry["class"] != "ambiguous":
            continue
        question = text_of.get(row_id, "")
        for mention, names in overloaded.items():
            if _flatten(mention) not in question:
                continue
            owners = {f":{name}" for name in names}
            if not any(len(owners & values) > 1 for values in by_family.values()):
                wrong.append((row_id, mention, sorted(names)))
            break

    assert wrong == []


def test_declared_answer_marks_still_appear_in_some_dump(graph) -> None:
    """Mỗi dấu hiệu khai trong ``ANSWERED_BY`` phải còn bắt được ÍT NHẤT một neo.

    Đây là chỗ chống mục ruỗng âm thầm. Sửa một bước trong ontology, hay đổi cách
    diễn đạt, mà quên sửa dấu hiệu ở đây thì ``answered_in_dump`` trả ``False``
    cho mọi neo: phép lọc **ngừng lọc mà không có triệu chứng nào**, và câu từ
    chối oan lặng lẽ quay lại đúng chỗ vừa dọn.
    """

    dumped = dump_literals(graph, load_catalogue(QUERY_CATALOGUE_PATH), PROCEDURE_FAMILY)
    marks = sorted({mark for values in ANSWERED_BY.values() for mark in values})
    assert marks, "không khai dấu hiệu nào"

    unused = [
        mark
        for mark in marks
        if not any(mark in text for text in dumped.values())
    ]

    assert unused == []


def test_no_general_entity_question_with_a_real_name_is_rejected(
    rows, resolved, graph, provenance
) -> None:
    """Tên gọi thật trong khuôn hỏi-chung phải trả toàn bộ node.

    Phép kiểm này bao phủ câu do khung ý định ghép với thực thể thuộc họ truy vấn
    khác; kiểm tra theo neo không bao phủ trường hợp đó. Các cụm bên dưới chỉ mô
    tả yêu cầu trả toàn bộ node, không phải câu hỏi thuộc tính như lệ phí, điểm
    chuẩn hoặc người ký duyệt. Việc mở rộng phạm vi trả lời được khai ở
    ``ANSWERED_BY`` và bộ sinh.
    """

    owners: dict[str, set[str]] = defaultdict(set)
    for node, texts in resolved.items():
        for text in texts:
            owners[_flatten(text, fold_d=True)].add(node)
    answerable_names = sorted(
        (text for text, nodes in owners.items() if len(nodes) == 1),
        key=len,
        reverse=True,
    )
    general_markers = tuple(
        _flatten(text, fold_d=True)
        for text in (
            "cho biết đầy đủ",
            "hướng dẫn đầy đủ",
            "mình cần tra cứu",
            "hãy tổng hợp",
            "có những điều gì cần biết",
            "có những điều gì cần lưu ý",
            "hồ sơ nguồn",
            "hồ sơ chính thức",
            "hướng dẫn nguồn",
            "trang danh mục ghi nhận",
            "nguồn chính thức trình bày",
            "được thực hiện cụ thể ra sao",
            "được tổ chức cụ thể ra sao",
            "được áp dụng cụ thể ra sao",
            "được xác định cụ thể ra sao",
            "được định nghĩa cụ thể ra sao",
        )
    )

    wrong = []
    for row in rows:
        if row["query_id"] != "no-information":
            continue
        question = _flatten(row["input"], fold_d=True)
        # Tên thật nhưng trỏ tới nhiều node ("Điều 1", "khoản 1 Điều 10") là
        # nhóm ``ambiguous`` và phải tiếp tục từ chối.
        #
        # Hỏi sổ khuôn thay vì dò lại tên mơ hồ trong câu hỏi: phong cách
        # ``noisy`` xoá dấu cách nên tên neo dính vào từ đứng trước
        # ("...tải xuống củaĐơn xin chuyển Chương trình đào tạo"), phép so ranh
        # giới từ trượt, nên tên mơ hồ không phải tiêu chí phân loại tin cậy.
        if provenance[row["id"]]["class"] == "ambiguous":
            continue
        if any(marker in question for marker in general_markers) and any(
            _contains_phrase(question, name) for name in answerable_names
        ):
            wrong.append(row["input"])

    assert answerable_names, "không nạp được tên gọi trả lời được"
    assert wrong == []


def test_rejection_rate_does_not_spike_by_question_length(splits) -> None:
    """Không bậc độ dài nào được vượt 1,5 lần tỷ lệ từ chối nền ở train."""

    rows = splits["train"]
    baseline = sum(
        row["query_id"] == "no-information" for row in rows
    ) / len(rows)
    bands: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for row in rows:
        words = len(row["input"].split())
        band = (
            "2-6" if words <= 6 else
            "7-9" if words <= 9 else
            "10-13" if words <= 13 else
            "14-17" if words <= 17 else
            "18+"
        )
        bands[band][1] += 1
        bands[band][0] += row["query_id"] == "no-information"

    rates = {
        band: rejected / total
        for band, (rejected, total) in bands.items()
    }
    assert set(rates) == {"2-6", "7-9", "10-13", "14-17", "18+"}
    assert {
        band: rate
        for band, rate in rates.items()
        if rate > baseline * 1.5
    } == {}


def test_release_rejection_rate_preserves_enough_no_information_training(rows) -> None:
    """Release phải giữ 12--20% câu ``no-information``.

    Phép kiểm này tồn tại vì trong một lượt chỉnh số, tham số từng bị hạ từ
    0,18 xuống 0,065, cắt hơn nửa tín hiệu dạy model từ chối, mà không phép
    kiểm nào thấy: chỗ không ai canh là chỗ trôi. Khoảng 12--20% rộng có chủ
    đích: nó canh việc tham số bị đổi âm thầm, không phải canh một con số cụ
    thể của release hôm nay.
    """

    rejection_rate = sum(
        row["query_id"] == "no-information" for row in rows
    ) / len(rows)

    assert 0.12 <= rejection_rate <= 0.20


def test_priority_domains_and_length_extremes_stay_balanced(splits) -> None:
    """Miền trọng tâm không lép vế; mọi miền trả lời được có đủ ngắn và dài."""

    catalogue = load_catalogue(QUERY_CATALOGUE_PATH)
    rows = splits["train"]
    by_domain: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_domain[catalogue[row["query_id"]].domain].append(row)

    # Số dòng phản ánh độ rộng ontology, không phản ánh mức ưu tiên của miền.
    # Chất lượng của các miền trọng tâm được đo bằng độ chính xác trên bộ chấm.

    answerable = {
        spec.domain
        for spec in catalogue.values()
        if spec.tier == "primary" and spec.domain != "out-of-domain"
    }
    unbalanced = {}
    for domain in sorted(answerable):
        domain_rows = by_domain[domain]
        assert domain_rows, f"miền trả lời được bị mất khỏi train: {domain}"
        short = sum(2 <= len(row["input"].split()) <= 6 for row in domain_rows)
        long = sum(len(row["input"].split()) >= 14 for row in domain_rows)
        if short / len(domain_rows) < 0.15 or long / len(domain_rows) < 0.15:
            unbalanced[domain] = {
                "rows": len(domain_rows),
                "short": short,
                "long": long,
            }

    assert unbalanced == {}


def test_held_out_splits_stay_big_enough_to_measure(splits) -> None:
    """Val và test phải đủ lớn để đo, tính bằng số dòng.

    Sai số của phép đo phụ thuộc số mẫu, không phụ thuộc tỷ lệ so với tập train.
    Sàn 380 dòng cho sai số chuẩn khoảng ±2,5 điểm phần trăm ở mức chính xác 50%
    và hẹp hơn khi model chính xác hơn; độ phân giải này đủ để so sánh model.
    """

    for split in ("val", "test"):
        assert len(splits[split]) >= 380, (split, len(splits[split]))


def test_all_static_families_have_generated_short_questions(splits) -> None:
    """Mười bốn họ không đi đường ``anchor`` vẫn phải có câu ngắn thật."""

    from tests.support.frames import load_frames

    catalogue = load_catalogue(QUERY_CATALOGUE_PATH)
    frames = load_frames(FRAMES_PATH, catalogue)
    declared = {
        query_id
        for query_id, items in frames.items()
        if any(frame.short for frame in items)
    }
    generated = {
        row["query_id"]
        for row in splits["train"]
        if len(row["input"].split()) <= 6
    }

    assert declared == STATIC_SHORT_FAMILIES
    assert STATIC_SHORT_FAMILIES - generated == set()


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

    checklist_path = REJECTION_CHECKLIST_PATH
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
        # Không bỏ qua dòng không nhận ra tên nào. Mọi mẫu hard-negative đều có
        # chỗ trống, nên dòng nào cũng phải chứa một cách gọi - bỏ qua chúng
        # sẽ tạo khoảng trống trong phạm vi kiểm tra.
        if not any(text in lowered for text in procedural):
            wrong.append(row["input"])

    assert wrong == []
    assert every, "không nạp được cách gọi nào - phép kiểm này đang rỗng"


def test_a_question_with_an_off_topic_tail_is_still_answered(rows) -> None:
    """Câu hỏi trả lời được kèm một vế ngoài lề vẫn phải được trả lời.

    Vế ngoài lề như lời chào hoặc cảm ơn không làm thay đổi dữ kiện chính cần
    truy xuất.
    """

    tails = {
        payload["class"]: payload["templates"]
        for payload in (
            json.loads(line)
            for line in (REJECTION_FRAMES_PATH)
            .read_text(encoding="utf-8")
            .splitlines()
            if line.strip()
        )
    }.get("distraction", [])

    assert tails, "không còn mẫu vế ngoài lề nào - phép kiểm này đang rỗng"

    marked = [
        row["input"]
        for row in rows
        if row["query_id"] == "no-information"
        and any(tail.strip().strip(",") in row["input"] for tail in tails)
    ]
    answered = [
        row
        for row in rows
        if row["query_id"] != "no-information"
        and any(tail.strip().strip(",") in row["input"] for tail in tails)
    ]

    assert marked == []
    assert answered, "không sinh được câu nào có vế ngoài lề"


def test_held_out_frames_are_not_near_duplicates_of_taught_frames() -> None:
    """Khung dùng để chấm không được là biến thể của khung đã dạy.

    Nếu train có *"{X} web đánh số bao nhiêu"* còn test có *"{X} trên web đánh số
    mấy"* thì tập chấm không đo "cách hỏi chưa từng thấy" nữa - nó đo trí nhớ.

    Bung toàn bộ phép thay từ để hỏi mà bộ sinh thật sự dùng, rồi so
    theo chuẩn hoá runtime. Như vậy hợp đồng là "không cùng một biến thể
    sinh được", không phải một ngưỡng similarity tùy chọn.
    """

    from tests.support.frames import load_frames, question_variants
    from tests.support.frames import split_frames

    catalogue = load_catalogue(QUERY_CATALOGUE_PATH)
    frames = load_frames(FRAMES_PATH, catalogue)

    duplicate_variants = []
    for query_id, items in frames.items():
        parts = split_frames(items)
        variants = {
            frame.text: {
                normalize_model_input(text).casefold()
                for text in question_variants(frame.text)
            }
            for frame in items
        }
        for left_split, right_split in (("train", "val"), ("train", "test"), ("val", "test")):
            for left in parts[left_split]:
                for right in parts[right_split]:
                    overlap = variants[left.text] & variants[right.text]
                    if overlap:
                        duplicate_variants.append(
                            (query_id, left.text, right.text, sorted(overlap))
                        )

    assert duplicate_variants == []


def test_rejection_classes_come_from_the_requirements_file() -> None:
    """Danh sách nhóm câu từ chối phải đọc từ ``coverage.json``.

    Tệp yêu cầu là nguồn chuẩn cho các nhóm, nên thay đổi phân loại được áp dụng
    nhất quán cho dataset và phép kiểm.
    """

    required = json.loads(
        (DATASET_DIR / "coverage.json").read_text(encoding="utf-8")
    )["rejection_classes"]
    checklist = json.loads(
        REJECTION_CHECKLIST_PATH.read_text(encoding="utf-8")
    )

    assert sorted(checklist) == sorted(required)
    assert all(checklist[name] for name in required)


def test_every_answer_carries_a_dated_source(rows, graph) -> None:
    """Mỗi dữ kiện trả về phải có nguồn, ngày nguồn và đường dẫn.

    Phép kiểm chạy truy vấn thật để xác nhận các giá trị nguồn mà engine trả về,
    bao gồm cả URL. Node chỉ trả ``tên gọi`` không khẳng định dữ kiện nên được
    nhận diện từ kết quả truy vấn thay vì bằng danh sách ngoại lệ viết tay.
    """

    from ontchatbot.research.graph import execute_select

    lookup = CardLookup()
    date_marks = re.compile(r"ngày \d{1,2}/\d{1,2}/\d{4}|\d{4}-\d{2}-\d{2}")
    targets = {
        (row["query_id"], tuple(row["target"]))
        for row in rows
        if row["query_id"] != "no-information"
    }
    assert targets, "không đọc được đích trả lời được nào"

    missing_source, missing_date = [], []
    for query_id, target in sorted(targets):
        target = lookup.query(query_id, target)
        answer = execute_select(graph, target)
        if not answer:
            continue
        if {str(row["thuoctinh"]) for row in answer} == {"tên gọi"}:
            continue
        # Đường dẫn là điều kiện cứng vì người dùng cần nó để tra cứu sâu hơn.
        # Tên trích dẫn không cần tách riêng khi văn bản tự trả lời về mình, vì
        # tiêu đề và ngày ban hành đã nằm trong câu trả lời.
        if not any(row.get("duongdan") for row in answer):
            missing_source.append(query_id)
            continue
        text = " | ".join(
            str(value) for row in answer for value in row.values() if value
        )
        if not date_marks.search(text):
            missing_date.append(query_id)

    assert missing_source == []
    assert missing_date == []
