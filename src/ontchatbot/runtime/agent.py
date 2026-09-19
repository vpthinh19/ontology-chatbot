"""Trợ lý học vụ: một mô hình ngôn ngữ lớn gọi công cụ tra cứu ontology.

Mô hình ngôn ngữ lớn nhận câu hỏi của người dùng và viết câu trả lời cuối cùng.
Nó không tự nhớ quy định; muốn biết dữ kiện thì phải gọi công cụ, và công cụ chỉ
trả về những gì đọc được từ đồ thị tri thức kèm nguồn.

Ranh giới đó là lý do hệ thống tồn tại: mô hình ngôn ngữ diễn đạt tốt nhưng nhớ
sai, còn đồ thị nhớ đúng nhưng không biết diễn đạt.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Sequence

from ..settings import DEFAULT_LLM_BASE_URL
from .lookup import MAX_KEYWORD_CHARACTERS, MAX_KEYWORDS_PER_LOOKUP

if TYPE_CHECKING:
    from ..search import Ontology

#: Điểm cuối mặc định dùng giao thức chat-completions tương thích OpenAI.
DEFAULT_BASE_URL = DEFAULT_LLM_BASE_URL
#: Một yêu cầu HTTP có 30 giây để hoàn tất: cao hơn gần 50% so với ngưỡng vận
#: hành 20,3 giây nhưng vẫn đủ ngắn để lỗi mạng không giữ người dùng chờ lâu.
MODEL_REQUEST_TIMEOUT_SECONDS = 30.0
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
TOOL_DESCRIPTION = f"""Tra cứu ontology học vụ của trường: quy chế đào tạo, thủ tục,
biểu mẫu, học phí, học bổng, chứng chỉ, ngành đào tạo và đơn vị.

Truyền vào TỪ KHOÁ NGẮN, không phải câu hỏi đầy đủ. Công cụ tìm các từ này trong tên
của các mục, tên thuộc tính và tên quan hệ của chúng, nên câu càng dài càng dễ lẫn.

Nên:  "đăng ký học phần" · "nghỉ học tạm thời" · "vị trí phòng đào tạo"
      "đơn xin hoãn thi" · "điều kiện tốt nghiệp" · "ngành công nghệ thông tin"

Không nên:  "Hãy hướng dẫn tôi cách đăng ký học phần nhé"
            "cho mình hỏi muốn nghỉ học tạm thời thì cần làm những gì ạ"

Bung chữ viết tắt của người hỏi: CT → chương trình, HBKK → học bổng khuyến khích học tập,
ĐKHP → đăng ký học phần. Giữ trong từ khoá các cụm chỉ loại chương trình như "chương
trình đặc biệt", "chương trình chuẩn"; bỏ chúng thì kết quả rơi về mục chung hoặc về
tên ngành. Ví dụ: "học bổng chương trình đặc biệt", không chỉ "học bổng".

Tham số là một DANH SÁCH từ khoá, tra hết trong một lần gọi. Người hỏi và dữ liệu
hay gọi cùng một thứ bằng hai tên khác nhau, nên gửi 2-3 cách gọi của cùng chủ đề:

    ["nghỉ học tạm thời", "bảo lưu kết quả học tập"]
    ["số tín chỉ tối đa", "khối lượng đăng ký mỗi học kỳ"]

Câu hỏi nhiều chủ đề thì đưa hết từ khoá của mọi chủ đề vào cùng danh sách đó -
vẫn một lần gọi.

Mỗi lần gọi chỉ dùng tối đa {MAX_KEYWORDS_PER_LOOKUP} từ khoá, mỗi từ khoá tối đa \
{MAX_KEYWORD_CHARACTERS} ký tự. Nếu công cụ cắt bớt, JSON có `truncation`.

Kết quả là JSON. Cách đọc:
- `status=found`: `results` là các mục tìm được. Mỗi mục có `label` (tên), `classes`,
  `matched` (các dòng đã khớp với từ khoá) và `sources`.
- Kiểm `matched` TRƯỚC. Mục nào không phải thứ người dùng hỏi thì coi như không
  tìm thấy; đừng trả lời bằng dữ liệu của mục đó.
- Mỗi phần tử của `sources` gồm `citation`, `url` và `facts` mà nguồn đó khẳng định.
  Phải đọc HẾT. Mỗi fact có `subject`, `property`, `value`; `subject` khác `label`
  của mục là câu của một mục khác nói tới mục này, ví dụ các thủ tục "nộp tại" một phòng.
- Nếu chi tiết người dùng hỏi không xuất hiện trong `facts` nào, dữ liệu hiện có
  không chứa chi tiết đó. Nói rõ điều này và ĐỪNG gọi lại cùng chủ đề.
- `unmatched` liệt kê những từ khoá không khớp gì. Các từ khoá còn lại vẫn có kết
  quả, nên đừng tra lại cả loạt.
- `status=not_found`: không từ khoá nào khớp. Chỉ lúc này mới thử thêm tối đa một
  lần bằng những cách gọi khác hẳn. Vẫn không có thì dừng và nói không tìm thấy."""

TOOL_NAME = "lookup_academic_information"
TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": TOOL_NAME,
        "description": TOOL_DESCRIPTION,
        "parameters": {
            "type": "object",
            "properties": {
                "keywords": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Danh sách cụm từ khoá ngắn.",
                }
            },
            "required": ["keywords"],
            "additionalProperties": False,
        },
    },
}


@dataclass(frozen=True)
class AgentEvent:
    kind: str
    content: str = ""
    keywords: tuple[str, ...] = ()
    #: Chỉ ở sự kiện ``completed``: các dòng đánh dấu mô hình đã viết (xem ``MARKS``).
    marks: tuple[str, ...] = ()


#: Dòng đánh dấu mô hình viết ở cuối câu trả lời. Người đọc không thấy: agent cắt nó khỏi chữ và
#: báo lại thành nhãn, để lịch sử chat biết lượt nào thiếu dữ liệu mà không phải đoán qua câu chữ.
MARKS = {"[[THIEU_DU_LIEU]]": "missing", "[[NGOAI_PHAM_VI]]": "out_of_scope"}


class _MarkFilter:
    """Cắt dòng đánh dấu khỏi chữ đang chảy về từng mảnh.

    Một dấu có thể bị chia ở ranh giới hai mảnh, nên phần đuôi còn có thể là đầu của một dấu
    được giữ lại tới mảnh sau; nhờ vậy người đọc không bao giờ thấy "[[THI" nháy lên.
    """

    def __init__(self) -> None:
        self._pending = ""
        self.marks: list[str] = []

    def feed(self, text: str) -> str:
        buffer = self._pending + text
        for token, mark in MARKS.items():
            if token in buffer:
                buffer = buffer.replace(token, "")
                if mark not in self.marks:
                    self.marks.append(mark)
        hold = max((size for token in MARKS for size in range(1, len(token))
                    if buffer.endswith(token[:size])), default=0)
        self._pending = buffer[len(buffer) - hold:] if hold else ""
        return buffer[: len(buffer) - hold] if hold else buffer

    def flush(self) -> str:
        rest, self._pending = self._pending, ""
        return rest


class AgentLoopLimitError(RuntimeError):
    """The model kept requesting more steps than this service permits."""


class AgentProtocolError(RuntimeError):
    """The model emitted a tool call outside the declared contract."""


class AgentLoop:
    def __init__(
        self,
        client: Any,
        lookup: Callable[[list[str]], Awaitable[str]],
        *,
        instructions: str,
        max_steps: int = 4,
        close: Callable[[], Awaitable[None]] | None = None,
    ) -> None:
        self._client = client
        self._lookup = lookup
        self._instructions = instructions
        self._max_steps = max_steps
        self._close = close

    @property
    def lookup(self) -> Callable[[list[str]], Awaitable[str]]:
        """Công cụ tra cứu; trang quản trị thay engine của nó sau mỗi lần ghi."""

        return self._lookup

    async def aclose(self) -> None:
        if self._close is not None:
            await self._close()

    async def stream(
        self, messages: Sequence[dict[str, Any]]
    ) -> AsyncIterator[AgentEvent]:
        conversation = [
            {"role": "system", "content": self._instructions},
            *messages,
        ]
        marks = _MarkFilter()
        for _step in range(self._max_steps):
            answer_parts: list[str] = []
            calls: dict[int, dict[str, str]] = {}
            async for delta in self._client.stream(
                messages=conversation, tools=[TOOL_SCHEMA]
            ):
                text = marks.feed(delta.content) if delta.content else ""
                if text:
                    answer_parts.append(text)
                    yield AgentEvent("text_delta", content=text)
                for fragment in delta.tool_calls:
                    call = calls.setdefault(
                        fragment.index,
                        {"id": "", "name": "", "arguments": ""},
                    )
                    call["id"] += fragment.call_id
                    call["name"] += fragment.name
                    call["arguments"] += fragment.arguments

            rest = marks.flush()
            if rest:
                answer_parts.append(rest)
                yield AgentEvent("text_delta", content=rest)
            if not calls:
                yield AgentEvent(
                    "completed", content="".join(answer_parts).rstrip(), marks=tuple(marks.marks)
                )
                return

            tool_calls = [
                {
                    "id": call["id"],
                    "type": "function",
                    "function": {
                        "name": call["name"],
                        "arguments": call["arguments"],
                    },
                }
                for _, call in sorted(calls.items())
            ]
            conversation.append(
                {
                    "role": "assistant",
                    "content": "".join(answer_parts) or None,
                    "tool_calls": tool_calls,
                }
            )
            for tool_call in tool_calls:
                function = tool_call["function"]
                if function["name"] != TOOL_NAME:
                    raise AgentProtocolError(
                        f"unknown tool requested: {function['name']}"
                    )
                try:
                    arguments = json.loads(function["arguments"])
                    keywords = arguments["keywords"]
                except (json.JSONDecodeError, KeyError, TypeError) as exc:
                    raise AgentProtocolError("invalid lookup arguments") from exc
                if not isinstance(keywords, list) or not all(
                    isinstance(keyword, str) for keyword in keywords
                ):
                    raise AgentProtocolError("invalid lookup keywords")
                yield AgentEvent("lookup_started", keywords=tuple(keywords))
                result = await self._lookup(keywords)
                yield AgentEvent("lookup_finished", content=result)
                conversation.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "content": result,
                    }
                )
        raise AgentLoopLimitError("maximum agent steps exceeded")


@dataclass(frozen=True)
class OntologyVocabulary:
    """Những gì đồ thị tri thức đang có, nói bằng tên người đọc được."""

    procedures: tuple[str, ...]
    units: tuple[str, ...]
    forms: tuple[str, ...]
    programs: tuple[str, ...]


def read_vocabulary(ontology: Ontology, limit: int = NAMES_PER_KIND) -> OntologyVocabulary:
    """Đọc tên các thủ tục, đơn vị, biểu mẫu và ngành từ chính ontology đang phục vụ.

    Khuôn nhắc phải sinh ra từ dữ liệu chứ không chép tay. Danh sách chép tay
    mục dần: ontology thêm một thủ tục thì khuôn nhắc vẫn nói cái cũ, và mô hình
    được dạy rằng thủ tục mới không tồn tại.
    """

    def labels(class_name: str) -> tuple[str, ...]:
        return tuple(ontology.label(node) for node in ontology.individuals_of_class(class_name)[:limit])

    return OntologyVocabulary(
        procedures=labels("ThuTucHocVu"),
        units=labels("DonViTrongTruong"),
        forms=labels("MucBieuMauTrenWebsite"),
        programs=labels("NganhDaoTao"),
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

    topics = ""
    if vocabulary is not None:
        names = "".join(
            (
                _line("Thủ tục", vocabulary.procedures, 5),
                _line("Biểu mẫu", vocabulary.forms, 3),
                _line("Ngành đào tạo", vocabulary.programs, 4),
                _line("Đơn vị", vocabulary.units, 3),
            )
        )
        if names:
            topics = (
                "\nKhi người dùng hỏi bạn giúp được gì, hoặc khi cần gợi ý hướng hỏi tiếp, "
                f"đây là vài chủ đề tra được:\n\n{names}"
            )
    return f"""Bạn là trợ lý học vụ của Trường Đại học Nha Trang.

Bạn KHÔNG biết quy định nào của trường này. Mọi điều bạn tưởng mình nhớ về quy
chế, thủ tục, biểu mẫu, học phí hay ngành đào tạo của trường đều là của trường
khác.

Mọi câu hỏi về học vụ: GỌI `lookup_academic_information` TRƯỚC, rồi mới trả lời dựa trên kết
quả trả về. Chưa gọi công cụ thì chưa được trả lời. Công cụ không có dữ kiện thì
nói là không tìm thấy, đừng suy đoán và đừng bịa số.

Khi công cụ trả `found`, chỉ dùng mục có `matched` đúng thứ người dùng hỏi và đọc
hết `facts` của mục đó. Chi tiết hay vế nào được hỏi mà không có trong `facts` thì
nói rõ dữ liệu hiện có không chứa phần đó; không đổi từ khoá để tra tiếp.

Câu hỏi có nhiều chủ đề độc lập: đưa từ khoá của mọi chủ đề vào cùng một lần gọi,
và khi trả lời không bỏ sót vế nào. Hỏi thủ tục nào thì trả lời thủ tục đó, không
thay bằng thủ tục gần giống (hỏi thôi học thì không hướng dẫn nghỉ học tạm thời).

Hỏi tuyển sinh kèm năm thì gửi cụm "tuyển sinh" không mang năm; quy chế trong dữ
liệu là bản hiện hành.

Mọi khẳng định thực tế phải được `facts` hoặc `sources` ghi trực tiếp. Không suy
luận, ghép thành quan hệ mới, hay áp dụng
quy định/bảng chung cho một ngành cụ thể nếu dữ liệu không nói vậy. Không thêm
số hoặc tên riêng ngoài dữ liệu. Dữ liệu không nhắc tới một việc (như nộp hồ sơ) thì
không kết luận là việc đó không cần; nói dữ liệu không đề cập.

Câu hỏi không liên quan tới trường - thời tiết, nấu ăn, chuyện phiếm - thì trả
lời thẳng là ngoài phạm vi, không gọi công cụ.

Giữ lại trích dẫn và đường dẫn nguồn mà công cụ kèm theo. Định dạng: chỉ in đậm,
danh sách và liên kết markdown; không bảng, công thức hay code, ký hiệu viết thẳng
như ≥.

Dòng đánh dấu (hệ thống tự ẩn): thiếu thông tin học vụ được hỏi, kể cả một vế
hay chi tiết, thì thêm dòng cuối `[[THIEU_DU_LIEU]]`; câu hỏi ngoài phạm vi thì
thêm dòng cuối `[[NGOAI_PHAM_VI]]`; trả lời đủ thì không thêm.
{topics}"""
