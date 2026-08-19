"""Giao diện HTTP: một trợ lý hội thoại, trả lời theo lối chảy dần.

Người dùng nói chuyện với mô hình ngôn ngữ lớn, không nói chuyện với đồ thị.
Đồ thị đứng sau một công cụ mà mô hình gọi khi cần dữ kiện, nên tầng này chỉ
làm hai việc: chuyển lượt nói vào trợ lý, và đẩy sự kiện ra ngay khi có.

Đẩy dần chứ không chờ trọn câu trả lời, vì một lượt có thể gồm vài lần tra cứu
cộng một đoạn văn được viết ra từng chữ; chờ xong mới hiện là để người dùng nhìn
màn hình trống suốt quãng đó.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, AsyncIterator, Sequence

from ..settings import PROJECT_ROOT

#: Vai được phép có trong lịch sử hội thoại do trình duyệt gửi lên.
_ROLES = ("user", "assistant")
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


def _conversation(message: str, history: Sequence[Any]) -> list[dict[str, str]]:
    """Ghép lịch sử với lượt mới thành đầu vào cho trợ lý.

    Lịch sử do trình duyệt giữ và gửi lên, nên phải lọc: chỉ nhận đúng hai vai
    và nội dung là chữ. Máy chủ không giữ phiên nào, nhờ vậy chạy nhiều bản sao
    không cần chia sẻ trạng thái.
    """

    turns = []
    for item in history:
        if not isinstance(item, dict):
            continue
        role, content = item.get("role"), item.get("content")
        if role in _ROLES and isinstance(content, str) and content.strip():
            turns.append({"role": role, "content": content})
    turns.append({"role": "user", "content": message})
    return turns


def _event(kind: str, **fields: Any) -> str:
    """Một sự kiện theo khuôn server-sent events."""

    return f"data: {json.dumps({'loai': kind, **fields}, ensure_ascii=False)}\n\n"


async def _stream(agent, message: str, history: Sequence[Any]) -> AsyncIterator[str]:
    from agents import Runner

    result = Runner.run_streamed(agent, _conversation(message, history))
    try:
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
                    yield _event("tra_cuu", tu_khoa=_tool_input(event.item))
                elif event.name == "tool_output":
                    yield _event("tra_cuu_xong")
    except Exception as exc:  # pragma: no cover - phụ thuộc dịch vụ bên ngoài.
        yield _event("loi", noi_dung=str(exc))
        return
    yield _event("xong", noi_dung=str(result.final_output or "") or _EMPTY_ANSWER)


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
    except ImportError as exc:  # pragma: no cover - requires inference extra.
        raise RuntimeError("install the inference extra to serve the API") from exc

    app = FastAPI(title="NTU Ontology Chatbot", version="0.4.1")

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/chat")
    async def chat(payload: dict):
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

    static_dir = webui_dir or PROJECT_ROOT / "webui"
    if static_dir.is_dir():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="webui")
    return app
