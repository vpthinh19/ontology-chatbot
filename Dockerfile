# syntax=docker/dockerfile:1

# CUDA và cuDNN đến từ image runtime chính thức của NVIDIA. Image Ubuntu này
# không kèm Python; uv cài đúng Python 3.12 một lần vào tầng dùng chung, nên cả
# builder lẫn runtime dùng cùng một interpreter và virtualenv không có symlink
# trỏ sang một image khác.
FROM nvidia/cuda:13.0.2-cudnn-runtime-ubuntu24.04 AS cuda-python

COPY --from=ghcr.io/astral-sh/uv:0.11.32 /uv /uvx /bin/
ENV UV_PYTHON_INSTALL_DIR=/opt/uv/python
RUN uv python install 3.12

# ---------- builder ----------
FROM cuda-python AS builder

WORKDIR /app

# Sao chép thay vì liên kết cứng để môi trường ảo còn dùng được sau khi COPY sang
# tầng runtime; dùng Python của image thay vì tải bản khác.
ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never

COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --python 3.12 --no-install-project --extra inference --no-dev

COPY src/ ./src/
COPY resources/ ./resources/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --python 3.12 --extra inference --no-dev

# Chỉ tải đồ thị ONNX của bộ phân loại được chọn. Các model còn lại và kết quả
# benchmark nằm cùng kho phát hành nhưng không thuộc ảnh chạy.
#
# Đồ thị này khép kín: nó mang sẵn trọng số đã hoà bộ điều hợp, kèm bộ tách từ và
# bảng nhãn. Không phải tải bộ mã hoá nền, và lúc chạy không ra mạng.
ARG HF_REPO=
ARG HF_REVISION=main
ARG HF_MODEL_PATH=onnx-xlmr
RUN test -n "${HF_REPO}" && \
    /app/.venv/bin/python -c "import shutil; from pathlib import Path; \
from huggingface_hub import snapshot_download; \
root=Path('/app/hf-model'); path='${HF_MODEL_PATH}'; \
snapshot_download(repo_id='${HF_REPO}', revision='${HF_REVISION}', \
local_dir=root, allow_patterns=[path + '/*']); \
shutil.copytree(root / path, '/app/classifier-model')"

# ---------- runtime ----------
FROM cuda-python AS runtime

# Vá các gói hệ điều hành trước khi đóng ảnh. Ảnh nền được dựng theo chu kỳ riêng
# nên nó luôn trễ hơn kho bản vá của bản phân phối vài tuần; không nâng ở đây thì
# mỗi lượt phát hành lại kế thừa đúng những lỗ hổng đã có bản sửa. Bước quét bảo
# mật trong quy trình dựng chặn ở mức nghiêm trọng, và nó chặn đúng những gói này.
#
# Chạy dưới người dùng thường, có thư mục nhà để các thư viện ghi cache tạm.
RUN set -eux; \
    apt-get update; \
    apt-get upgrade -y --no-install-recommends; \
    apt-get install -y --no-install-recommends ca-certificates; \
    rm -rf /var/lib/apt/lists/*; \
    groupmod --new-name ontchatbot ubuntu; \
    usermod --login ontchatbot --home /home/ontchatbot --move-home ubuntu
WORKDIR /app

COPY --from=builder --chown=ontchatbot:ontchatbot /app/.venv /app/.venv
COPY --from=builder --chown=ontchatbot:ontchatbot /app/src /app/src
COPY --from=builder --chown=ontchatbot:ontchatbot /app/resources /app/resources
COPY --from=builder --chown=ontchatbot:ontchatbot /app/classifier-model /app/model

RUN mkdir -p /app/logs && chown ontchatbot:ontchatbot /app/logs

# Biến môi trường lúc CHẠY container:
#
#   ONTCHATBOT_LLM_API_KEY   BẮT BUỘC. Khoá truy cập máy chủ mô hình ngôn ngữ lớn.
#                            Chỉ đọc từ môi trường, cố ý không có cờ dòng lệnh, để
#                            khoá không lọt vào lịch sử lệnh hay danh sách tiến trình.
#   ONTCHATBOT_LLM_MODEL     BẮT BUỘC. Tên mô hình điều phối.
#   ONTCHATBOT_LLM_BASE_URL  Tuỳ chọn. Địa chỉ máy chủ mô hình; mặc định là nhà cung
#                            cấp đã đặt trong mã.
#   ONTCHATBOT_DEVICE        Tuỳ chọn. ``cuda`` (mặc định của ảnh) hoặc ``cpu``.
#   ONTCHATBOT_CORS_ORIGINS  Bắt buộc khi frontend ở domain khác. Danh sách origin
#                            cách nhau bằng dấu phẩy, ví dụ https://demo.vercel.app.
#
# Đường dẫn model, địa chỉ và cổng lắng nghe đã nằm trong CMD ở cuối tệp.
# Dịch vụ kiểm hai biến bắt buộc ngay lúc khởi động và dừng hẳn nếu thiếu, nên
# thiếu biến thì container tắt thay vì chạy rồi hỏng lúc có người hỏi.
#
# PATH đặt môi trường ảo lên đầu. Chế độ ngoại tuyến vì model đã nằm trong ảnh,
# không lượt chạy nào được ra mạng. Giới hạn vùng cấp phát bộ nhớ giảm khoảng
# 50-100 MB thường trú ở mức tải một yêu cầu tại một thời điểm.
#
# Mặc định chạy trên card đồ hoạ: ảnh này dựng để triển khai trên máy chủ có card,
# và card được cấp thẳng vào container. Chạy thử trên máy cá nhân thì cần cờ
# ``--gpus all``; máy không có card thì đặt ONTCHATBOT_DEVICE=cpu.
#
# Múi giờ đặt theo nơi đặt trường, vì nhật ký được đọc bằng mắt trên terminal chứ
# không qua công cụ nào biết quy đổi. Không đặt thì container chạy theo giờ quốc
# tế và mọi mốc thời gian lệch bảy tiếng so với người đọc. Mốc thời gian vẫn ghi
# kèm độ lệch, nên đổi biến này thì dòng nhật ký tự nói lên múi giờ mới.
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=Asia/Ho_Chi_Minh \
    HF_HUB_OFFLINE=1 \
    HF_HUB_DISABLE_TELEMETRY=1 \
    MALLOC_ARENA_MAX=2 \
    ONTCHATBOT_DEVICE=cuda

USER ontchatbot
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request, sys; \
sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=3).status == 200 else 1)" \
    || exit 1

CMD ["serve_sparql", "--model-dir", "/app/model", "--host", "0.0.0.0", "--port", "8000"]
