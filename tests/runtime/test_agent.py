"""Canh hợp đồng giữa trợ lý và công cụ tra cứu.

Mô hình ngôn ngữ chỉ thấy hai thứ trước khi quyết định gọi công cụ: khuôn nhắc
hệ thống và mô tả công cụ. Cả hai là văn bản, nên chúng hỏng lặng lẽ - không có
ngoại lệ nào được ném ra khi một hướng dẫn biến mất, chỉ có chất lượng câu trả
lời tụt xuống mà không rõ vì sao.
"""

from __future__ import annotations

import asyncio
import json
import pytest
from types import SimpleNamespace

from ontchatbot.runtime.agent import (
    MAX_KEYWORD_CHARACTERS,
    MAX_KEYWORDS_PER_LOOKUP,
    TOOL_DESCRIPTION,
    OntologyVocabulary,
    build_agent,
    build_instructions,
    build_tool,
    look_up,
    look_up_async,
)

pytest.importorskip("agents", reason="cần thư viện openai-agents")


class _StubChatbot:
    """Đứng thay đường tra cứu thật để phép kiểm không cần model lẫn đồ thị."""

    def __init__(self) -> None:
        self.asked: list[str] = []

    def answer(self, question: str) -> str:
        self.asked.append(question)
        return f"dữ kiện của {question}"


VOCABULARY = OntologyVocabulary(
    procedures=("Thủ tục nghỉ học tạm thời",),
    units=("Phòng Đào tạo Đại học",),
    forms=("Mục tải: Đơn xin hoãn thi",),
    programs=("Công nghệ thông tin",),
)


def test_tool_tells_the_model_to_send_keywords_not_sentences() -> None:
    """Hướng dẫn rút câu hỏi thành từ khoá phải tới được mô hình.

    Thư viện chỉ lấy câu tóm tắt và đoạn đầu của chú thích làm mô tả công cụ,
    nên phần ví dụ từng bị cắt mất mà không có dấu hiệu nào.
    """

    description = build_tool(_StubChatbot()).description

    assert "TỪ KHOÁ NGẮN" in description
    assert "Nên:" in description and "Không nên:" in description
    # Một ví dụ của mỗi phía: dạng nên gửi, và dạng câu hỏi đầy đủ nên tránh.
    assert "đăng ký học phần" in description
    assert "Hãy hướng dẫn tôi cách đăng ký học phần nhé" in description


def test_tool_passes_the_keyword_through_unchanged() -> None:
    chatbot = _StubChatbot()
    tool = build_tool(chatbot)

    assert tool.name == "tra_cuu_hoc_vu"
    assert tool.params_json_schema["required"] == ["tu_khoa"]
    assert tool.params_json_schema["properties"]["tu_khoa"]["description"]


def test_instructions_name_what_the_assistant_can_look_up() -> None:
    """Khuôn nhắc phải nêu phạm vi dữ liệu, nếu không mô hình gọi công cụ cho cả
    câu ngoài miền và trả về câu từ chối thay vì trả lời thẳng."""

    instructions = build_instructions(VOCABULARY)

    # Tên xuất hiện sau khi bỏ tiền tố phân loại của ontology: người dùng gọi
    # "nghỉ học tạm thời", không gọi "Thủ tục nghỉ học tạm thời".
    for name in (
        "nghỉ học tạm thời",
        "Phòng Đào tạo Đại học",
        "Đơn xin hoãn thi",
        "Công nghệ thông tin",
    ):
        assert name in instructions, name


def test_instructions_forbid_answering_from_memory() -> None:
    """Ranh giới của hệ thống: mô hình diễn đạt, đồ thị giữ dữ kiện."""

    instructions = build_instructions(VOCABULARY)

    assert "tra_cuu_hoc_vu" in instructions
    assert "đừng suy đoán" in instructions
    assert "đừng bịa số" in instructions
    # Quy tắc gọi công cụ phải đứng TRƯỚC danh sách chủ đề. Đảo lại thì nó bị
    # chôn giữa một khối tên dài và tỉ lệ gọi công cụ tụt hẳn.
    assert instructions.index("GỌI `tra_cuu_hoc_vu` TRƯỚC") < instructions.index("Thủ tục:")
    # Trích dẫn và đường dẫn phải đi tới câu trả lời cuối, nếu không người đọc
    # mất đường đối chiếu với văn bản gốc.
    assert "trích dẫn" in instructions and "đường dẫn" in instructions


def test_instructions_are_built_from_the_graph_not_written_by_hand() -> None:
    """Danh sách chép tay mục dần: ontology thêm một thủ tục thì khuôn nhắc vẫn
    nói cái cũ. Tên trong khuôn nhắc phải đến từ từ vựng truyền vào."""

    other = OntologyVocabulary(
        procedures=("Thủ tục chuyển trường",), units=(), forms=(), programs=()
    )

    assert "chuyển trường" in build_instructions(other)
    assert "nghỉ học tạm thời" not in build_instructions(other)


def test_tool_description_is_the_shared_constant() -> None:
    assert build_tool(_StubChatbot()).description == TOOL_DESCRIPTION.strip()


def test_tool_teaches_the_model_to_read_the_structured_result_and_stop() -> None:
    description = build_tool(_StubChatbot()).description

    assert "JSON" in description
    assert "du_lieu" in description and "nguon" in description
    # Cách gọi nhiều từ khoá một lượt phải nằm trong mô tả, nếu không mô hình
    # gửi từng cụm một và mất đúng phần lợi của việc đổi sang danh sách.
    assert "DANH SÁCH" in description
    assert "tu_khoa_khong_thay" in description
    assert "không xuất hiện" in description
    assert "ĐỪNG gọi lại" in description
    assert "tu_khoa_da_cat" in description


def test_instructions_require_one_lookup_for_every_topic() -> None:
    instructions = build_instructions(VOCABULARY)

    assert "Câu hỏi có nhiều chủ đề độc lập" in instructions
    assert "đúng một lần cho từng chủ đề" in instructions
    assert "Không suy" in instructions and "luận" in instructions
    assert "bảng chung cho một ngành cụ thể" in instructions


def test_system_prompt_stays_below_four_hundred_words() -> None:
    assert len(build_instructions().split()) < 400


def test_a_broken_lookup_reaches_the_assistant_as_no_information() -> None:
    """Truy vấn hỏng và không tìm thấy là một thứ đối với người gọi.

    Trợ lý đọc trạng thái trong kết quả để quyết định tra lại hay dừng. Một
    ngoại lệ không mang trạng thái đó, nên nó làm hỏng lượt chạy giữa cuộc hội
    thoại thay vì thành một câu trả lời trung thực.
    """

    from types import SimpleNamespace

    from ontchatbot.runtime.generator import QueryGenerationError
    from ontchatbot.runtime.render import NO_INFORMATION_REPLY
    from ontchatbot.runtime.sparql import SparqlError

    for error in (QueryGenerationError("rỗng"), SparqlError("sai cú pháp")):
        def fail(_, error=error) -> str:
            raise error

        assert look_up(SimpleNamespace(answer_many=fail), ["học phí"]) == NO_INFORMATION_REPLY

    ok = SimpleNamespace(
        answer_many=lambda ds: json.dumps({"trang_thai": "co_du_lieu", "du_lieu": ds})
    )
    assert json.loads(look_up(ok, ["học phí", "học bổng"]))["du_lieu"] == [
        "học phí",
        "học bổng",
    ]
    # Một chuỗi lẻ vẫn tra được: mô hình đôi khi gửi chuỗi thay vì danh sách.
    assert json.loads(look_up(ok, "học phí"))["du_lieu"] == ["học phí"]


def test_lookup_caps_keyword_count_and_length_and_reports_it_as_json() -> None:
    """Bỏ giới hạn sẽ để quá 45 giây khi mô hình gửi một danh sách dài."""

    seen = []

    def answer_many(keywords):
        seen.extend(keywords)
        return '{"trang_thai": "khong_co_thong_tin", "du_lieu": [], "nguon": []}'

    long_keyword = "x" * (MAX_KEYWORD_CHARACTERS + 1)
    reply = look_up(
        SimpleNamespace(answer_many=answer_many),
        [long_keyword, *(f"từ khoá {index}" for index in range(MAX_KEYWORDS_PER_LOOKUP + 2))],
    )

    payload = json.loads(reply)
    assert len(seen) == MAX_KEYWORDS_PER_LOOKUP
    assert all(len(keyword) <= MAX_KEYWORD_CHARACTERS for keyword in seen)
    assert payload["tu_khoa_da_cat"] == {
        "so_luong_toi_da": MAX_KEYWORDS_PER_LOOKUP,
        "do_dai_toi_da": MAX_KEYWORD_CHARACTERS,
        "so_luong_bo_qua": 3,
        "so_luong_rut_gon": 1,
    }


def test_async_tool_bounds_keywords_before_shared_lookup() -> None:
    """The shared coordinator only receives normalized, bounded keywords."""

    seen = []

    async def lookup(keywords):
        seen.append(keywords)
        return json.dumps({"trang_thai": "co_du_lieu", "du_lieu": keywords})

    result = asyncio.run(
        look_up_async(
            lookup,
            ["học phí", "học phí", "x" * (MAX_KEYWORD_CHARACTERS + 1)],
        )
    )

    payload = json.loads(result)
    assert seen == [["học phí", "x" * MAX_KEYWORD_CHARACTERS]]
    assert payload["tu_khoa_da_cat"]["so_luong_rut_gon"] == 1


def test_async_tool_keeps_domain_errors_as_no_information() -> None:
    """A failing cached lookup remains a model-readable result, not a tool error."""

    from ontchatbot.runtime.generator import QueryGenerationError
    from ontchatbot.runtime.render import NO_INFORMATION_REPLY
    from ontchatbot.runtime.sparql import SparqlError

    for error in (QueryGenerationError("rỗng"), SparqlError("sai cú pháp")):
        async def fail(_keywords, error=error):
            raise error

        assert asyncio.run(look_up_async(fail, ["học phí"])) == NO_INFORMATION_REPLY

    async def unexpected(_keywords):
        raise RuntimeError("mất kết nối")

    with pytest.raises(RuntimeError, match="mất kết nối"):
        asyncio.run(look_up_async(unexpected, ["học phí"]))


def test_tool_creates_one_configured_shared_lookup_pool(monkeypatch) -> None:
    """Recreating the pool per call would discard both cache layers."""

    created = []

    class FakePool:
        def __init__(self, chatbot, **kwargs) -> None:
            created.append((chatbot, kwargs))

        async def __call__(self, keywords) -> str:
            return json.dumps({"trang_thai": "co_du_lieu", "du_lieu": keywords})

    monkeypatch.setattr("ontchatbot.runtime.agent.AsyncLookupPool", FakePool)
    monkeypatch.setattr(
        "agents.function_tool", lambda **_kwargs: lambda function: function
    )

    chatbot = _StubChatbot()
    tool = build_tool(
        chatbot,
        lookup_workers=3,
        classification_cache_entries=17,
        sparql_cache_bytes=23,
    )

    assert created == [
        (
            chatbot,
            {
                "workers": 3,
                "classification_cache_entries": 17,
                "sparql_cache_bytes": 23,
            },
        )
    ]
    assert json.loads(asyncio.run(tool(["học phí"]))) == {
        "trang_thai": "co_du_lieu",
        "du_lieu": ["học phí"],
    }


def test_the_assistant_does_not_think_at_the_lowest_effort() -> None:
    """Mức suy luận thấp đổi được tốc độ, nhưng có lúc không viết câu nào.

    Đo trên 24 lượt: mức thấp cho ba lượt trả về rỗng, mức mặc định không lượt
    nào. Một bong bóng trống là hỏng nặng hơn phần lợi nó mang lại.
    """

    from ontchatbot.runtime.agent import REASONING_EFFORT

    assert REASONING_EFFORT != "low"


def test_every_model_request_has_an_explicit_timeout_and_one_retry(monkeypatch) -> None:
    """Bỏ cấu hình sẽ để client quay về 600 giây và hai lần thử lại."""

    import agents
    import openai

    client_options = {}

    def fake_client(**kwargs):
        client_options.update(kwargs)
        return SimpleNamespace()

    monkeypatch.setattr(openai, "AsyncOpenAI", fake_client)
    monkeypatch.setattr(agents, "Agent", lambda **kwargs: SimpleNamespace(**kwargs))
    monkeypatch.setattr(
        agents,
        "OpenAIChatCompletionsModel",
        lambda **kwargs: SimpleNamespace(**kwargs),
    )
    monkeypatch.setattr(agents, "set_tracing_disabled", lambda _: None)
    monkeypatch.setattr("ontchatbot.runtime.agent.build_instructions", lambda: "prompt")
    tool_options = {}

    def fake_build_tool(
        _, *, lookup_workers, classification_cache_entries, sparql_cache_bytes
    ):
        tool_options["lookup_workers"] = lookup_workers
        tool_options["classification_cache_entries"] = classification_cache_entries
        tool_options["sparql_cache_bytes"] = sparql_cache_bytes
        return "tool"

    monkeypatch.setattr("ontchatbot.runtime.agent.build_tool", fake_build_tool)

    build_agent(_StubChatbot(), model="mo-hinh")

    assert client_options["timeout"] == 30.0
    assert client_options["max_retries"] == 1
    assert tool_options == {
        "lookup_workers": 4,
        "classification_cache_entries": 4096,
        "sparql_cache_bytes": 64 * 1024 * 1024,
    }
