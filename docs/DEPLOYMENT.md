# Đưa vào môi trường sử dụng

Tệp này trả lời cần có gì để chạy thành phần tra cứu trong một hệ thống khác. Tệp dành cho kỹ sư tích hợp dự án, không giả định người đọc đã mở mã nguồn.

## Thành phần cần có

| Thành phần | Vai trò |
|---|---|
| Mô hình đã huấn luyện | Đổi câu hỏi tiếng Việt thành câu truy vấn hoặc “không có thông tin”. |
| Ontology | Tập dữ kiện học vụ và liên kết về văn bản nguồn. |
| Danh mục 50 khuôn truy vấn | Chỉ ra các cách đọc dữ liệu được phép. |
| Dịch vụ tra cứu | Kiểm tra câu truy vấn, chạy truy vấn và trả dữ kiện. |
| Lớp hội thoại, nếu cần | Nhận hội thoại và dùng dữ kiện trả về để viết câu trả lời cuối. |

SPARQL là ngôn ngữ dùng để hỏi ontology. Ontology là dữ liệu có cấu trúc gồm các mục học vụ và liên kết giữa chúng. Một node là một mục trong ontology, ví dụ một thủ tục hoặc một bảng.

## Luồng tích hợp

1. Gửi câu hỏi tiếng Việt đến thành phần tra cứu.
2. Thành phần tạo SPARQL hoặc trả “không có thông tin”.
3. Hệ thống kiểm tra câu truy vấn có thuộc một trong 50 khuôn và chỉ đọc dữ liệu hay không.
4. Nếu hợp lệ, hệ thống trả dữ kiện của node, trích dẫn và đường dẫn tới tài liệu gốc.
5. Nếu có lớp hội thoại bên ngoài, lớp này chỉ dùng các dữ kiện trả về để diễn đạt câu trả lời.

## Yêu cầu an toàn

- Chỉ cho phép truy vấn đọc dữ liệu.
- Không cho câu truy vấn mở dữ liệu từ nguồn bên ngoài.
- Từ chối câu không khớp danh mục khuôn truy vấn.
- Giới hạn lượng dữ liệu trả về cho mỗi yêu cầu.
- Giữ trích dẫn và đường dẫn nguồn cùng với dữ kiện khi hiển thị.
- Phân biệt “không có thông tin” với lỗi của dịch vụ.

## Biến môi trường

Trợ lý gọi một mô hình ngôn ngữ lớn qua mạng, nên nó cần biết gọi đi đâu và bằng
khoá nào. Ba giá trị này truyền bằng biến môi trường:

| Biến | Nghĩa |
|---|---|
| `ONTCHATBOT_LLM_API_KEY` | khoá truy cập máy chủ mô hình |
| `ONTCHATBOT_LLM_BASE_URL` | địa chỉ máy chủ, theo giao thức của OpenAI |
| `ONTCHATBOT_LLM_MODEL` | tên mô hình trên máy chủ đó |

Khoá **chỉ** đọc từ biến môi trường. Không có tham số dòng lệnh nào nhận khoá,
nên nó không lọt vào lịch sử lệnh hay danh sách tiến trình đang chạy; mã nguồn
cũng không ghi khoá ra log.

Khi chạy bằng Docker, truyền chúng qua phần khai báo biến môi trường của
container. Khi chạy tại chỗ để thử, đặt trong tệp `.env` ở gốc dự án - tệp này
đã được loại khỏi git.

## Chạy dịch vụ

Inference là giai đoạn mô hình tạo kết quả cho một yêu cầu đang được phục vụ. Nhóm cài đặt cùng tên chứa các thư viện cần cho giai đoạn này.

```bash
uv sync --extra inference
uv run serve_sparql --model-dir <thu_muc_mo_hinh>
```

Lệnh đầu cài các thư viện cần để chạy dịch vụ. Lệnh thứ hai khởi động dịch vụ với thư mục chứa mô hình đã chuyển đổi để phục vụ.

## Điều cần kiểm tra trước khi dùng

```bash
uv run validate_sparql_dataset
.venv/bin/python -m pytest tests -q
```

Các lệnh này kiểm tra chuỗi dữ liệu và các phép kiểm tự động. Dự án chưa có số đo công khai cho việc vận hành dịch vụ; cần đo trong môi trường dự kiến sử dụng trước khi đặt yêu cầu về tốc độ hoặc tải xử lý.

## Tài liệu liên quan

- [Cách các thành phần phối hợp](ARCHITECTURE.md)
- [Ontology và nguồn](ONTOLOGY.md)
- [Thông tin về mô hình](MODEL_CARD.md)
