# Kiến trúc hệ thống

Tài liệu này mô tả các thành phần và trách nhiệm của chúng. Nó kỹ thuật hơn
[tài liệu ý tưởng](CONCEPT.md), nhưng vẫn không đòi hỏi đọc mã nguồn.

## Đường đi của một câu hỏi

```text
câu hỏi của người dùng
  → chuẩn hoá nhẹ
  → mô hình sinh chuỗi
      ├── báo không có thông tin ──────────────→ "Không có thông tin."
      └── một câu truy vấn
            → kiểm tra an toàn
            → đối chiếu danh mục dạng câu hỏi
            → chạy trên mạng lưới kiến thức
            → định dạng kết quả ───────────────→ câu trả lời
```

Truy vấn hỏng, không thuộc danh mục, hoặc không trả về dữ liệu đều dẫn tới cùng
một câu "Không có thông tin."

## Trách nhiệm từng thành phần

| Thành phần | Nhận | Trả | Cố ý **không** làm |
|---|---|---|---|
| Chuẩn hoá | câu hỏi thô | văn bản sạch nhẹ | dò thực thể, đoán ý định |
| Mô hình | văn bản | truy vấn hoặc lời từ chối | đọc nội dung mạng lưới |
| Kiểm tra an toàn | truy vấn | truy vấn an toàn | sửa truy vấn |
| Đối chiếu danh mục | truy vấn | truy vấn thuộc một dạng đã khai | chọn dạng gần đúng |
| Máy truy vấn | truy vấn + mạng lưới | các giá trị | suy đoán ý người dùng |
| Định dạng | các giá trị | văn bản hiển thị | chứa logic riêng cho học vụ |

Cột cuối quan trọng ngang cột đầu. Mỗi thành phần **từ chối làm hộ việc của
thành phần khác**, nên khi có lỗi thì xác định được ngay lỗi thuộc về ai.

## Vì sao cần đối chiếu danh mục

Kiểm tra an toàn chỉ chặn cú pháp sai và thao tác nguy hiểm. Nó không chặn được
một truy vấn hợp lệ hoàn toàn nhưng ghép thực thể với quan hệ theo cách không ai
định nghĩa — ví dụ duyệt mọi thủ tục rồi đổ nguyên văn hàng chục điều luật ra
màn hình.

Đối chiếu danh mục so khớp **chính xác** truy vấn với các dạng đã khai báo.
Khớp thì chạy tiếp; không khớp thì từ chối. Không có "gần đúng".

## An toàn truy vấn

Hệ thống chỉ chấp nhận truy vấn **chỉ đọc**. Cụ thể: cấm mọi thao tác thay đổi
dữ liệu, cấm gọi ra nguồn dữ liệu bên ngoài, cấm lấy tất cả các cột mà không nêu
rõ cột kết quả, và giới hạn độ dài truy vấn lẫn số dòng trả về.

Kết quả trả về phải là **tên gọi hoặc giá trị**, không bao giờ là một mắt lưới
trong mạng. Ràng buộc này bảo đảm người dùng luôn nhận được chữ đọc được, chứ
không phải một mã định danh nội bộ.

## Xử lý lỗi

Ba tình huống nghiệp vụ — mô hình từ chối, truy vấn không hợp lệ, kết quả rỗng —
cùng trả về "Không có thông tin." với mã trạng thái thành công, vì đó là câu trả
lời hợp lệ của hệ thống.

Lỗi nạp mô hình, lỗi đọc mạng lưới và lỗi lập trình **không** bị che thành phản
hồi nghiệp vụ. Che chúng đi sẽ khiến một sự cố hạ tầng trông y hệt một câu hỏi
ngoài phạm vi.

Mỗi lượt hỏi được gắn một mã truy vết và ghi lại: câu gốc, câu đã chuẩn hoá,
chuỗi mô hình sinh ra nguyên văn, thời gian sinh, trạng thái kiểm tra, số dòng
kết quả, câu trả lời cuối và tổng thời gian.

## Ranh giới giữa phần chạy thật và phần nghiên cứu

Phần chạy thật chỉ cần: một mô hình đã chuyển đổi, bộ tách từ của nó, mạng lưới
kiến thức, và danh mục dạng câu hỏi. Nó **không** dùng tới mã huấn luyện, mã tạo
dữ liệu hay mã báo cáo.

Ranh giới này giữ cho bản triển khai nhẹ và có thể kiểm chứng: thứ chạy trên máy
chủ là một tập con nhỏ, không kéo theo toàn bộ công cụ nghiên cứu.

## Từ huấn luyện tới triển khai

```text
mô hình gốc → tinh chỉnh một phần nhỏ tham số → chọn điểm dừng bằng tập kiểm định
            → hợp nhất phần đã tinh chỉnh vào mô hình gốc
            → đánh giá lại trên tập kiểm tra
            → chuyển đổi sang dạng chạy nhanh trên CPU
```

Ba mô hình được so sánh bằng cùng một giao thức; chỉ một mô hình được triển
khai. Bản chuyển đổi được đánh giá lại trên đúng tập kiểm tra để xác nhận nó cho
kết quả tương đương bản gốc — bước chuyển đổi chỉ được phép làm nhanh hơn, không
được phép làm đổi câu trả lời.

## Dạng dữ liệu bên trong

Sau khi truy vấn chạy xong, dữ liệu chỉ còn là các dòng gồm cặp *tên cột — giá
trị*, với giá trị là chữ, số, đúng/sai hoặc rỗng.

Không có cấu trúc dữ liệu riêng cho từng loại câu trả lời học vụ. Nhờ vậy thêm
một dạng câu hỏi mới không đòi hỏi sửa phần định dạng.
