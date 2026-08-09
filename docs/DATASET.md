# Dữ liệu huấn luyện

## Trạng thái hiện tại

> **Dataset đã được sinh lại theo danh mục hiện hành và kiểm toàn chuỗi đạt.**
> Bộ hiện tại có **5.902 câu** (huấn luyện 5.204 · kiểm định 349 · kiểm tra 349).
>
> Bộ 4.454 câu mô tả ở cuối tài liệu được tạo trước đợt tái cấu trúc mạng lưới
> kiến thức và **không còn hợp lệ**: các truy vấn đích của nó dùng những quan hệ
> đã bị thay thế. Giữ lại chỉ để đối chiếu.

## Dataset này dạy mô hình việc gì

Đúng một việc: đọc một câu hỏi tiếng Việt và sinh ra **một** trong hai thứ —
một câu truy vấn, hoặc dòng chữ báo không có thông tin.

Cả hai nằm chung một bộ dữ liệu, không tách làm hai nhiệm vụ. Mô hình vì thế học
đồng thời cách truy vấn và cách nhận ra giới hạn của mình.

## Hình dạng một bản ghi

Mỗi dòng có đúng năm trường:

| Trường | Vai trò |
|---|---|
| mã câu hỏi | định danh duy nhất |
| dạng câu hỏi | nhóm các câu dùng chung một cấu trúc truy vấn |
| phong cách | một trong bốn cách diễn đạt (xem dưới) |
| câu hỏi | câu tiếng Việt tự nhiên, giữ nguyên như người dùng gõ |
| đích | câu truy vấn chuẩn, hoặc dòng chữ báo không có thông tin |

Một dạng câu hỏi có thể sinh ra nhiều đích khác nhau, vì cùng một cấu trúc truy
vấn có thể thay tên thực thể hoặc con số ở bên trong.

## Danh mục dạng câu hỏi

Dataset không được viết tự do. Mọi đích phải khớp **chính xác** một dạng câu hỏi
đã khai báo trong danh mục. Danh mục hiện có **183 dạng**, phân theo lĩnh vực:

| Lĩnh vực | Số dạng |
|---|---:|
| Quy tắc học vụ | 64 |
| Học phí | 32 |
| Quy trình học vụ | 24 |
| Tra cứu văn bản | 23 |
| Chứng chỉ | 23 |
| Biểu mẫu | 15 |
| Giới thiệu năng lực | 1 |
| Từ chối trả lời | 1 |

Trong đó **29 dạng được viết tay** vì máy không sinh được: chúng cần so sánh
ngưỡng ("7,5 điểm xếp loại gì", "70 tín chỉ là năm mấy", "học phí ngành X khoá
65"), gom nhiều thông tin về một bản ghi, đi ngược chiều đồ thị, hoặc trả **nội
dung kèm nguồn trích dẫn và đường dẫn văn bản gốc** trong cùng một lần hỏi.
153 dạng còn lại được sinh tự động từ mạng lưới kiến thức để bảo đảm không sót
khả năng nào.

### Hai tầng ưu tiên

Mỗi dạng mang một tầng. **63 dạng primary** là câu hỏi người dùng thật sự đặt,
nên bắt buộc có dữ liệu huấn luyện. **120 dạng secondary** vẫn truy vấn được ở
runtime và vẫn phủ danh mục khả năng trả lời, nhưng không tiêu ngân sách dạy học.

Số dạng primary **giảm dần theo chủ đích**: mỗi khi hai dạng hoá ra trả lời cùng
một câu hỏi của con người, dạng thừa bị hạ xuống secondary và dạng giữ lại được
mở rộng để trả trọn cụm thông tin. Ép model chọn giữa hai đích đều đúng chỉ dạy
nó đoán bừa.

Phân tầng tồn tại vì độ phủ và ngân sách dạy học là hai câu hỏi khác nhau. Bộ sinh
cơ học tạo cả những dạng hỏi vòng tròn — *"khoản 3 Điều 24 thuộc điều số mấy"* —
mà câu trả lời đã nằm sẵn trong câu hỏi. Chúng không chỉ tốn dữ liệu: chúng trông
gần giống các dạng hữu ích nên làm model lẫn khi chọn dạng.

Lĩnh vực **tra cứu văn bản** là mới. Nó phục vụ những câu hỏi nhắm thẳng vào
điều khoản — "Điều 24 quy định gì", "khoản 3 Điều 24 ghi gì", "điểm c khoản 1
Điều 25 ghi gì" — vốn không trả lời được ở bản trước. Cả ba cấp đều có một dạng
trả **nội dung kèm nguồn**.

## Bốn phong cách diễn đạt

Sinh viên không hỏi bằng văn phong hành chính. Dataset cố ý phủ bốn kiểu:

| Phong cách | Mô tả |
|---|---|
| Trang trọng | câu đầy đủ, gần văn bản hành chính |
| Thông thường | cách hỏi trung tính hằng ngày |
| Khẩu ngữ | "tui", "sao giờ", cách nói hội thoại |
| Có lỗi viết | viết tắt, thiếu dấu, lỗi gõ nhưng vẫn còn nghĩa |

## Ranh giới từ chối

Một câu chỉ nhận đích là truy vấn khi mạng lưới trả lời được **toàn bộ** yêu cầu.
Các câu còn lại nhận đích là dòng chữ báo không có thông tin, chia tám nhóm:
chào hỏi và trò chuyện, chủ đề không liên quan, gần phạm vi nhưng thiếu dữ liệu,
câu mơ hồ, câu ghép nhiều ý, câu dùng từ học vụ nhưng sai quan hệ, câu ngoài
phạm vi có lỗi viết, và **câu thiếu thông tin phân biệt**.

Nhóm cuối đáng nói riêng. Vài dạng câu hỏi cần hai thông tin mới trả lời được:
học phí cần cả ngành và khoá, quy đổi chứng chỉ cần cả loại và điểm. Hỏi *"học
phí khoá 67 là bao nhiêu"* thì khoá 67 có **năm** mức khác nhau tuỳ ngành — trả
một con số bất kỳ là trả lời sai. Những câu này được sinh bằng cách **đo trên đồ
thị**: chỉ giá trị nào thực sự cho ra nhiều đáp án mới thành câu từ chối, và chỉ
khi không dạng nào khác trả lời được phần còn lại.

Với câu ghép, hệ thống không trả lời một phần.

## Chia tập và chống rò rỉ

Ba tập: huấn luyện, kiểm định (chọn điểm dừng huấn luyện) và kiểm tra (đánh giá
cuối cùng, chỉ dùng một lần).

Mọi dạng câu hỏi phải xuất hiện ở cả ba tập. Tập huấn luyện phải phủ đủ bốn
phong cách cho mỗi dạng và toàn bộ các giá trị hữu hạn. Hai tập còn lại giữ lại
**cách diễn đạt chưa từng thấy**, chứ không giấu đi cấu trúc chưa từng được dạy
— mục tiêu là đo khả năng hiểu cách hỏi mới, không phải đoán mò cấu trúc lạ.

Mỗi dạng câu hỏi có **10 cách diễn đạt: dạy 8, giấu 1 cho kiểm định và 1 cho
kiểm tra**. Tỉ lệ giấu trước đây là 50% (4 trong 8) và đo được hậu quả rõ: có
13 cách diễn đạt bị giấu mà mô hình sai **toàn bộ** — sai hết nghĩa là chưa từng
được dạy, nên đó là phép đo cách hỏi lạ chứ không phải phép đo năng lực.

Cách diễn đạt nào bị giấu cũng **không được chọn theo độ khác lạ**. Bản trước
luôn giấu cách nói khác biệt nhất, khiến tập chấm toàn lối nói dị thường và mọi
điểm số đo được đều là cận dưới. Nay chọn theo một thứ tự ổn định không liên
quan tới độ khác lạ, nên tập chấm là mẫu đại diện.

Các ràng buộc được kiểm tra tự động:

1. mã câu hỏi duy nhất trong toàn bộ dataset;
2. không câu hỏi nào trùng nhau sau chuẩn hoá giữa các tập;
3. không có câu gần trùng cùng một dạng đi xuyên tập;
4. mọi đích trong phạm vi phải chạy được trên mạng lưới và trả về ít nhất một
   dòng dữ liệu;
5. mọi đích ngoài phạm vi trùng khớp chính xác dòng chữ từ chối;
6. các câu hỏi kiểm tra tay xuất hiện đúng một lần trong tập kiểm tra;
7. nội dung tập kiểm tra được niêm phong bằng mã băm.

Ràng buộc số 4 đáng chú ý: một đích chỉ được nhận nếu nó **thực sự lấy ra được
dữ liệu**. Điều này loại bỏ khả năng dạy mô hình sinh ra những truy vấn hợp lệ
về cú pháp nhưng rỗng ruột.

## Chuẩn hoá câu hỏi

Câu hỏi được lưu nguyên văn. Trước khi đưa vào mô hình, cả lúc huấn luyện lẫn
lúc chạy thật đều dùng chung một bước chuẩn hoá nhẹ: thống nhất cách mã hoá dấu
tiếng Việt, thu gọn khoảng trắng, và mở rộng một danh sách cố định các viết tắt
chắc nghĩa trong miền học vụ (ví dụ "hp" thành "học phần").

Bước này cố ý không dò tìm thực thể, không sửa từ gần đúng và không đoán ý.
Chuẩn hoá thông minh quá sẽ âm thầm làm thay việc của mô hình, khiến kết quả
đánh giá không còn phản ánh năng lực thật.

## Số liệu bộ dữ liệu cũ

Giữ lại để đối chiếu; **không còn hợp lệ** với mạng lưới hiện hành.

| Tập | Số câu |
|---|---:|
| Huấn luyện | 3.645 |
| Kiểm định | 402 |
| Kiểm tra | 407 |
| **Tổng** | **4.454** |

Bộ này phủ 51 dạng câu hỏi của danh mục cũ và chia theo lĩnh vực: quy trình học
vụ 2.552, học phí 363, quy tắc học vụ 295, chứng chỉ 271, biểu mẫu 146, từ chối
827.

## Tái tạo

Mạng lưới kiến thức, danh mục dạng câu hỏi, quy tắc độ phủ và ba tập dữ liệu là
đầu vào gốc. Danh mục khả năng trả lời, bản kê và các báo cáo là kết quả sinh ra
từ chúng.

```bash
uv run validate_sparql_dataset   # chỉ đọc, kiểm tra toàn chuỗi
uv run generate_reports          # chỉ ghi lại các kết quả dẫn xuất
```
