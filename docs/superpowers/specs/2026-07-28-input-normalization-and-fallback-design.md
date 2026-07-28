# Chuẩn hoá đầu vào và phản hồi dự phòng

## Mục tiêu

Cải thiện nhanh trải nghiệm production trong khi chờ công văn chính thức để xây
lại ontology và hai dataset. Thay đổi chỉ gồm chuẩn hoá viết tắt, một phản hồi
dự phòng thống nhất và lưu lại câu hỏi thực tế của người dùng.

Không sửa ontology, không sửa `resources/dataset/main` hoặc
`resources/dataset/gate`, không fine-tuning và không thay đổi kiến trúc model.

## Chuẩn hoá đầu vào

`normalize_model_input` tiếp tục là hàm duy nhất dùng chung cho gate, model sinh
SPARQL, huấn luyện và đánh giá. Hàm chỉ làm sạch Unicode, khoảng trắng và bung
whitelist theo ranh giới token; không đoán intent, entity hay sửa chính tả.

Giữ toàn bộ ánh xạ hiện có và bổ sung nhóm chắc nghĩa, có giá trị trực tiếp với
miền học vụ:

- `hp` → `học phần`;
- `dk`, `đk` → `đăng ký`;
- `đkhp` → `đăng ký học phần`;
- `dkmh`, `đkmh` → `đăng ký môn học`;
- `ctdt`, `ctđt` → `chương trình đào tạo`;
- `cvht` → `cố vấn học tập`;
- `gdtc` → `giáo dục thể chất`;
- `gdqp` → `giáo dục quốc phòng`;
- `gpa` → `điểm trung bình`;
- `kqht` → `kết quả học tập`;
- `mh` → `môn học`;
- `bl` → `bảo lưu`;
- `pdt`, `pđt` → `phòng đào tạo`;
- `khong` → `không`, `dc`, `đc`, `duoc` → `được`;
- `hoc` → `học`, `lam` → `làm`;
- `nth`, `ntnao` → `như thế nào`, `thnao` → `thế nào`;
- `bgio`, `bjo` → `bao giờ`, `khinao` → `khi nào`;
- `trc` → `trước`, `vs` → `với`, `cx` → `cũng`, `rui` → `rồi`;
- `fai`, `phai` → `phải`, `bik`, `bjk`, `bjt` → `biết`.

Không sao chép toàn bộ bảng cũ. Những dạng đa nghĩa như `bn`, `hk`, `bg`, `m`,
`h`, `v`, `g`, `ng`, `nh`, `ck` không được bổ sung nếu chưa có quy tắc chắc
nghĩa. Normalizer phải giữ nguyên chữ hoa/thường của phần văn bản không được
thay thế và phải idempotent.

## Phản hồi UX

Dùng đúng một hằng số:

```text
Không có thông tin.
```

API trả HTTP 200 cùng phản hồi này trong ba trường hợp:

1. gate từ chối câu hỏi;
2. SPARQL hợp lệ nhưng ontology trả về không có dòng nào;
3. đầu ra model không phải truy vấn SPARQL hợp lệ hoặc truy vấn không thể thực
   thi vì lỗi dữ liệu/truy vấn dự kiến.

Log vẫn giữ nguyên nguyên nhân thật, request ID, quyết định gate, SPARQL và stack
trace để chẩn đoán. Lỗi khởi động, lỗi nạp model/ontology và lỗi lập trình ngoài
đường xử lý truy vấn không bị che; chúng vẫn là lỗi hệ thống.

## Lưu câu hỏi thực tế

Tạo `resources/cases/user_queries.txt`, mỗi dòng là một câu hỏi nguyên văn đã
được người dùng thử trên giao diện. File này không thuộc train/validation/test
hiện tại và không mang nhãn tạm thời.

Khi có công văn và ontology mới, từng câu trong file phải được gán nhãn gate,
SPARQL đích và biến thể phù hợp rồi mới đưa vào dataset mới. Bản thân câu nguyên
văn được giữ làm ca hồi quy để bảo đảm hành vi mà người dùng thực sự cần.

## Kiểm thử và giới hạn thực hiện

- Unit test từng ánh xạ mới, ranh giới token và tính idempotent.
- Runtime/API test ba đường cùng trả `Không có thông tin.`.
- Test xác nhận lỗi hệ thống bất ngờ không bị nuốt.
- Chạy nhóm test runtime liên quan, sau đó chạy toàn bộ test một lần.
- Không benchmark, fine-tuning, chuyển đổi model hoặc sửa các script nghiên cứu.
- Không stage các file người dùng đang sửa: `.gitignore`,
  `resources/ontology/ontology_v9.properties`, `uv.lock`, `test.html`,
  `test_phobert.py`, `test_preprocess.py`.
