"""Sinh dataset từ ontology, danh mục truy vấn và khung câu hỏi.

Chiều đi một chiều, không được đảo: ontology quyết định trả lời được gì, danh mục
quyết định hình dạng truy vấn, khung quyết định cách hỏi. Câu hỏi được **ghép**
chứ không viết tay từng câu, và đích được **bung ra từ ``target_template``** chứ
không gõ lại - 841 dòng của bản cũ chết chỉ vì lệch đúng một từ ``DISTINCT``.

Bốn ràng buộc thiết kế, mỗi cái chống lại một lỗi đã thực sự xảy ra:

1. **Chia tập theo KHUNG, không theo dòng.** Sinh tổ hợp rồi chia ngẫu nhiên thì
   test chỉ là hoán vị của train. Val/test dùng khung mà train chưa từng thấy.
2. **Cặp tương phản tối thiểu.** Mỗi neo xuất hiện với MỌI ý định hợp lệ của nó,
   nên ranh giới giữa các ý định được dạy tường minh. Đây là chế độ lỗi đo được ở
   bản cũ: nhận đúng thực thể, chọn sai quan hệ.
3. **Trọng số theo miền.** Quy trình học vụ là trọng tâm dự án nhưng chỉ chiếm 14%
   không gian đích; không cân lại thì model dồn năng lực vào tra cứu điều khoản.
4. **Câu từ chối sinh từ đồ thị thật**, không bịa: cách gọi mơ hồ và ghép sai neo.
"""

from __future__ import annotations

import hashlib
import json
import random
import re
from itertools import product
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from rdflib import RDF, Graph, URIRef

from ..catalogue import QuerySpec
from ..settings import ONTOLOGY_NS
from ..runtime.sparql import SparqlError, execute_select
from ..runtime.text import normalize_model_input
from .compose import Frame, REGISTERS, choose_mention, decorate, question_variants
from .dataset import NEAR_DUPLICATE_THRESHOLD, _character_trigrams

MARKER = "không có thông tin"

#: Họ trả lời "chatbot làm được gì" - liệt kê thẳng các thủ tục từ ontology.
CAPABILITY_FAMILY = "assistant-capabilities"
#: MỌI câu từ chối đều trả ``MARKER``. Đã thử cho nhóm ngoài phạm vi trả về
#: truy vấn liệt kê năng lực và **đo được 42% sai** - cao nhất toàn bộ danh mục.
#:
#: Lý do rất cơ học: ``MARKER`` dài 4 token và là hằng số, model chỉ cần nhớ một
#: chuỗi. Truy vấn năng lực dài ~30 token và phải sinh chính xác từng ký tự cho
#: những câu vào chẳng liên quan gì nhau, từ "chào bạn" tới "giá vàng hôm nay".
#: Chế độ lỗi cũng tệ hơn: thay vì im lặng an toàn, model đẻ ra truy vấn trông
#: hợp lý với thực thể BỊA (":GradalReviewProcedure" cho câu "đi Đà Lạt mấy
#: tiếng"), và một câu như vậy đã lọt qua cả bốn cửa runtime.
#:
#: NGOẠI LỆ DUY NHẤT: nhóm ``greeting-social``. Câu chào là thứ đầu tiên gần như
#: ai cũng gõ, và trả "Không có thông tin." ngay câu đầu thì phần lớn người ta
#: đóng luôn - còn liệt kê thủ tục thì vừa chào lại vừa chỉ đường.
#:
#: Khác hẳn lần thử trước ở chỗ QUY MÔ: lần đó bắt model sinh chuỗi 30 token cho
#: MỌI câu lạc đề, từ "chào bạn" tới "giá vàng hôm nay" tới "cách nấu phở" -
#: những câu chẳng liên quan gì nhau mà cùng một đáp án. Chào hỏi thì là một tập
#: nhỏ, rất đều, và model đã nhận đúng 6/6 ở lượt đo gần nhất.
_CAPABILITY_KINDS = frozenset({"greeting-social"})

#: Số dòng train sinh cho mỗi target, theo miền.
#:
#: Quy trình học vụ là trọng tâm dự án. Cân bằng bằng SỐ CÂU chứ không bằng cách
#: cắt bớt khả năng trả lời: tra cứu điều khoản vẫn phủ đủ, chỉ ít câu hơn.
DOMAIN_WEIGHT = {
    "procedure": 6,
    # Biểu mẫu là một trong bốn việc người dùng nêu, mà chỉ chiếm 6,7% dataset.
    "form": 6,
    "certificate": 3,
    "tuition": 3,
    "academic-rule": 2,
    "document": 1,
}
DEFAULT_WEIGHT = 2

#: Số neo lấy mẫu cho val và test ở mỗi họ. Val/test đo cách hỏi mới, không đo
#: khả năng nhớ thêm thực thể, nên không cần phủ hết neo.
HELD_OUT_ANCHORS = 6
#: Sàn dòng train cho MỖI HỌ, bất kể họ đó áp cho bao nhiêu thực thể.
#:
#: Mỗi họ là một HÌNH DẠNG câu truy vấn - một tổ hợp cú pháp SPARQL riêng. Model
#: phải dựng lại được hình dạng đó, không chỉ nhớ chuỗi. Sàn cũ là 4: có 30 họ
#: được dạy dưới 10 dòng, tức là model nhìn thấy cả một dạng cú pháp đúng bốn
#: lần rồi phải tự sinh lại chính xác từng ký tự.
#:
#: Số dòng của một họ đang tỉ lệ với SỐ THỰC THỂ nó áp được, mà số đó là chuyện
#: ngẫu nhiên của công văn chứ không phải thước đo độ khó cú pháp: "nộp học phí
#: bằng hình thức nào" chỉ có một đích nên được 7 dòng, trong khi nó là câu phổ
#: biến bậc nhất.
_MIN_TRAIN_ROWS = 12
_MIN_HELD_OUT_ROWS = 2

#: Trọng số riêng cho từng họ, CHỈ đặt ở chỗ có bằng chứng thật.
#:
#: Không xếp hạng 22 thủ tục theo phỏng đoán: dự án không có log câu hỏi thật,
#: đoán sai thì đóng đinh một thiên lệch sai vào dữ liệu mà không ai biết. Ba
#: mẩu bằng chứng đang có: người dùng khẳng định nộp tiền/đóng học phí là câu
#: phổ biến nhất; giảng viên chủ nhiệm đề tài test câu "bạn hỗ trợ được gì";
#: và bốn việc người dùng nêu là làm được gì / quy trình / biểu mẫu / nguồn.
FAMILY_WEIGHT = {
    # Câu đầu tiên gần như ai cũng hỏi, mà chỉ có đúng một đích.
    "assistant-capabilities": 40,
    # Người dùng khẳng định đây là câu phổ biến nhất; cũng chỉ một đích.
    "academic-procedure-supports-payment-method-label": 24,
    # "Nguồn công văn nếu cần" - một trong bốn việc người dùng nêu. CHỈ nâng các
    # họ gắn nguồn vào NỘI DUNG thủ tục; không nâng ``source-citation``, vì họ đó
    # áp cho hàng trăm thực thể nên nhân trọng số lên là nó nuốt cả dataset -
    # nhân 4 đã đẩy tra cứu văn bản từ 19,6% lên 26,9%.
    "procedure-steps-with-source": 8,
    "procedure-requirements-with-source": 8,
}

#: Cặp họ mà model ĐO ĐƯỢC là hay nhầm sang nhau, kèm số ca sai trong 455 câu
#: chấm của lượt huấn luyện đầu tiên.
#:
#: Bộ sinh vốn đã cho mỗi neo xuất hiện với mọi ý định hợp lệ của nó, nhưng các
#: dòng đó nằm rải rác. Ranh giới giữa hai ý định sát nhau chỉ học được khi model
#: nhìn thấy chúng trên CÙNG một thực thể, đủ nhiều lần. Lượt bổ sung dưới đây
#: sinh đúng những cặp đó.
CONTRAST_PAIRS = (
    # BỎ cặp ("class-size-rule", "class-size-rule-maximum-value"): đo lại thì
    # hai họ đó trả lời CÙNG MỘT câu hỏi của con người, nên dạy đối chiếu là
    # dạy model đoán. Họ con đã hạ xuống secondary thay vì bơm thêm dữ liệu.
    # 6 ca: các bước kèm nguồn <-> điều kiện kèm nguồn
    ("procedure-steps-with-source", "procedure-requirements-with-source"),
    # 5 ca: tên quốc tế <-> tên tiếng Việt của cùng một chứng chỉ
    ("certificate-official-certificate-name", "certificate-label"),
    # 4 ca: tiêu đề mục tải <-> đường dẫn tải
    ("form-catalogue-entry-listed-title", "form-catalogue-entry-download-url"),
    # 3 ca: tiêu đề đầy đủ <-> tên gọi của cùng một văn bản
    ("document-title", "document-label"),
    # Mẫu "thêm một chặng thừa": hỏi tóm tắt thủ tục mà model chèn nextProcedure
    ("academic-procedure-summary-text",
     "academic-procedure-next-procedure-summary-text"),
)
#: Số lượt sinh cho mỗi cặp, mỗi bên.
_CONTRAST_ROWS = 14

#: Thực thể được hỏi nhiều hơn hẳn phần còn lại, theo người dùng.
PRIORITY_ANCHORS = frozenset({":TuitionPaymentProcedure"})
#: Xác suất lượt bơm thêm chọn đúng một thực thể ưu tiên, khi họ đó có.
_PRIORITY_ANCHOR_SHARE = 0.35
#: Miền trọng tâm của dự án; coverage.json đòi đủ bốn phong cách ở mọi tập.
_PRIORITY_DOMAINS = frozenset({"procedure"})

#: Tỷ lệ câu từ chối trên mỗi tập.
_REJECTION_SHARE = 0.18
#: Tỷ lệ câu hỏi trả lời được nhưng có kèm một vế ngoài lề.
#:
#: Đây KHÔNG phải câu từ chối. Bản trước dạy "có vế ngoài lề thì từ chối tất",
#: nghĩa là người dùng viết *"đăng ký học phần thế nào ạ, em cảm ơn"* cũng có
#: nguy cơ bị im lặng. Giờ dạy ngược lại: bỏ qua vế thừa, trả lời phần hỏi thật.
_DISTRACTION_SHARE = 0.04


@dataclass(frozen=True)
class Row:
    id: str
    query_id: str
    register: str
    input: str
    target: str

    def as_json(self) -> dict[str, str]:
        return {
            "id": self.id,
            "query_id": self.query_id,
            "register": self.register,
            "input": self.input,
            "target": self.target,
        }


#: Số khung giữ lại cho mỗi tập đánh giá.
#:
#: Số khung GIẤU cho mỗi bên (val và test).
#:
#: Từng là 2, tức mỗi họ có 8 khung thì dạy 4 giấu 4 - **giấu 50%**, trong khi
#: thông lệ là 10-20%. Hệ quả đo được ở lượt 4: **13 khung bị giấu sai 100%**,
#: không đúng lấy một câu. Sai *toàn bộ* nghĩa là model chưa từng thấy lối nói
#: đó, nên đó là phép đo cách hỏi lạ chứ không phải phép đo năng lực.
#:
#: Nay là 1: mỗi họ 10 khung, **dạy 8 - chỉnh 1 - chấm 1**, giấu 20%.
#:
#: Một khung mỗi bên nghe mỏng, nhưng nỗi lo "may rủi" chỉ đúng khi đọc TỪNG HỌ.
#: Số tổng cộng gộp 61 họ nên vẫn có 61 khung chưa từng thấy mỗi bên - đủ dày.
#: Và nó chỉ mỏng khi khung giấu được chọn thiên lệch; ``split_safe_order`` nay
#: chọn theo thứ tự băm ổn định chứ không lấy khung dị nhất.
HELD_OUT_FRAMES = 1

#: Chỗ trống trong mẫu câu từ chối ``incomplete-request`` mang ĐÚNG tên slot của
#: họ truy vấn, để ghép được với giá trị đã đo là gây nhiều đáp án.
_SLOT_PLACEHOLDER = re.compile(r"\{([a-z][a-z0-9_]*)\}")


#: Giá trị mẫu để ước lượng câu hỏi SAU KHI đã ghép tên thực thể.
#:
#: Đo trên khung trần là không đủ: hai khung chỉ giống nhau 0,816 ở dạng trần đã thành
#: 0,934 sau khi cùng ghép một cái tên dài, vì tên đóng góp y hệt vào cả hai.
_PROBE = {
    "anchor": "Thủ tục nghỉ học tạm thời", "score": "7.5", "credits": "70",
    "rule": "Quy mô lớp Khối kỹ thuật", "program": "Công nghệ thông tin",
    "cohort": "65", "amount": "520000", "certificate": "IELTS",
    "article": "24", "clause": "3",
}
#: Biên an toàn dưới ngưỡng của validator, vì giá trị mẫu chỉ xấp xỉ tên thật.
#:
#: 0,05 vẫn để lọt: hai khung "{anchor} đăng ký tối thiểu mấy tín chỉ" và
#: "{anchor} tối thiểu bao nhiêu tín chỉ" - sau phép thay từ để hỏi chỉ còn khác
#: đúng chữ "đăng ký" - đo được 0,965 trên câu thật mà ước lượng vẫn dưới ngưỡng.
_ORDER_MARGIN = 0.05


def _probe_grams(
    frame: Frame,
    anchor: str | None = None,
    *,
    variants: bool = True,
) -> list[frozenset[str]]:
    text = frame.text
    for name, value in _PROBE.items():
        text = text.replace(f"{{{name}}}", anchor if name == "anchor" and anchor else value)
    forms = question_variants(text) if variants else (text,)
    return [_character_trigrams(form) for form in forms]


def split_safe_order(
    frames: tuple[Frame, ...],
    anchor: str | None = None,
) -> tuple[Frame, ...]:
    """Chọn khung để giấu đi sao cho chúng KHÔNG gần trùng khung đã dạy.

    Validator cấm câu gần trùng nằm khác tập (ngưỡng trigram 0,84) - và cấm đúng:
    nếu train có *"{anchor} được đăng ký nhiều nhất mấy tín chỉ"* còn val có
    *"theo {anchor} học nhiều nhất mấy tín chỉ"* thì tập chấm không còn đo "cách
    hỏi chưa từng thấy" nữa.

    Bản đầu gom khung gần nhau thành cụm rồi rải cụm vào các tập. Nó **sai âm
    thầm** khi cả họ chỉ có một cụm: val/test rỗng, rồi đoạn dự phòng bốc ngược
    khung từ train ra lấp - phá đúng đảm bảo nó phải giữ. Nới biên an toàn còn
    làm nặng thêm vì càng nhiều họ gom về một cụm.

    Bản này chọn thẳng: lấy làm khung giấu đi những khung **ít giống phần còn lại
    nhất**, rồi KIỂM lại. Không đạt thì ném lỗi nêu tên họ - khung phải viết lại,
    không xếp lại được.

    ``anchor`` phải là tên DÀI NHẤT mà họ này dùng được: độ giống tăng theo độ
    dài phần chung, ước lượng bằng tên ngắn hơn sẽ báo an toàn nhầm.
    """

    held = HELD_OUT_FRAMES
    items = list(frames)
    # Khung DẠY được nhân biến thể từ để hỏi; khung CHẤM thì không - xem
    # ``_question_core``. Đo đúng như vậy, nếu không phép ước lượng tự thổi
    # phồng bề mặt va chạm rồi bắt viết lại những khung vốn không va nhau.
    wide = {frame.text: _probe_grams(frame, anchor) for frame in items}
    narrow = {frame.text: _probe_grams(frame, anchor, variants=False) for frame in items}

    def similarity(left: Frame, right: Frame, both_wide: bool = False) -> float:
        right_grams = wide[right.text] if both_wide else narrow[right.text]
        return max(
            len(a & b) / len(a | b)
            for a in wide[left.text]
            for b in right_grams
        )

    def worst_against(frame: Frame, others: list[Frame]) -> float:
        """Độ giống cao nhất giữa ``frame`` và phần còn lại, xét CẢ HAI chiều.

        Phép đo bất đối xứng (khung dạy được nhân biến thể, khung chấm thì
        không), mà khung được chọn sẽ nằm ở cả hai vế khi kiểm chéo tập.
        """

        return max(
            (
                max(similarity(frame, other, both_wide=True), similarity(other, frame))
                for other in others
                if other is not frame
            ),
            default=0.0,
        )

    # KHÔNG chọn khung "riêng biệt nhất" để giấu. Bản trước làm vậy và nó tạo ra
    # một thiên lệch có hệ thống: tập chấm toàn cách nói dị nhất của mỗi họ, nên
    # mọi điểm số đo được đều là CẬN DƯỚI chứ không phải năng lực thật. Càng giấu
    # ít khung thì thiên lệch càng nặng - giấu 2 trong 10 mà vẫn lấy 2 cái dị
    # nhất thì tập chấm còn lệch hơn giấu 4 trong 8.
    #
    # Thay bằng: duyệt theo một thứ tự ỔN ĐỊNH nhưng không liên quan tới độ dị
    # (băm của chính khung), lấy khung ĐẦU TIÊN mà giấu đi vẫn an toàn. Ổn định
    # nên tái tạo được và không cần seed; không liên quan độ dị nên tập chấm là
    # mẫu đại diện.
    remaining = list(items)
    chosen: list[Frame] = []
    while len(chosen) < 2 * held and len(remaining) > 2:
        shuffled = sorted(
            remaining,
            key=lambda frame: hashlib.sha256(
                f"{frame.query_id}\x00{frame.text}".encode("utf-8")
            ).hexdigest(),
        )
        pick = next(
            (
                frame
                for frame in shuffled
                if worst_against(frame, remaining) < NEAR_DUPLICATE_THRESHOLD
            ),
            # Không khung nào giấu được an toàn: lấy cái ít va nhất rồi để phép
            # kiểm cuối ném lỗi nêu tên họ, thay vì lặng lẽ trả về bộ hỏng.
            min(remaining, key=lambda frame: (worst_against(frame, remaining), frame.text)),
        )
        chosen.append(pick)
        remaining.remove(pick)

    train = remaining
    val, test = chosen[:held], chosen[held:]
    worst = 0.0
    for left_group, right_group in ((train, val), (train, test), (val, test)):
        for left in left_group:
            for right in right_group:
                worst = max(worst, similarity(left, right))
    # So với ĐÚNG ngưỡng của validator, không trừ biên: phép ước lượng dùng tên
    # thực thể DÀI NHẤT, mà với một cái tên 58 ký tự thì hai khung ngắn bất kỳ
    # cũng trông giống nhau. Trừ thêm biên là bắt viết lại những khung vốn không
    # va nhau trên câu thật.
    if worst >= NEAR_DUPLICATE_THRESHOLD:
        raise ValueError(
            f"{items[0].query_id}: khung quá giống nhau để chia tập "
            f"(cao nhất {worst:.3f}); phải viết lại khung cho khác nhau hơn"
        )
    return tuple(train + val + test)


def split_frames(frames: tuple[Frame, ...]) -> dict[str, tuple[Frame, ...]]:
    """Chia khung: phần lớn cho train, hai cho val, hai cho test.

    Đây là trục chia tập DUY NHẤT. Neo thì phải xuất hiện ở train (model cần học
    tên của chúng); cái được giấu đi là CÁCH HỎI.
    """

    held = HELD_OUT_FRAMES
    if len(frames) < 2 * held + 2:
        raise ValueError(
            f"{frames[0].query_id}: cần ít nhất {2 * held + 2} khung để chia tập"
        )
    return {
        "train": frames[: -2 * held],
        "val": frames[-2 * held : -held],
        "test": frames[-held:],
    }


def _fill_targets(spec: QuerySpec, binding: Mapping[str, str]) -> str:
    target = spec.target_template
    for name, value in binding.items():
        target = target.replace(f"${{{name}}}", value)
    return target


def _question_core(
    frame: Frame,
    binding: Mapping[str, str],
    mentions: Mapping[str, tuple[str, ...]],
    spec: QuerySpec,
    register: str,
    rng: random.Random,
    *,
    variants: bool = True,
) -> str:
    """Câu hỏi đã ghép xong nhưng CHƯA khoác phong cách.

    Tách riêng để còn gắn được vế ngoài lề vào giữa: đuôi nhiễu phải nằm trước
    dấu kết câu, không phải sau nó.
    """

    values: dict[str, str] = {}
    for name, value in binding.items():
        if spec.slots[name].kind == "iri":
            values[name] = choose_mention(mentions[value[1:]], register, rng)
        else:
            values[name] = value
    filled = frame.fill(values)
    # Phép thay từ để hỏi là trục LÀM GIÀU KHI DẠY, không phải trục đánh giá.
    # Nhân nó ở val/test khiến hai khung vốn khác nhau đẻ ra hai câu gần trùng
    # nằm khác tập, và validator đỏ ở tận cuối chuỗi.
    return rng.choice(question_variants(filled)) if variants else filled


def _question(
    frame: Frame,
    binding: Mapping[str, str],
    mentions: Mapping[str, tuple[str, ...]],
    spec: QuerySpec,
    register: str,
    rng: random.Random,
    *,
    variants: bool = True,
) -> str:
    """Ghép một câu hỏi hoàn chỉnh từ khung, cách gọi tên và phong cách."""

    core = _question_core(
        frame, binding, mentions, spec, register, rng, variants=variants
    )
    return decorate(core, register, rng)


def executable_bindings(
    graph: Graph,
    catalogue: Mapping[str, QuerySpec],
    bindings: Mapping[str, list[dict[str, str]]],
) -> dict[str, list[dict[str, str]]]:
    """Bỏ những bộ giá trị mà truy vấn thật sự KHÔNG trả về dòng nào.

    Validator bắt mọi đích trong miền phải lấy ra được dữ liệu. Slot IRI thì đã
    có test riêng bảo đảm, nhưng slot số lấy từ ``coverage.json`` là giá trị do
    người chốt - một mốc ngưỡng viết sai sẽ tạo ra dòng dạy model sinh truy vấn
    rỗng ruột, đúng thứ ràng buộc số 4 của ``docs/DATASET.md`` cấm.
    """

    kept: dict[str, list[dict[str, str]]] = {}
    for query_id, options in bindings.items():
        spec = catalogue[query_id]
        alive = []
        for binding in options:
            try:
                if execute_select(graph, _fill_targets(spec, binding), max_rows=200):
                    alive.append(binding)
            except SparqlError:
                continue
        kept[query_id] = alive
    return kept


def incomplete_specifications(
    graph: Graph,
    catalogue: Mapping[str, QuerySpec],
    bindings: Mapping[str, list[dict[str, str]]],
) -> dict[str, list[tuple[str, str]]]:
    """Giá trị nào mà nêu MỘT MÌNH nó thì câu hỏi còn nhiều đáp án.

    Vài họ đòi hai thông tin mới trả lời được: học phí cần cả NGÀNH và KHOÁ, quy
    đổi chứng chỉ cần cả LOẠI và ĐIỂM. Người hỏi thường chỉ nêu một - *"học phí
    k67 như thế nào"* - và lượt 6 cho thấy model đáp **550.000** rất chắc chắn
    trong khi khoá 67 có tới **năm** mức khác nhau tuỳ ngành. Trả một con số tiền
    sai mà nói như đúng rồi là kiểu hỏng tệ nhất ở một buổi demo.

    Đo thẳng trên đồ thị chứ không chốt tay: giữ một slot, chạy hết mọi giá trị
    của slot kia, đếm số đáp án KHÁC NHAU. Chỉ giá trị nào cho ra nhiều hơn một
    đáp án mới được dùng làm câu từ chối - nếu chỉ có một đáp án thì câu hỏi ấy
    trả lời được và dạy từ chối là dạy sai.

    Trả về ``{query_id: [(tên slot, giá trị), ...]}``.
    """

    # Bỏ bớt một slot có thể ra đúng câu hỏi mà một họ KHÁC trả lời được: bỏ
    # ``clause`` khỏi "khoản 2 Điều 24" còn lại "Điều 24 nói gì", mà đó chính là
    # ``article-with-source``. Dạy từ chối câu ấy là dạy sai hẳn.
    answerable_alone = {
        frozenset(spec.slots)
        for spec in catalogue.values()
        if spec.tier == "primary" and spec.slots
    }

    found: dict[str, list[tuple[str, str]]] = {}
    for query_id, spec in sorted(catalogue.items()):
        if spec.tier != "primary" or len(spec.slots) < 2:
            continue
        combinations = bindings.get(query_id) or []
        for kept in sorted(spec.slots):
            if frozenset({kept}) in answerable_alone:
                continue
            answers: dict[str, set[tuple]] = {}
            for binding in combinations:
                if kept not in binding:
                    continue
                try:
                    rows = execute_select(
                        graph, _fill_targets(spec, binding), max_rows=50
                    )
                except SparqlError:
                    continue
                for row in rows:
                    answers.setdefault(binding[kept], set()).add(
                        tuple(sorted((name, str(value)) for name, value in row.items()))
                    )
            for value, distinct in sorted(answers.items()):
                if len(distinct) > 1:
                    found.setdefault(query_id, []).append((kept, value))
    return found


def generate(
    graph: Graph,
    catalogue: Mapping[str, QuerySpec],
    frames: Mapping[str, tuple[Frame, ...]],
    mentions: Mapping[str, tuple[str, ...]],
    ambiguous: Mapping[str, tuple[str, ...]],
    bindings: Mapping[str, list[dict[str, str]]],
    templates: Mapping[str, tuple[str, ...]],
    *,
    seed: int = 42,
) -> tuple[dict[str, list[Row]], dict[str, list[str]]]:
    """Sinh ba tập và bảng phân nhóm câu từ chối."""

    rng = random.Random(seed)
    splits: dict[str, list[Row]] = {"train": [], "val": [], "test": []}
    seen: set[str] = set()
    counter = 0

    def emit(split: str, query_id: str, register: str, question: str, target: str) -> bool:
        """Thêm một dòng. Trả về False nếu câu đã tồn tại - người gọi PHẢI thử lại.

        Bỏ trùng âm thầm sẽ ăn mất lần xuất hiện duy nhất của một giá trị slot,
        hoặc của một phong cách, và validator sẽ đỏ ở tận cuối chuỗi.
        """

        nonlocal counter
        key = normalize_model_input(question).casefold()
        if not key or key in seen:
            return False
        seen.add(key)
        counter += 1
        splits[split].append(
            Row(f"question-{counter:06d}", query_id, register, question, target)
        )
        return True

    def attempt(
        split: str,
        query_id: str,
        spec: QuerySpec,
        binding: Mapping[str, str],
        options: tuple[Frame, ...],
        register: str,
    ) -> bool:
        """Thử vài lần với khung khác nhau cho tới khi ra một câu chưa có."""

        target = _fill_targets(spec, binding)
        for _ in range(12):
            frame = rng.choice(options)
            question = _question(
                frame, binding, mentions, spec, register, rng,
                variants=split == "train",
            )
            if emit(split, query_id, register, question, target):
                return True
        return False

    for query_id in sorted(frames):
        spec = catalogue[query_id]
        parts = split_frames(frames[query_id])
        options = bindings.get(query_id, [])
        if not options:
            continue
        weight = FAMILY_WEIGHT.get(
            query_id, DOMAIN_WEIGHT.get(spec.domain, DEFAULT_WEIGHT)
        )

        # TRAIN. Ba lượt, theo đúng thứ tự ưu tiên của các ràng buộc:
        #   1. mỗi neo ít nhất một lần  -> phủ hết giá trị slot hữu hạn;
        #   2. mỗi phong cách ít nhất một lần -> đủ bốn register;
        #   3. bơm thêm cho đủ trọng số miền.
        used: set[str] = set()
        for index, binding in enumerate(options):
            register = REGISTERS[index % len(REGISTERS)]
            if attempt("train", query_id, spec, binding, parts["train"], register):
                used.add(register)
        for register in REGISTERS:
            if register in used:
                continue
            for binding in options:
                if attempt("train", query_id, spec, binding, parts["train"], register):
                    used.add(register)
                    break
        target_rows = max(_MIN_TRAIN_ROWS, len(options) * weight)
        produced = sum(1 for row in splits["train"] if row.query_id == query_id)
        priority = [
            option
            for option in options
            if option.get("anchor") in PRIORITY_ANCHORS
        ]
        for _ in range(target_rows * 6):
            if produced >= target_rows:
                break
            # Thực thể ưu tiên vẫn nằm chung danh sách, chỉ được bốc trúng nhiều
            # hơn - phủ hết neo là ràng buộc cứng, không được hy sinh.
            binding = (
                rng.choice(priority)
                if priority and rng.random() < _PRIORITY_ANCHOR_SHARE
                else rng.choice(options)
            )
            register = rng.choice(REGISTERS)
            produced += attempt(
                "train", query_id, spec, binding, parts["train"], register
            )

        # VAL và TEST - khung chưa từng thấy ở train, và phải đủ hai dòng với hai
        # phong cách khác nhau kể cả khi họ chỉ có một neo.
        for split in ("val", "test"):
            sample = (
                options
                if len(options) <= HELD_OUT_ANCHORS
                else rng.sample(options, HELD_OUT_ANCHORS)
            )
            # Miền ưu tiên phải đủ CẢ BỐN phong cách ở val và test, không chỉ hai:
            # coverage.json đòi vậy, và đó là nhóm trọng tâm của dự án.
            floor = (
                len(REGISTERS)
                if spec.domain in _PRIORITY_DOMAINS
                else _MIN_HELD_OUT_ROWS
            )
            registers = list(REGISTERS)
            rng.shuffle(registers)
            for index in range(max(floor, len(sample))):
                binding = sample[index % len(sample)]
                register = registers[index % len(REGISTERS)]
                attempt(split, query_id, spec, binding, parts[split], register)

    _add_contrast_pairs(splits, emit, frames, catalogue, mentions, bindings, rng)
    _balance_letter_case(splits, emit, frames, catalogue, mentions, bindings, rng)
    _add_distractions(
        splits, emit, frames, catalogue, mentions, bindings, rng, templates
    )
    checklist: dict[str, list[str]] = {}
    _add_rejections(
        splits, emit, graph, frames, catalogue, mentions, ambiguous, bindings, rng,
        templates, checklist,
        incomplete_specifications(graph, catalogue, bindings),
    )
    return splits, checklist


def _add_contrast_pairs(
    splits: dict[str, list[Row]],
    emit,
    frames: Mapping[str, tuple[Frame, ...]],
    catalogue: Mapping[str, QuerySpec],
    mentions: Mapping[str, tuple[str, ...]],
    bindings: Mapping[str, list[dict[str, str]]],
    rng: random.Random,
) -> None:
    """Dạy hai ý định hay bị nhầm lẫn TRÊN CÙNG một thực thể.

    Lượt huấn luyện đầu tiên cho thấy 75% lỗi là chọn sai quan hệ, và ma trận
    nhầm lẫn chỉ ra vài cặp cụ thể - có cặp nhầm cả hai chiều. Bơm dữ liệu đại
    trà không chạm tới chuyện đó: cái thiếu không phải số lượng mà là **sự đối
    chiếu**. Hai câu chỉ khác nhau ở ý định, cùng một thực thể, mới dạy được
    ranh giới.

    Chỉ thêm dòng vào train: val/test phải giữ nguyên để số đo còn so được.
    """

    for left, right in CONTRAST_PAIRS:
        if left not in frames or right not in frames:
            continue
        shared = {
            binding["anchor"]
            for binding in bindings.get(left, [])
            if "anchor" in binding
        } & {
            binding["anchor"]
            for binding in bindings.get(right, [])
            if "anchor" in binding
        }
        if not shared:
            continue
        anchors = sorted(shared)
        for index in range(_CONTRAST_ROWS):
            anchor = anchors[index % len(anchors)]
            register = REGISTERS[index % len(REGISTERS)]
            for query_id in (left, right):
                spec = catalogue[query_id]
                binding = {"anchor": anchor}
                parts = split_frames(frames[query_id])["train"]
                for _ in range(6):
                    question = _question(
                        rng.choice(parts), binding, mentions, spec, register, rng
                    )
                    if emit(
                        "train",
                        query_id,
                        register,
                        question,
                        _fill_targets(spec, binding),
                    ):
                        break


def _balance_letter_case(
    splits: dict[str, list[Row]],
    emit,
    frames: Mapping[str, tuple[Frame, ...]],
    catalogue: Mapping[str, QuerySpec],
    mentions: Mapping[str, tuple[str, ...]],
    bindings: Mapping[str, list[dict[str, str]]],
    rng: random.Random,
) -> None:
    """Mọi tên viết hoa phải từng xuất hiện ở dạng chữ thường ít nhất một lần.

    Trục hoa/thường trong ``compose`` là xác suất theo phong cách, và xác suất
    không bảo đảm được gì cho những thực thể chỉ có vài dòng: một cái tên xuất
    hiện bốn lần mà lần nào cũng rơi vào giọng trang trọng thì model không bao
    giờ thấy nó viết thường - đúng dạng người dùng thật gõ vào ô chat.

    Lượt này quét nốt phần đuôi đó. Nó chỉ THÊM dòng, không sửa dòng nào.
    """

    # Kho phải giữ NGUYÊN dạng chữ: hạ thường cả kho thì mọi lần xuất hiện viết
    # hoa cũng khớp, và lượt này không bao giờ chạy.
    seen = "\n".join(row.input for row in splits["train"])
    # Chỉ hai phong cách này dùng được: ``formal`` viết hoa lại chữ đầu câu nên
    # phá đúng thứ ta đang sửa, còn ``noisy`` bỏ dấu nên không để lại dạng chữ
    # thường đọc được. Xoay vòng hai cái còn lại để không lệch phân bố phong cách.
    usable = ("neutral", "colloquial")
    emitted = 0
    for query_id in sorted(frames):
        spec = catalogue[query_id]
        if set(spec.slots) != {"anchor"} or not bindings.get(query_id):
            continue
        parts = split_frames(frames[query_id])["train"]
        for binding in bindings[query_id]:
            for text in mentions.get(binding["anchor"][1:], ()):
                lowered = text.casefold()
                if text == lowered or lowered in seen:
                    continue
                register = usable[emitted % len(usable)]
                for frame in parts:
                    question = decorate(
                        rng.choice(question_variants(frame.fill({"anchor": lowered}))),
                        register,
                        rng,
                    )
                    if emit(
                        "train",
                        query_id,
                        register,
                        question,
                        _fill_targets(spec, binding),
                    ):
                        seen += "\n" + question
                        emitted += 1
                        break


def _add_distractions(
    splits: dict[str, list[Row]],
    emit,
    frames: Mapping[str, tuple[Frame, ...]],
    catalogue: Mapping[str, QuerySpec],
    mentions: Mapping[str, tuple[str, ...]],
    bindings: Mapping[str, list[dict[str, str]]],
    rng: random.Random,
    templates: Mapping[str, tuple[str, ...]],
) -> None:
    """Câu hỏi trả lời được, kèm một vế ngoài lề - vẫn phải TRẢ LỜI.

    Bản trước xếp những câu này vào nhóm từ chối, tức là dạy một luật khá mạnh:
    hễ có vế thừa thì im lặng. Người dùng thật viết *"đăng ký học phần thế nào
    ạ, em cảm ơn nhiều"* rơi đúng vào cái bẫy đó.

    Đích ở đây là đích THẬT của phần hỏi được, nên câu vừa dạy model bỏ qua nhiễu
    vừa không mất một dòng ngân sách nào cho việc dạy im lặng.
    """

    tails = templates.get("distraction", ())
    anchored = [query_id for query_id in sorted(frames) if bindings.get(query_id)]
    if not anchored or not tails:
        return

    for split in ("train", "val", "test"):
        options = _split_templates(tails, split)
        if not options:
            continue
        quota = max(len(REGISTERS), int(len(splits[split]) * _DISTRACTION_SHARE))
        produced = 0
        for _ in range(quota * 20):
            if produced >= quota:
                break
            query_id = rng.choice(anchored)
            spec = catalogue[query_id]
            parts = split_frames(frames[query_id])[split]
            binding = rng.choice(bindings[query_id])
            register = rng.choice(REGISTERS)
            core = _question_core(
                rng.choice(parts), binding, mentions, spec, register, rng
            )
            question = decorate(core + rng.choice(options), register, rng)
            produced += emit(
                split, query_id, register, question, _fill_targets(spec, binding)
            )


def _add_rejections(
    splits: dict[str, list[Row]],
    emit,
    graph: Graph,
    frames: Mapping[str, tuple[Frame, ...]],
    catalogue: Mapping[str, QuerySpec],
    mentions: Mapping[str, tuple[str, ...]],
    ambiguous: Mapping[str, tuple[str, ...]],
    bindings: Mapping[str, list[dict[str, str]]],
    rng: random.Random,
    templates: Mapping[str, tuple[str, ...]],
    checklist: dict[str, list[str]],
    incomplete: Mapping[str, list[tuple[str, str]]],
) -> None:
    """Câu từ chối, đủ các nhóm mà ``coverage.json`` đòi, mỗi nhóm đủ bốn phong cách.

    Hai nhóm sinh thẳng từ đồ thị nên không phải bịa:

    * ``ambiguous`` - cách gọi trỏ tới nhiều thứ KHÁC NHAU ("Điều 1" có ở cả ba
      tài liệu với nội dung khác hẳn nhau);
    * ``near-domain-missing`` - hỏi một khía cạnh mà ontology không ghi cho thực
      thể đó (thời hạn của một thủ tục không có thời hạn).

    Cả hai đều là ca "gần miền" - nhóm bản v0.4.1 yếu nhất (92,22%, dưới ngưỡng
    94%) - và sinh từ đồ thị thật thì bảo đảm chúng thực sự không trả lời được.

    Tờ đơn và mục tải của chính nó KHÔNG thuộc nhóm này: chúng là một thứ ngoài
    đời bị mô hình hai lần, và coi chúng là mơ hồ đã dạy chatbot từ chối đúng câu
    hỏi tự nhiên nhất về biểu mẫu.
    """

    anchored = [
        query_id
        for query_id in sorted(frames)
        if "anchor" in catalogue[query_id].slots and bindings.get(query_id)
    ]
    if not anchored:
        return

    # Mọi mẫu hard-negative ngầm định chỗ trống là một THỦ TỤC: "{X} nộp ở đâu",
    # "học bổng cho người làm {X}", "{X} thi vào ngày nào". Bốc thực thể bừa thì
    # 80% số dòng ra câu vô nghĩa - "học bổng cho người làm Quyết định 1052".
    # Câu vô nghĩa vẫn dạy từ chối, nhưng dạy model nhận ra sự vô nghĩa chứ
    # không dạy được ranh giới thật.
    #
    # Lọc theo LỚP trong đồ thị, không theo miền của họ truy vấn: miền
    # ``procedure`` gồm cả trường hợp học vụ ("nhập ngũ", "lý do cá nhân"), và
    # "lý do cá nhân năm nay điểm chuẩn bao nhiêu" cũng vô nghĩa y như vậy.
    procedures = {
        f":{str(node).rsplit('#', 1)[-1]}"
        for node in graph.subjects(RDF.type, URIRef(ONTOLOGY_NS + "AcademicProcedure"))
    }
    procedural = [
        (query_id, binding)
        for query_id in anchored
        for binding in bindings[query_id]
        if binding.get("anchor") in procedures
    ]

    def anchor_text(register: str) -> str | None:
        if not procedural:
            return None
        local = rng.choice(procedural)[1]["anchor"][1:]
        return (
            choose_mention(mentions[local], register, rng)
            if local in mentions
            else None
        )

    def build(kind: str, register: str, split: str) -> str | None:
        """Mẫu câu cũng phải CHIA THEO TẬP, y như khung ý định.

        Dùng chung mẫu giữa các tập sinh ra câu gần trùng, và validator bắt đúng
        chỗ đó ở ngưỡng 0,84 - "chào bạn nhỉ?" ở train với "chào bạn ta?" ở test
        không phải hai câu khác nhau.
        """

        if kind == "ambiguous":
            if not ambiguous:
                return None
            # Khung phải là khung của một họ NHẬN được chính thực thể đó, nếu
            # không ta hỏi thời hạn của một điều luật và câu vô nghĩa vì sai
            # loại chứ không vì mơ hồ - hai lý do từ chối rất khác nhau.
            text = rng.choice(sorted(ambiguous))
            owners = {f":{name}" for name in ambiguous[text]}
            fitting = [
                query_id
                for query_id in anchored
                if owners & {
                    binding["anchor"]
                    for binding in bindings[query_id]
                    if "anchor" in binding
                }
            ]
            if not fitting:
                return None
            frame = rng.choice(split_frames(frames[rng.choice(fitting)])[split])
            return decorate(frame.fill({"anchor": text}), register, rng)
        if kind == "incomplete-request":
            # Mẫu mang đúng MỘT chỗ trống, tên trùng tên slot. Ghép nó với những
            # giá trị đã ĐO ĐƯỢC là gây nhiều đáp án - xem
            # ``incomplete_specifications``. Không đo được thì không sinh, thà
            # thiếu câu từ chối còn hơn dạy từ chối một câu trả lời được.
            options = _split_templates(templates.get(kind, ()), split)
            if not options:
                return None
            text = rng.choice(options)
            slot_names = {
                name for name in _SLOT_PLACEHOLDER.findall(text)
            }
            if len(slot_names) != 1:
                return None
            name = slot_names.pop()
            choices = [
                (query_id, value)
                for query_id, items in sorted(incomplete.items())
                for slot, value in items
                if slot == name
            ]
            if not choices:
                return None
            query_id, value = rng.choice(choices)
            slot = catalogue[query_id].slots[name]
            filled = (
                choose_mention(mentions[value[1:]], register, rng)
                if slot.kind == "iri"
                else value
            )
            return decorate(text.replace("{" + name + "}", filled), register, rng)
        if kind == "near-domain-missing":
            query_id = rng.choice(anchored)
            text = _outsider_mention(
                query_id, catalogue, bindings, mentions, register, rng
            )
            if text is None:
                return None
            frame = rng.choice(split_frames(frames[query_id])[split])
            return decorate(frame.fill({"anchor": text}), register, rng)
        options = _split_templates(templates.get(kind, ()), split)
        if not options:
            return None
        text = rng.choice(options)
        if "{anchor}" in text:
            mention = anchor_text(register)
            if mention is None:
                return None
            text = text.replace("{anchor}", mention)
        return decorate(text, register, rng)

    def outcome(kind: str) -> tuple[str, str]:
        """Đích của một câu từ chối - xem ghi chú đầu tệp về ngoại lệ chào hỏi."""

        if kind in _CAPABILITY_KINDS and CAPABILITY_FAMILY in catalogue:
            return CAPABILITY_FAMILY, catalogue[CAPABILITY_FAMILY].target_template
        return "no-information", MARKER

    kinds = ("greeting-social", "unrelated", "near-domain-missing", "ambiguous",
             "noisy-out-of-domain", "hard-negative", "adjacent-domain",
             "incomplete-request")
    for split in ("train", "val", "test"):
        quota = max(
            len(kinds) * len(REGISTERS),
            int(len(splits[split]) * _REJECTION_SHARE),
        )
        produced = 0
        # Lượt một: bảo đảm mọi (nhóm, phong cách) đều có mặt - đây là ràng buộc
        # cứng của coverage.json, không phải chỉ tiêu mềm.
        for kind in kinds:
            for register in REGISTERS:
                for _ in range(40):
                    question = build(kind, register, split)
                    if question is None:
                        continue
                    before = len(splits[split])
                    family, target = outcome(kind)
                    emit(split, family, register, question, target)
                    if len(splits[split]) > before:
                        checklist.setdefault(kind, []).append(splits[split][-1].id)
                        produced += 1
                        break
        # Lượt hai: bơm cho đủ tỷ lệ.
        for _ in range(quota * 12):
            if produced >= quota:
                break
            kind = rng.choice(kinds)
            register = rng.choice(REGISTERS)
            question = build(kind, register, split)
            if question is None:
                continue
            before = len(splits[split])
            family, target = outcome(kind)
            emit(split, family, register, question, target)
            if len(splits[split]) > before:
                checklist.setdefault(kind, []).append(splits[split][-1].id)
                produced += 1


def _split_templates(options: tuple[str, ...], split: str) -> tuple[str, ...]:
    """Cắt danh sách mẫu câu theo tập, cùng nguyên tắc với khung ý định."""

    held = HELD_OUT_FRAMES
    if len(options) < 2 * held + 2:
        held = 1
    if len(options) < 3:
        return options
    return {
        "train": options[: -2 * held],
        "val": options[-2 * held : -held],
        "test": options[-held:],
    }[split]


def _outsider_mention(
    query_id: str,
    catalogue: Mapping[str, QuerySpec],
    bindings: Mapping[str, list[dict[str, str]]],
    mentions: Mapping[str, tuple[str, ...]],
    register: str,
    rng: random.Random,
) -> str | None:
    """Một thực thể CÙNG MIỀN nhưng nằm ngoài danh sách neo của họ này.

    Ví dụ hỏi thời hạn của một thủ tục mà ontology không ghi thời hạn: câu nghe
    hoàn toàn hợp lý, và đó chính là điều làm nó thành ca từ chối khó.
    """

    spec = catalogue[query_id]
    allowed = {binding["anchor"] for binding in bindings.get(query_id, [])}
    pool = [
        binding["anchor"]
        for other, options in bindings.items()
        if catalogue[other].domain == spec.domain
        for binding in options
        if "anchor" in binding and binding["anchor"] not in allowed
    ]
    if not pool:
        return None
    local = rng.choice(pool)[1:]
    if local not in mentions:
        return None
    return choose_mention(mentions[local], register, rng)


def write_splits(splits: Mapping[str, list[Row]], directory: Path) -> None:
    for name, rows in splits.items():
        path = Path(directory) / f"{name}.jsonl"
        path.write_text(
            "".join(
                json.dumps(row.as_json(), ensure_ascii=False) + "\n" for row in rows
            ),
            encoding="utf-8",
        )


def build_bindings(
    catalogue: Mapping[str, QuerySpec],
    frames: Mapping[str, tuple[Frame, ...]],
    numeric_cases: list[dict],
    article_numbers: tuple[str, ...],
    clause_numbers: tuple[tuple[str, str], ...],
) -> dict[str, list[dict[str, str]]]:
    """Mọi bộ giá trị slot hợp lệ của từng họ.

    Slot IRI lấy thẳng danh sách đã khai trong danh mục - **không bao giờ** lấy
    neo ngoài danh sách đó, vì truy vấn sinh ra sẽ rỗng và ta lại dạy model một
    liên kết không có thật. Slot số lấy từ ``coverage.json``, riêng số hiệu điều
    và khoản suy thẳng từ ontology.
    """

    by_query: dict[str, list[dict[str, str]]] = {}
    cases: dict[str, list[dict[str, str]]] = {}
    for case in numeric_cases:
        cases.setdefault(case["query_id"], []).append(case["slots"])

    for query_id in frames:
        spec = catalogue[query_id]
        names = sorted(spec.slots)
        if not names:
            by_query[query_id] = [{}]
            continue
        if query_id == "article-with-source":
            by_query[query_id] = [{"article": number} for number in article_numbers]
            continue
        if query_id == "clause-with-source":
            by_query[query_id] = [
                {"article": article, "clause": clause}
                for article, clause in clause_numbers
            ]
            continue
        numbers = [name for name in names if spec.slots[name].kind == "number"]
        if numbers:
            # Slot số có miền vô hạn nên giá trị phải do người chốt, không sinh
            # bừa: mỗi ca trong coverage.json là một mốc ngưỡng có chủ đích.
            #
            # Nhưng slot IRI đi kèm thì PHẢI phủ hết: họ học phí khai 41 ngành,
            # mà coverage.json chỉ nêu 6 ca mẫu. Nhân chéo mốc ngưỡng với toàn bộ
            # danh sách IRI; tổ hợp nào không trả về dòng nào sẽ bị
            # ``executable_bindings`` loại sau.
            marks = [
                {name: slots[name] for name in numbers}
                for slots in cases.get(query_id, [])
                if all(name in slots for name in numbers)
            ]
            iris = [name for name in names if name not in numbers]
            by_query[query_id] = [
                {**mark, **dict(zip(iris, combination, strict=True))}
                for mark in marks
                for combination in product(*(spec.slots[name].values for name in iris))
            ]
            continue
        # Slot IRI không phải lúc nào cũng tên "anchor" - còn "rule", "certificate",
        # "program". Nhân chéo các danh sách đã khai; không họ nào có quá một slot
        # IRI nên tích không nổ.
        by_query[query_id] = [
            dict(zip(names, combination, strict=True))
            for combination in product(*(spec.slots[name].values for name in names))
        ]
    return by_query
