"""Giao diện HTTP: một trợ lý hội thoại, trả lời theo lối chảy dần.

Người dùng nói chuyện với mô hình ngôn ngữ lớn, không nói chuyện với đồ thị.
Đồ thị đứng sau một công cụ mà mô hình gọi khi cần dữ kiện, nên tầng này chỉ
làm hai việc: chuyển lượt nói vào trợ lý, và đẩy sự kiện ra ngay khi có.

Đẩy dần chứ không chờ trọn câu trả lời, vì một lượt có thể gồm vài lần tra cứu
cộng một đoạn văn được viết ra từng chữ; chờ xong mới hiện là để người dùng nhìn
màn hình trống suốt quãng đó.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from pathlib import Path
from typing import Any, AsyncIterator, Sequence

from ..settings import PROJECT_ROOT

#: Nhật ký của tầng này là chỗ duy nhất thấy được trọn một lượt: câu người dùng
#: gõ, mỗi lần trợ lý tra cứu, câu trả lời cuối, và thời gian cả lượt. Các tầng
#: dưới chỉ thấy từ khoá đã được rút gọn, nên đọc riêng chúng thì không biết
#: người hỏi gì và trợ lý đáp gì.
#:
#: Đánh đổi: nhật ký chứa nội dung người dùng nhập. Đây là dịch vụ học vụ không
#: đăng nhập, không kèm danh tính, nhưng ai đọc được terminal thì đọc được câu hỏi.
logger = logging.getLogger(__name__)

#: Vai được phép có trong lịch sử hội thoại do trình duyệt gửi lên.
_ROLES = ("user", "assistant")
#: Mười cặp tin nhắn gần nhất đủ giữ mạch cho các câu hỏi nối tiếp, đồng thời
#: chặn chi phí và ngữ cảnh mô hình tăng mãi theo tuổi của tab trình duyệt.
#: System prompt thuộc ``Agent.instructions``, nằm ngoài lát cắt lịch sử này.
MAX_HISTORY_MESSAGES = 20
#: Thông báo này đi riêng khỏi câu trả lời để người dùng biết ngữ cảnh cũ đã bị
#: bỏ mà nội dung vận hành không bị ghi ngược vào lịch sử như lời của trợ lý.
_HISTORY_TRIMMED_MESSAGE = (
    "Cuộc trò chuyện đã dài nên mình chỉ dùng 20 tin nhắn gần nhất; "
    "các lượt cũ hơn không còn nằm trong ngữ cảnh."
)
#: Hạn toàn lượt rộng hơn hai lần p95 10,8 giây và hơn hai lần đỉnh vận hành
#: 20,3 giây. Nó bao trọn các vòng gọi công cụ nhưng vẫn kết thúc hữu hạn khi
#: một luồng model không đóng hoặc nhiều lần gọi nối nhau cùng chậm.
MODEL_TURN_TIMEOUT_SECONDS = 45.0
_MODEL_TIMEOUT_MESSAGE = (
    "Mô hình đã quá thời gian chờ. Bạn vui lòng thử lại, hoặc hỏi ngắn hơn."
)
#: 256 KiB rộng hơn nhiều so với 20 tin nhắn hội thoại học vụ thông thường,
#: nhưng đủ nhỏ để mỗi kết nối đang đọc body có mức dùng bộ nhớ hữu hạn.
MAX_REQUEST_BODY_BYTES = 256 * 1024
_REQUEST_TOO_LARGE_MESSAGE = "Yêu cầu quá lớn; kích thước tối đa là 256 KiB."
#: Mô hình phát hai luồng chữ: phần lập luận riêng của nó, và câu trả lời. Chỉ
#: câu trả lời mới thuộc về người đọc; phần lập luận là tiếng Anh, dài gấp rưỡi,
#: và nói về việc soạn câu chứ không nói về học vụ.
_ANSWER_DELTA = "response.output_text.delta"
#: Một lượt chạy có thể kết thúc mà mô hình không viết câu nào - nó gọi công cụ
#: rồi dừng. Người dùng không phân biệt được chuyện đó với hệ thống treo, nên
#: khoảng trống phải thành một câu nói rõ là chưa có câu trả lời.
_EMPTY_ANSWER = (
    "Xin lỗi, mình chưa tạo được câu trả lời cho câu hỏi này. Bạn thử hỏi lại, "
    "hoặc tách thành từng ý nhỏ hơn."
)


def _bounded_history(
    history: Sequence[Any],
) -> tuple[list[dict[str, str]], bool]:
    """Lọc lịch sử do trình duyệt giữ và cắt ở phía cũ nhất."""

    turns: list[dict[str, str]] = []
    for item in history:
        if not isinstance(item, dict):
            continue
        role, content = item.get("role"), item.get("content")
        if role in _ROLES and isinstance(content, str) and content.strip():
            turns.append({"role": role, "content": content})
    trimmed = len(turns) > MAX_HISTORY_MESSAGES
    return turns[-MAX_HISTORY_MESSAGES:], trimmed


def _conversation(message: str, history: Sequence[Any]) -> list[dict[str, str]]:
    """Ghép lịch sử hợp lệ, có giới hạn với lượt mới của người dùng.

    Máy chủ không giữ phiên nào, nhờ vậy chạy nhiều bản sao không cần chia sẻ
    trạng thái. System prompt vẫn do Agent giữ và không đi qua hàm này.
    """

    turns, _ = _bounded_history(history)
    turns.append({"role": "user", "content": message})
    return turns


def _event(kind: str, **fields: Any) -> str:
    """Một sự kiện theo khuôn server-sent events."""

    return f"data: {json.dumps({'loai': kind, **fields}, ensure_ascii=False)}\n\n"


async def _stream(agent, message: str, history: Sequence[Any]) -> AsyncIterator[str]:
    from agents import Runner
    from openai import APITimeoutError

    conversation, history_trimmed = _bounded_history(history)
    turn = uuid.uuid4().hex[:12]
    started = time.perf_counter()
    lookups = 0
    answer = ""
    # Người đọc nhật ký cần phân biệt bốn kết cục, vì chúng cần bốn cách sửa:
    # xong bình thường, quá hạn chờ model, lỗi, và người dùng đóng tab giữa
    # chừng. Kết cục cuối trước đây không để lại dấu vết nào và trông y hệt một
    # lượt treo.
    outcome = "abandoned"
    logger.info("turn=%s question=%r history=%d", turn, message, len(conversation))
    conversation.append({"role": "user", "content": message})
    try:
        try:
            async with asyncio.timeout(MODEL_TURN_TIMEOUT_SECONDS):
                result = Runner.run_streamed(agent, conversation)
                if history_trimmed:
                    yield _event("canh_bao", noi_dung=_HISTORY_TRIMMED_MESSAGE)
                async for event in result.stream_events():
                    if event.type == "raw_response_event":
                        if getattr(event.data, "type", None) != _ANSWER_DELTA:
                            continue
                        delta = getattr(event.data, "delta", None)
                        if isinstance(delta, str) and delta:
                            yield _event("chu", noi_dung=delta)
                    elif event.type == "run_item_stream_event":
                        # Người dùng cần thấy trợ lý đang tra cứu, nếu không quãng chờ
                        # giữa các lần gọi công cụ trông như hệ thống đứng máy.
                        if event.name == "tool_called":
                            keywords = _tool_input(event.item)
                            lookups += 1
                            logger.info("turn=%s lookup=%r", turn, keywords)
                            yield _event("tra_cuu", tu_khoa=keywords)
                        elif event.name == "tool_output":
                            yield _event("tra_cuu_xong")
        except (TimeoutError, APITimeoutError):
            outcome = "timeout"
            yield _event("loi", noi_dung=_MODEL_TIMEOUT_MESSAGE)
            return
        except Exception as exc:  # pragma: no cover - phụ thuộc dịch vụ bên ngoài.
            outcome = "error"
            logger.exception("turn=%s failed", turn)
            yield _event("loi", noi_dung=str(exc))
            return
        answer = str(result.final_output or "") or _EMPTY_ANSWER
        outcome = "ok"
        yield _event("xong", noi_dung=answer)
    finally:
        # Trong ``finally`` để một lượt luôn đóng sổ, kể cả khi trình duyệt ngắt
        # kết nối giữa chừng và bộ sinh này bị đóng ngay tại một ``yield``.
        logger.info(
            "turn=%s outcome=%s answer=%r lookups=%d total_ms=%.1f",
            turn,
            outcome,
            answer,
            lookups,
            (time.perf_counter() - started) * 1000,
        )


def _tool_input(item: Any) -> str:
    """Từ khoá mà trợ lý gửi cho công cụ, để hiện lên giao diện."""

    raw = getattr(getattr(item, "raw_item", None), "arguments", None)
    if not isinstance(raw, str):
        return ""
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return raw
    return _flatten(parsed)


def _flatten(value: Any) -> str:
    if isinstance(value, dict):
        return " · ".join(_flatten(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return " · ".join(_flatten(item) for item in value)
    return str(value)


def create_app(agent, webui_dir: Path | None = None):
    try:
        from fastapi import FastAPI, HTTPException
        from fastapi.responses import StreamingResponse
        from fastapi.staticfiles import StaticFiles
        from starlette.requests import Request
    except ImportError as exc:  # pragma: no cover - requires inference extra.
        raise RuntimeError("install the inference extra to serve the API") from exc

    # Lấy phiên bản từ chính gói, không chép lại con số: nâng phiên bản ở một
    # chỗ thì API báo theo ngay, khỏi lệch âm thầm.
    from .. import __version__

    app = FastAPI(title="NTU Ontology Chatbot", version=__version__)

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    async def chat(request):
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                declared_size = int(content_length)
            except ValueError:
                raise HTTPException(
                    status_code=400, detail="Content-Length must be an integer"
                ) from None
            if declared_size > MAX_REQUEST_BODY_BYTES:
                raise HTTPException(status_code=413, detail=_REQUEST_TOO_LARGE_MESSAGE)

        body = bytearray()
        async for chunk in request.stream():
            if len(body) + len(chunk) > MAX_REQUEST_BODY_BYTES:
                raise HTTPException(status_code=413, detail=_REQUEST_TOO_LARGE_MESSAGE)
            body.extend(chunk)
        try:
            payload = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise HTTPException(status_code=400, detail="request body must be valid JSON") from None
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="request body must be an object")

        message = payload.get("message")
        if not isinstance(message, str) or not message.strip():
            raise HTTPException(status_code=400, detail="message must be non-empty text")
        history = payload.get("history") or []
        if not isinstance(history, list):
            raise HTTPException(status_code=400, detail="history must be a list")
        return StreamingResponse(
            _stream(agent, message.strip(), history),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    # ``Request`` là phụ thuộc tuỳ chọn được nạp trong hàm này; gắn kiểu trước
    # lúc đăng ký để FastAPI truyền request ASGI thay vì coi nó là query param.
    chat.__annotations__["request"] = Request
    app.post("/chat")(chat)

    static_dir = webui_dir or PROJECT_ROOT / "webui"
    if static_dir.is_dir():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="webui")
    return app
