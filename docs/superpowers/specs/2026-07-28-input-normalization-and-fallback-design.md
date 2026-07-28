# Chuẩn hoá đầu vào và phản hồi dự phòng

## Chuẩn hoá đầu vào

`normalize_model_input` là hàm duy nhất dùng chung cho huấn luyện, đánh giá và
runtime. Hàm chỉ chuẩn hoá Unicode, khoảng trắng, vị trí dấu và bung whitelist
theo ranh giới token; không đoán intent, entity, IRI hoặc sửa chính tả.

Các ánh xạ chắc nghĩa gồm cả:

- `hp` → `học phần`;
- `dk`, `đk` → `đăng ký`;
- `đkhp` → `đăng ký học phần`;
- `dkmh`, `đkmh` → `đăng ký môn học`;
- nhóm acronym học vụ đã được kiểm thử trong `runtime/text.py`;
- nhóm chat spelling chắc nghĩa đã được kiểm thử trong
  `tests/runtime/test_model_text.py`.

Không bổ sung dạng đa nghĩa như `hk`, `bg`, `m`, `h`, `v`, `g`, `ng`, `nh`,
`ck` nếu chưa có quy tắc chắc nghĩa. Normalizer phải giữ ranh giới token và
idempotent.

## Phản hồi UX

Model chủ động từ chối bằng target:

```text
không có thông tin
```

Giao diện dùng đúng phản hồi:

```text
Không có thông tin.
```

Phản hồi này áp dụng khi model sinh marker, output/query dự kiến bị lỗi hoặc
ontology không có kết quả. Log giữ output và nguyên nhân thật. Lỗi nạp
model/ontology và lỗi lập trình không bị che.

## Câu hỏi thực tế

`resources/cases/user_queries.txt` giữ nguyên văn câu người dùng đã thử. Sau khi
ontology mới hoàn tất, từng câu được gán SPARQL hoặc marker và đưa vào dataset
hợp nhất, đồng thời tiếp tục làm ca hồi quy production.
