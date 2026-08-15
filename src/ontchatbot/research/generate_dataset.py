"""Sinh dataset từ ontology, danh mục truy vấn và khung câu hỏi.

Chiều đi một chiều, không được đảo: ontology quyết định trả lời được gì, danh mục
quyết định hình dạng truy vấn, khung quyết định cách hỏi. Câu hỏi được **ghép**
chứ không viết tay từng câu, và đích được **bung ra từ ``target_template``** chứ
không gõ lại: một dấu lệch trong truy vấn viết tay làm hỏng cả loạt dòng.

Bốn ràng buộc thiết kế:

1. **Chia tập theo KHUNG, không theo dòng.** Sinh tổ hợp rồi chia ngẫu nhiên thì
   test chỉ là hoán vị của train. Val/test dùng khung mà train chưa từng thấy.
2. **Cặp tương phản tối thiểu.** Mỗi neo xuất hiện với MỌI ý định hợp lệ của nó,
   nên ranh giới giữa các ý định được dạy tường minh. Chế độ lỗi nó chống lại là
   nhận đúng thực thể nhưng chọn sai quan hệ.
3. **Trọng số theo miền.** Quy trình học vụ là trọng tâm dự án nhưng chỉ chiếm 14%
   không gian đích; không cân lại thì model dồn năng lực vào tra cứu điều khoản.
4. **Câu từ chối sinh từ đồ thị thật**, không bịa: cách gọi mơ hồ và ghép sai neo.
"""

from __future__ import annotations

import hashlib
import json
import random
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from itertools import product
from pathlib import Path
from typing import Mapping

from rdflib import RDF, Graph, URIRef

from ..catalogue import QuerySpec
from ..settings import ONTOLOGY_NS
from ..runtime.sparql import SparqlError, execute_select
from ..runtime.text import normalize_model_input
from .compose import Frame, REGISTERS, choose_mention, decorate, question_variants
from .coverage import assess_name_coverage, require_complete_coverage
from .dataset import NEAR_DUPLICATE_THRESHOLD, _character_trigrams

MARKER = "không có thông tin"

#: Họ dump trọn node của thủ tục học vụ. Kho neo của câu từ chối lấy từ đây, và
#: cũng chính truy vấn này quyết định câu từ chối có bị gán oan hay không.
PROCEDURE_FAMILY = "academic-procedure-facts"

# CÔNG CỤ NÀY CHỈ CÓ HAI VIỆC: truy ra dữ kiện đã có, hoặc nói không có thông
# tin. Không có việc thứ ba.
#
# Vì vậy MỌI câu từ chối đều trả ``MARKER``, và **họ "liệt kê năng lực" đã bị bỏ
# hẳn** (2026-08-14, người dùng chốt). Nay không còn ngoại lệ nào cả.
#
# Đường đi của quyết định này, ghi lại kẻo có người khôi phục:
#
# * Ban đầu nhóm ``greeting-social`` được trả về họ liệt kê thủ tục, lý do: câu
#   chào là thứ đầu tiên ai cũng gõ, từ chối ngay thì người ta đóng app.
# * 2026-08-12 bỏ ngoại lệ đó cho câu chào, vì "bạn tên là gì" và "cảm ơn nhiều
#   nhé" đều trả về 24 thủ tục - người dùng chỉ thẳng đây là sai.
# * 2026-08-14 bỏ nốt CẢ HỌ. Câu hỏi năng lực thật ("bạn có thể hỗ trợ thông tin
#   gì") cũng không phải việc của công cụ: giới thiệu phạm vi là việc của LLM
#   lớn, nó biết mình gắn công cụ nào.
#
# Lý do kỹ thuật củng cố thêm: ``MARKER`` dài 4 token và là hằng số, model chỉ
# cần nhớ một chuỗi. Truy vấn năng lực dài ~30 token và phải sinh đúng từng ký
# tự cho những câu vào chẳng liên quan gì nhau. Chế độ lỗi cũng tệ hơn: thay vì
# im lặng an toàn, model đẻ ra truy vấn trông hợp lý với thực thể BỊA
# (":GradalReviewProcedure" cho câu "đi Đà Lạt mấy tiếng"), và một câu như vậy
# đã lọt qua cả bốn cửa runtime.
#
# CÒN BỎ NGỎ: công cụ nên phân biệt "đây là câu xã giao" với "tôi không tìm ra
# gì" - hai tín hiệu khác nhau đối với LLM lớn. Hiện cả hai cùng rơi vào
# ``no-information``. Để lại cho lượt thêm vỏ bọc đầu ra.

#: Dấu hiệu cho thấy KẾT QUẢ DUMP đã trả lời câu mà khuôn từ chối hỏi.
#:
#: Mọi họ ``*-facts`` đều lấy TRỌN node, nên nếu dữ kiện được hỏi nằm trong kết
#: quả dump thì nhãn ``no-information`` là sai, và thước đo quay ra trừ điểm
#: chính hành vi đúng. Khuôn khai ở đây chỉ được ghép với neo mà kết quả dump
#: KHÔNG chứa dấu hiệu tương ứng.
#:
#: ĐỌC KỸ CHỖ NÀY - ĐÂY LÀ HAI THỨ RẤT DỄ LẪN:
#:
#: * Cụm từ dưới đây dò trong **CÂU TRẢ LỜI** (kết quả dump của từng neo), không
#:   dò trong câu hỏi. Nó đọc dữ liệu thật, và đổi theo ontology: sửa một bước
#:   trong ``hasStep`` là kết luận đổi theo, không ai phải nhớ sửa danh sách.
#: * Bản hỏng trước dò cụm từ trong **CÂU HỎI** bằng 16 cụm viết cứng, và để lọt
#:   24 câu từ chối oan. Đừng quay lại kiểu đó.
#:
#: VÌ SAO KHÔNG CANH BẰNG "NODE CÓ THUỘC TÍNH X": đã thử và KHÔNG ĐỦ. Dữ kiện
#: hay nằm trong chữ tự do của ``stepText`` chứ không thành thuộc tính riêng -
#: mức phí 5.500đ của thủ tục nộp học phí và người ký của thủ tục xét tốt nghiệp
#: đều nằm trong nội dung bước. Canh theo thuộc tính bỏ lọt đúng những ca đó.
#:
#: THÀ LỌC RỘNG CÒN HƠN LỌC HỤT. Lọc rộng chỉ mất vài câu từ chối hợp lệ; lọc
#: hụt là dạy model từ chối câu trả lời được, và đó là bệnh đang chữa. Cùng
#: nguyên tắc đã ghi ở nhóm ``incomplete-request``.
#: ĐỪNG khai nhãn của ObjectProperty ở đây - nó KHÔNG BAO GIỜ xuất hiện trong
#: kết quả. Khuôn dump lọc ``isLiteral(?giatri)``, mà ``decidedBy`` trỏ tới node
#: ``:UniversityPresident`` chứ không phải chuỗi chữ, nên nhãn "do ai quyết định"
#: rơi mất; dữ kiện chỉ tới được qua NHÁNH NHẢY MỘT BƯỚC và hiện ra dưới dạng
#: ``tên gọi => Hiệu trưởng``. Vì vậy phải bắt bằng chính giá trị đó.
#:
#: Đây cũng là lý do cách canh này chặt hơn cách canh theo thuộc tính: cụm
#: "hiệu trưởng" bắt được 11 neo, trong khi ``decidedBy`` chỉ có ở 9 - hai neo
#: kia nhắc người ký trong nội dung bước mà không có thuộc tính riêng.
#: ``test_declared_answer_marks_still_appear_in_some_dump`` canh cho không cụm
#: nào ở đây mục ruỗng thành vô dụng.
_SIGNER = ("ký quyết định", "hiệu trưởng")
_FEE = ("miễn phí", "chịu phí", "đồng mỗi lần", "phí 5.500")
_DURATION = ("nội dung thời hạn", "trong thời hạn", "trong vòng")
ANSWERED_BY: Mapping[str, tuple[str, ...]] = {
    # Người ký. KHÔNG chặn theo ``reviewedBy``: "được xét bởi" là hội đồng thẩm
    # định, không phải người ký quyết định - hai vai trò khác nhau trong chính
    # ontology. Neo nào mà bước của nó có nhắc tới việc ký thì cụm ở trên bắt
    # được, không cần mượn ``reviewedBy`` làm proxy.
    "{anchor} do ai ký duyệt": _SIGNER,
    "ai ký quyết định cho {anchor}": _SIGNER,
    "ai là người ký duyệt {anchor} năm nay": _SIGNER,
    # Phí. Thủ tục nộp học phí ghi thẳng "miễn phí ... chịu phí 5.500 đồng mỗi
    # lần" trong nội dung bước.
    "{anchor} có mất phí không": _FEE,
    "{anchor} tốn bao nhiêu tiền": _FEE,
    "lệ phí làm {anchor} là bao nhiêu": _FEE,
    "{anchor} phải đóng thêm khoản nào không": _FEE,
    # Người phụ trách. Đa số thủ tục nộp cho phòng/khoa, nhưng thủ tục nghỉ ốm
    # nộp thẳng cho "Giảng viên giảng dạy học phần".
    "giảng viên nào phụ trách {anchor}": ("giảng viên",),
    # Thời gian xử lý. Cố ý lấy rộng: "trong thời hạn 03 tháng" của thủ tục xét
    # tốt nghiệp là thời gian xử lý thật, còn "nộp đơn trong vòng 01 tuần" thì
    # chỉ là hạn nộp - lọc rộng gạt cả hai, và đó là phía an toàn.
    "{anchor} mất bao nhiêu ngày mới được duyệt": _DURATION,
    "làm {anchor} mất bao lâu mới xong": _DURATION,
}


def dump_literals(
    graph: Graph, catalogue: Mapping[str, QuerySpec], family: str
) -> dict[str, str]:
    """Chạy truy vấn dump THẬT cho mọi neo của ``family``, gộp chữ trả về.

    Một truy vấn cho mỗi neo, không phải cho mỗi cặp (khuôn, neo): câu dump chỉ
    phụ thuộc neo. 24 lượt truy vấn, đủ rẻ để chạy trong cả bộ sinh lẫn bộ kiểm.
    """

    spec = catalogue[family]
    slot = spec.slots["anchor"]
    values: dict[str, str] = {}
    for value in slot.values:
        query = spec.target_template.replace("${anchor}", value)
        rows = execute_select(graph, query)
        values[value[1:]] = " · ".join(
            str(cell) for row in rows for cell in row.values() if cell is not None
        ).casefold()
    return values


def answered_in_dump(dumped: str, template: str) -> bool:
    """Kết quả dump ``dumped`` có chứa dữ kiện mà ``template`` hỏi không?

    Khuôn không khai trong :data:`ANSWERED_BY` thì luôn trả ``False`` - nó hỏi
    thứ ontology không mô hình hoá, nên neo nào cũng hợp lệ.
    """

    return any(mark in dumped for mark in ANSWERED_BY.get(template, ()))


#: Số dòng train sinh cho mỗi target, theo miền.
#:
#: Quy trình học vụ là trọng tâm dự án. Cân bằng bằng SỐ CÂU chứ không bằng cách
#: cắt bớt khả năng trả lời: tra cứu điều khoản vẫn phủ đủ, chỉ ít câu hơn.
DOMAIN_WEIGHT = {
    # Một lượt dương thêm cho mỗi neo thủ tục trải đều các băng độ dài, nhất là
    # 10-13 từ, để bậc này không chỉ học tín hiệu từ chối.
    "procedure": 14,
    # Biểu mẫu là một trong bốn việc người dùng nêu, mà chỉ chiếm 6,7% dataset.
    "form": 13,
    "certificate": 1,
    "tuition": 1,
    "academic-rule": 1,
    "document": 1,
}
DEFAULT_WEIGHT = 1

#: Trần số dòng theo số cặp tên/neo của mỗi họ. Trọng số miền trước đây không
#: có tác dụng ở ``procedure`` và ``form`` vì trần chung 2 lần chặn lại trước.
#: Hai miền trọng tâm được phép lặp nhiều cách hỏi hơn; các miền còn lại dừng
#: ngay ở sàn cặp tên/neo để điều khoản/văn bản không tiếp tục lấn át.
DOMAIN_ROW_CAP_MULTIPLIER = {
    "procedure": 7,
    "form": 7,
}
DEFAULT_ROW_CAP_MULTIPLIER = 1

#: Số neo lấy mẫu cho val và test ở mỗi họ. Val/test đo cách hỏi mới, không đo
#: khả năng nhớ thêm thực thể, nên không cần phủ hết neo.
#: Tập chấm phải chiếm đủ tỷ lệ sau khi quota train được cân lại. 32 neo giữ
#: val/test trên 8,3% tổng thay vì để tập chấm bị loãng khi số ví dụ train đổi;
#: đây là lượng mẫu theo mỗi họ, không phải chỉ tiêu tổng chốt cứng.
HELD_OUT_ANCHORS = 32
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
#: phổ biến nhất; và bốn việc người dùng nêu là làm được gì / quy trình / biểu
#: mẫu / nguồn.
#:
#: Họ ``assistant-capabilities`` từng đứng đầu bảng này với trọng số 40, vì câu
#: "bạn hỗ trợ được gì" gần như ai cũng hỏi. Đã BỎ cùng cả họ ngày 2026-08-14:
#: giới thiệu phạm vi trả lời là việc của LLM lớn, không phải của công cụ.
FAMILY_WEIGHT = {
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
_CONTRAST_ROWS = 8

#: Thực thể được hỏi nhiều hơn hẳn phần còn lại, theo người dùng.
PRIORITY_ANCHORS = frozenset({":TuitionPaymentProcedure"})
#: Xác suất lượt bơm thêm chọn đúng một thực thể ưu tiên, khi họ đó có.
_PRIORITY_ANCHOR_SHARE = 0.35
#: Miền trọng tâm của dự án; coverage.json đòi đủ bốn phong cách ở mọi tập.
_PRIORITY_DOMAINS = frozenset({"procedure"})

#: Tỷ lệ câu từ chối trên mỗi tập.
#: 16,8% giữ tín hiệu ``no-information`` trong dải phát hành 14--16%. Ngân sách
#: dòng đã được người dùng nâng sau khi ontology có thêm Quyết định 626; các
#: câu dương băng 7--9 được bơm riêng bên dưới để tỷ lệ này không làm dốc theo
#: độ dài trở lại.
_REJECTION_SHARE = 0.168
#: Tỷ lệ câu hỏi trả lời được nhưng có kèm một vế ngoài lề.
#:
#: Đây KHÔNG phải câu từ chối. Bản trước dạy "có vế ngoài lề thì từ chối tất",
#: nghĩa là người dùng viết *"đăng ký học phần thế nào ạ, em cảm ơn"* cũng có
#: nguy cơ bị im lặng. Giờ dạy ngược lại: bỏ qua vế thừa, trả lời phần hỏi thật.
_DISTRACTION_SHARE = 0.014


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


@dataclass(frozen=True)
class BindingFilterResult:
    """Binding còn dùng được và số binding bị từng hàng rào loại."""

    bindings: dict[str, list[dict[str, str]]]
    rejected_out_of_range: int
    rejected_non_executable: int


@dataclass(frozen=True)
class _NumericFamily:
    """Cách đọc một miền số có cấu trúc từ ontology."""

    number_slot: str
    anchor_class: str
    context: tuple[tuple[str, str], ...]
    minimum: str
    maximum: str


@dataclass(frozen=True)
class NumericAnchor:
    """Một neo/tổ hợp thật cùng khoảng số và mốc đại diện nhỏ gọn của nó."""

    query_id: str
    identity: str
    number_slot: str
    context: tuple[tuple[str, str], ...]
    minimum: Decimal | None
    minimum_inclusive: bool
    maximum: Decimal | None
    maximum_inclusive: bool
    representative: Decimal

    def contains(self, binding: Mapping[str, str]) -> bool:
        if any(binding.get(slot) != value for slot, value in self.context):
            return False
        try:
            number = Decimal(binding[self.number_slot])
        except (KeyError, InvalidOperation):
            return False
        if self.minimum is not None and (
            number < self.minimum
            or (number == self.minimum and not self.minimum_inclusive)
        ):
            return False
        return self.maximum is None or number < self.maximum or (
            number == self.maximum and self.maximum_inclusive
        )


# Chỉ bốn họ này có ô số mang nghĩa một miền. Số điều/khoản là định danh và đi
# nhánh riêng. Mỗi cấu hình chỉ nêu thuộc tính RDF có cấu trúc; tuyệt đối không
# đọc số từ ``criterionText``.
_NUMERIC_FAMILIES = {
    "academic-performance-band-by-score": _NumericFamily(
        number_slot="diem",
        anchor_class="AcademicPerformanceBand",
        context=(),
        minimum="minimumValue",
        maximum="maximumValue",
    ),
    "graduation-band-by-score": _NumericFamily(
        number_slot="diem",
        anchor_class="GraduationClassificationBand",
        context=(),
        minimum="minimumValue",
        maximum="maximumValue",
    ),
    "study-year-band-by-credits": _NumericFamily(
        number_slot="tinchi",
        anchor_class="StudyYearBand",
        context=(),
        minimum="minimumValue",
        maximum="maximumValue",
    ),
    "language-course-type-by-cohort": _NumericFamily(
        number_slot="khoa",
        anchor_class="LanguageCourseClassification",
        context=(("hocphan", "appliesToLanguageCourse"),),
        minimum="minimumCohortNumber",
        maximum="maximumCohortNumber",
    ),
}


#: Số khung giữ lại cho mỗi tập đánh giá.
#:
#: Số khung GIẤU cho mỗi bên (val và test): mỗi họ 10 khung, **dạy 8 - chỉnh 1 -
#: chấm 1**, tức giấu 20%.
#:
#: Giấu quá nửa thì tập chấm chỉ còn toàn lối nói model chưa từng thấy, và điểm
#: số đo cách hỏi lạ chứ không đo năng lực. Một khung mỗi bên nghe mỏng khi đọc
#: từng họ, nhưng cộng lại vẫn là mỗi bên một khung chưa từng thấy cho mọi họ.
#: Khung giấu phải chọn theo thứ tự băm ổn định, không lấy khung dị nhất.
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


def name_teaching_cases(
    spec: QuerySpec,
    bindings: list[dict[str, str]],
    mentions: Mapping[str, tuple[str, ...]],
) -> list[tuple[dict[str, str], str, str]]:
    """Liệt kê ổn định mọi ``(binding, slot IRI, tên gọi)`` cần dạy.

    Hàm không nhận RNG: seed chỉ được phép đổi cách trang trí các dòng, không
    được đổi tập cặp ``(node, nhãn)`` bắt buộc.
    """

    return [
        (binding, slot_name, label)
        for binding in bindings
        for slot_name in sorted(binding)
        if spec.slots[slot_name].kind == "iri"
        for label in mentions[binding[slot_name][1:]]
    ]


def _question_core(
    frame: Frame,
    binding: Mapping[str, str],
    mentions: Mapping[str, tuple[str, ...]],
    spec: QuerySpec,
    register: str,
    rng: random.Random,
    *,
    variants: bool = True,
    mention_overrides: Mapping[str, str] | None = None,
) -> str:
    """Câu hỏi đã ghép xong nhưng CHƯA khoác phong cách.

    Tách riêng để còn gắn được vế ngoài lề vào giữa: đuôi nhiễu phải nằm trước
    dấu kết câu, không phải sau nó.
    """

    values: dict[str, str] = {}
    for name, value in binding.items():
        if spec.slots[name].kind == "iri":
            values[name] = (
                mention_overrides[name]
                if mention_overrides is not None and name in mention_overrides
                else choose_mention(mentions[value[1:]], register, rng)
            )
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
    mention_overrides: Mapping[str, str] | None = None,
) -> str:
    """Ghép một câu hỏi hoàn chỉnh từ khung, cách gọi tên và phong cách."""

    core = _question_core(
        frame,
        binding,
        mentions,
        spec,
        register,
        rng,
        variants=variants,
        mention_overrides=mention_overrides,
    )
    return decorate(core, register, rng, short=frame.short)


def executable_bindings(
    graph: Graph,
    catalogue: Mapping[str, QuerySpec],
    bindings: Mapping[str, list[dict[str, str]]],
) -> BindingFilterResult:
    """Bỏ binding ngoài thang hoặc không trả về dòng nào, kèm số bị loại.

    Validator bắt mọi đích trong miền phải lấy ra được dữ liệu. Slot số dù được
    suy từ ontology vẫn phải qua hàng rào độc lập: một ánh xạ thuộc tính sai có
    thể tạo ra dòng dạy model sinh truy vấn rỗng ruột, đúng thứ ràng buộc số 4
    của ``docs/DATASET.md`` cấm.

    Kiểm tra miền số trước khi chạy truy vấn để một thay đổi ở câu SPARQL không
    thể vô tình biến giá trị ngoài thang thành binding hợp lệ.
    """

    kept: dict[str, list[dict[str, str]]] = {}
    rejected_out_of_range = 0
    rejected_non_executable = 0
    anchors = numeric_anchors(graph)
    for query_id, options in bindings.items():
        spec = catalogue[query_id]
        alive = []
        for binding in options:
            if query_id in _NUMERIC_FAMILIES and not any(
                anchor.contains(binding) for anchor in anchors[query_id]
            ):
                rejected_out_of_range += 1
                continue
            try:
                if execute_select(graph, _fill_targets(spec, binding), max_rows=200):
                    alive.append(binding)
                else:
                    rejected_non_executable += 1
            except SparqlError:
                rejected_non_executable += 1
                continue
        kept[query_id] = alive
    return BindingFilterResult(
        bindings=kept,
        rejected_out_of_range=rejected_out_of_range,
        rejected_non_executable=rejected_non_executable,
    )


def _compact_iri(value: URIRef) -> str:
    text = str(value)
    if not text.startswith(ONTOLOGY_NS):
        raise ValueError(f"IRI ngoài namespace ontology: {text}")
    return ":" + text.removeprefix(ONTOLOGY_NS)


def _decimal(graph: Graph, node: URIRef, predicate: str) -> Decimal | None:
    value = next(graph.objects(node, URIRef(ONTOLOGY_NS + predicate)), None)
    return Decimal(str(value)) if value is not None else None


def _inclusive(graph: Graph, node: URIRef, predicate: str) -> bool:
    value = next(graph.objects(node, URIRef(ONTOLOGY_NS + predicate)), None)
    return True if value is None else bool(value.toPython())


def _representative(
    minimum: Decimal | None,
    minimum_inclusive: bool,
    maximum: Decimal | None,
    maximum_inclusive: bool,
) -> Decimal:
    """Chọn đúng một mốc, dịch một đơn vị vào trong nếu cận đang mở."""

    if minimum is not None:
        return minimum if minimum_inclusive else minimum + Decimal(1)
    if maximum is not None:
        return maximum if maximum_inclusive else maximum - Decimal(1)
    raise ValueError("neo số không có cận có cấu trúc")


def numeric_anchors(graph: Graph) -> dict[str, tuple[NumericAnchor, ...]]:
    """Đọc các neo/tổ hợp số thật; không đụng tới ``criterionText``.

    Các dải học lực, tốt nghiệp, năm học và khóa học giữ từng cá thể làm neo.
    Cận mở được dịch vào trong trước khi tạo binding, nên ``> 68`` sinh 69 chứ
    không sinh 68.
    """

    result: dict[str, tuple[NumericAnchor, ...]] = {}
    for query_id, family in _NUMERIC_FAMILIES.items():
        nodes = sorted(
            set(
                graph.subjects(
                    RDF.type, URIRef(ONTOLOGY_NS + family.anchor_class)
                )
            ),
            key=str,
        )
        records: list[
            tuple[
                URIRef,
                tuple[tuple[str, str], ...],
                Decimal | None,
                bool,
                Decimal | None,
                bool,
            ]
        ] = []
        for node in nodes:
            context_options: list[tuple[str, tuple[str, ...]]] = []
            for slot, predicate in family.context:
                values = tuple(
                    sorted(
                        _compact_iri(value)
                        for value in graph.objects(
                            node, URIRef(ONTOLOGY_NS + predicate)
                        )
                        if isinstance(value, URIRef)
                    )
                )
                if not values:
                    break
                context_options.append((slot, values))
            else:
                minimum = _decimal(graph, node, family.minimum)
                maximum = _decimal(graph, node, family.maximum)
                if minimum is None and maximum is None:
                    continue
                for values in product(*(values for _, values in context_options)):
                    records.append(
                        (
                            node,
                            tuple(
                                (slot, value)
                                for (slot, _), value in zip(
                                    context_options, values, strict=True
                                )
                            ),
                            minimum,
                            _inclusive(graph, node, "minimumInclusive"),
                            maximum,
                            _inclusive(graph, node, "maximumInclusive"),
                        )
                    )

        result[query_id] = tuple(
            NumericAnchor(
                query_id=query_id,
                identity=_compact_iri(node),
                number_slot=family.number_slot,
                context=context,
                minimum=minimum,
                minimum_inclusive=minimum_inclusive,
                maximum=maximum,
                maximum_inclusive=maximum_inclusive,
                representative=_representative(
                    minimum,
                    minimum_inclusive,
                    maximum,
                    maximum_inclusive,
                ),
            )
            for (
                node,
                context,
                minimum,
                minimum_inclusive,
                maximum,
                maximum_inclusive,
            ) in records
        )
    return result


def numeric_binding_gaps(
    graph: Graph,
    bindings: Mapping[str, list[dict[str, str]]],
) -> dict[str, tuple[str, ...]]:
    """Neo/tổ hợp số thật chưa được bất kỳ binding nào phủ."""

    return {
        query_id: tuple(
            anchor.identity
            for anchor in anchors
            if not any(
                anchor.contains(binding)
                for binding in bindings.get(query_id, ())
            )
        )
        for query_id, anchors in numeric_anchors(graph).items()
    }


def out_of_range_numeric_bindings(
    graph: Graph,
    bindings: Mapping[str, list[dict[str, str]]],
) -> list[tuple[str, dict[str, str]]]:
    """Binding số không nằm trong bất kỳ thang thật nào của đúng ngữ cảnh."""

    anchors = numeric_anchors(graph)
    return [
        (query_id, binding)
        for query_id, options in bindings.items()
        if query_id in anchors
        for binding in options
        if not any(anchor.contains(binding) for anchor in anchors[query_id])
    ]


def incomplete_specifications(
    graph: Graph,
    catalogue: Mapping[str, QuerySpec],
    bindings: Mapping[str, list[dict[str, str]]],
) -> dict[str, list[tuple[str, str]]]:
    """Giá trị nào mà nêu MỘT MÌNH nó thì câu hỏi còn nhiều đáp án.

    Vài họ đòi hai thông tin mới trả lời được: phân loại học phần ngoại ngữ cần
    cả HỌC PHẦN và KHOÁ. Người hỏi thường chỉ nêu một - *"khóa 68 học ngoại ngữ
    thế nào"* - trong khi một khoá có nhiều học phần. Trả một phân loại sai mà
    nói như đúng rồi là kiểu hỏng tệ nhất.

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

    missing_bindings = sorted(
        query_id
        for query_id, spec in catalogue.items()
        if spec.tier == "primary"
        and spec.domain != "out-of-domain"
        and not bindings.get(query_id)
    )
    if missing_bindings:
        raise ValueError(
            "các họ trong danh mục không thể sinh dataset:\n"
            + "\n".join(
                f"- {query_id}: không sinh được binding"
                for query_id in missing_bindings
            )
        )

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
        grams = _character_trigrams(question)
        if any(
            row.query_id == query_id
            and len(grams & other) / len(grams | other)
            >= NEAR_DUPLICATE_THRESHOLD
            for other_split, rows in splits.items()
            if other_split != split
            for row in rows
            for other in [_character_trigrams(row.input)]
        ):
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
        *,
        mention_overrides: Mapping[str, str] | None = None,
        preferred_frame: Frame | None = None,
    ) -> bool:
        """Thử vài lần với khung khác nhau cho tới khi ra một câu chưa có."""

        target = _fill_targets(spec, binding)
        candidates = ([preferred_frame] if preferred_frame is not None else []) + [
            rng.choice(options) for _ in range(12)
        ]
        for frame in candidates:
            question = _question(
                frame, binding, mentions, spec, register, rng,
                variants=split == "train",
                mention_overrides=mention_overrides,
            )
            if emit(split, query_id, register, question, target):
                return True
        return False

    for query_id in sorted(frames):
        spec = catalogue[query_id]
        parts = split_frames(frames[query_id])
        options = bindings[query_id]
        weight = FAMILY_WEIGHT.get(
            query_id, DOMAIN_WEIGHT.get(spec.domain, DEFAULT_WEIGHT)
        )

        # TRAIN. Ba lượt, theo đúng thứ tự ưu tiên của các ràng buộc:
        #   1. mỗi cặp (node, tên gọi) ít nhất một lần;
        #   2. mỗi phong cách ít nhất một lần -> đủ bốn register;
        #   3. bơm thêm có giới hạn, không quá hai lượt cho mỗi cặp tên.
        used: set[str] = set()
        name_pairs = name_teaching_cases(spec, options, mentions)
        # ``noisy`` cố ý phá chính tả, nên không dùng nó cho dòng chứng minh một
        # nhãn đã được dạy nguyên vẹn. Lượt register kế tiếp vẫn bổ sung noisy.
        teaching_registers = ("formal", "neutral", "colloquial")
        for index, (binding, slot_name, label) in enumerate(name_pairs):
            register = teaching_registers[index % len(teaching_registers)]
            if attempt(
                "train",
                query_id,
                spec,
                binding,
                parts["train"],
                register,
                mention_overrides={slot_name: label},
                preferred_frame=parts["train"][index % len(parts["train"])],
            ):
                used.add(register)
        # Khung đánh dấu ``short`` là cam kết dữ liệu, không phải gợi ý để RNG
        # có thể vô tình bỏ qua. Mỗi khung ngắn nằm ở phần train phải sinh được
        # ít nhất một dòng và phải đi qua ``decorate(..., short=True)``.
        for index, frame in enumerate(
            item for item in parts["train"] if item.short
        ):
            register = REGISTERS[index % len(REGISTERS)]
            short_options = sorted(
                options,
                key=lambda binding: sum(
                    min(
                        (len(text.split()) for text in mentions.get(value[1:], ())),
                        default=1000,
                    )
                    for name, value in binding.items()
                    if spec.slots[name].kind == "iri"
                ),
            )
            if attempt(
                "train",
                query_id,
                spec,
                short_options[index % len(short_options)],
                parts["train"],
                register,
                preferred_frame=frame,
            ):
                used.add(register)
        # Họ không có slot IRI (các bảng cố định) vẫn cần một dòng nền trước khi
        # đi qua sàn phong cách và trọng số.
        if not name_pairs:
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
        pair_floor = max(len(name_pairs), len(options))
        row_cap_multiplier = DOMAIN_ROW_CAP_MULTIPLIER.get(
            spec.domain, DEFAULT_ROW_CAP_MULTIPLIER
        )
        target_rows = max(
            _MIN_TRAIN_ROWS,
            min(len(options) * weight, row_cap_multiplier * pair_floor),
        )
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
            wanted = max(floor, len(sample))
            produced = 0
            used_registers: set[str] = set()
            # ``attempt`` có thể bị từ chối vì trùng/gần-trùng. Chỉ gọi đúng
            # ``wanted`` lần làm một họ thỉnh thoảng hụt sàn val/test khi seed
            # đổi đường RNG; thử bù có giới hạn và đếm những dòng thật đã emit.
            for index in range(wanted * 12):
                if produced >= wanted and len(used_registers) >= floor:
                    break
                binding = sample[index % len(sample)]
                register = registers[index % len(REGISTERS)]
                if attempt(split, query_id, spec, binding, parts[split], register):
                    produced += 1
                    used_registers.add(register)

    _add_contrast_pairs(splits, emit, frames, catalogue, mentions, bindings, rng)
    _balance_letter_case(splits, emit, frames, catalogue, mentions, bindings, rng)
    _add_short_questions(splits, emit, catalogue, mentions, bindings, rng)
    _add_distractions(
        splits, emit, frames, catalogue, mentions, bindings, rng, templates
    )
    checklist: dict[str, list[str]] = {}
    provenance: dict[str, dict[str, str]] = {}
    _add_rejections(
        splits, emit, graph, frames, catalogue, mentions, ambiguous, bindings, rng,
        templates, checklist,
        incomplete_specifications(graph, catalogue, bindings),
        provenance,
    )
    name_coverage = assess_name_coverage(
        {
            split: [row.as_json() for row in rows]
            for split, rows in splits.items()
        },
        catalogue,
        mentions,
    )
    require_complete_coverage(
        {"complete": not name_coverage["missing"], "name_coverage": name_coverage}
    )
    return splits, checklist, provenance


#: Đuôi ngắn ghép ngay sau tên gọi. MỌI tập dùng chung rổ này, kể cả đuôi rỗng.
#:
#: Chống rò rỉ bằng cách chia THỰC THỂ chứ không chia đuôi câu. Chia theo đuôi
#: thì dạng "tên gọi đứng một mình" - đúng ca người dùng thử hỏng - chỉ nằm ở
#: train, và tập test không bao giờ đo được nó. Chia theo thực thể thì cả ba tập
#: đều có dạng trần, chỉ khác tên gọi, nên vẫn không có câu nào trùng câu nào.
#:
#: Và nó biến đây thành PHÉP ĐO TỔNG QUÁT HOÁ thật: thực thể ở val/test vẫn được
#: dạy đầy đủ ở train qua các khung DÀI, chỉ chưa từng thấy ở dạng ngắn. Câu hỏi
#: đo được là "học dạng ngắn ở thực thể này, có bắc sang thực thể khác không".
#:
#: Mọi đuôi đều là kiểu "kể tôi nghe về X", hợp với MỌI họ, vì thiết kế nay trả
#: TRỌN NODE bất kể hỏi cách nào. Cố ý không dùng đuôi hẹp nghĩa (" các bước",
#: " hạn nộp") - chúng chỉ hợp một số họ và sẽ đẻ ra câu vô nghĩa ở họ khác.
_SHORT_TAILS: tuple[str, ...] = ("", " thế nào", " làm sao", " ra sao", " là gì")

#: Thực thể thứ i của một họ thuộc về tập nào, khi sinh câu ngắn. Ba trên năm
#: cho train, còn lại chia đôi - đủ để val và test đều có dạng trần.
_SHORT_SPLIT_CYCLE = ("train", "train", "train", "val", "test")

#: Số dòng câu ngắn mỗi họ, theo miền và tập. Đây là các con số CỐ Ý: tập dạy cũ có đúng 53
#: dòng từ 6 từ trở xuống trên 2.065, và 45,3% trong số đó bị gán từ chối - tức
#: là nó dạy thẳng "ngắn thì từ chối". Chỗ này bơm đủ dòng ngắn TRẢ LỜI ĐƯỢC để
#: xoá tương quan ấy, ở mọi họ chứ không riêng họ nào.
#:
#: Quota được đo theo miền thay vì cộng 22 dòng vào mọi họ: ``document`` cần bù
#: nhiều vì tên dài, còn ``academic-rule`` có nhiều họ nên chỉ cần sáu dòng/họ.
#: Val/test giữ quota nhỏ; độ dày của chúng đến từ số neo held-out riêng.
_SHORT_ROWS_BY_DOMAIN = {
    "academic-rule": {"train": 6, "val": 3, "test": 3},
    # Thủ tục cần thêm mẫu 2-6 từ để chính miền trọng tâm vượt sàn 15%; quota
    # này dạy cách gọi ngắn trả lời được, không trộn nó với câu từ chối.
    "procedure": {"train": 39, "val": 3, "test": 3},
    "form": {"train": 45, "val": 3, "test": 3},
    # Tên toạ độ văn bản dài năm từ nên vẫn cần quota riêng; 80 giữ tỷ lệ 2-6
    # từ trong vùng 16-19%, đồng thời nhường ngân sách cho miền trọng tâm thay
    # vì để document một mình đẩy tổng và vế tham chiếu lên quá cao.
    "document": {"train": 80, "val": 4, "test": 4},
    "tuition": {"train": 7, "val": 3, "test": 3},
    "certificate": {"train": 8, "val": 3, "test": 3},
}
_DEFAULT_SHORT_ROWS = {"train": 4, "val": 3, "test": 3}

# Vùng 7-9 từ từng có 31,8% câu từ chối, cao hơn cả vùng 2-6. Chỉ bơm tên gọi
# trần không chữa được bậc này, nên train nhận thêm câu hỏi-chung được giữ đúng
# trong khoảng 7-9 từ. Các đuôi vẫn hỏi trọn node, không thu hẹp sang một thuộc
# tính cụ thể.
_COMPACT_TAILS: tuple[str, ...] = (
    " cần biết gì",
    " có gì cần lưu ý",
    " hướng dẫn đầy đủ giúp mình",
    " cho mình biết với",
    " thông tin đầy đủ",
    " quy định thế nào",
)
_COMPACT_TRAIN_ROWS_BY_DOMAIN = {
    # Giữ câu dương 7-9 từ đúng tại miền trọng tâm để dốc từ chối của bậc này
    # không vượt nền; 70 tạo biên dưới 1,42×, còn quota từ chối được hạ riêng
    # để tổng vẫn nằm dưới 4.150 dòng mà không rút ví dụ dương của bậc này.
    "procedure": 70,
    "form": 35,
    "tuition": 6,
    "certificate": 6,
}
_DEFAULT_COMPACT_TRAIN_ROWS = 1

# Từng bù riêng bậc 10-13; sau khi chuyển quota 7-9 sang miền trọng tâm, bậc này
# đã tự ở dưới trần. Giữ đường sinh với quota 0 để phép đo sau có thể bật lại.
_MEDIUM_TAILS: tuple[str, ...] = (
    " có những nội dung quan trọng nào cần lưu ý",
    " được quy định cụ thể trong văn bản hiện hành ra sao",
    " cần tra cứu đầy đủ những thông tin học vụ nào",
    " được hướng dẫn chi tiết theo quy định như thế nào",
)
_MEDIUM_TRAIN_ROWS = 0


def _add_short_questions(
    splits: dict[str, list[Row]],
    emit,
    catalogue: Mapping[str, QuerySpec],
    mentions: Mapping[str, tuple[str, ...]],
    bindings: Mapping[str, list[dict[str, str]]],
    rng: random.Random,
) -> None:
    """Tên gọi đứng một mình, và tên gọi cộng một hai từ.

    Người dùng đặc tả rõ: *"với các kiểu 'abcxyz làm thế nào', 'làm sao abcxyz',
    hay đơn giản 'abcxyz' thì lấy hết toàn bộ thuộc tính của node đó"*. Vế cuối
    chưa bao giờ vào khung, và hậu quả đo được: câu dạy NGẮN NHẤT chứa "chuyển
    ngành" dài 11 từ, "bảo lưu" 10 từ, "học lại" 7 từ. Model chưa từng thấy một
    tên gọi đứng một mình nên nó từ chối - đúng bốn câu người dùng thử tay.

    Chỉ chạy cho họ lấy trọn một node qua chỗ trống ``anchor``. Mười ba họ không
    có chỗ trống và ``payment-fee-by-method`` (có ``phuongthuc`` nhưng hỏi phí,
    không hỏi trọn node phương thức) phải dùng khung ngắn soạn tay. Nếu cho họ
    phí đi đường này, câu trần "VNPAY" sẽ bị gán thành câu hỏi phí giao dịch.
    """

    for query_id, spec in sorted(catalogue.items()):
        slots = frozenset(spec.slots)
        if slots != {"anchor"}:
            continue
        slot = "anchor"
        if spec.slots[slot].kind != "iri":
            continue
        options = [b for b in bindings.get(query_id, ()) if slot in b]
        if not options:
            continue
        # Thực thể chia về tập theo vị trí, nên một thực thể chỉ sinh câu ngắn
        # cho ĐÚNG MỘT tập - không có đường nào để câu test trùng câu train.
        buckets: dict[str, list[dict[str, str]]] = {"train": [], "val": [], "test": []}
        for index, binding in enumerate(options):
            buckets[_SHORT_SPLIT_CYCLE[index % len(_SHORT_SPLIT_CYCLE)]].append(binding)
        # Họ chỉ có một hai thực thể thì phép chia trên bỏ đói train. Dạy vẫn là
        # ưu tiên: thà val/test thiếu câu ngắn ở họ đó còn hơn train không có.
        if not buckets["train"]:
            buckets["train"] = options

        short_rows = _SHORT_ROWS_BY_DOMAIN.get(spec.domain, _DEFAULT_SHORT_ROWS)
        for split, wanted in short_rows.items():
            pool = buckets[split]
            if not pool:
                continue
            produced = 0
            # Nhiều lượt hơn hẳn số cần: emit trả False khi câu đã tồn tại, và
            # tên gọi ngắn rất dễ đụng nhau giữa các họ cùng trỏ một thực thể.
            for index in range(wanted * 12):
                if produced >= wanted:
                    break
                binding = pool[index % len(pool)]
                register = REGISTERS[index % len(REGISTERS)]
                tail = _SHORT_TAILS[index % len(_SHORT_TAILS)]
                names = mentions.get(binding[slot][1:])
                if not names:
                    break
                question = decorate(
                    f"{choose_mention(names, register, rng)}{tail}",
                    register,
                    rng,
                    short=True,
                )
                # Tên thực thể có thể tự nó đã dài hơn sáu từ. Không được tính
                # một câu như vậy vào quota "ngắn", nếu không các miền nhiều
                # tên văn bản dài vẫn thiếu mẫu 2-6 từ dù bộ sinh báo đủ quota.
                if not 2 <= len(question.split()) <= 6:
                    continue
                if emit(split, query_id, register, question,
                        _fill_targets(spec, binding)):
                    produced += 1

        # Bậc 7-9 cần mẫu dương riêng; kiểm số từ TRƯỚC khi emit để thay đổi tên
        # dài/ngắn trong ontology không âm thầm đẩy chúng sang bậc khác.
        produced = 0
        pool = buckets["train"]
        compact_rows = _COMPACT_TRAIN_ROWS_BY_DOMAIN.get(
            spec.domain, _DEFAULT_COMPACT_TRAIN_ROWS
        )
        for index in range(compact_rows * 80):
            if produced >= compact_rows:
                break
            binding = pool[index % len(pool)]
            register = REGISTERS[index % len(REGISTERS)]
            names = mentions.get(binding[slot][1:])
            if not names:
                continue
            tail = _COMPACT_TAILS[index % len(_COMPACT_TAILS)]
            question = decorate(
                f"{choose_mention(names, register, rng)}{tail}",
                register,
                rng,
                short=True,
            )
            if not 7 <= len(question.split()) <= 9:
                continue
            if emit(
                "train",
                query_id,
                register,
                question,
                _fill_targets(spec, binding),
            ):
                produced += 1

        produced = 0
        for index in range(_MEDIUM_TRAIN_ROWS * 80):
            if produced >= _MEDIUM_TRAIN_ROWS:
                break
            binding = pool[index % len(pool)]
            register = REGISTERS[index % len(REGISTERS)]
            names = mentions.get(binding[slot][1:])
            if not names:
                continue
            tail = _MEDIUM_TAILS[index % len(_MEDIUM_TAILS)]
            question = decorate(
                f"{choose_mention(names, register, rng)}{tail}",
                register,
                rng,
            )
            if not 10 <= len(question.split()) <= 13:
                continue
            if emit(
                "train", query_id, register, question, _fill_targets(spec, binding)
            ):
                produced += 1


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
    provenance: dict[str, dict[str, str]],
) -> None:
    """Câu từ chối, đủ các nhóm mà ``coverage.json`` đòi, mỗi nhóm đủ bốn phong cách.

    ``provenance`` nhận lại **khuôn và neo đã đẻ ra từng dòng**. Dòng dataset chỉ
    mang câu hỏi trần, nên không có sổ này thì phép kiểm buộc phải đoán ngược
    khuôn từ chữ nghĩa câu hỏi - đúng cái bẫy đã để lọt 24 câu từ chối oan. Có
    sổ thì phép kiểm tra thẳng đồ thị: neo này có mang dữ kiện khuôn kia hỏi
    không.

    Hai nhóm sinh thẳng từ đồ thị nên không phải bịa:

    * ``ambiguous`` - cách gọi trỏ tới nhiều thứ KHÁC NHAU ("Điều 1" có ở cả ba
      tài liệu với nội dung khác hẳn nhau);
    * ``near-domain-missing`` - hỏi một khía cạnh mà ontology không ghi cho thực
      thể đó (thời hạn của một thủ tục không có thời hạn).

    Cả hai đều là ca "gần miền", và sinh từ đồ thị thật thì bảo đảm chúng thực sự
    không trả lời được.

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
    # Chạy MỘT lần cho cả lượt sinh: câu dump chỉ phụ thuộc neo, mà mỗi neo bị
    # thử với hàng chục khuôn.
    dumped = dump_literals(graph, catalogue, PROCEDURE_FAMILY)

    def anchor_text(register: str, template: str = "") -> tuple[str, str] | None:
        """Bốc một thủ tục làm neo, nhưng LOẠI thủ tục trả lời được câu hỏi.

        ``template`` phải truyền vào TRƯỚC khi bốc neo, không phải sau: chọn neo
        rồi mới chọn khuôn thì không còn cơ hội loại cặp hỏng.

        Trả về ``(cách gọi, tên node)`` - tên node đi vào sổ ``provenance``.
        """

        pool = [
            item
            for item in procedural
            if not answered_in_dump(dumped.get(item[1]["anchor"][1:], ""), template)
        ]
        if not pool:
            return None
        local = rng.choice(pool)[1]["anchor"][1:]
        if local not in mentions:
            return None
        return choose_mention(mentions[local], register, rng), local

    def build(kind: str, register: str, split: str) -> tuple[str, str, str] | None:
        """Mẫu câu cũng phải CHIA THEO TẬP, y như khung ý định.

        Dùng chung mẫu giữa các tập sinh ra câu gần trùng, và validator bắt đúng
        chỗ đó ở ngưỡng 0,84 - "chào bạn nhỉ?" ở train với "chào bạn ta?" ở test
        không phải hai câu khác nhau.
        """

        def decorate_with_anchor(template: str, mention: str) -> str:
            """Khoác register nhưng không làm lỗi chính tả bên trong tên neo."""

            placeholder = "§§§"
            decorated = decorate(
                template.replace("{anchor}", placeholder), register, rng
            )
            return decorated.replace(placeholder, mention)

        if kind == "ambiguous":
            if not ambiguous:
                return None
            # Khung phải là khung của một họ NHẬN được chính thực thể đó, nếu
            # không ta hỏi thời hạn của một điều luật và câu vô nghĩa vì sai
            # loại chứ không vì mơ hồ - hai lý do từ chối rất khác nhau.
            #
            # Và họ đó phải nhận được TỪ HAI chủ sở hữu trở lên. Cách gọi mơ hồ
            # thôi thì CHƯA đủ: nếu các chủ sở hữu nằm ở những họ khác nhau,
            # chính KHUNG đã gỡ xong mơ hồ và câu hỏi có đúng một đáp án.
            #
            # Ca thật đã dính: "Mẫu số 13" trỏ tới hai tờ đơn KHÁC NHAU ngoài
            # đời - quyết định đánh số 13 cho đơn xin chuyển trường, website
            # đánh số 13 cho đơn học cùng lúc hai chương trình. Nhưng hỏi
            # "thông tin tải xuống của Mẫu số 13" thì chỉ còn mục tải, tức trả
            # lời được; 15 dòng đã bị gán từ chối oan vì thiếu điều kiện này.
            # "Điều 1" thì ngược lại: cả ba tài liệu đều rơi vào cùng một họ
            # tra điều luật, nên khung không gỡ được gì và nó mơ hồ thật.
            text = rng.choice(sorted(ambiguous))
            owners = {f":{name}" for name in ambiguous[text]}
            fitting = [
                query_id
                for query_id in anchored
                if len(
                    owners
                    & {
                        binding["anchor"]
                        for binding in bindings[query_id]
                        if "anchor" in binding
                    }
                )
                > 1
            ]
            if not fitting:
                return None
            frame = rng.choice(split_frames(frames[rng.choice(fitting)])[split])
            # Neo ở đây là một CÁCH GỌI mơ hồ, cố ý không trỏ về một node duy
            # nhất, nên không có tên node để ghi sổ.
            return decorate_with_anchor(frame.text, text), frame.text, ""
        if kind == "incomplete-request":
            # V3 có hai dạng yêu cầu thiếu thông tin hợp lệ:
            #
            # * không có chỗ trống: người hỏi chưa nêu BẤT KỲ thực thể nào;
            # * đúng một chỗ trống: người hỏi chỉ nêu một slot đã ĐO ĐƯỢC là
            #   còn dẫn tới nhiều đáp án - xem ``incomplete_specifications``.
            #
            # Không chấp nhận nhiều chỗ trống hay một slot chưa đo được; thà
            # thiếu câu từ chối còn hơn dạy từ chối một câu trả lời được.
            options = _split_templates(templates.get(kind, ()), split)
            if not options:
                return None
            text = rng.choice(options)
            slot_names = {
                name for name in _SLOT_PLACEHOLDER.findall(text)
            }
            if not slot_names:
                return decorate(text, register, rng), text, ""
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
            return (
                decorate(text.replace("{" + name + "}", filled), register, rng),
                text,
                value[1:] if slot.kind == "iri" else "",
            )
        if kind == "near-domain-missing":
            # Hỏi một THUỘC TÍNH không có của thủ tục thật. Bản trước lấy một
            # thực thể ngoài họ A rồi nhét vào khung hỏi-chung của A; nhưng mọi
            # họ ``*-facts`` đều lấy trọn node, nên câu ấy vẫn trả lời được qua
            # họ B và bị gán sai ``no-information``.
            options = _split_templates(templates.get(kind, ()), split)
            if not options:
                return None
            template = rng.choice(options)
            picked = anchor_text(register, template)
            if picked is None:
                return None
            mention, local = picked
            return decorate_with_anchor(template, mention), template, local
        options = _split_templates(templates.get(kind, ()), split)
        if not options:
            return None
        text = rng.choice(options)
        if "{anchor}" in text:
            picked = anchor_text(register, text)
            if picked is None:
                return None
            mention, local = picked
            return decorate_with_anchor(text, mention), text, local
        return decorate(text, register, rng), text, ""

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
                    built = build(kind, register, split)
                    if built is None:
                        continue
                    question, template, anchor = built
                    before = len(splits[split])
                    family, target = "no-information", MARKER
                    emit(split, family, register, question, target)
                    if len(splits[split]) > before:
                        checklist.setdefault(kind, []).append(splits[split][-1].id)
                        provenance[splits[split][-1].id] = {
                            "class": kind, "template": template, "anchor": anchor
                        }
                        produced += 1
                        if kind == "near-domain-missing":
                            _emit_cross_family_general_question(
                                split,
                                register,
                                splits,
                                emit,
                                frames,
                                catalogue,
                                mentions,
                                bindings,
                                rng,
                            )
                        break
        # Lượt hai: bơm cho đủ tỷ lệ.
        for _ in range(quota * 12):
            if produced >= quota:
                break
            kind = rng.choice(kinds)
            register = rng.choice(REGISTERS)
            built = build(kind, register, split)
            if built is None:
                continue
            question, template, anchor = built
            before = len(splits[split])
            family, target = "no-information", MARKER
            emit(split, family, register, question, target)
            if len(splits[split]) > before:
                checklist.setdefault(kind, []).append(splits[split][-1].id)
                provenance[splits[split][-1].id] = {
                    "class": kind, "template": template, "anchor": anchor
                }
                produced += 1
                if kind == "near-domain-missing":
                    _emit_cross_family_general_question(
                        split,
                        register,
                        splits,
                        emit,
                        frames,
                        catalogue,
                        mentions,
                        bindings,
                        rng,
                    )


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


def _emit_cross_family_general_question(
    split: str,
    register: str,
    splits: Mapping[str, list[Row]],
    emit,
    frames: Mapping[str, tuple[Frame, ...]],
    catalogue: Mapping[str, QuerySpec],
    mentions: Mapping[str, tuple[str, ...]],
    bindings: Mapping[str, list[dict[str, str]]],
    rng: random.Random,
) -> bool:
    """Dạy khung hỏi-chung của họ A với thực thể thật thuộc họ B.

    Đây là đúng nhóm trước kia bị gán nhầm ``no-information``. Khung có thể nói
    "quy tắc", "điều kiện", "cần lưu ý" hay "hướng dẫn", nhưng hợp đồng của
    công cụ là nhận ra tên gọi rồi trả trọn node. Đích vì vậy phải thuộc họ đang
    sở hữu thực thể, không thuộc họ cung cấp cách diễn đạt.
    """

    sources = [
        query_id
        for query_id in sorted(frames)
        if set(catalogue[query_id].slots) == {"anchor"}
        and bindings.get(query_id)
    ]
    for _ in range(40):
        source_id = rng.choice(sources)
        source_spec = catalogue[source_id]
        disallowed = {
            binding["anchor"] for binding in bindings[source_id]
        }
        owners = [
            (owner_id, binding)
            for owner_id, options in sorted(bindings.items())
            if owner_id != source_id
            and catalogue[owner_id].domain == source_spec.domain
            and set(catalogue[owner_id].slots) == {"anchor"}
            for binding in options
            if binding["anchor"] not in disallowed
            and binding["anchor"][1:] in mentions
        ]
        if not owners:
            continue
        owner_id, binding = rng.choice(owners)
        frame = rng.choice(split_frames(frames[source_id])[split])
        mention = choose_mention(
            mentions[binding["anchor"][1:]], register, rng
        )
        question = decorate(
            frame.fill({"anchor": mention}), register, rng, short=frame.short
        )
        grams = _character_trigrams(question)
        if any(
            row.query_id == owner_id
            and len(grams & other) / len(grams | other)
            >= NEAR_DUPLICATE_THRESHOLD
            for other_split, rows in splits.items()
            if other_split != split
            for row in rows
            for other in [_character_trigrams(row.input)]
        ):
            continue
        if emit(
            split,
            owner_id,
            register,
            question,
            _fill_targets(catalogue[owner_id], binding),
        ):
            return True
    return False


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
    graph: Graph,
    catalogue: Mapping[str, QuerySpec],
    frames: Mapping[str, tuple[Frame, ...]],
    article_numbers: tuple[str, ...],
    clause_numbers: tuple[tuple[str, str], ...],
) -> dict[str, list[dict[str, str]]]:
    """Mọi bộ giá trị slot hợp lệ của từng họ.

    Slot IRI độc lập lấy danh sách đã khai trong danh mục. Bốn họ có miền số suy
    đúng một mốc cho mỗi neo/tổ hợp từ thuộc tính RDF có cấu trúc. Riêng số hiệu
    điều và cặp điều–khoản cũng suy thẳng từ ontology.
    """

    by_query: dict[str, list[dict[str, str]]] = {}
    inferred_numeric = {
        query_id: [
            {
                **dict(anchor.context),
                anchor.number_slot: format(anchor.representative, "f"),
            }
            for anchor in anchors
        ]
        for query_id, anchors in numeric_anchors(graph).items()
    }

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
            by_query[query_id] = inferred_numeric.get(query_id, [])
            continue
        # Slot IRI không phải lúc nào cũng tên "anchor" - còn "rule", "certificate",
        # "program". Nhân chéo các danh sách đã khai; không họ nào có quá một slot
        # IRI nên tích không nổ.
        by_query[query_id] = [
            dict(zip(names, combination, strict=True))
            for combination in product(*(spec.slots[name].values for name in names))
        ]
    return by_query
