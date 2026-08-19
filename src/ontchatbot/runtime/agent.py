"""Trợ lý học vụ: một mô hình ngôn ngữ lớn gọi công cụ tra cứu ontology.

Mô hình ngôn ngữ lớn nhận câu hỏi của người dùng và viết câu trả lời cuối cùng.
Nó không tự nhớ quy định; muốn biết dữ kiện thì phải gọi công cụ, và công cụ chỉ
trả về những gì đọc được từ đồ thị tri thức kèm nguồn.

Ranh giới đó là lý do hệ thống tồn tại: mô hình ngôn ngữ diễn đạt tốt nhưng nhớ
sai, còn đồ thị nhớ đúng nhưng không biết diễn đạt.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Sequence

from ..settings import ONTOLOGY_NS
from .model import QueryGenerationError
from .pipeline import OntologyChatbot
from .render import NO_INFORMATION_REPLY
from .sparql import SparqlError
from .sparql import load_ontology

#: Điểm cuối mặc định. Máy chủ nhận cùng giao thức với OpenAI nên thư viện
#: ``openai-agents`` dùng được mà không cần lớp chuyển đổi nào.
DEFAULT_BASE_URL = "https://lightning.ai/api/v1/"
#: Một yêu cầu HTTP có 30 giây để hoàn tất: cao hơn gần 50% so với ngưỡng vận
#: hành 20,3 giây nhưng vẫn đủ ngắn để lỗi mạng không giữ người dùng chờ lâu.
MODEL_REQUEST_TIMEOUT_SECONDS = 30.0
#: Một lần thử lại hấp thụ lỗi kết nối thoáng qua; hạn toàn lượt ở tầng API vẫn
#: chặn tổng thời gian dù cả hai lần gọi đều chậm.
MODEL_MAX_RETRIES = 1
#: Mức suy luận của mô hình điều phối: để nhà cung cấp tự chọn.
#:
#: Hạ xuống mức thấp thì ít lượt tra hơn, nhanh hơn, và hết ký hiệu nội bộ trong
#: câu trả lời - nhưng cứ khoảng một trong mười lượt, mô hình gọi công cụ xong
#: rồi kết thúc mà không viết câu nào. Một câu trả lời trống là hỏng nặng hơn
#: mấy thứ kia cộng lại, nên không ghim mức thấp.
REASONING_EFFORT = None

#: Số tên mỗi loại nêu trong khuôn nhắc.
#:
#: Khuôn nhắc chỉ cần đủ để mô hình biết công cụ tra được những GÌ, rồi tự đoán
#: từ khoá gần đúng. Liệt kê trọn danh mục làm khuôn nhắc phình ra mà không giúp
#: thêm, vì mô hình đâu cần thuộc lòng danh sách - nó chỉ cần biết phạm vi.
NAMES_PER_KIND = 12

#: Mô tả công cụ mà mô hình đọc trước khi quyết định gọi nó.
#:
#: Truyền tường minh chứ không để thư viện đọc từ chú thích: thư viện chỉ lấy
#: câu tóm tắt và đoạn đầu, nên phần ví dụ - thứ dạy mô hình rút câu hỏi thành
#: từ khoá - bị bỏ mất mà không báo gì.
#:
#: Ví dụ đứng ở đây vì bộ sinh truy vấn được dạy trên câu hỏi ngắn: câu hỏi
#: người dùng gõ thường dài và lịch sự, còn tên mục trong đồ thị thì ngắn.
TOOL_DESCRIPTION = """Tra dữ kiện học vụ từ đồ thị tri thức của trường: quy chế
đào tạo, thủ tục, biểu mẫu, học phí, chứng chỉ và ngành đào tạo.

Truyền vào TỪ KHOÁ NGẮN, không phải câu hỏi đầy đủ. Công cụ khớp từ khoá với tên
các mục trong đồ thị, nên câu càng dài càng dễ trượt.

Nên:  "đăng ký học phần" · "nghỉ học tạm thời" · "học phí một tín chỉ"
      "đơn xin hoãn thi" · "điều kiện tốt nghiệp" · "ngành công nghệ thông tin"

Không nên:  "Hãy hướng dẫn tôi cách đăng ký học phần nhé"
            "cho mình hỏi muốn nghỉ học tạm thời thì cần làm những gì ạ"

Tham số là một DANH SÁCH từ khoá, tra hết trong một lần gọi. Người hỏi và đồ thị
hay gọi cùng một thứ bằng hai tên khác nhau, nên gửi 2-3 cách gọi của cùng chủ đề
để tăng khả năng trúng:

    ["nghỉ học tạm thời", "bảo lưu kết quả học tập"]
    ["điều kiện tốt nghiệp", "xét tốt nghiệp"]

Câu hỏi nhiều chủ đề thì đưa hết từ khoá của mọi chủ đề vào cùng danh sách đó -
vẫn một lần gọi.

Kết quả là JSON. Cách đọc:
- `trang_thai=co_du_lieu`: `nguon` là TRỌN VẸN những gì tìm được. Mỗi mục gồm
  trích dẫn, đường dẫn, và `du_lieu` mà nguồn đó khẳng định. Phải đọc HẾT.
- Nếu chi tiết người dùng hỏi không xuất hiện trong bất kỳ bản ghi nào, cơ sở dữ
  liệu không có chi tiết đó. Nói rõ điều này và ĐỪNG gọi lại cùng chủ đề.
- `tu_khoa_khong_thay` liệt kê những từ khoá không khớp gì. Các từ khoá còn lại
  vẫn có dữ liệu, nên đừng tra lại cả loạt.
- `trang_thai=khong_co_thong_tin`: không từ khoá nào khớp. Chỉ lúc này mới thử
  thêm tối đa một lần bằng những cách gọi khác hẳn. Vẫn không có thì dừng và nói
  không tìm thấy."""


@dataclass(frozen=True)
class OntologyVocabulary:
    """Những gì đồ thị tri thức đang có, nói bằng tên người đọc được."""

    procedures: tuple[str, ...]
    units: tuple[str, ...]
    forms: tuple[str, ...]
    programs: tuple[str, ...]


def read_vocabulary(graph=None, limit: int = NAMES_PER_KIND) -> OntologyVocabulary:
    """Đọc tên các quy trình, đơn vị, biểu mẫu và ngành từ chính đồ thị.

    Khuôn nhắc phải sinh ra từ dữ liệu chứ không chép tay. Danh sách chép tay
    mục dần: ontology thêm một thủ tục thì khuôn nhắc vẫn nói cái cũ, và mô hình
    được dạy rằng thủ tục mới không tồn tại.
    """

    graph = graph if graph is not None else load_ontology()

    def labels(class_name: str) -> tuple[str, ...]:
        query = (
            f"SELECT DISTINCT ?label WHERE {{ ?node a <{ONTOLOGY_NS}{class_name}> ; "
            "<http://www.w3.org/2000/01/rdf-schema#label> ?label }"
        )
        found = sorted(str(row[0]) for row in graph.query(query))
        return tuple(found[:limit])

    return OntologyVocabulary(
        procedures=labels("AcademicProcedure"),
        units=labels("OrganizationalUnit"),
        forms=labels("FormCatalogueEntry"),
        programs=labels("AcademicProgram"),
    )


#: Tiền tố kỹ thuật trong nhãn ontology, không thuộc tên biểu mẫu.
_LABEL_NOISE = ("Mục tải:", "Thủ tục")


def _clean(name: str) -> str:
    """Bỏ tiền tố phân loại khỏi nhãn để còn lại tên người gọi hàng ngày."""

    for prefix in _LABEL_NOISE:
        if name.startswith(prefix):
            name = name[len(prefix) :]
    return name.lstrip(" -").strip()


def _line(title: str, names: Sequence[str], limit: int) -> str:
    if not names:
        return ""
    cleaned = [_clean(name) for name in names[:limit]]
    return f"- {title}: " + ", ".join(cleaned) + "\n"


def build_instructions(vocabulary: OntologyVocabulary | None = None) -> str:
    """Dựng lời hướng dẫn hệ thống cho trợ lý.

    Thứ tự trong lời hướng dẫn quyết định hành vi nhiều hơn nội dung. Quy tắc gọi
    công cụ đứng đầu và đứng riêng; danh sách chủ đề đứng sau. Đảo lại thì quy
    tắc bị chôn giữa một khối tên dài và tỉ lệ gọi công cụ tụt hẳn.

    Danh sách chủ đề không phục vụ việc gọi công cụ - nó phục vụ lúc người dùng
    hỏi trợ lý giúp được gì, và lúc trợ lý cần gợi ý hướng hỏi tiếp.
    """

    vocabulary = vocabulary or read_vocabulary()
    topics = "".join(
        (
            _line("Thủ tục", vocabulary.procedures, 5),
            _line("Biểu mẫu", vocabulary.forms, 3),
            _line("Ngành đào tạo", vocabulary.programs, 4),
            _line("Đơn vị", vocabulary.units, 3),
        )
    )
    return f"""Bạn là trợ lý học vụ của Trường Đại học Nha Trang.

Bạn KHÔNG biết quy định nào của trường này. Mọi điều bạn tưởng mình nhớ về quy
chế, thủ tục, biểu mẫu, học phí hay ngành đào tạo của trường đều là của trường
khác.

Mọi câu hỏi về học vụ: GỌI `tra_cuu_hoc_vu` TRƯỚC, rồi mới trả lời dựa trên kết
quả trả về. Chưa gọi công cụ thì chưa được trả lời. Công cụ không có dữ kiện thì
nói là không tìm thấy, đừng suy đoán và đừng bịa số.

Khi công cụ trả `co_du_lieu`, đọc hết `du_lieu` rồi coi đó là kết quả cuối của
chủ đề. Nếu chi tiết được hỏi không xuất hiện, nói dữ liệu hiện có không chứa
chi tiết ấy; không đổi từ khoá để tra tiếp.

Câu hỏi có nhiều chủ đề độc lập: tách và gọi đúng một lần cho từng chủ đề trước
khi trả lời; không bỏ sót vế nào.

Mọi khẳng định thực tế phải được `du_lieu` hoặc `nguon` ghi trực tiếp. Không suy
luận, ghép thành quan hệ mới, hay áp dụng
quy định/bảng chung cho một ngành cụ thể nếu dữ liệu không nói vậy. Không thêm
số hoặc tên riêng ngoài dữ liệu.

Câu hỏi không liên quan tới trường - thời tiết, nấu ăn, chuyện phiếm - thì trả
lời thẳng là ngoài phạm vi, không gọi công cụ.

Giữ lại trích dẫn và đường dẫn nguồn mà công cụ kèm theo.

Khi người dùng hỏi bạn giúp được gì, hoặc khi cần gợi ý hướng hỏi tiếp, đây là
vài chủ đề tra được:

{topics}"""


def look_up(chatbot: OntologyChatbot, tu_khoa: Sequence[str] | str) -> str:
    """Tra một chủ đề và luôn trả về đúng khuôn kết quả đã hẹn.

    Truy vấn sinh ra hỏng là chuyện của tầng dưới; với người gọi thì nó không
    khác gì không tìm thấy. Trợ lý đọc trạng thái trong kết quả để quyết định
    tra lại hay dừng, mà một ngoại lệ thì không mang trạng thái đó - nó làm hỏng
    cả lượt chạy thay vì thành một câu trả lời trung thực.
    """

    keywords = [tu_khoa] if isinstance(tu_khoa, str) else list(tu_khoa)
    try:
        return chatbot.answer_many(keywords)
    except (QueryGenerationError, SparqlError):
        return NO_INFORMATION_REPLY


def build_tool(chatbot: OntologyChatbot):
    """Bọc đường tra cứu ontology thành một công cụ cho mô hình gọi.

    Công cụ dựng trong hàm để nó giữ được ``chatbot`` đã cấu hình sẵn; thư viện
    đọc chú thích của hàm bên trong để sinh mô tả công cụ, nên phần hướng dẫn
    cách gọi nằm ngay trong chú thích đó.
    """

    from agents import function_tool

    @function_tool(description_override=TOOL_DESCRIPTION)
    def tra_cuu_hoc_vu(tu_khoa: list[str]) -> str:
        """Tra các chủ đề học vụ.

        Args:
            tu_khoa: Danh sách cụm từ khoá ngắn, ví dụ ["đăng ký học phần"].
        """

        return look_up(chatbot, tu_khoa)

    return tra_cuu_hoc_vu


def build_agent(
    chatbot: OntologyChatbot,
    *,
    model: str,
    base_url: str | None = None,
    api_key: str | None = None,
):
    """Dựng trợ lý: một mô hình ngôn ngữ lớn kèm đúng một công cụ.

    Máy chủ mô hình nói cùng giao thức với OpenAI, nên chỉ cần trỏ địa chỉ khác;
    không có lớp chuyển đổi nào ở giữa.
    """

    from agents import Agent, ModelSettings, OpenAIChatCompletionsModel, set_tracing_disabled
    from openai import AsyncOpenAI
    from openai.types.shared import Reasoning

    # Không gửi vết chạy ra dịch vụ ngoài: câu hỏi của người dùng là dữ liệu của
    # trường, và điểm cuối này không phải OpenAI.
    set_tracing_disabled(True)

    client = AsyncOpenAI(
        base_url=base_url or os.environ.get("ONTCHATBOT_LLM_BASE_URL", DEFAULT_BASE_URL),
        api_key=api_key or os.environ.get("ONTCHATBOT_LLM_API_KEY", ""),
        timeout=MODEL_REQUEST_TIMEOUT_SECONDS,
        max_retries=MODEL_MAX_RETRIES,
    )
    return Agent(
        name="Trợ lý học vụ",
        instructions=build_instructions(),
        tools=[build_tool(chatbot)],
        model=OpenAIChatCompletionsModel(model=model, openai_client=client),
        model_settings=(
            ModelSettings(reasoning=Reasoning(effort=REASONING_EFFORT))
            if REASONING_EFFORT
            else ModelSettings()
        ),
    )
