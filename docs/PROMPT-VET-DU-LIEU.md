# Prompt vét dữ liệu bằng deep research

Dán nguyên khối dưới đây vào ChatGPT hoặc Gemini ở chế độ deep research. **Không sửa gì**,
kể cả dòng đầu — mọi người dùng chung một prompt, chạy trên cả hai công cụ rồi gộp kết quả.
Chỗ nào hai bên khác nhau là chỗ cần mở văn bản gốc ra đối chiếu.

Prompt này thay cho bộ prompt dài theo chủ đề T01–T12 ở
[`ONTOLOGY-DEEP-RESEARCH-PROMPT.md`](ONTOLOGY-DEEP-RESEARCH-PROMPT.md). Bộ cũ vẫn dùng được khi
cần đào sâu một chủ đề, nhưng dài thì chất lượng kém đi, nên mặc định dùng bản ngắn này.

Định dạng trả về được thiết kế cho kiến trúc mới: **mỗi dòng bảng là một phát biểu độc lập kèm
nguồn của chính nó**, khớp đúng một câu ba phần cộng địa chỉ trích dẫn.

---

```markdown
Vét thông tin học vụ chính thức của Trường Đại học Nha Trang (NTU) mà sinh viên thường hỏi,
tập trung vào các mảng: giấy xác nhận và giấy tờ hành chính; miễn giảm học phí, trợ cấp xã hội
và chính sách hỗ trợ; mức học phí theo ngành và theo khoá, gia hạn đóng và nợ học phí; mã ngành,
khoa quản lý, tổng tín chỉ, thời gian đào tạo và chuẩn đầu ra ngoại ngữ/tin học của từng ngành;
danh bạ các đơn vị phục vụ sinh viên kèm địa chỉ, điện thoại, email, giờ làm việc; điểm rèn luyện,
khen thưởng, kỷ luật; ký túc xá, thư viện, bảo hiểm y tế, hỗ trợ việc làm; thẻ sinh viên, tài khoản
và các cổng thông tin trực tuyến; thủ tục nhập học và tuần sinh hoạt công dân.

Nguồn: chỉ dùng ntu.edu.vn và tên miền con (pdtdaihoc, phongctsv, phongkhtc, phongcntt, tuyensinh,
sinhvien, htdnhtsv, daotao, thuvien), cùng văn bản Bộ GD&ĐT / Chính phủ mà NTU dẫn chiếu. Không dùng
diễn đàn, mạng xã hội, trang tuyển sinh của bên thứ ba.

Bỏ qua nội dung 6 văn bản đã có: QĐ 1052 (17/7/2025) và QĐ 1965 sửa đổi, QĐ 626 (29/4/2026),
QĐ 753 (2021), QĐ 729 học phí, QĐ 317 học bổng, danh mục biểu mẫu Phòng Đào tạo.

Trả về markdown, mỗi dòng là MỘT phát biểu kèm nguồn của chính nó:

| Thực thể | Loại | Nội dung | Quan hệ | Trích dẫn | Văn bản | Link |
|---|---|---|---|---|---|---|
| Giấy xác nhận đang học | thủ tục | Sinh viên nộp đơn tại Phòng CTCT&SV, nhận kết quả sau 03 ngày làm việc. | nộp tại → Phòng CTCT&SV | mục 2 | Trang biểu mẫu Phòng CTCT&SV | https://... |

- Nội dung: chép sát nguyên văn, một dòng một ý, giữ nguyên con số và đơn vị.
- Trích dẫn: vị trí chính xác — "khoản 3 Điều 24", "điểm a khoản 1 Điều 25", "bảng 1 Phụ lục II".
  Không có trích dẫn thì bỏ dòng đó.
- Loại: thủ tục · quy tắc · đơn vị · biểu mẫu · ngành · khái niệm · mức thu.
- Quan hệ: chỉ ghi khi văn bản nói rõ (nộp tại, do ai thực hiện, quyết định bởi, dùng mẫu,
  thuộc khoa, áp dụng cho, thời hạn). Không có thì để trống.

Sau bảng: mục "Tên gọi khác" liệt kê cách gọi dân dã của từng thực thể; mục "Chưa tìm được"
liệt kê thứ không có nguồn chính thức.

Không suy đoán — không chắc thì cho vào "Chưa tìm được". Không thu thập danh sách sinh viên
hay thông tin cá nhân.
```

---

## Hai khoảng trống chờ đúng bộ dữ liệu này

- **18 chứng chỉ** chưa có nội dung nào; 12 cái có tên đầy đủ, còn tên gọi phụ theo ngôn ngữ thì
  đã thêm tay ngày 12/9. Cần: điều kiện công nhận, mức điểm quy đổi, thời hạn hiệu lực.
- **41 ngành đào tạo** mới chỉ có tên và khối ngành. Cần: mã ngành, khoa/viện quản lý, tổng tín
  chỉ, thời gian đào tạo chuẩn, chuẩn đầu ra ngoại ngữ và tin học.

Và một việc chờ kết quả để làm một lượt: **đối chiếu hai bộ biểu mẫu** — Phụ lục 4 của Quy chế
1052 với trang danh mục của Phòng Đào tạo. Hai nơi đánh số khác nhau (cùng một tờ đơn mang số 13
trên web và số 15 trong quy chế), 8 mục tải chưa nối biểu mẫu nào và 6 biểu mẫu chưa có mục tải.
