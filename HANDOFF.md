# Bàn giao — trạng thái ngày 21/08/2026

Tệp này ghi những gì đã đo được và những gì còn dở, để người tiếp nhận không phải
đo lại và không lặp lại các bẫy đã dính.

## 1. Trạng thái kho mã

Nhánh `dev`, **7 commit chưa đẩy lên**. Bộ kiểm: **364 xanh, 5 bỏ qua** (~9,5 phút).

⚠️ Trước khi đẩy, kiểm `du -sh .git` — phải khoảng **34 MB**. Có lúc nó phồng lên
851 MB vì hai gói đã biên dịch lọt vào lịch sử; đã gỡ và thêm luật bỏ qua. Dịch vụ
lưu trữ mã chặn tệp trên 100 MB nên lần đẩy sẽ hỏng giữa chừng nếu chúng quay lại.

## 2. Ba việc còn dở, xếp theo mức quan trọng

### 2.1 Báo cáo đang trộn ba cách chạy khác nhau — NGHIÊM TRỌNG NHẤT

| mục trong README | số | đo bằng |
|---|---|---|
| §7.1 bảng bốn mô hình | 81,8% · 86,3% · 78,2% | thư viện huấn luyện, **không phải bộ chạy đang phục vụ** |
| §7.5 đầu-cuối 85 câu | 47 đúng · 6,25 s | bộ chạy trên bộ xử lý trung tâm, nén 8 bit |
| §7.6 thời gian trong công cụ | 2.538 ms | bộ chạy trên card đồ hoạ, độ chính xác đầy đủ |

Bộ chạy đang phục vụ chấm **81,2 / 85,4 / 91,5**, không phải 81,8 / 86,3 / 92,1.

**Phải làm:** chấm lại bốn mô hình bằng đúng bộ chạy phục vụ trên đủ 390 câu, và đo
lại đầu-cuối trên card đồ hoạ để §7.5 và §7.6 cùng một nền. Cả hai là chạy lại bộ đo
có sẵn, không phải viết mới.

### 2.2 Đường biên dịch sẵn mới thử 40 câu

`src/ontchatbot/runtime/aoti.py` nhanh hơn 1,75 lần và cho **40/40 truy vấn giống
hệt** bộ chạy hiện tại, nhưng:

- chưa chạy đủ 390 câu bằng bộ chấm của dự án
- chưa thử trên máy phục vụ thật
- gói biên dịch cho **một đời card cụ thể**; dựng lại mất 76 giây
- lớp bọc còn dùng thư viện Python để nạp gói, nên **chưa bỏ được thư viện huấn
  luyện khỏi ảnh triển khai**; muốn bỏ hẳn phải viết bộ nạp bằng C++

**Chưa nên đưa vào phục vụ.** Nó là kết quả nghiên cứu, chưa phải sản phẩm.

### 2.3 55 nhãn từ chối gán sai

Trong 884 câu mang nhãn "không có thông tin", **55 câu đồ thị trả lời được**:
43 ở tập dạy, 6 ở tập kiểm định, 6 ở tập chấm. Cả 55 cùng một chủ đề — biểu mẫu xin
chuyển chương trình đào tạo.

Sửa nhãn kéo theo **huấn luyện lại cả bốn mô hình**. Đã công bố trong phần hạn chế
của README, chưa sửa. Danh sách mã số đầy đủ nằm trong báo cáo của lượt soát.

## 3. Số đã đo, dùng được ngay

### Bộ chạy: chọn card đồ hoạ ở độ chính xác đầy đủ

Cùng một bản mô hình, cùng 120 câu, cùng tiền xử lý, xử lý từng câu một:

| cách chạy | đúng | trung vị |
|---|---:|---:|
| bộ xử lý trung tâm, đầy đủ | 82,5% | 4.192 ms |
| bộ xử lý trung tâm, nén 8 bit | 82,5% | 1.893 ms |
| **card đồ hoạ, đầy đủ** | **82,5%** | **1.222 ms** |
| card đồ hoạ, nén 8 bit | 78,3% | 592 ms |
| card đồ hoạ, nửa độ chính xác | 80,0% | 692 ms |

**Nén 8 bit không mất điểm trên bộ xử lý trung tâm nhưng mất 4,2 điểm trên card.**
Khác biệt nằm ở nhân tính số nguyên của hai nền, không ở kiểu số bao quanh. Ở độ
chính xác đầy đủ, hai nền cho kết quả **giống nhau trên cả 120 câu**.

⚠️ **Không suy kết quả của nền này sang nền kia.**

### Chạy song song

Sáu người hỏi cùng lúc:

| | thời gian |
|---|---:|
| mặc định | 7.403 ms |
| số luồng mỗi bản dịch = 8 | 7.383 ms — **vô tác dụng trên card** |
| **số bản dịch song song = 6** | **5.677 ms** |
| nhiều bản sao mô hình | 5.941 ms — kém hơn, lại tốn bộ nhớ card |

Đặt số bản dịch song song bằng số người dùng đồng thời. Số luồng mỗi bản dịch chỉ
có tác dụng trên bộ xử lý trung tâm.

### Gộp lô

Trên **câu dài của bộ dữ liệu**: lô từ 8 trở xuống cho **0/120 câu đổi**, nhanh 6,3 lần.
Trên **cụm từ khoá ngắn**: **5/50 cụm đổi** truy vấn tuỳ cụm nào đi kèm.

Nên đường phục vụ giữ lô 1; đường chấm điểm bật lô 8.

⚠️ Ghi chú cũ nói "gộp 4 mất 3,6 điểm kể cả ở độ chính xác đầy đủ" — **sai, không
tái hiện được**.

### Cấu hình phục vụ

```
ONTCHATBOT_DEVICE=cuda
ONTCHATBOT_COMPUTE_TYPE=float32
ONTCHATBOT_INTER_THREADS=6
```

Thư viện cần thêm: `nvidia-cublas-cu12`. **Không cần cuDNN** — tiết kiệm 1,3 GB.
Không cần đặt đường tìm thư viện nếu gói nằm cùng môi trường.

## 4. Bẫy đã dính, đừng lặp lại

**Thước đo hỏng trông y hệt mô hình kém.** Ba lỗi phép đo trong một phiên, cả ba
đều cho ra số trông hợp lý: so nhầm chuỗi từ chối (đích thật là "không có thông
tin"), so hai lượt khác số vòng học, và đặt tên biến vòng lặp trùng biến toàn cục.
Dấu hiệu: con số tròn trĩnh bất thường như 0/55.

**So hai thước khác nhau.** Có lúc gộp khoản/điểm về điều rồi đặt cạnh mốc cũ vốn
đòi trúng đúng khoản/điểm. Luôn hỏi: hai con số này chia cho cùng mẫu số không.

**Chỉ số trộn hai bài toán.** "Từ chối đúng 92,1%" thực ra là quyết định trả
lời-hay-từ-chối trên cả 390 câu. Tách ra: bắt câu ngoài phạm vi **78,2%**, không từ
chối oan 94,3%. Gọi sai tên làm **đảo thứ hạng** giữa các mô hình.

**Tin số cũ mà không kiểm.** Hai kết luận trong bản ghi cũ hoá ra sai khi đo lại.
Bản ghi cũ đáng nghi khi nó đến từ cùng đợt với một phép đo đã biết là hỏng.

**Vòng chờ tự khớp chính nó.** Dò tiến trình theo chuỗi ký tự sẽ bắt trúng chính
lệnh đang chạy vòng lặp đó.

**Dọn tiến trình nền sau mỗi lượt đo.** Mỗi lượt giữ mô hình trong bộ nhớ máy lẫn
bộ nhớ card; để chồng chất sẽ làm treo máy.

## 5. Chi tiết kỹ thuật của gói biên dịch sẵn

Ba điều phải biết, mỗi điều từng chặn cả buổi:

1. Mô hình **không khai token mở đầu bộ giải mã** ở cả hai chỗ cấu hình; nó bắt đầu
   bằng token mở đầu chuỗi. Truy thẳng thuộc tính đó **ném lỗi** chứ không trả rỗng.
2. Hàm đóng gói **so sánh giá trị trả về với đường dẫn truyền vào**, và luôn trả về
   chuỗi — nên phải truyền chuỗi, không phải đối tượng đường dẫn.
3. Chiều dài chuỗi vào phải khai dạng **tám nhân một số trừ một**, vì bộ mã hoá đệm
   chuỗi về bội của tám.

Vòng giải mã chiếm **99,4%** thời gian, bộ mã hoá chỉ **0,6%**. Biên dịch riêng bộ
mã hoá là vô ích. Chỗ gỡ được bài toán là **cấp bộ nhớ đệm một lần cho trọn độ dài
tối đa**, để hình dạng phép tính cố định qua mọi bước.

## 6. Bản đồ tệp

`FILES.md` liệt kê cả 147 tệp mã và dữ liệu, mỗi tệp một dòng mô tả.
