# Đưa vào môi trường sử dụng

Tệp này trả lời cách chạy thành phần tra cứu trong một hệ thống khác.

## Thành phần cần có

| Thành phần | Vai trò |
|---|---|
| Mô hình đã huấn luyện | Đổi câu hỏi thành câu truy vấn hoặc “không có thông tin”. |
| Ontology | Cung cấp dữ kiện học vụ và liên kết về nguồn. |
| Danh mục khuôn truy vấn | Giới hạn các cách đọc dữ liệu được phép. |
| Dịch vụ tra cứu | Kiểm tra truy vấn và trả dữ kiện. |
| Lớp hội thoại, nếu cần | Diễn đạt từ dữ kiện trả về. |

## Biến môi trường

Đặt các biến sau trong môi trường chạy dịch vụ:

| Biến | Nghĩa |
|---|---|
| `ONTCHATBOT_LLM_API_KEY` | Khoá truy cập máy chủ mô hình ngôn ngữ lớn. |
| `ONTCHATBOT_LLM_BASE_URL` | Địa chỉ máy chủ theo giao thức OpenAI. |
| `ONTCHATBOT_LLM_MODEL` | Tên mô hình trên máy chủ đó. |

Khoá chỉ được đọc từ biến môi trường. Dịch vụ không nhận khoá qua tham số dòng lệnh và không ghi khoá ra log.

## Chạy dịch vụ

```bash
uv sync --extra inference
export ONTCHATBOT_LLM_API_KEY=<khoa_truy_cap>
export ONTCHATBOT_LLM_BASE_URL=<dia_chi_may_chu>
export ONTCHATBOT_LLM_MODEL=<ten_mo_hinh>
uv run serve_sparql --model-dir <thu_muc_mo_hinh>
```

Lệnh cuối khởi động dịch vụ tại `127.0.0.1:8000`. Đổi địa chỉ hoặc cổng bằng `--host` và `--port` khi cần.

## Kiểm tra trước khi dùng

```bash
uv run validate_sparql_dataset
.venv/bin/python -m pytest tests -q
```

Các lệnh này kiểm tra chuỗi dữ liệu và các phép kiểm tự động của dự án.

## Tài liệu liên quan

- [Cách các thành phần phối hợp](ARCHITECTURE.md)
- [Thông tin về mô hình](MODEL_CARD.md)
