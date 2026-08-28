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
from typing import Any, Sequence

from ..settings import DEFAULT_LLM_BASE_URL, ONTOLOGY_NS
from .render import NO_INFORMATION_REPLY, dump_payload

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

#: Mỗi từ khoá mất khoảng 1,8 giây vì bộ sinh truy vấn cố ý chạy tuần tự. 20
#: từ khoá tương ứng khoảng 36 giây, để lại phần thời gian của lượt 45 giây cho
#: điều phối và viết câu trả lời thay vì làm người dùng chờ tới hạn toàn lượt.
MAX_KEYWORDS_PER_LOOKUP = 20
#: Công cụ chỉ cần cụm từ ngắn; 120 ký tự chặn một câu hỏi dài hoặc dữ liệu rác
#: chiếm thời gian tiền xử lý mà vẫn rộng hơn đáng kể một tên thủ tục thông thường.
MAX_KEYWORD_CHARACTERS = 120

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

Mỗi lần gọi chỉ dùng tối đa 20 từ khoá, mỗi từ khoá tối đa 120 ký tự. Nếu công cụ
cắt bớt, JSON có `tu_khoa_da_cat` với các giới hạn và số cụm đã bị bỏ qua hoặc
rút ngắn.

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
        for _step in range(self._max_steps):
            answer_parts: list[str] = []
            calls: dict[int, dict[str, str]] = {}
            async for delta in self._client.stream(
                messages=conversation, tools=[TOOL_SCHEMA]
            ):
                if delta.content:
                    answer_parts.append(delta.content)
                    yield AgentEvent("text_delta", content=delta.content)
                for fragment in delta.tool_calls:
                    call = calls.setdefault(
                        fragment.index,
                        {"id": "", "name": "", "arguments": ""},
                    )
                    call["id"] += fragment.call_id
                    call["name"] += fragment.name
                    call["arguments"] += fragment.arguments

            if not calls:
                yield AgentEvent("completed", content="".join(answer_parts))
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
                yield AgentEvent("lookup_finished")
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


# Snapshot generated from the packaged ontology. Only the names actually used by
# ``build_instructions`` are retained so health startup never parses RDF data.
DEFAULT_VOCABULARY = OntologyVocabulary(
    procedures=(
        "Thủ tục chuyển ngành",
        "Thủ tục chuyển trường",
        "Thủ tục công nhận kết quả học tập và chuyển đổi tín chỉ",
        "Thủ tục học liên thông",
        "Thủ tục nghỉ học tạm thời",
    ),
    units=(
        "Bộ môn",
        "Khoa hoặc viện đào tạo",
        "Phòng Công tác Chính trị và Sinh viên",
    ),
    forms=(
        "Mục tải: - Đơn xin chuyển ngành chương trình Minh Phú -CT đại chuẩn",
        "Mục tải: Mẫu số 13 - Đơn đăng ký học cùng lúc hai chương trình đào tạo",
        "Mục tải: Phiếu báo điểm bổ sung",
    ),
    programs=(
        "Công nghệ chế biến thủy sản",
        "Công nghệ chế tạo máy",
        "Công nghệ sinh học",
        "Công nghệ thông tin",
    ),
)


def read_vocabulary(graph=None, limit: int = NAMES_PER_KIND) -> OntologyVocabulary:
    """Đọc tên các quy trình, đơn vị, biểu mẫu và ngành từ chính đồ thị.

    Khuôn nhắc phải sinh ra từ dữ liệu chứ không chép tay. Danh sách chép tay
    mục dần: ontology thêm một thủ tục thì khuôn nhắc vẫn nói cái cũ, và mô hình
    được dạy rằng thủ tục mới không tồn tại.
    """

    from .sparql import execute_select, load_ontology

    if graph is None:
        graph = load_ontology()

    def labels(class_name: str) -> tuple[str, ...]:
        query = (
            f"SELECT DISTINCT ?label WHERE {{ ?node a <{ONTOLOGY_NS}{class_name}> ; "
            "<http://www.w3.org/2000/01/rdf-schema#label> ?label }"
        )
        # Đi qua ``execute_select`` để phần chữ của literal được bóc ra theo đúng
        # một quy tắc với mọi chỗ khác; lấy chuỗi thẳng từ node đồ thị sẽ kéo theo
        # cả dấu nháy và thẻ ngôn ngữ.
        # Trần chỉ để một lỗi nào đó không kéo cả đồ thị vào bộ nhớ; lớp đông
        # nhất hiện có 41 nhãn, nên nó không cắt gì trong thực tế.
        rows = execute_select(graph, query, max_rows=100_000)
        found = sorted(str(row["label"]) for row in rows)
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

    vocabulary = vocabulary or DEFAULT_VOCABULARY
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

Mọi câu hỏi về học vụ: GỌI `lookup_academic_information` TRƯỚC, rồi mới trả lời dựa trên kết
quả trả về. Chưa gọi công cụ thì chưa được trả lời. Công cụ không có dữ kiện thì
nói là không tìm thấy, đừng suy đoán và đừng bịa số.

Khi công cụ trả `co_du_lieu`, đọc hết `du_lieu` rồi coi đó là kết quả cuối của
chủ đề. Nếu chi tiết được hỏi không xuất hiện, nói dữ liệu hiện có không chứa
chi tiết ấy; không đổi từ khoá để tra tiếp.

Câu hỏi có nhiều chủ đề độc lập: tách và gọi đúng một lần cho từng chủ đề trước
khi trả lời; không bỏ sót vế nào.

Hỏi tuyển sinh kèm năm thì gửi cụm "tuyển sinh" không mang năm; quy chế trong dữ
liệu là bản hiện hành.

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


def _bounded_keywords(
    keywords: Sequence[str] | str,
) -> tuple[list[str], dict[str, int] | None]:
    """Chuẩn hoá đầu vào công cụ và giữ thời gian một lượt có giới hạn."""

    raw_keywords = [keywords] if isinstance(keywords, str) else list(keywords)
    shortened = 0
    normalized: list[str] = []
    for keyword in raw_keywords:
        if not isinstance(keyword, str):
            continue
        cleaned = keyword.strip()
        if not cleaned:
            continue
        if len(cleaned) > MAX_KEYWORD_CHARACTERS:
            cleaned = cleaned[:MAX_KEYWORD_CHARACTERS].rstrip()
            shortened += 1
        normalized.append(cleaned)

    unique = list(dict.fromkeys(normalized))
    omitted = max(0, len(unique) - MAX_KEYWORDS_PER_LOOKUP)
    selected = unique[:MAX_KEYWORDS_PER_LOOKUP]
    if not (omitted or shortened):
        return selected, None
    return selected, {
        "so_luong_toi_da": MAX_KEYWORDS_PER_LOOKUP,
        "do_dai_toi_da": MAX_KEYWORD_CHARACTERS,
        "so_luong_bo_qua": omitted,
        "so_luong_rut_gon": shortened,
    }


def _with_truncation_notice(reply: str, notice: dict[str, int] | None) -> str:
    """Chuẩn hoá thành JSON và gắn thông tin cắt bớt vào kết quả."""

    try:
        payload = json.loads(reply)
    except (TypeError, json.JSONDecodeError):
        payload = json.loads(NO_INFORMATION_REPLY)
    if not isinstance(payload, dict):
        payload = json.loads(NO_INFORMATION_REPLY)
    if notice is not None:
        payload["tu_khoa_da_cat"] = notice
    return dump_payload(payload)


async def look_up_async(lookup, keywords: Sequence[str] | str) -> str:
    """Apply the established tool boundary before calling the shared coordinator."""

    from .generator import QueryGenerationError
    from .sparql import SparqlError

    keywords, notice = _bounded_keywords(keywords)
    try:
        reply = await lookup(keywords)
    except (QueryGenerationError, SparqlError):
        reply = NO_INFORMATION_REPLY
    return _with_truncation_notice(reply, notice)
