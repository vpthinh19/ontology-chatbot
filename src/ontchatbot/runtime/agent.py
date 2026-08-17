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
from .pipeline import OntologyChatbot
from .sparql import load_ontology

#: Điểm cuối mặc định. Máy chủ nhận cùng giao thức với OpenAI nên thư viện
#: ``openai-agents`` dùng được mà không cần lớp chuyển đổi nào.
DEFAULT_BASE_URL = "https://lightning.ai/api/v1/"

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
đào tạo, thủ tục, biểu mẫu, học phí, chứng chỉ, ngành đào tạo.

Truyền vào TỪ KHOÁ NGẮN, không phải câu hỏi đầy đủ. Công cụ khớp từ khoá với tên
các mục trong đồ thị, nên câu càng dài càng dễ trượt.

Nên:  "đăng ký học phần" · "nghỉ học tạm thời" · "học phí một tín chỉ"
      "đơn xin hoãn thi" · "điều kiện tốt nghiệp" · "ngành công nghệ thông tin"

Không nên:  "Hãy hướng dẫn tôi cách đăng ký học phần nhé"
            "cho mình hỏi muốn nghỉ học tạm thời thì cần làm những gì ạ"

Một lần gọi tra một chủ đề; câu hỏi chứa hai chủ đề thì gọi hai lần. Không tra
được thì thử từ khoá ngắn hơn, hoặc một cách gọi khác của cùng mục - ví dụ
"bảo lưu" thay cho "nghỉ học tạm thời"."""


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


def _bullets(title: str, names: Sequence[str]) -> str:
    if not names:
        return ""
    return f"{title}: " + " · ".join(names) + "\n"


def build_instructions(vocabulary: OntologyVocabulary | None = None) -> str:
    """Dựng khuôn nhắc hệ thống cho trợ lý.

    Khuôn nhắc phải nói ba điều, vì thiếu điều nào thì mô hình cũng hỏng theo một
    kiểu riêng: trợ lý làm được gì (thiếu thì nó từ chối việc nó làm được), phạm
    vi dữ liệu (thiếu thì nó gọi công cụ cho câu ngoài miền), và cách gọi công cụ
    (thiếu thì nó truyền cả câu hỏi dài và công cụ tra trượt).
    """

    vocabulary = vocabulary or read_vocabulary()
    known = "".join(
        (
            _bullets("Thủ tục học vụ", vocabulary.procedures),
            _bullets("Đơn vị phụ trách", vocabulary.units),
            _bullets("Biểu mẫu", vocabulary.forms),
            _bullets("Ngành đào tạo", vocabulary.programs),
        )
    )
    return f"""Bạn là trợ lý học vụ của Trường Đại học Nha Trang. Bạn trả lời câu
hỏi về quy chế đào tạo, thủ tục học vụ, biểu mẫu, học phí, chứng chỉ và ngành
đào tạo.

QUY TẮC BẮT BUỘC: với MỌI câu hỏi về học vụ, gọi `tra_cuu_hoc_vu` TRƯỚC khi
viết câu trả lời. Kể cả khi bạn thấy mình đã biết câu trả lời, kể cả khi chủ đề
có tên trong danh sách bên dưới - vẫn phải gọi. Quy chế của trường này khác với
quy chế bạn từng đọc ở nơi khác, và một con số nhớ nhầm là một sinh viên nộp sai
hồ sơ.

Nếu công cụ không trả về dữ kiện, hãy nói rõ là không tìm thấy thông tin và gợi ý
người dùng hỏi lại bằng cách khác - đừng suy đoán, đừng bịa số, đừng dẫn một quy
định mà công cụ không đưa ra.

Khi trả lời, giữ lại trích dẫn và đường dẫn nguồn mà công cụ kèm theo, để người
đọc đối chiếu được với văn bản gốc.

Danh sách dưới đây cho biết công cụ TRA ĐƯỢC những gì, để bạn chọn từ khoá. Nó
KHÔNG phải nội dung câu trả lời - tên có trong danh sách không có nghĩa là bạn
biết nội dung của nó. Còn nhiều mục khác cùng loại không liệt kê ở đây.

{known}
Câu hỏi ngoài phạm vi học vụ của trường - thời tiết, nấu ăn, chuyện phiếm - thì
trả lời thẳng là ngoài phạm vi, không gọi công cụ."""


def build_tool(chatbot: OntologyChatbot):
    """Bọc đường tra cứu ontology thành một công cụ cho mô hình gọi.

    Công cụ dựng trong hàm để nó giữ được ``chatbot`` đã cấu hình sẵn; thư viện
    đọc chú thích của hàm bên trong để sinh mô tả công cụ, nên phần hướng dẫn
    cách gọi nằm ngay trong chú thích đó.
    """

    from agents import function_tool

    @function_tool(description_override=TOOL_DESCRIPTION)
    def tra_cuu_hoc_vu(tu_khoa: str) -> str:
        """Tra một chủ đề học vụ.

        Args:
            tu_khoa: Cụm từ khoá ngắn nêu chủ đề, ví dụ "đăng ký học phần".
        """

        return chatbot.answer(tu_khoa)

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

    from agents import Agent, OpenAIChatCompletionsModel, set_tracing_disabled
    from openai import AsyncOpenAI

    # Không gửi vết chạy ra dịch vụ ngoài: câu hỏi của người dùng là dữ liệu của
    # trường, và điểm cuối này không phải OpenAI.
    set_tracing_disabled(True)

    client = AsyncOpenAI(
        base_url=base_url or os.environ.get("ONTCHATBOT_LLM_BASE_URL", DEFAULT_BASE_URL),
        api_key=api_key or os.environ.get("ONTCHATBOT_LLM_API_KEY", ""),
    )
    return Agent(
        name="Trợ lý học vụ",
        instructions=build_instructions(),
        tools=[build_tool(chatbot)],
        model=OpenAIChatCompletionsModel(model=model, openai_client=client),
    )
