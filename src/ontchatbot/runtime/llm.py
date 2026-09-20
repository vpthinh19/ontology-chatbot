"""Gọi mô hình qua giao thức chat-completions (tương thích OpenAI) và đọc câu trả lời chảy dần (SSE)."""

from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

logger = logging.getLogger(__name__)

#: Số lần gọi lại sau lần đầu khi dịch vụ mô hình trục trặc tạm thời.
MAX_RETRIES = 3
#: Phải chờ lâu hơn chừng này thì báo người dùng thử lại sau, thay vì để màn hình đứng im.
MAX_RETRY_WAIT_SECONDS = 10.0
_RETRYABLE_STATUS = {408, 409, 429}
#: Dịch vụ quá tải chứ không hỏng.
_BUSY_STATUS = {429, 503}


class LightningProtocolError(RuntimeError):
    """Luồng trả về không đúng giao thức SSE (thiếu ``[DONE]``)."""


class LightningBusyError(RuntimeError):
    """Dịch vụ mô hình quá tải lâu hơn mức một người đang chat chờ được."""

    def __init__(self, retry_after: float) -> None:
        super().__init__(f"Lightning is rate limiting; retry after {retry_after:.0f}s")
        self.retry_after = retry_after


def _retry_after(response: httpx.Response) -> float | None:
    """Số giây chờ trong header Retry-After: dạng số giây hoặc dạng ngày giờ HTTP."""

    value = response.headers.get("retry-after", "").strip()
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        pass
    try:
        when = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return max(0.0, (when - datetime.now(timezone.utc)).total_seconds())


@dataclass(frozen=True)
class ToolCallDelta:
    index: int
    call_id: str = ""
    name: str = ""
    arguments: str = ""
    #: Trường riêng của nhà cung cấp đi kèm lời gọi. Gemini 3 gửi chữ ký suy nghĩ ở đây và BẮT BUỘC
    #: nhận lại nguyên vẹn khi ta trả kết quả công cụ về, không thì từ chối với 400.
    extra_content: Any = None


@dataclass(frozen=True)
class ChatDelta:
    content: str = ""
    tool_calls: tuple[ToolCallDelta, ...] = ()
    finish_reason: str | None = None


def _chi_so(tool_call: dict[str, Any], vi_tri: int, thu_tu: dict[str, int]) -> int:
    """Chỉ số để gom các mảnh của cùng một lời gọi công cụ.

    Google AI Studio không gửi ``index`` mà chỉ gửi ``id``, nên khi thiếu ``index`` thì đánh số theo
    thứ tự mã lời gọi xuất hiện; mảnh không mang mã thì thuộc về lời gọi vừa mở.
    """

    chi_so = tool_call.get("index")
    if isinstance(chi_so, int):
        return chi_so
    ma = tool_call.get("id") or ""
    if not ma:
        return max(thu_tu.values()) if thu_tu else vi_tri
    return thu_tu.setdefault(ma, len(thu_tu))


class LightningClient:
    """Gửi hội thoại kèm khai báo công cụ, trả về từng mảnh ``ChatDelta``.

    Lỗi tạm thời (mạng, 408/409/429, 5xx) được gọi lại tối đa ``MAX_RETRIES`` lần, nhưng chỉ khi chưa
    có chữ nào tới người dùng.
    """

    def __init__(
        self,
        http: httpx.AsyncClient,
        *,
        model: str,
        retries: int = MAX_RETRIES,
        sleep: Callable[[float], Awaitable[Any]] = asyncio.sleep,
        jitter: Callable[[], float] = random.random,
    ) -> None:
        self._http = http
        self._model = model
        self._retries = retries
        self._sleep = sleep
        self._jitter = jitter

    #: Dặn thêm cho riêng nhà này, nối vào cuối lời nhắc hệ thống. Lời nhắc chung phải giữ nguyên chữ
    #: vì số liệu trong báo cáo đo trên nó, nên chỗ nào cần nói riêng thì nói ở đây.
    DAN_THEM = ""

    def _messages(self, messages: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
        ra = [dict(message) for message in messages]
        if self.DAN_THEM and ra and ra[0].get("role") == "system":
            ra[0]["content"] = f"{ra[0]['content']}\n\n{self.DAN_THEM}"
        return ra

    async def stream(
        self,
        *,
        messages: Sequence[dict[str, Any]],
        tools: Sequence[dict[str, Any]],
    ) -> AsyncIterator[ChatDelta]:
        body = {
            "model": self._model,
            "messages": self._messages(messages),
            "tools": list(tools),
            "tool_choice": "auto",
            "stream": True,
        }
        for retry in range(self._retries + 1):
            emitted = False
            try:
                async for delta in self._stream_once(body):
                    emitted = True
                    yield delta
                return
            except (httpx.TransportError, httpx.HTTPStatusError) as exc:
                status = getattr(getattr(exc, "response", None), "status_code", None)
                retryable = status is None or status in _RETRYABLE_STATUS or status >= 500
                # Đã hiện chữ cho người dùng thì gọi lại sẽ làm câu trả lời lặp.
                if emitted or not retryable:
                    raise
                told = _retry_after(exc.response) if status is not None else None
                # Không được bảo chờ bao lâu thì chờ 1, 2, 4 giây, thêm một chút
                # ngẫu nhiên để nhiều lượt cùng bị chặn không gọi lại cùng lúc.
                wait = told if told is not None else 2**retry + 0.5 * self._jitter()
                if retry == self._retries or wait > MAX_RETRY_WAIT_SECONDS:
                    if status in _BUSY_STATUS:
                        raise LightningBusyError(wait) from exc
                    raise
                await self._sleep(wait)

    async def _stream_once(
        self, body: dict[str, Any]
    ) -> AsyncIterator[ChatDelta]:
        thu_tu: dict[str, int] = {}
        async with self._http.stream(
            "POST", "chat/completions", json=body
        ) as response:
            if response.is_error:
                # Đọc thân phản hồi trước khi đóng luồng: lời nhắn của dịch vụ nói rõ sai ở đâu.
                await response.aread()
            response.raise_for_status()
            completed = False
            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data = line[6:]
                if data == "[DONE]":
                    completed = True
                    break
                payload = json.loads(data)
                choices = payload.get("choices", [])
                if not choices:
                    continue
                choice = choices[0]
                delta = choice.get("delta") or {}
                content = delta.get("content")
                if not isinstance(content, str):
                    content = ""
                tool_calls = tuple(
                    ToolCallDelta(
                        index=_chi_so(tool_call, vi_tri, thu_tu),
                        call_id=tool_call.get("id") or "",
                        name=(tool_call.get("function") or {}).get("name") or "",
                        arguments=(tool_call.get("function") or {}).get("arguments")
                        or "",
                        extra_content=tool_call.get("extra_content"),
                    )
                    for vi_tri, tool_call in enumerate(delta.get("tool_calls") or ())
                )
                finish_reason = choice.get("finish_reason")
                if content or tool_calls or finish_reason:
                    yield ChatDelta(
                        content=content,
                        tool_calls=tool_calls,
                        finish_reason=finish_reason,
                    )
            if not completed:
                raise LightningProtocolError("Lightning stream ended without [DONE]")


class GeminiClient(LightningClient):
    """Google AI Studio. Cũng nói giao thức OpenAI, nhưng có mấy nết riêng.

    Bản lite bám sát câu "giữ lại trích dẫn" tới mức nhắc lại cùng một nguồn sau từng ý, nên câu trả lời
    rối mắt; dặn thêm ở đây thì gemma không thấy và số liệu báo cáo không đụng tới. Hai nết còn lại
    (không gửi ``index``, đòi lại chữ ký suy nghĩ) đã lo ở lớp cha vì nhà khác cũng có thể như vậy.

    Chữ hiện lên của một liên kết KHÔNG quyết định ở đây: mô hình nào cũng có thể đặt tên liên kết là
    "Link", nên trang web đổi những tên chung chung đó thành "Nguồn" (``webui/markdown.js``). Dặn ở đây
    chỉ để Gemini gọi đúng tên nguồn ngay từ đầu, khỏi phải chữa.
    """

    DAN_THEM = (
        "Mỗi nguồn chỉ nhắc MỘT lần: gom phần trích dẫn thành danh sách ở cuối câu trả lời, không chèn "
        "vào giữa các ý. Giữ nguyên toạ độ (điều, khoản, phương thức, bước, ngày truy cập) và đường dẫn "
        "mà công cụ đưa; không rút gọn trích dẫn thành mỗi tên văn bản. Mỗi mục trong danh sách là một "
        "liên kết markdown lấy chính trích dẫn làm chữ."
    )


#: Lớp phụ trách từng nhà cung cấp. Hệ thống chỉ gọi ``stream(messages=..., tools=...)``, không cần biết là nhà nào.
CLIENTS: dict[str, type[LightningClient]] = {"lightning": LightningClient, "gemini": GeminiClient}


#: Im lặng giữa hai mảnh lâu hơn chừng này thì coi như đứt. Rộng tay, vì cắt một câu trả lời đang chảy
#: là mất hẳn lượt: đã có chữ trên màn hình thì không được đổi nơi trả lời.
ENDPOINT_READ_TIMEOUT_SECONDS = 12.0
#: Chờ MẢNH ĐẦU của một điểm cuối còn đường lui lâu hơn chừng này thì chuyển sang điểm cuối sau.
#: Đo 20/09 trên 3 câu hỏi: gemma 0,82-0,98 s ở vòng gọi đầu và 0,81-1,53 s ở vòng sau khi đã tra cứu,
#: Gemini 1,1-1,3 s; nên ba giây là rộng gấp đôi mức chậm nhất đo được. Điểm cuối CUỐI không bị hạn này:
#: không còn nơi nào khác thì chờ thêm vẫn hơn là bỏ lượt.
FIRST_CHUNK_TIMEOUT_SECONDS = 3.0
#: Điểm cuối vừa hỏng bị bỏ qua trong chừng này, để lượt sau không phải dò lại từ đầu.
ENDPOINT_COOLDOWN_SECONDS = 120.0


def _than_loi(exc: Exception) -> str:
    """Lời nhắn dịch vụ mô hình gửi kèm mã lỗi, để log nói được sai ở đâu."""

    response = getattr(exc, "response", None)
    if response is None:
        return ""
    try:
        than = response.text
    except Exception:  # thân phản hồi chưa đọc được (luồng đã đóng)
        return ""
    than = " ".join(than.split())
    return f" - {than[:200]}" if than else ""


def _ke_lai_bang_loi(messages: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Hội thoại kể cho một nhà cung cấp khác nghe, không còn lời gọi công cụ.

    Lời gọi công cụ mang dấu riêng của nơi sinh ra nó: Gemini 3 đòi lại đúng chữ ký suy nghĩ của mình và từ
    chối lời gọi của nhà khác. Nên khi đổi nơi trả lời giữa chừng, kết quả tra cứu được kể lại như một tin
    nhắn thường; nội dung không mất gì, mô hình mới vẫn viết tiếp được câu trả lời.
    """

    ra: list[dict[str, Any]] = []
    for message in messages:
        if message.get("role") == "assistant" and message.get("tool_calls"):
            if message.get("content"):
                ra.append({"role": "assistant", "content": message["content"]})
        elif message.get("role") == "tool":
            ra.append({"role": "user", "content": f"Kết quả tra cứu:\n{message.get('content') or ''}"})
        else:
            ra.append(message)
    return ra


@dataclass(frozen=True)
class Endpoint:
    """Một nơi có thể trả lời: địa chỉ giao thức chat-completions, khoá và tên mô hình."""

    base_url: str
    api_key: str
    model: str
    #: Khoá trong ``CLIENTS``: lớp nào biết nết riêng của nhà này.
    provider: str = "lightning"

    @property
    def label(self) -> str:
        return f"{self.model} @ {self.base_url.split('//', 1)[-1].split('/', 1)[0]}"


async def _cho_manh_dau(dong: AsyncIterator[ChatDelta], han: float | None) -> AsyncIterator[ChatDelta]:
    """Chuyển tiếp một luồng mảnh, nhưng chỉ cho mảnh ĐẦU ``han`` giây; các mảnh sau chờ bao lâu cũng được.

    Mô hình lành lặn lên tiếng trong khoảng một giây. Im lâu hơn thế ở mảnh đầu gần như luôn là hỏng, mà
    lúc đó chưa có chữ nào tới người đọc nên chuyển nơi khác vẫn còn kịp và không ai thấy gì.
    """

    try:
        if han is None:
            dau = await anext(dong, None)
        else:
            async with asyncio.timeout(han):
                dau = await anext(dong, None)
        if dau is None:
            return
        yield dau
        async for delta in dong:
            yield delta
    finally:
        await dong.aclose()


class FallbackClient:
    """Gọi lần lượt các điểm cuối cho tới khi có mảnh trả lời đầu tiên.

    Điểm cuối hỏng bị ghi nhớ trong ``cooldown`` giây nên chỉ lượt đầu phải dò; các lượt sau đi thẳng
    tới nơi đang trả lời. Đã có chữ tới người dùng thì KHÔNG đổi điểm cuối nữa, vì câu trả lời sẽ lặp.
    Mỗi điểm cuối chỉ được gọi lại khi nó là điểm cuối cuối cùng: còn nơi khác để thử thì chuyển luôn.
    """

    def __init__(
        self,
        endpoints: Sequence[Endpoint],
        *,
        open_client: Callable[[Endpoint], httpx.AsyncClient],
        sleep: Callable[[float], Awaitable[Any]] = asyncio.sleep,
        jitter: Callable[[], float] = random.random,
        clock: Callable[[], float] = time.monotonic,
        cooldown: float = ENDPOINT_COOLDOWN_SECONDS,
        first_chunk: float = FIRST_CHUNK_TIMEOUT_SECONDS,
    ) -> None:
        if not endpoints:
            raise ValueError("cần ít nhất một điểm cuối mô hình")
        self._endpoints = tuple(endpoints)
        self._open_client = open_client
        self._sleep = sleep
        self._jitter = jitter
        self._clock = clock
        self._cooldown = cooldown
        self._first_chunk = first_chunk
        self._down: dict[str, float] = {}
        self._clients: dict[str, tuple[httpx.AsyncClient, LightningClient]] = {}

    def _client(self, endpoint: Endpoint, *, last: bool) -> LightningClient:
        """Mở kết nối cho điểm cuối khi lần đầu cần tới, rồi dùng lại."""

        cached = self._clients.get(endpoint.label)
        if cached is None:
            http = self._open_client(endpoint)
            lop = CLIENTS.get(endpoint.provider, LightningClient)
            cached = (http, lop(http, model=endpoint.model, retries=MAX_RETRIES if last else 0,
                                sleep=self._sleep, jitter=self._jitter))
            self._clients[endpoint.label] = cached
        return cached[1]

    def _order(self) -> list[Endpoint]:
        """Điểm cuối chưa bị đánh dấu hỏng trước, rồi tới những cái đang trong thời gian nghỉ."""

        now = self._clock()
        sang = [e for e in self._endpoints if self._down.get(e.label, 0.0) <= now]
        return sang or list(self._endpoints)

    async def stream(
        self,
        *,
        messages: Sequence[dict[str, Any]],
        tools: Sequence[dict[str, Any]],
    ) -> AsyncIterator[ChatDelta]:
        thu = self._order()
        ke_lai: list[dict[str, Any]] | None = None
        for vi_tri, endpoint in enumerate(thu):
            emitted = False
            if vi_tri and ke_lai is None:
                ke_lai = _ke_lai_bang_loi(messages)
            cuoi = vi_tri == len(thu) - 1
            try:
                async for delta in _cho_manh_dau(
                    self._client(endpoint, last=cuoi).stream(
                        messages=messages if not vi_tri else ke_lai, tools=tools
                    ),
                    None if cuoi else self._first_chunk,
                ):
                    if not emitted:
                        emitted = True
                        self._down.pop(endpoint.label, None)
                        if vi_tri:
                            logger.warning("model fallback: trả lời bằng %s", endpoint.label)
                    yield delta
                return
            except (httpx.TransportError, httpx.HTTPStatusError, LightningProtocolError, LightningBusyError,
                    TimeoutError) as exc:
                if emitted or cuoi:
                    raise
                self._down[endpoint.label] = self._clock() + self._cooldown
                logger.warning("model endpoint %s hỏng (%s: %s%s), chuyển sang %s",
                               endpoint.label, type(exc).__name__, str(exc)[:120], _than_loi(exc),
                               thu[vi_tri + 1].label)

    async def aclose(self) -> None:
        for http, _ in self._clients.values():
            await http.aclose()
        self._clients.clear()
