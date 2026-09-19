"""Giao diện HTTP của trợ lý: nhận câu hỏi, đẩy sự kiện ra ngay khi có (server-sent events).

Máy chủ không giữ phiên hội thoại: trang gửi kèm lịch sử mỗi câu, nên nhiều bản dịch vụ chạy song
song không cần chia sẻ trạng thái.
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import secrets
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

import httpx
from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, StreamingResponse
from starlette.routing import Route

from .agent import AgentLoopLimitError
from .chatlog import new_id, summarize_lookup, valid_id
from .llm import LightningBusyError

#: Ở mức debug, nhật ký ghi cả câu hỏi và câu trả lời.
logger = logging.getLogger(__name__)

#: Vai được phép trong lịch sử do trang gửi lên.
_ROLES = ("user", "assistant")
#: Số tin nhắn lịch sử gần nhất đưa vào mô hình.
MAX_HISTORY_MESSAGES = 20
#: Hạn của cả lượt, gồm mọi lần gọi mô hình và tra cứu.
MODEL_TURN_TIMEOUT_SECONDS = 45.0
#: Số lượt chạy cùng lúc, và số lượt được xếp hàng chờ.
MAX_CONCURRENT_TURNS = 16
MAX_QUEUED_TURNS = 64
#: Chờ trong hàng quá mức này thì báo bận. Cộng với hạn của lượt phải dưới ``MAX_REQUEST_SECONDS``.
MAX_QUEUE_WAIT_SECONDS = 15.0
#: Mức nền tảng triển khai cắt một request còn mở (ràng buộc bên ngoài).
MAX_REQUEST_SECONDS = 60.0
#: Trần số bước mô hình trong một lượt; câu thường cần hai bước: tra cứu rồi viết câu trả lời.
MAX_MODEL_STEPS = 4
MAX_REQUEST_BODY_BYTES = 256 * 1024

_MODEL_TIMEOUT_MESSAGE = "Mô hình đã quá thời gian chờ. Bạn vui lòng thử lại, hoặc hỏi ngắn hơn."
_BUSY_MESSAGE = "Hệ thống đang có nhiều người hỏi cùng lúc. Bạn chờ một chút rồi gửi lại nhé."
_QUEUE_TIMEOUT_MESSAGE = "Hệ thống vẫn đang bận nên chưa tới lượt bạn. Bạn thử gửi lại sau ít phút nhé."
_MODEL_ERROR_MESSAGE = "Mình chưa kết nối được với mô hình ngôn ngữ. Bạn thử gửi lại sau ít phút nhé."
_TOO_MANY_STEPS_MESSAGE = (
    "Câu hỏi này làm mình tra đi tra lại mà chưa ra kết quả. Bạn thử hỏi ngắn hơn, "
    "hoặc tách thành từng ý nhỏ."
)
_REQUEST_TOO_LARGE_MESSAGE = "Yêu cầu quá lớn; kích thước tối đa là 256 KiB."
#: Mô hình có thể dừng mà không viết gì; người dùng vẫn phải nhận một câu.
_EMPTY_ANSWER = (
    "Xin lỗi, mình chưa tạo được câu trả lời cho câu hỏi này. Bạn thử hỏi lại, "
    "hoặc tách thành từng ý nhỏ hơn."
)


def _rate_limited_message(retry_after: float) -> str:
    seconds = max(1, math.ceil(retry_after))
    wait = f"{math.ceil(seconds / 60)} phút" if seconds >= 90 else f"{seconds} giây"
    return f"Hệ thống đang nhận quá nhiều câu hỏi. Bạn thử gửi lại sau khoảng {wait} nhé."


def conversation(message: str, history: Sequence[Any]) -> list[dict[str, str]]:
    """Lịch sử hợp lệ (bỏ vai lạ, tin rỗng; giữ ``MAX_HISTORY_MESSAGES`` tin cuối) cộng câu mới."""

    turns = [
        {"role": item["role"], "content": item["content"]}
        for item in history
        if isinstance(item, dict) and item.get("role") in _ROLES
        and isinstance(item.get("content"), str) and item["content"].strip()
    ]
    return [*turns[-MAX_HISTORY_MESSAGES:], {"role": "user", "content": message}]


class TurnGate:
    """Giữ số lượt chạy cùng lúc trong ``slots``, xếp hàng tối đa ``queue_size`` lượt.

    Xong một lượt là lượt kế tiếp vào ngay. Cửa tính theo lượt trả lời chứ không theo lần gọi
    mô hình: lượt đã vào thì chạy trọn.
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
        """Giữ chỗ ngay: 0 là vào thẳng, số dương là vị trí trong hàng, ``None`` là hàng đầy.

        Giữ ngay tại đây chứ không đợi lúc chờ thật, vì giữa hai việc đó có một lần nhường quyền
        chạy (gửi vị trí cho trang), đủ để lượt tới sau chen vào làm hàng dài quá trần.
        """

        if not self._slots.locked():
            return 0
        if self._waiting >= self._queue_size:
            return None
        self._waiting += 1
        return self._waiting

    def leave(self) -> None:
        self._waiting -= 1

    async def acquire(self, queued: bool) -> None:
        """Chờ tới lượt; ``TimeoutError`` khi chờ quá lâu. Lượt vào thẳng không đặt hạn."""

        async with asyncio.timeout(self._max_wait if queued else None):
            await self._slots.acquire()

    def release(self) -> None:
        self._slots.release()


class Turn:
    """Một lượt hỏi đáp: vào cửa, chạy trợ lý, đẩy sự kiện, rồi ghi nhật ký và lịch sử chat.

    Kết cục (``outcome``): ok · busy (hàng đầy) · queue-timeout · timeout · too-many-steps ·
    rate-limited · error · abandoned (trang đóng giữa chừng).
    """

    def __init__(
        self,
        agent,
        message: str,
        history: Sequence[Any],
        gate: TurnGate,
        chat_log=None,
        *,
        by_admin: bool = False,
        session: str | None = None,
    ) -> None:
        self.agent = agent
        self.message = message
        self.conversation = conversation(message, history)
        self.gate = gate
        self.chat_log = chat_log
        self.by_admin = by_admin
        self.id = uuid.uuid4().hex[:12]
        self.started = time.perf_counter()
        self.started_at = datetime.now().astimezone()
        self.session = session or new_id(self.started_at)
        self.outcome = "abandoned"
        self.answer = ""
        self.marks: list[str] = []
        self.lookups: list[dict] = []
        self.queue_ms = 0.0
        self._partial: list[str] = []
        self._error_text = ""
        #: Chi tiết kỹ thuật của lỗi, cho người quản trị; người dùng chỉ thấy lời báo.
        self._error_detail = ""
        self._lookups_started = 0
        self._pending_keywords: tuple[str, ...] = ()
        self._sse_events = 0
        self._sse_bytes = 0

    async def events(self) -> AsyncIterator[str]:
        logger.debug("turn=%s question=%r history=%d", self.id, self.message, len(self.conversation) - 1)
        queued = holding = False
        try:
            place = self.gate.join()
            if place is None:
                yield self._fail("busy", _BUSY_MESSAGE)
                return
            queued = place > 0
            if queued:
                yield self._emit("queued", position=place)
            waiting_since = time.perf_counter()
            try:
                await self.gate.acquire(queued)
            except TimeoutError:
                yield self._fail("queue-timeout", _QUEUE_TIMEOUT_MESSAGE)
                return
            finally:
                self.queue_ms = (time.perf_counter() - waiting_since) * 1000
                if queued:
                    self.gate.leave()
                    queued = False
            holding = True
            async for chunk in self._answer():
                yield chunk
        finally:
            # Chạy cả khi trang đóng giữa chừng: không nhả chỗ thì cửa tự nghẽn dần.
            if queued:
                self.gate.leave()
            if holding:
                self.gate.release()
            self._finish()

    async def _answer(self) -> AsyncIterator[str]:
        try:
            async with asyncio.timeout(MODEL_TURN_TIMEOUT_SECONDS):
                async for event in self.agent.stream(self.conversation):
                    chunk = self._on_event(event)
                    if chunk is not None:
                        yield chunk
                if self.outcome != "ok":
                    self.answer, self.outcome = _EMPTY_ANSWER, "ok"
                    yield self._emit("completed", content=self.answer)
        except (TimeoutError, httpx.TimeoutException):
            yield self._fail("timeout", _MODEL_TIMEOUT_MESSAGE)
        except AgentLoopLimitError:
            logger.warning("turn=%s hit the ceiling of %d steps", self.id, MAX_MODEL_STEPS)
            yield self._fail("too-many-steps", _TOO_MANY_STEPS_MESSAGE)
        except LightningBusyError as exc:
            self._error_detail = str(exc)
            logger.warning("turn=%s rate limited, retry after %.0fs", self.id, exc.retry_after)
            yield self._fail("rate-limited", _rate_limited_message(exc.retry_after))
        except Exception as exc:
            self._error_detail = f"{type(exc).__name__}: {exc}"
            logger.exception("turn=%s failed", self.id)
            yield self._fail("error", _MODEL_ERROR_MESSAGE)

    def _on_event(self, event) -> str | None:
        if event.kind == "text_delta" and event.content:
            self._partial.append(event.content)
            return self._emit("text_delta", content=event.content)
        if event.kind == "lookup_started":
            self._lookups_started += 1
            self._pending_keywords = event.keywords
            keywords = " · ".join(event.keywords)
            logger.debug("turn=%s lookup=%r", self.id, keywords)
            return self._emit("lookup_started", keywords=keywords)
        if event.kind == "lookup_finished":
            self.lookups.append(summarize_lookup(self._pending_keywords, event.content))
            return self._emit("lookup_finished")
        if event.kind == "completed":
            self.answer = event.content or _EMPTY_ANSWER
            self.marks = list(event.marks)
            self.outcome = "ok"
            return self._emit("completed", content=self.answer)
        return None

    def _emit(self, kind: str, **fields: Any) -> str:
        chunk = f"data: {json.dumps({'type': kind, **fields}, ensure_ascii=False)}\n\n"
        self._sse_events += 1
        self._sse_bytes += len(chunk.encode("utf-8"))
        return chunk

    def _fail(self, outcome: str, message: str) -> str:
        self.outcome, self._error_text = outcome, message
        return self._emit("error", content=message)

    def _finish(self) -> None:
        elapsed_ms = (time.perf_counter() - self.started) * 1000
        logger.info(
            "turn=%s outcome=%s lookups=%d queue_ms=%.1f sse_events=%d sse_bytes=%d answer_chars=%d total_ms=%.1f",
            self.id, self.outcome, self._lookups_started, self.queue_ms, self._sse_events, self._sse_bytes,
            len(self.answer), elapsed_ms,
        )
        logger.debug("turn=%s answer=%r", self.id, self.answer)
        if self.chat_log is None:
            return
        self.chat_log.submit({
            "id": new_id(self.started_at),
            "time": self.started_at.isoformat(timespec="seconds"),
            "question": self.message,
            "session": self.session,
            "answer": self.answer or "".join(self._partial),
            "outcome": self.outcome,
            "error": self._error_detail or self._error_text,
            "admin": self.by_admin,
            "lookups": self.lookups,
            "marks": self.marks,
            "duration_ms": round(elapsed_ms),
        })


class BackendAuth:
    """Khoá dịch vụ: frontend gửi ``Authorization: Bearer <khoá>``. Không đặt khoá thì không kiểm."""

    def __init__(self, token: str | None) -> None:
        self.token = token

    def deny(self, request: Request) -> JSONResponse | None:
        """``None`` khi request được phép, không thì phản hồi 401."""

        if self.token is None:
            return None
        scheme, separator, candidate = request.headers.get("authorization", "").partition(" ")
        if separator == " " and scheme.lower() == "bearer" and secrets.compare_digest(
            candidate.encode("utf-8"), self.token.encode("utf-8")
        ):
            return None
        return JSONResponse({"detail": "Unauthorized"}, status_code=401, headers={"WWW-Authenticate": "Bearer"})


def _error(status_code: int, detail: str) -> JSONResponse:
    return JSONResponse({"detail": detail}, status_code=status_code)


class ChatApi:
    """Đường ``/health`` và ``/chat``."""

    def __init__(self, agent, gate: TurnGate, auth: BackendAuth, *, chat_log=None, admin=None) -> None:
        self.agent = agent
        self.gate = gate
        self.auth = auth
        self.chat_log = chat_log
        #: ``AdminApi`` khi trang quản trị mở: câu quản trị tự hỏi thử được gắn nhãn trong lịch sử chat.
        self.admin = admin

    def routes(self) -> list[Route]:
        return [Route("/health", self.health, methods=["GET"]), Route("/chat", self.chat, methods=["POST"])]

    async def health(self, request: Request):
        return self.auth.deny(request) or JSONResponse({"status": "ok"})

    async def chat(self, request: Request):
        denied = self.auth.deny(request)
        if denied is not None:
            return denied
        payload = await self._read_json(request)
        if isinstance(payload, JSONResponse):
            return payload
        message = payload.get("message")
        if not isinstance(message, str) or not message.strip():
            return _error(400, "message must be non-empty text")
        history = payload.get("history") or []
        if not isinstance(history, list):
            return _error(400, "history must be a list")
        # Mã phiên chỉ để gom các lượt trong lịch sử chat; sai dạng thì cấp mã mới.
        session = payload.get("session")
        if not valid_id(session):
            session = new_id(datetime.now().astimezone())
        by_admin = self.admin is not None and self.admin.has_session(request)
        turn = Turn(self.agent, message.strip(), history, self.gate, self.chat_log, by_admin=by_admin, session=session)
        return StreamingResponse(
            turn.events(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "X-Chat-Session": session},
        )

    @staticmethod
    async def _read_json(request: Request) -> dict | JSONResponse:
        """Body JSON dạng đối tượng, đọc có giới hạn kích thước; sai thì phản hồi lỗi."""

        declared = request.headers.get("content-length")
        if declared is not None:
            try:
                if int(declared) > MAX_REQUEST_BODY_BYTES:
                    return _error(413, _REQUEST_TOO_LARGE_MESSAGE)
            except ValueError:
                return _error(400, "Content-Length must be an integer")
        body = bytearray()
        async for chunk in request.stream():
            if len(body) + len(chunk) > MAX_REQUEST_BODY_BYTES:
                return _error(413, _REQUEST_TOO_LARGE_MESSAGE)
            body.extend(chunk)
        try:
            payload = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return _error(400, "request body must be valid JSON")
        if not isinstance(payload, dict):
            return _error(400, "request body must be an object")
        return payload


def create_app(
    agent,
    gate: TurnGate | None = None,
    *,
    backend_token: str | None = None,
    admin=None,
    admin_token: str | None = None,
    chat_log=None,
    cors_origins: Sequence[str] = (),
    on_close: Callable[[], Awaitable[None]] | None = None,
) -> Starlette:
    """Ứng dụng Starlette. Trang quản trị (``admin``: ``AdminStore``) chỉ mở khi có ``admin_token``.

    ``on_close`` chạy khi máy chủ tắt, để đóng tài nguyên của dịch vụ.
    """

    auth = BackendAuth(backend_token)
    admin_api = None
    if admin is not None and admin_token:
        from ..admin.http import AdminApi

        admin_api = AdminApi(admin, admin_token, auth.deny, chat_log)
    chat_api = ChatApi(agent, gate or TurnGate(), auth, chat_log=chat_log, admin=admin_api)
    routes = chat_api.routes() + (admin_api.routes() if admin_api is not None else [])

    @asynccontextmanager
    async def lifespan(_app):
        try:
            yield
        finally:
            if on_close is not None:
                await on_close()

    app = Starlette(routes=routes, lifespan=lifespan)
    if cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(cors_origins),
            allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            # Thiếu ``Authorization`` ở đây thì trình duyệt chặn ngay ở bước hỏi trước (OPTIONS).
            allow_headers=["Authorization", "Content-Type", "X-Admin-Token"],
            max_age=600,
        )
    return app
