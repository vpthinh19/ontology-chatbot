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
import os
import secrets
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Sequence

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
#: Số lượt trả lời được chạy cùng lúc. Hồ sơ khởi động có thể thu hẹp hoặc nới
#: cửa này, nhưng mặc định luôn hữu hạn để một đợt dồn không chiếm hết tài nguyên.
#:
#: Cửa tính theo lượt trả lời chứ không theo request HTTP, vì một tin nhắn tiêu ít
#: nhất hai lượt gọi mô hình - đếm request là đếm sai thứ cần giữ. Nhưng nó cũng
#: không chặn từng lượt gọi một: chúng nằm giữa một lượt trả lời, mà chặn đúng lúc
#: mô hình vừa tra cứu xong thì người dùng nhận nửa câu trả lời, tệ hơn là bị từ
#: chối ngay từ đầu. Vào được thì chạy trọn vẹn.
MAX_CONCURRENT_TURNS = 16
#: Hàng đợi có trần, để một đợt dồn bất ngờ không thành hàng dài mà ai cũng bỏ đi
#: trước khi tới lượt.
MAX_QUEUED_TURNS = 64
#: Chờ quá mức này thì nói thẳng là đang bận, thay vì để người ta ngồi nhìn màn
#: hình trống - đằng nào họ cũng bấm lại, và lần bấm đó chiếm thêm một chỗ.
#:
#: Nền tảng triển khai tự cắt một request đang mở, nên hạn này cộng với hạn chờ
#: mô hình phải nằm gọn dưới mức đó, xem ``MAX_REQUEST_SECONDS``.
MAX_QUEUE_WAIT_SECONDS = 15.0
#: Mức mà nền tảng triển khai cắt một request còn đang mở. Không phải hằng số ta
#: chọn - nó là ràng buộc từ bên ngoài, chép vào đây để phép kiểm canh được.
#:
#: Vượt mức này thì kết nối bị cắt giữa chừng và người dùng mất câu trả lời, lại
#: còn mất luôn câu báo lỗi tử tế của ta. Nới hạn chờ mô hình hay hạn chờ hàng
#: đợi thì phải nhìn lại tổng, chứ hai con số đó cộng lại mới là thứ nền tảng đo.
MAX_REQUEST_SECONDS = 60.0
#: Trần số bước mô hình được đi trong một lượt. Một câu hỏi bình thường đi hai
#: bước: một để quyết định tra cứu, một để viết câu trả lời. Mặc định của thư viện
#: là mười, nên nếu không đặt thì một câu làm mô hình loay hoay tốn gấp năm lần
#: bình thường mà không có gì cản. Trần này nhân với số lượt chạy cùng lúc mới ra
#: tổng số lượt gọi có thể đang bay.
MAX_MODEL_STEPS = 4
_BUSY_MESSAGE = (
    "Hệ thống đang có nhiều người hỏi cùng lúc. Bạn chờ một chút rồi gửi lại nhé."
)
_QUEUE_TIMEOUT_MESSAGE = (
    "Hệ thống vẫn đang bận nên chưa tới lượt bạn. Bạn thử gửi lại sau ít phút nhé."
)
_TOO_MANY_STEPS_MESSAGE = (
    "Câu hỏi này làm mình tra đi tra lại mà chưa ra kết quả. Bạn thử hỏi ngắn hơn, "
    "hoặc tách thành từng ý nhỏ."
)
_LEGACY_EVENT_KINDS = {
    "text_delta": "chu",
    "lookup_started": "tra_cuu",
    "lookup_finished": "tra_cuu_xong",
    "queued": "hang_doi",
    "warning": "canh_bao",
    "completed": "xong",
    "error": "loi",
}
#: 256 KiB rộng hơn nhiều so với 20 tin nhắn hội thoại học vụ thông thường,
#: nhưng đủ nhỏ để mỗi kết nối đang đọc body có mức dùng bộ nhớ hữu hạn.
MAX_REQUEST_BODY_BYTES = 256 * 1024
_REQUEST_TOO_LARGE_MESSAGE = "Yêu cầu quá lớn; kích thước tối đa là 256 KiB."
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

    payload = {"type": kind, **fields, "loai": _LEGACY_EVENT_KINDS[kind]}
    if "content" in fields:
        payload["noi_dung"] = fields["content"]
    if "keywords" in fields:
        payload["tu_khoa"] = fields["keywords"]
    if "position" in fields:
        payload["vi_tri"] = fields["position"]
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


class TurnGate:
    """Cửa vào giữ số lượt trả lời chạy cùng lúc trong một mức đã định.

    Thả theo chỗ trống chứ không theo nhịp đồng hồ. Một lượt dài từ nửa giây tới
    45 giây, nên nhịp thả cố định buộc phải đoán trước thời gian đó: đoán nhanh
    thì các lượt chồng lên nhau - đúng cái cửa này sinh ra để tránh - còn đoán
    chậm thì máy ngồi không trong lúc hàng vẫn dài. Xong một lượt là thả ngay
    lượt kế tiếp, khỏi đoán, và khỏi chỉnh lại khi tốc độ mô hình thay đổi.
    """

    def __init__(
        self,
        slots: int = MAX_CONCURRENT_TURNS,
        queue_size: int = MAX_QUEUED_TURNS,
        max_wait_seconds: float = MAX_QUEUE_WAIT_SECONDS,
    ) -> None:
        self._slots = asyncio.Semaphore(slots)
        self._queue_size = queue_size
        self._max_wait = max_wait_seconds
        self._waiting = 0

    def join(self) -> int | None:
        """Giữ chỗ cho một lượt vừa tới.

        Trả về 0 khi vào thẳng được, vị trí trong hàng đếm từ 1 khi phải chờ, và
        ``None`` khi hàng đã đầy.

        Chỗ được giữ ngay tại đây chứ không đợi tới lúc chờ thật, vì giữa hai
        việc đó có một sự kiện đi ra trình duyệt - tức là một lần nhường quyền
        chạy, đủ để những lượt tới sau chen vào và làm hàng dài quá trần.
        """

        if not self._slots.locked():
            return 0
        if self._waiting >= self._queue_size:
            return None
        self._waiting += 1
        return self._waiting

    def leave(self) -> None:
        """Trả lại chỗ trong hàng cho một lượt không còn chờ nữa."""

        self._waiting -= 1

    async def acquire(self, queued: bool) -> None:
        """Chờ tới lượt; ném ``TimeoutError`` nếu chờ quá lâu.

        Lượt vào thẳng không đặt hạn chờ: nó không hề chờ, và ``join`` vừa nói là
        còn chỗ ngay trước đó mà không có lần nhường quyền chạy nào ở giữa.
        """

        async with asyncio.timeout(self._max_wait if queued else None):
            await self._slots.acquire()

    def release(self) -> None:
        self._slots.release()


async def _stream(
    agent, message: str, history: Sequence[Any], gate: TurnGate
) -> AsyncIterator[str]:
    conversation, history_trimmed = _bounded_history(history)
    turn = uuid.uuid4().hex[:12]
    started = time.perf_counter()
    lookups = 0
    answer = ""
    queue_ms = 0.0
    sse_events = 0
    sse_bytes = 0

    def emit(kind: str, **fields: Any) -> str:
        nonlocal sse_events, sse_bytes
        chunk = _event(kind, **fields)
        sse_events += 1
        sse_bytes += len(chunk.encode("utf-8"))
        return chunk
    # Người đọc nhật ký cần phân biệt từng kết cục, vì chúng cần những cách sửa
    # khác nhau: xong bình thường, quá hạn chờ model, chạm trần số bước, bị từ
    # chối vì hàng đầy, chờ trong hàng quá lâu, lỗi, và người dùng đóng tab giữa
    # chừng. Kết cục cuối trước đây không để lại dấu vết nào và trông y hệt một
    # lượt treo. Ba kết cục dính tới cửa vào tách riêng nhau vì chúng đòi ba
    # phản ứng khác hẳn: nới cửa, nới hàng, hay chấp nhận là đang quá tải thật.
    outcome = "abandoned"
    # Chỗ trong hàng và chỗ chạy đều được nhả ở ``finally``, nên phải biết mình
    # đang giữ cái nào: một lượt bị đóng giữa chừng có thể đang giữ chỗ trong
    # hàng mà chưa bao giờ được chạy.
    queued = False
    holding = False
    logger.debug("turn=%s question=%r history=%d", turn, message, len(conversation))
    conversation.append({"role": "user", "content": message})
    try:
        place = gate.join()
        if place is None:
            outcome = "busy"
            yield emit("error", content=_BUSY_MESSAGE)
            return
        queued = place > 0
        if queued:
            # Xếp hàng mà im lặng thì nhìn y hệt hệ thống treo, nên vị trí phải
            # ra tới trình duyệt trước khi bắt đầu chờ chứ không phải sau.
            yield emit("queued", position=place)
        try:
            queue_started = time.perf_counter()
            try:
                await gate.acquire(queued)
            finally:
                queue_ms = (time.perf_counter() - queue_started) * 1000
        except TimeoutError:
            outcome = "queue-timeout"
            yield emit("error", content=_QUEUE_TIMEOUT_MESSAGE)
            return
        finally:
            # Nhả chỗ trong hàng ngay khi hết chờ, chờ được hay không cũng vậy.
            # Giữ nó tới cuối lượt thì hàng trông đầy hơn thực tế và từ chối
            # những người lẽ ra còn chỗ.
            if queued:
                gate.leave()
                queued = False
        holding = True
        import httpx

        from .agent import AgentLoopLimitError

        try:
            async with asyncio.timeout(MODEL_TURN_TIMEOUT_SECONDS):
                if history_trimmed:
                    yield emit("warning", content=_HISTORY_TRIMMED_MESSAGE)
                completed = False
                async for event in agent.stream(conversation):
                    if event.kind == "text_delta" and event.content:
                        yield emit("text_delta", content=event.content)
                    elif event.kind == "lookup_started":
                        keywords = " · ".join(event.keywords)
                        lookups += 1
                        logger.debug("turn=%s lookup=%r", turn, keywords)
                        yield emit("lookup_started", keywords=keywords)
                    elif event.kind == "lookup_finished":
                        yield emit("lookup_finished")
                    elif event.kind == "completed":
                        answer = event.content or _EMPTY_ANSWER
                        outcome = "ok"
                        completed = True
                        yield emit("completed", content=answer)
                if not completed:
                    answer = _EMPTY_ANSWER
                    outcome = "ok"
                    yield emit("completed", content=answer)
        except (TimeoutError, httpx.TimeoutException):
            outcome = "timeout"
            yield emit("error", content=_MODEL_TIMEOUT_MESSAGE)
            return
        except AgentLoopLimitError:
            # Ghi ở mức cảnh báo chứ không phải lỗi: trần này do ta đặt, và nếu
            # có câu hỏi thật cần nhiều bước hơn thì đây là chỗ nó lộ ra.
            outcome = "too-many-steps"
            logger.warning("turn=%s hit the ceiling of %d steps", turn, MAX_MODEL_STEPS)
            yield emit("error", content=_TOO_MANY_STEPS_MESSAGE)
            return
        except Exception as exc:  # pragma: no cover - phụ thuộc dịch vụ bên ngoài.
            outcome = "error"
            logger.exception("turn=%s failed", turn)
            yield emit("error", content=str(exc))
            return
    finally:
        # Trong ``finally`` để một lượt luôn nhả chỗ và luôn đóng sổ, kể cả khi
        # trình duyệt ngắt kết nối giữa chừng và bộ sinh này bị đóng ngay tại một
        # ``yield``. Không có nhánh này thì mỗi tab đóng lúc đang xếp hàng ăn mất
        # một chỗ vĩnh viễn, và cửa vào tự bóp nghẹt chính nó.
        if queued:
            gate.leave()
        if holding:
            gate.release()
        logger.info(
            "turn=%s outcome=%s lookups=%d queue_ms=%.1f sse_events=%d "
            "sse_bytes=%d answer_chars=%d total_ms=%.1f",
            turn,
            outcome,
            lookups,
            queue_ms,
            sse_events,
            sse_bytes,
            len(answer),
            (time.perf_counter() - started) * 1000,
        )
        logger.debug("turn=%s answer=%r", turn, answer)


def create_app(
    agent,
    gate: TurnGate | None = None,
    *,
    backend_token: str | None = None,
):
    try:
        from starlette.applications import Starlette
        from starlette.middleware.cors import CORSMiddleware
        from starlette.requests import Request
        from starlette.responses import JSONResponse, StreamingResponse
        from starlette.routing import Route
    except ImportError as exc:  # pragma: no cover - requires inference extra.
        raise RuntimeError("install the inference extra to serve the API") from exc

    gate = gate if gate is not None else TurnGate()

    def authorize(request: Request):
        if backend_token is None:
            return None
        scheme, separator, candidate = request.headers.get(
            "authorization", ""
        ).partition(" ")
        authorized = (
            separator == " "
            and scheme.lower() == "bearer"
            and secrets.compare_digest(
                candidate.encode("utf-8"), backend_token.encode("utf-8")
            )
        )
        if authorized:
            return None
        return JSONResponse(
            {"detail": "Unauthorized"},
            status_code=401,
            headers={"WWW-Authenticate": "Bearer"},
        )

    def error(status_code: int, detail: str):
        return JSONResponse({"detail": detail}, status_code=status_code)

    async def health(request: Request):
        denied = authorize(request)
        return denied or JSONResponse({"status": "ok"})

    async def chat(request: Request):
        denied = authorize(request)
        if denied is not None:
            return denied
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                declared_size = int(content_length)
            except ValueError:
                return error(400, "Content-Length must be an integer")
            if declared_size > MAX_REQUEST_BODY_BYTES:
                return error(413, _REQUEST_TOO_LARGE_MESSAGE)

        body = bytearray()
        async for chunk in request.stream():
            if len(body) + len(chunk) > MAX_REQUEST_BODY_BYTES:
                return error(413, _REQUEST_TOO_LARGE_MESSAGE)
            body.extend(chunk)
        try:
            payload = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return error(400, "request body must be valid JSON")
        if not isinstance(payload, dict):
            return error(400, "request body must be an object")

        message = payload.get("message")
        if not isinstance(message, str) or not message.strip():
            return error(400, "message must be non-empty text")
        history = payload.get("history") or []
        if not isinstance(history, list):
            return error(400, "history must be a list")
        return StreamingResponse(
            _stream(agent, message.strip(), history, gate),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @asynccontextmanager
    async def lifespan(_app):
        try:
            yield
        finally:
            close = getattr(agent, "aclose", None)
            if close is not None:
                await close()

    app = Starlette(
        routes=[
            Route("/health", health, methods=["GET"]),
            Route("/chat", chat, methods=["POST"]),
        ],
        lifespan=lifespan,
    )
    frontend_origins = [
        origin.strip().rstrip("/")
        for origin in os.environ.get("ONTCHATBOT_CORS_ORIGINS", "").split(",")
        if origin.strip()
    ]
    if frontend_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=frontend_origins,
            allow_methods=["GET", "POST", "OPTIONS"],
            # ``Authorization`` mang khoá đi qua cổng đứng trước dịch vụ. Trình
            # duyệt hỏi trước bằng một request ``OPTIONS`` và chỉ gửi request
            # thật khi header đó nằm trong danh sách này, nên bỏ sót nó thì mọi
            # lượt chat từ frontend khác domain đều chết ngay ở bước hỏi trước.
            allow_headers=["Authorization", "Content-Type"],
            max_age=600,
        )

    return app
