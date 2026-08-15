# Dataset

## Quy mô artifact hiện có

Ba tệp JSONL chứa **5.036 câu**:

| Tệp | Số dòng dữ liệu |
|---|---:|
| `resources/dataset/train.jsonl` | 4.251 |
| `resources/dataset/val.jsonl` | 398 |
| `resources/dataset/test.jsonl` | 387 |
| **Tổng** | **5.036** |

Các số trên được đếm trực tiếp từ ba tệp. `reports/dataset.json` xác nhận cùng
tổng `dataset.records = 5036` và cùng số bản ghi theo split. Đây là thống kê
artifact, không phải kết quả model.

## Trạng thái tương thích

Dataset được sinh từ catalogue v3 hiện tại. Mọi họ xuất hiện ở val/test đã được
dạy ở train; mọi giá trị slot hữu hạn cần thiết đều có ở train; 781/781 tên gọi
được phủ; các split không trùng sau chuẩn hoá. Tám lớp câu từ chối trong
`coverage.json`, gồm `incomplete-request`, đều có đủ ba split và bốn register.

## Hình dạng bản ghi

Mỗi dòng JSONL có:

| Trường | Vai trò |
|---|---|
| `id` | mã duy nhất |
| `query_id` | họ/shape truy vấn |
| `register` | phong cách diễn đạt |
| `input` | câu hỏi tiếng Việt |
| `target` | SPARQL chuẩn hoặc marker không có thông tin |

Ba split phục vụ các vai trò khác nhau. Tập kiểm tra chỉ dùng ở bước đánh giá
cuối; không dùng để chọn cấu hình hoặc bổ sung ví dụ.

## Mục tiêu v3

Dataset v3 phải dạy ánh xạ từ yêu cầu tiếng Việt sang shape lấy trọn node. Shape
chính trả `?thuoctinh ?giatri ?nguon ?duongdan` cho node neo và dữ kiện con
trực tiếp. Câu hỏi về nhiều khía cạnh của cùng một thủ tục dùng chung một shape
node đầy đủ thay vì mỗi khía cạnh một query hẹp.

Các bảng dùng shape riêng để trả nguyên `verbatimTableText` của node bảng cùng
nguồn. Dataset không được tạo target truy vấn từng cell hoặc tái dựng mapping
hàng–cột.

## Danh mục truy vấn hiện hành

`resources/dataset/catalogue.jsonl` hiện có **50 họ**: các họ bảng, các họ
`*-facts` lấy trọn node, một shape phí theo phương thức và một họ từ chối. Toàn
bộ **49 họ** ngoài họ từ chối đều được sinh tự động - không còn họ nào viết tay,
và `catalogue-manual.jsonl` đã bị xoá cùng họ "liệt kê năng lực" ngày 2026-08-14.

Ba split đều dùng đủ 50 họ hiện hành; họ có mặt ở held-out luôn có mặt ở train.

## Phân bố trong report

`reports/dataset.json` ghi phân bố của 5.036 dòng hiện có:

| Miền | Số câu |
|---|---:|
| `academic-rule` | 894 |
| `procedure` | 1.114 |
| `form` | 621 |
| `out-of-domain` | 638 |
| `document` | 931 |
| `tuition` | 159 |
| `certificate` | 188 |

| Phong cách | Số câu |
|---|---:|
| `colloquial` | 1.305 |
| `neutral` | 1.221 |
| `formal` | 954 |
| `noisy` | 1.065 |

Các bảng này mô tả nội dung file hiện có. Coverage/readiness được dẫn xuất riêng
trong cùng report và chỉ xanh khi toàn bộ hợp đồng dữ liệu đạt.

## Điều kiện trước khi dùng lại dataset

- mọi `query_id` phải có trong catalogue hiện hành;
- mọi target trong miền phải khớp shape, chỉ đọc và trả dữ liệu;
- frame phải dùng đúng slot mà họ truy vấn khai báo;
- các split không trùng sau chuẩn hoá;
- train phải phủ các giá trị hữu hạn cần thiết;
- manifest và report phải có checksum đúng với file;
- tập test không tham gia chọn checkpoint.

Kiểm tra read-only bằng:

```bash
uv run validate_sparql_dataset
.venv/bin/python -m pytest tests/research -q
```

Sinh lại report bằng `uv run generate_reports` sau mỗi lần thay nguồn dataset.
