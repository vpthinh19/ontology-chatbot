# Thông tin học vụ chính thức — Trường Đại học Nha Trang (NTU)
## Bản hợp nhất tốt nhất hiện tại — Cập nhật 12/09/2026

> **Phạm vi nguồn:** Sử dụng `ntu.edu.vn` và các tên miền con được phép: `pdtdaihoc`, `phongctsv`, `phongkhtc`, `phongcntt`, `tuyensinh`, `sinhvien`, `htdnhtsv`, `daotao`, `thuvien`, `ctdt`, `phongdbcl`, `pdtsaudaihoc`, `thanhnien`, `trungtamdtbd`, `xettuyen`. **Nguồn pháp lý bổ sung được chấp nhận** gồm `vanban.chinhphu.vn`, `chinhphu.vn`, `xaydungchinhsach.chinhphu.vn`, cổng Bộ GD&ĐT và các văn bản Chính phủ/Bộ mà NTU dẫn chiếu.
>
> **Đã loại khỏi căn cứ theo yêu cầu:** QĐ 1052 (17/7/2025) và QĐ 1965 sửa đổi, QĐ 626 (29/4/2026), QĐ 753 (2021), QĐ 729 học phí, QĐ 317 học bổng, danh mục biểu mẫu Phòng Đào tạo. Việc mở rộng whitelist tên miền không làm thay đổi danh sách văn bản bị loại này.
>
> **Nguyên tắc:** Mỗi dòng có nguồn riêng, kèm vị trí trích dẫn cụ thể. Chỉ ghi khi có nguồn chính thức; nội dung chưa xác minh đưa vào mục **Chưa tìm được**. Không suy đoán. Không thu thập danh sách sinh viên/thông tin cá nhân.
>
> **Schema fact:** Một thực thể có thể xuất hiện ở nhiều dòng nếu mỗi dòng biểu diễn một phát biểu khác nhau (ví dụ địa chỉ, chức năng, thủ tục). Đây không phải duplicate. Các loại dữ liệu dùng trong bản này gồm `đơn vị`, `thủ tục`, `quy tắc`, `biểu mẫu`, `ngành`, `chương trình`, `học phần`, `khái niệm`, `mức thu`. Record tuyển sinh theo mã ngành dùng `ngành`; record mô tả một CTĐT/phiên bản/khóa cụ thể dùng `chương trình`.

> **Thống kê kỹ thuật:** Mỗi dòng dữ liệu trong các bảng fact thuộc mục 1–9 được tính là **1 fact record**. Khóa dedupe chính xác là toàn bộ các trường nội dung cốt lõi của dòng sau chuẩn hóa Unicode NFC và khoảng trắng, **không tính** ba trường audit (`Trạng thái hiệu lực`, `Mức độ tin cậy`, `Ngày kiểm tra cuối`). Bản này có **204 dòng fact và 204 fact độc lập**; không có duplicate chính xác theo quy tắc trên. Alias, Audit, “Chưa tìm được” và bảng minh họa metadata không được tính.

---

## 1. Bảng thực thể — Đơn vị phục vụ sinh viên

| Thực thể | Loại | Nội dung | Quan hệ | Trích dẫn | Văn bản | Link | Mức độ tin cậy | Trạng thái hiệu lực | Ngày kiểm tra cuối |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Phòng Công tác Chính trị và Sinh viên | đơn vị | Tầng 1, Khu nhà Hiệu bộ; ĐT: 0258.2221900; Fax: 0258.3831147; Email: ctsv@ntu.edu.vn; Trưởng phòng: ThS. Đỗ Quốc Việt | thuộc → Trường ĐH Nha Trang | mục “Chức năng và trách nhiệm” | Trang giới thiệu đơn vị hỗ trợ sinh viên | https://ntu.edu.vn/sinh-vien/cac-%C4%91on-vi-ho-tro/phong-cong-tac-chinh-tri-va-sinh-vien | Cao | Hiện hành tại ngày kiểm tra | 12/09/2026 |
| Phòng CT&SV | đơn vị | Quản lý hồ sơ sinh viên; chính sách/quyền lợi; đề xuất khen thưởng, kỷ luật, thuyên chuyển; theo dõi SV ngoại trú; tiếp nhận và giải đáp thắc mắc người học | thuộc → Trường ĐH Nha Trang | mục “I. CHỨC NĂNG, NHIỆM VỤ” | Trang “Chức năng nhiệm vụ” Phòng CTSV | https://phongctsv.ntu.edu.vn/gioi-thieu/chuc-nang-nhiem-vu | Cao | Hiện hành tại ngày kiểm tra | 12/09/2026 |
| Ths. Đỗ Quốc Việt | khái niệm | Trưởng Phòng CTSV; phụ trách chung, chế độ chính sách, học bổng, học vụ, khen thưởng; chủ trì tổ chức cuộc thi học thuật, phong trào VH-VN-TDTT | phụ trách → Phòng CTSV | mục “II. PHÂN CÔNG NHIỆM VỤ”, mục 1 | Trang “Chức năng nhiệm vụ” Phòng CTSV | https://phongctsv.ntu.edu.vn/gioi-thieu/chuc-nang-nhiem-vu | Cao | Hiện hành tại ngày kiểm tra | 12/09/2026 |
| Ths. Ngô Văn An | khái niệm | Phó Trưởng Phòng CTSV; giáo dục chính trị tư tưởng; triển khai văn hóa học đường; tổ chức Tuần sinh hoạt công dân; phổ biến pháp luật, phòng chống tệ nạn | phụ trách → Tuần sinh hoạt công dân | mục “II. PHÂN CÔNG NHIỆM VỤ”, mục 2 | Trang “Chức năng nhiệm vụ” Phòng CTSV | https://phongctsv.ntu.edu.vn/gioi-thieu/chuc-nang-nhiem-vu | Cao | Hiện hành tại ngày kiểm tra | 12/09/2026 |
| Ths Vũ Thị Nhung | khái niệm | Cán bộ Phòng CTSV; quản lý BHYT, BHTT cho SV chính quy; thông tin kết quả học tập, rèn luyện về gia đình SV | phụ trách → BHYT sinh viên | mục “II. PHÂN CÔNG NHIỆM VỤ”, mục 3 | Trang “Chức năng nhiệm vụ” Phòng CTSV | https://phongctsv.ntu.edu.vn/gioi-thieu/chuc-nang-nhiem-vu | Cao | Hiện hành tại ngày kiểm tra | 12/09/2026 |
| CV Nguyễn Trần Ngọc Hiếu | khái niệm | Cán bộ Phòng CTSV; quản lý SV ngoại trú; thuyên chuyển SV; tổng hợp danh sách SV buộc thôi học; chủ trì in, cấp, phát thẻ SV | phụ trách → thẻ sinh viên | mục “II. PHÂN CÔNG NHIỆM VỤ”, mục 4 | Trang “Chức năng nhiệm vụ” Phòng CTSV | https://phongctsv.ntu.edu.vn/gioi-thieu/chuc-nang-nhiem-vu | Cao | Hiện hành tại ngày kiểm tra | 12/09/2026 |
| CV Trần Thị Thùy Dương | khái niệm | Cán bộ Phòng CTSV; quản lý hồ sơ chế độ chính sách, học bổng; quản lý trang web Phòng | phụ trách → chế độ chính sách, học bổng | mục “II. PHÂN CÔNG NHIỆM VỤ”, mục 6 | Trang “Chức năng nhiệm vụ” Phòng CTSV | https://phongctsv.ntu.edu.vn/gioi-thieu/chuc-nang-nhiem-vu | Cao | Hiện hành tại ngày kiểm tra | 12/09/2026 |
| CV. Trang Kim Yến | khái niệm | Cán bộ Phòng CTSV; tiếp nhận giấy vay vốn; khen thưởng, kỷ luật sinh viên | phụ trách → khen thưởng, kỷ luật | mục “II. PHÂN CÔNG NHIỆM VỤ”, mục 7 | Trang “Chức năng nhiệm vụ” Phòng CTSV | https://phongctsv.ntu.edu.vn/gioi-thieu/chuc-nang-nhiem-vu | Cao | Hiện hành tại ngày kiểm tra | 12/09/2026 |
| CV. Trần Thị Thu Trang | khái niệm | Cán bộ Phòng CTSV; đầu mối cựu sinh viên; đồng phụ trách Tuần sinh hoạt công dân | phụ trách → cựu sinh viên, Tuần SHCD | mục “II. PHÂN CÔNG NHIỆM VỤ”, mục 8 | Trang “Chức năng nhiệm vụ” Phòng CTSV | https://phongctsv.ntu.edu.vn/gioi-thieu/chuc-nang-nhiem-vu | Cao | Hiện hành tại ngày kiểm tra | 12/09/2026 |
| Phòng Đào tạo Đại học | đơn vị | Tầng 1, Tòa nhà Hiệu Bộ; ĐT: 02583831148; Email: daotao@ntu.edu.vn; Trưởng phòng: PGS.TS. Tô Văn Phương | thuộc → Trường ĐH Nha Trang | mục “Liên hệ” footer | Trang chủ Phòng Đào tạo Đại học | https://pdtdaihoc.ntu.edu.vn/ | Cao | Hiện hành tại ngày kiểm tra | 12/09/2026 |
| PGS.TS. Tô Văn Phương | khái niệm | Trưởng phòng Đào tạo; Email: phuongtv@ntu.edu.vn; ĐT: 0905.398.699; kế hoạch phát triển đào tạo, tổ chức và liên kết đào tạo, kiểm định chất lượng | phụ trách → Phòng Đào tạo | mục “Phân công nhiệm vụ”, dòng 1 | Trang “Chức năng nhiệm vụ Phòng Đào tạo” | https://pdtdaihoc.ntu.edu.vn/gioi-thieu/chuc-nang-nhiem-vu | Cao | Hiện hành tại ngày kiểm tra | 12/09/2026 |
| TS. Phạm Thanh Nhựt | khái niệm | Phó trưởng phòng Đào tạo; Email: nhutpt@ntu.edu.vn; quản lý phát triển ngành, CTĐT, đề cương học phần ĐH; chương trình trao đổi SV | phụ trách → Phòng Đào tạo | mục “Phân công nhiệm vụ”, dòng 2 | Trang “Chức năng nhiệm vụ Phòng Đào tạo” | https://pdtdaihoc.ntu.edu.vn/gioi-thieu/chuc-nang-nhiem-vu | Cao | Hiện hành tại ngày kiểm tra | 12/09/2026 |
| ThS. Đỗ Văn Cao | khái niệm | Phó trưởng phòng Đào tạo; Email: caodv@ntu.edu.vn; kế hoạch đào tạo, giáo vụ/học vụ ĐH chính quy, tốt nghiệp, CTĐT đặc biệt | phụ trách → Phòng Đào tạo | mục “Phân công nhiệm vụ”, dòng 3 | Trang “Chức năng nhiệm vụ Phòng Đào tạo” | https://pdtdaihoc.ntu.edu.vn/gioi-thieu/chuc-nang-nhiem-vu | Cao | Hiện hành tại ngày kiểm tra | 12/09/2026 |
| ThS. Đỗ Thị Hương | khái niệm | Chuyên viên Phòng Đào tạo; Email: huongdt@ntu.edu.vn; học vụ cho Khoa Cơ khí, KTGT, CNTT, KHXH&NV, Ngoại ngữ | phụ trách học vụ → 5 khoa | mục “Phân công nhiệm vụ”, dòng 5 | Trang “Chức năng nhiệm vụ Phòng Đào tạo” | https://pdtdaihoc.ntu.edu.vn/gioi-thieu/chuc-nang-nhiem-vu | Cao | Hiện hành tại ngày kiểm tra | 12/09/2026 |
| CN. Ngô Thị Thu Hạnh | khái niệm | Chuyên viên Phòng Đào tạo; Email: hanhntt@ntu.edu.vn; học vụ cho Khoa Điện-Điện tử, Xây dựng, CNTP, Viện NTTS, KTTS, CNSH&MT | phụ trách học vụ → 6 đơn vị | mục “Phân công nhiệm vụ”, dòng 6 | Trang “Chức năng nhiệm vụ Phòng Đào tạo” | https://pdtdaihoc.ntu.edu.vn/gioi-thieu/chuc-nang-nhiem-vu | Cao | Hiện hành tại ngày kiểm tra | 12/09/2026 |
| ThS. Vương Thị Bích Hảo | khái niệm | Chuyên viên Phòng Đào tạo; Email: haovtb@ntu.edu.vn; học vụ cho Khoa Du lịch, Kinh tế, Kế toán | phụ trách học vụ → 3 khoa | mục “Phân công nhiệm vụ”, dòng 7 | Trang “Chức năng nhiệm vụ Phòng Đào tạo” | https://pdtdaihoc.ntu.edu.vn/gioi-thieu/chuc-nang-nhiem-vu | Cao | Hiện hành tại ngày kiểm tra | 12/09/2026 |
| Phòng Tài chính | đơn vị | Tòa nhà A8; ĐT: 02583831150; Email: khtc@ntu.edu.vn; Trưởng phòng: PGS.TS Phạm Hồng Mạnh; tham mưu tài chính, kế toán, đầu tư, xây dựng cơ bản | thuộc → Trường ĐH Nha Trang | mục “Liên hệ” footer | Trang chủ Phòng Tài chính | https://phongkhtc.ntu.edu.vn/ | Cao | Hiện hành tại ngày kiểm tra | 12/09/2026 |
| Phòng Tài chính | đơn vị | Chức năng gồm 5 mảng: (1) Tài chính và kế toán — tham mưu mức thu học phí/phí/giá dịch vụ, đề án học phí hằng năm, quản lý thu-chi; (2) Kế hoạch và tự chủ tài chính; (3) Đầu tư, mua sắm; (4) Đấu thầu, đấu giá; (5) Công tác khác |  | mục “CHỨC NĂNG - NHIỆM VỤ”, đề mục 1a | Trang “Chức năng - Nhiệm vụ” Phòng Tài chính | https://phongkhtc.ntu.edu.vn/gioi-thieu/chuc-nang-nhiem-vu | Cao | Hiện hành tại ngày kiểm tra | 12/09/2026 |
| Phòng Hạ tầng và CNTT | đơn vị | Tòa nhà Đa Năng, phòng 506; ĐT: 0258.2461.303; Email: cntt@ntu.edu.vn; hỗ trợ tài khoản và thư điện tử SV | hỗ trợ → tài khoản, email | mục “Các đơn vị chức năng” | Trang Liên hệ NTU | https://ntu.edu.vn/lien-he | Cao | Hiện hành tại ngày kiểm tra | 12/09/2026 |
| Trung tâm Hỗ trợ Việc làm và Khởi nghiệp | đơn vị | Tầng 2, Tòa nhà A3; ĐT: 0258.6280441; Email: tttvhtsv@ntu.edu.vn; kết nối doanh nghiệp, hỗ trợ việc làm, thực tập, kỹ năng mềm, khởi nghiệp | hỗ trợ → việc làm, kỹ năng mềm | phần “Chức năng” | Trang Trung tâm HTVL&KN | https://htdnhtsv.ntu.edu.vn/ | Cao | Hiện hành tại ngày kiểm tra | 12/09/2026 |
| Trung tâm Thông tin và Tư liệu (Thư viện) | đơn vị | Số 2 Nguyễn Đình Chiểu, phường Bắc Nha Trang; Email: tttl@ntu.edu.vn; cán bộ Vũ Thị Trang: 0258 471 773, tv@ntu.edu.vn |  | mục “Liên hệ” cuối trang | Trang chủ Thư viện NTU | https://thuvien.ntu.edu.vn/ | Cao | Hiện hành tại ngày kiểm tra | 12/09/2026 |
| Trung tâm Giáo dục quốc phòng và An ninh | đơn vị | Phụ trách đăng ký/hủy học phần GDTC và GDQP-AN | phụ trách → đăng ký/hủy học phần | mục “Các đơn vị chức năng” | Trang Liên hệ NTU | https://ntu.edu.vn/lien-he | Cao | Hiện hành tại ngày kiểm tra | 12/09/2026 |
| Trung tâm Đào tạo và Bồi dưỡng | đơn vị | Tầng 3 Tòa Nhà Đa Năng; tuyển sinh lớp vừa làm vừa học, liên thông đại học | thuộc → Trường ĐH Nha Trang | mục giới thiệu | Trang chủ Trung tâm Đào tạo và Bồi dưỡng | https://trungtamdtbd.ntu.edu.vn/ | Cao | Hiện hành tại ngày kiểm tra | 12/09/2026 |
| Trường Đại học Nha Trang | đơn vị | Trụ sở: 02 Nguyễn Đình Chiểu, phường Bắc Nha Trang, Khánh Hòa; ĐT: 02583831149; Email: dhnt@ntu.edu.vn |  | mục “Liên hệ” footer | Trang chủ ntu.edu.vn | https://ntu.edu.vn/ | Cao | Hiện hành tại ngày kiểm tra | 12/09/2026 |

---

## 2. Bảng thực thể — Cổng thông tin, tài khoản, thủ tục hành chính

| Thực thể | Loại | Nội dung | Quan hệ | Trích dẫn | Văn bản | Link | Mức độ tin cậy | Trạng thái hiệu lực | Ngày kiểm tra cuối |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Cổng sinhvien.ntu.edu.vn | đơn vị | Hệ thống đăng nhập quản lý đào tạo; hiển thị chức năng App Mobile SV, thông báo học phí/BHYT | dùng cho → quản lý đào tạo | trang đăng nhập | Cổng Sinh viên NTU | https://sinhvien.ntu.edu.vn/ | Cao | Hiện hành tại ngày kiểm tra | 12/09/2026 |
| Tài khoản website sinh viên | quy tắc | Tài khoản là mã số SV in trên giấy báo nhập học/biên lai học phí; mật khẩu mặc định là số CCCD/CMND/ngày sinh khi đăng ký xét tuyển | đăng nhập → sinhvien.ntu.edu.vn | mục hướng dẫn đăng nhập | Hướng dẫn đăng nhập | https://phongcntt.ntu.edu.vn/uploads/4/files/2.DangNhap.pdf | Cao | Hiện hành tại ngày kiểm tra | 12/09/2026 |
| Email sinh viên | khái niệm | Sau khi đăng nhập, SV xem được tên ngành, tên lớp và địa chỉ email tên miền ntu.edu.vn | cung cấp qua → tài khoản | nội dung hướng dẫn | Hướng dẫn Phòng CNTT | https://phongcntt.ntu.edu.vn/thong-bao/huong-dan-dang-nhap-website-sinh-vien-va-su-dung-email-sinh-vien | Cao | Hiện hành tại ngày kiểm tra | 12/09/2026 |
| Mật khẩu mặc định | quy tắc | Nhà trường yêu cầu SV không sử dụng mật khẩu mặc định cho cả email và website SV | phải đổi → sinh viên | ghi chú trong hướng dẫn | Hướng dẫn Phòng CNTT | https://phongcntt.ntu.edu.vn/thong-bao/huong-dan-dang-nhap-website-sinh-vien-va-su-dung-email-sinh-vien | Cao | Hiện hành tại ngày kiểm tra | 12/09/2026 |
| Phương thức đóng học phí online | thủ tục | Vào sinhvien.ntu.edu.vn → học phí → đóng qua cổng VnPay, hoặc quét QR bằng app ngân hàng | thực hiện tại → sinhvien.ntu.edu.vn | mục 1 | Thông báo cách thức nộp học phí | https://phongcntt.ntu.edu.vn/thong-bao/thong-bao-cach-thuc-nop-hoc-phi-sinh-vien | Cao | Hiện hành tại ngày kiểm tra | 12/09/2026 |
| Agribank, VietinBank, LPBank | thủ tục | Dùng Mobile Banking/Internet Banking của 03 ngân hàng để đóng học phí | dùng để → nộp học phí | mục 2 | Thông báo cách thức nộp học phí | https://phongcntt.ntu.edu.vn/thong-bao/thong-bao-cach-thuc-nop-hoc-phi-sinh-vien | Cao | Hiện hành tại ngày kiểm tra | 12/09/2026 |
| Đăng ký giấy xác nhận vay vốn online | thủ tục | Giấy xác nhận vay vốn in theo Mẫu 01/TDSV từ phần mềm quản lý SV; nhận bản cứng tại Phòng CTCTSV (P.114); thời gian 04 ngày (không tính T7, CN) | nộp tại → Phòng CTCTSV (P.114) | mục “ĐĂNG KÝ GIẤY XÁC NHẬN VAY VỐN ONLINE” | Trang “Quy trình xử lý công việc” Phòng CTSV | https://phongctsv.ntu.edu.vn/van-ban-bieu-mau/quy-trinh-xu-ly-cong-viec | Cao | Hiện hành tại ngày kiểm tra | 12/09/2026 |
| Giấy xác nhận đang học | biểu mẫu | Mục 18 trong danh mục biểu mẫu Phòng CTSV; dùng xác nhận SV đang học để hưởng ưu đãi giáo dục | dùng mẫu → Phòng CTCT&SV | mục 18 | Danh mục biểu mẫu Phòng CTSV | https://phongctsv.ntu.edu.vn/van-ban-bieu-mau/bieu-mau | Cao | Hiện hành tại ngày kiểm tra | 12/09/2026 |
| Giấy xác nhận đang học | thủ tục | Trang “Liên hệ” NTU hướng dẫn SV liên hệ thư ký văn phòng khoa/viện quản lý ngành học | liên hệ → Khoa/Viện | mục “Các đơn vị chức năng”, mục 10 | Trang Liên hệ NTU | https://ntu.edu.vn/lien-he | Cao | Hiện hành tại ngày kiểm tra | 12/09/2026 |
| Thẻ sinh viên | thủ tục | Phòng CTCT&SV xử lý việc in thẻ sinh viên | xử lý bởi → Phòng CTCT&SV | mục “Các đơn vị chức năng” | Trang Liên hệ NTU | https://ntu.edu.vn/lien-he | Cao | Hiện hành tại ngày kiểm tra | 12/09/2026 |
| Phúc khảo bài thi | thủ tục | SV muốn phúc khảo nộp đơn tại Khoa/Viện quản lý ngành học | nộp tại → Khoa/Viện | mục “Các đơn vị chức năng” | Trang Liên hệ NTU | https://ntu.edu.vn/lien-he | Cao | Hiện hành tại ngày kiểm tra | 12/09/2026 |
| Nhập học 2026 | thủ tục | Đăng ký KTX online, đóng học phí tại `xettuyen.ntu.edu.vn/NhapHoc`; thời gian nộp HP từ 12/08/2026 đến 23/08/2026 | thực hiện tại → xettuyen.ntu.edu.vn/NhapHoc | mục 2.1 | Hướng dẫn nhập học 2026 | https://xettuyen.ntu.edu.vn/ | Cao | Hiện hành tại ngày kiểm tra | 12/09/2026 |
| Hồ sơ nhập học | thủ tục | Giấy chứng nhận kết quả thi THPT, giấy khai sinh, học bạ THPT, bằng tốt nghiệp THPT, CCCD | nộp cho → NTU | mục “Bước 4. Nộp hồ sơ nhập học” | Hướng dẫn nhập học 2026 | https://xettuyen.ntu.edu.vn/ | Cao | Hiện hành tại ngày kiểm tra | 12/09/2026 |
| Chế độ chính sách khi nhập học | thủ tục | Giấy tờ chế độ chính sách nộp tại Phòng CTSV sau khi vào học kỳ chính | nộp tại → Phòng CTCT&SV | ghi chú sau danh mục hồ sơ | Hướng dẫn nhập học 2026 | https://xettuyen.ntu.edu.vn/ | Cao | Hiện hành tại ngày kiểm tra | 12/09/2026 |
| Tuần sinh hoạt công dân – sinh viên K68 | thủ tục | Lịch tuần SHCD-SV khóa 68-2026; nội dung gồm giới thiệu trường, công tác SV, đào tạo, thư viện, tài chính, Đoàn-Hội | áp dụng cho → khóa 68 | lịch ngày 18/8 | Lịch Tuần SHCD-SV K68 | https://tuyensinh.ntu.edu.vn/dai-hoc/nhap-hoc | Cao | Hiện hành tại ngày kiểm tra | 12/09/2026 |

---

## 3. Bảng thực thể — Học phí, miễn giảm, chính sách hỗ trợ

| Thực thể | Loại | Nội dung | Quan hệ | Trích dẫn | Văn bản | Link | Mức độ tin cậy | Trạng thái hiệu lực | Ngày kiểm tra cuối |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Học phí | khái niệm | Xác định theo khung tại Điều 10 NĐ 238/2025/NĐ-CP; cơ sở GD công lập căn cứ mức trần và định mức kinh tế-kỹ thuật để quyết định mức thu cụ thể | xác định bởi → cơ sở GD và khung pháp lý | Điều 10 NĐ 238/2025/NĐ-CP | NĐ 238/2025/NĐ-CP | https://vanban.chinhphu.vn/?pageid=27160&docid=215169&classid=1 | Cao | Có hiệu lực/chưa thấy văn bản thay thế | 12/09/2026 |
| Học phí theo tín chỉ | quy tắc | “Tổng học phí theo tín chỉ tối đa bằng tổng học phí tính theo niên chế” | giới hạn bởi → tổng HP toàn khóa | phần “Học phí đào tạo đại học tính theo tín chỉ” | NĐ 238/2025/NĐ-CP | https://vanban.chinhphu.vn/?pageid=27160&docid=215169&classid=1 | Cao | Có hiệu lực/chưa thấy văn bản thay thế | 12/09/2026 |
| Học phí khi học quá thời hạn | quy tắc | Học phí tín chỉ từ thời điểm quá hạn được xác định lại trên cơ sở thời gian học thực tế và bù đắp chi phí | áp dụng cho → SV quá thời hạn | phần “Học phí đào tạo đại học tính theo tín chỉ” | NĐ 238/2025/NĐ-CP | https://vanban.chinhphu.vn/?pageid=27160&docid=215169&classid=1 | Cao | Có hiệu lực/chưa thấy văn bản thay thế | 12/09/2026 |
| Học lại | quy tắc | Mức học phí học lại tối đa không vượt mức trần tương ứng, trừ trường hợp tổ chức học riêng theo nhu cầu | áp dụng cho → học lại | phần “Các cơ sở GD công lập quy định mức học phí học lại” | NĐ 238/2025/NĐ-CP | https://vanban.chinhphu.vn/?pageid=27160&docid=215169&classid=1 | Cao | Có hiệu lực/chưa thấy văn bản thay thế | 12/09/2026 |
| Sinh viên khuyết tật | khái niệm | HS, SV trong cơ sở GD nghề nghiệp và GD đại học là người khuyết tật thuộc đối tượng miễn học phí | áp dụng cho → miễn học phí | khoản 3 Điều 15 | NĐ 238/2025/NĐ-CP | https://vanban.chinhphu.vn/?pageid=27160&docid=215169&classid=1 | Cao | Có hiệu lực/chưa thấy văn bản thay thế | 12/09/2026 |
| Người học 16–22 tuổi hưởng TCXH hằng tháng | khái niệm | Người 16–22 tuổi đang học ĐH văn bằng thứ nhất thuộc nhóm hưởng TCXH theo khoản 1, 2 Điều 5 NĐ 20/2021/NĐ-CP được miễn học phí | áp dụng cho → miễn học phí | khoản 4 Điều 15 | NĐ 238/2025/NĐ-CP | https://vanban.chinhphu.vn/?pageid=27160&docid=215169&classid=1 | Cao | Có hiệu lực/chưa thấy văn bản thay thế | 12/09/2026 |
| Học bổng 4,2 triệu đồng/tháng | mức thu | Chương trình vi mạch bán dẫn và ngành khoa học cơ bản trình độ ĐH: 4.200.000 đồng/tháng | áp dụng cho → nhóm vi mạch bán dẫn/KH cơ bản | phần “Mức học bổng”, SV đại học | NĐ 179/2026/NĐ-CP | https://phongctsv.ntu.edu.vn/uploads/46/files/2026/269-179-ndcp.signed.pdf | Cao | Có hiệu lực/chưa thấy văn bản thay thế | 12/09/2026 |
| Học bổng 3,7 triệu đồng/tháng | mức thu | Chương trình ngành kỹ thuật then chốt và công nghệ chiến lược trình độ ĐH: 3.700.000 đồng/tháng | áp dụng cho → nhóm KT then chốt/CN chiến lược | phần “Mức học bổng”, SV đại học | NĐ 179/2026/NĐ-CP | https://phongctsv.ntu.edu.vn/uploads/46/files/2026/269-179-ndcp.signed.pdf | Cao | Có hiệu lực/chưa thấy văn bản thay thế | 12/09/2026 |
| Chính sách học bổng NĐ 179/2026 | quy tắc | Áp dụng cho đối tượng tuyển sinh từ năm 2025 trở đi; thời điểm cấp học bổng tính từ 01/09/2026 | áp dụng từ → 01/09/2026 | điều khoản hiệu lực | NĐ 179/2026/NĐ-CP | https://phongctsv.ntu.edu.vn/uploads/46/files/2026/269-179-ndcp.signed.pdf | Cao | Lịch sử/đối chiếu | 12/09/2026 |
| Danh mục 111 ngành học bổng | khái niệm | QĐ 1826/QĐ-BGDĐT xác định 111 ngành thuộc 15 nhóm; mã ngành là căn cứ xác định | áp dụng theo → mã ngành | nguyên tắc áp dụng; Phụ lục | QĐ 1826/QĐ-BGDĐT 26/06/2026 | https://phongctsv.ntu.edu.vn/uploads/46/files/2026/269-qd-1826.pdf | Cao | Có hiệu lực/chưa thấy văn bản thay thế | 12/09/2026 |
| Nợ học phí | quy tắc | Quy trình thu HP có biểu “DANH SÁCH SINH VIÊN NỢ HỌC PHÍ”, theo dõi HP dư đầu kỳ, phải đóng, đã đóng, còn phải đóng | theo dõi bởi → quy trình thu HP | Mẫu 03 | Quy trình thu học phí NTU | https://phongkhtc.ntu.edu.vn/uploads/1/Doc/779/quy-trinh-thu-hoc-phi-cua-truong-dai-hoc-nha-trang-pdf.pdf | Cao | Hiện hành tại ngày kiểm tra | 12/09/2026 |
| Cấm thi/hủy đăng ký do nợ HP | quy tắc | Trang Phòng KHTC ghi nhận danh sách SV dự kiến “cấm thi và hủy kết quả đăng ký môn học do nợ học phí” | áp dụng khi → nợ học phí | thông báo ngày 01/12/2023 | Trang Phòng KHTC | https://phongkhtc.ntu.edu.vn/ | Cao | Lịch sử/đối chiếu | 12/09/2026 |
| Bảo hiểm y tế | thủ tục | Cổng `sinhvien.ntu.edu.vn` trực tiếp hiển thị thông báo “Đóng tiền BHYT, BHTT sinh viên năm học 2026-2027”; thông báo nêu BHYT là bắt buộc và BHTT là tự nguyện. | đóng tại → NTU | thông báo trên cổng SV | Cổng Sinh viên NTU | https://sinhvien.ntu.edu.vn/ | Cao | Đang áp dụng theo mốc nêu trong record | 12/09/2026 |
| Bảo hiểm thân thể | mức thu | Cổng `sinhvien.ntu.edu.vn` trực tiếp ghi mức phí BHTT tự nguyện là 150.000 đồng/1 năm. | tự nguyện → sinh viên | thông báo năm học 2026-2027 | Cổng Sinh viên NTU | https://sinhvien.ntu.edu.vn/ | Cao | Đang áp dụng theo mốc nêu trong record | 12/09/2026 |
| Trợ cấp xã hội | mức thu | NTU công bố hồ sơ/trang quyết định TCXH theo học kỳ; mức cụ thể lấy từ quyết định chi tương ứng | áp dụng theo → quyết định từng HK | trang “Chính sách” | Phòng CTCT&SV | https://phongctsv.ntu.edu.vn/che-%C4%91o-chinh-sach/chinh-sach | Cao | Hiện hành tại ngày kiểm tra | 12/09/2026 |
| QĐ 1314/QĐ-ĐHNT | quy tắc | Ban hành Quy trình thu học phí của Trường ĐH Nha Trang, ban hành ngày 28/08/2025 |  | mục “Danh mục” hàng 25 | Trang Văn bản Phòng Tài chính | https://phongkhtc.ntu.edu.vn/uploads/1/Doc/779/quy-trinh-thu-hoc-phi-cua-truong-dai-hoc-nha-trang-pdf.pdf | Cao | Có hiệu lực/chưa thấy văn bản thay thế | 12/09/2026 |
| QĐ 1025/QĐ-ĐHNT | quy tắc | Ban hành Quy chế Quản lý công nợ của Trường ĐH Nha Trang, ban hành ngày 18/08/2023 |  | mục “Danh mục” hàng 55 | Trang Văn bản Phòng Tài chính | https://phongkhtc.ntu.edu.vn/uploads/1/Doc/242/qd-1025---ban-hanh-quy-che-quan-ly-cong-no.pdf.pdf | Cao | Chưa xác định | 12/09/2026 |
| QĐ 1413/QĐ-ĐHNT | quy tắc | Ban hành Quy định đóng học phí, ban hành ngày 18/10/2022 — căn cứ pháp lý cho thông báo đóng HP từng học kỳ | căn cứ → thông báo đóng HP | mục “Danh mục” hàng 59 | Trang Văn bản Phòng Tài chính | https://phongkhtc.ntu.edu.vn/uploads/1/Doc/240/quy-%C4%91%E1%BB%8Bnh-1413-(18102022)--%C4%91%C3%B3ng-h%E1%BB%8Dc-ph%C3%AD.pdf.pdf | Cao | Chưa xác định | 12/09/2026 |

---

## 4. Bảng thực thể — Điểm rèn luyện, khen thưởng, kỷ luật

| Thực thể | Loại | Nội dung | Quan hệ | Trích dẫn | Văn bản | Link | Mức độ tin cậy | Trạng thái hiệu lực | Ngày kiểm tra cuối |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Đánh giá điểm rèn luyện | thủ tục | Quy trình chính thức của Phòng CTSV xác nhận chuỗi bước: HSSV tự đánh giá → Chi hội chấm điểm công khai → Liên chi hội Khoa/Viện kiểm tra → Hội SV trường kiểm tra/xác nhận → đơn vị phụ trách tổng hợp. Các mốc tuần 2–7 từng xuất hiện trong bản trích xuất trước chưa được tái xác minh đầy đủ ở lần kiểm tra 12/09/2026 nên không dùng làm fact chính. | căn cứ → QĐ 60/2007/QĐ-BGDĐT | mục “Quy trình đánh giá điểm rèn luyện”, bảng quy trình | Trang “Quy trình xử lý công việc” Phòng CTSV | https://phongctsv.ntu.edu.vn/van-ban-bieu-mau/quy-trinh-xu-ly-cong-viec | Trung bình | Hiện hành tại ngày kiểm tra | 12/09/2026 |
| Mẫu phiếu đánh giá điểm rèn luyện | biểu mẫu | Mục 2 trong danh mục biểu mẫu Phòng CTSV | dùng mẫu → đánh giá ĐRL | mục 2 | Danh mục biểu mẫu Phòng CTSV | https://phongctsv.ntu.edu.vn/uploads/46/files/Bi%E1%BB%83u%20m%E1%BA%ABu%20CTSV/2_%20Phieu%20ren%20luyen.doc | Cao | Hiện hành tại ngày kiểm tra | 12/09/2026 |
| Quy chế đánh giá rèn luyện | quy tắc | Quy chế đánh giá điểm rèn luyện sinh viên, áp dụng từ năm học 2015-2016 |  | mục “Văn bản của Trường” | Trang Văn bản Phòng CTSV | https://phongctsv.ntu.edu.vn/uploads/46/files/van-ban-truong/QC%20REN%20LUYEN.pdf | Cao | Hiện hành tại ngày kiểm tra | 12/09/2026 |
| Khen thưởng | đơn vị | Phòng CTCT&SV phụ trách đề xuất khen thưởng sinh viên | đề xuất bởi → Phòng CTCT&SV | mục “Chức năng và trách nhiệm” | Trang Phòng CTCT&SV | https://ntu.edu.vn/sinh-vien/cac-%C4%91on-vi-ho-tro/phong-cong-tac-chinh-tri-va-sinh-vien | Cao | Hiện hành tại ngày kiểm tra | 12/09/2026 |
| Kỷ luật | đơn vị | Phòng CTCT&SV phụ trách đề xuất kỷ luật sinh viên | đề xuất bởi → Phòng CTCT&SV | mục “Chức năng và trách nhiệm” | Trang Phòng CTCT&SV | https://ntu.edu.vn/sinh-vien/cac-%C4%91on-vi-ho-tro/phong-cong-tac-chinh-tri-va-sinh-vien | Cao | Hiện hành tại ngày kiểm tra | 12/09/2026 |
| Văn hóa học đường | quy tắc | Quy định Văn hóa học đường ban hành kèm QĐ 1351/QĐ-ĐHNT ngày 03/09/2025; phụ lục thể hiện các mức xử lý từ nhắc nhở, khiển trách, cảnh cáo, đình chỉ học tập đến buộc thôi học | quy định bởi → QĐ 1351/QĐ-ĐHNT | phụ lục bảng xử lý kỷ luật | Quy định Văn hóa học đường | https://phongctsv.ntu.edu.vn/uploads/46/files/2025/269-Q%C4%90%201351_Q%C4%90%20V%C4%83n%20h%C3%B3a%20h%E1%BB%8Dc%20%C4%91%C6%B0%E1%BB%9Dng%202025.pdf | Cao | Hiện hành tại ngày kiểm tra | 12/09/2026 |
| QĐ 1022/QĐ-ĐHNT | quy tắc | Quy chế Công tác sinh viên, ban hành ngày 02/11/2015; quyền lợi và nghĩa vụ SV trong quá trình học tập |  | mục “Văn bản của Trường” | Trang Văn bản Phòng CTSV | https://phongctsv.ntu.edu.vn/uploads/46/files/cong-tac-sv/Quy%20che%20CTSV_021115.pdf | Cao | Hiện hành tại ngày kiểm tra | 12/09/2026 |

---

## 5. Bảng thực thể — Ký túc xá, thư viện, hỗ trợ việc làm

| Thực thể | Loại | Nội dung | Quan hệ | Trích dẫn | Văn bản | Link | Mức độ tin cậy | Trạng thái hiệu lực | Ngày kiểm tra cuối |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Ký túc xá | khái niệm | Hệ thống KTX gồm 8 tòa K1-K8, 405 phòng, sức chứa hơn 2.682 chỗ |  | mục “Hệ thống ký túc xá” | Trang Cơ sở vật chất NTU | https://ntu.edu.vn/gioi-thieu/co-so-vat-chat | Trung bình | Hiện hành tại ngày kiểm tra | 12/09/2026 |
| Ký túc xá | khái niệm | KTX đặt trong khuôn viên trường; có KTX sau đại học và KTX dành cho SV xuất sắc |  | mục “Ký túc xá sinh viên” | Trang Đời sống sinh viên NTU | https://ntu.edu.vn/sinh-vien/%C4%91oi-song-sinh-vien | Trung bình | Hiện hành tại ngày kiểm tra | 12/09/2026 |
| Hỗ trợ việc làm | thủ tục | Trung tâm liên hệ, kết nối với đơn vị sử dụng lao động để hỗ trợ việc làm và thực tập cho SV | hỗ trợ → việc làm, thực tập | phần “Chức năng” | Trang Trung tâm HTVL&KN | https://htdnhtsv.ntu.edu.vn/ | Cao | Hiện hành tại ngày kiểm tra | 12/09/2026 |
| Hướng nghiệp | thủ tục | Trung tâm chủ trì/phối hợp triển khai hướng nghiệp, tư vấn, đào tạo kỹ năng mềm, việc làm, du học, khởi nghiệp | triển khai → Trung tâm HTVL&KN | phần “Nhiệm vụ” | Trang Trung tâm HTVL&KN | https://htdnhtsv.ntu.edu.vn/ | Cao | Hiện hành tại ngày kiểm tra | 12/09/2026 |
| Thư viện số | thủ tục | SV dùng thư viện số; nếu tài liệu không có bản số, gửi yêu cầu qua email thuvien@ntu.edu.vn | yêu cầu tài liệu → Thư viện | nội dung hướng dẫn | Thư viện NTU | https://thuvien.ntu.edu.vn/News.aspx?catid=2100&contentid=438&dmd_id=157341 | Cao | Hiện hành tại ngày kiểm tra | 12/09/2026 |

---

## 6. Bảng thực thể — Chương trình đào tạo (phân tách theo mã ngành + chương trình + khóa)

> **Nguyên tắc:** Mỗi CTĐT được ghi riêng theo mã ngành + tên chương trình + khóa áp dụng. Không gộp các chương trình khác nhau của cùng một mã ngành.

| Thực thể | Loại | Mã ngành | Chương trình/Khóa | Nội dung | Trích dẫn | Văn bản | Link | Mức độ tin cậy | Trạng thái hiệu lực | Ngày kiểm tra cuối |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Công nghệ thông tin — CTĐT 2026 | chương trình | 7480201 | Chương trình chuẩn, K2026 | Đơn vị QL: Khoa CNTT; trình độ ĐH; chính quy; 4 năm; tiếng Việt; văn bằng Cử nhân CNTT; tổng TC 130; GD tổng quát 43; GD chuyên nghiệp 87; tốt nghiệp 5 | mục I; mục VI | CTĐT CNTT chuẩn 2026, PDF 210 | https://ctdt.ntu.edu.vn/ctdt/210.pdf | Cao | Đang áp dụng theo nguồn 2026 | 12/09/2026 |
| Công nghệ thông tin — CTĐT 2026 | quy tắc | 7480201 | Chương trình chuẩn, K2026 | Chuẩn đầu ra PLO2: năng lực ngoại ngữ bậc 4/6; năng lực số bậc 4/8 | mục III.1, PLO2 | CTĐT CNTT chuẩn 2026, PDF 210 | https://ctdt.ntu.edu.vn/ctdt/210.pdf | Cao | Đang áp dụng theo nguồn 2026 | 12/09/2026 |
| Công nghệ thông tin K65 | chương trình | 7480201 | K65, QĐ 1047 | Đơn vị QL: Khoa CNTT; thời gian ĐT 4 năm | phần I | CTĐT CNTT K65, QĐ 1047/QĐ-ĐHNT 18/08/2023 | https://pdtdaihoc.ntu.edu.vn/Uploads/38/QD%201017%20%2818.8.2023%29%20ban%20hanh%20CTDT%20trinh%20do%20DH%20nganh%20Cong%20nghe%20thong%20tin%20-%20K65.pdf | Cao | Lịch sử/đối chiếu | 12/09/2026 |
| Quản trị kinh doanh K65 | chương trình | 7340101 | K65, QĐ 1020 | Đơn vị QL: Khoa Kinh tế; thời gian ĐT 4 năm | phần I | CTĐT QTKD K65, QĐ 1020/QĐ-ĐHNT 18/08/2023 | https://pdtdaihoc.ntu.edu.vn/Uploads/38/QD%201020%20%2818.8.2023%29%20ban%20hanh%20CTDT%20trinh%20do%20DH%20nganh%20Quan%20tri%20kinh%20doanh%20-%20K65.pdf | Cao | Lịch sử/đối chiếu | 12/09/2026 |
| Quản trị kinh doanh — CTĐT 2026 | chương trình | 7340101 | Chương trình chuẩn, K2026 | Đơn vị QL: Khoa Kinh doanh; trình độ ĐH; chính quy; 3,5 năm | mục I | CTĐT QTKD, PDF 206 | https://ctdt.ntu.edu.vn/ctdt/206.pdf | Cao | Đang áp dụng theo nguồn 2026 | 12/09/2026 |
| Quản trị kinh doanh song ngữ Anh-Việt — CTĐT 2026 | chương trình | 7340101 | Song ngữ Anh-Việt, K2026 | Đơn vị QL: Khoa Kinh doanh; trình độ ĐH; chính quy | mục I | CTĐT QTKD song ngữ Anh-Việt, PDF 207 | https://ctdt.ntu.edu.vn/ctdt/207.pdf | Cao | Đang áp dụng theo nguồn 2026 | 12/09/2026 |
| Marketing — CTĐT 2026 | chương trình | 7340115 | Chương trình chuẩn, K2026 | Đơn vị QL: Khoa Kinh doanh; trình độ ĐH; chính quy; 3,5 năm; văn bằng Cử nhân Marketing | mục I | Dự thảo CTĐT Marketing, PDF 197 | https://ctdt.ntu.edu.vn/ctdt/197.pdf | Trung bình | Dự thảo | 12/09/2026 |
| Quản trị dịch vụ du lịch và lữ hành — CTĐT 2026 | chương trình | 7810103 | Chương trình chuẩn, K2026 | Đơn vị QL: Khoa Du lịch; trình độ ĐH; chính quy; 3,5 năm | mục I | CTĐT QTDVDL&LH, PDF 202 | https://ctdt.ntu.edu.vn/ctdt/202.pdf | Cao | Đang áp dụng theo nguồn 2026 | 12/09/2026 |
| Quản trị dịch vụ du lịch và lữ hành — CTĐT 2026 | chương trình | 7810103 | Chương trình khác (PDF 217), K2026 | Đơn vị QL: Khoa Du lịch; trình độ ĐH; chính quy; 3,5 năm; ngôn ngữ Tiếng Việt & Tiếng Anh | mục I | CTĐT QTDVDL&LH, PDF 217 | https://ctdt.ntu.edu.vn/ctdt/217.pdf | Cao | Đang áp dụng theo nguồn 2026 | 12/09/2026 |
| Quản trị dịch vụ du lịch và lữ hành (song ngữ Pháp-Việt) | chương trình | 7810103P | Song ngữ Pháp-Việt | Thuộc Khoa Du lịch | bảng danh sách CTĐT | Cổng CTĐT NTU | https://ctdt.ntu.edu.vn/daihoc | Trung bình | Chưa xác định | 12/09/2026 |
| Nuôi trồng thủy sản | chương trình | 7620301 | QĐ 1223, K63 | Đơn vị QL: Viện Nuôi trồng Thủy sản; thời gian ĐT 4,5 năm | phần I | CTĐT NTTS, QĐ 1223/QĐ-ĐHNT 16/11/2021 | https://pdtdaihoc.ntu.edu.vn/uploads/38/files/CTDT/K63/QD%201223%20vv%20ban%20hanh%20CTDT%20trinh%20do%20DH%20nganh%20Nuoi%20trong%20thuy%20san%20%2816_11_2021%29%281%29.pdf | Cao | Lịch sử/đối chiếu | 12/09/2026 |
| Khai thác thủy sản | ngành | 7620304 | Chương trình chuẩn/đại trà | 03 chuyên ngành: Khai thác thuỷ sản, Khai thác hàng hải thủy sản, Khoa học thủy sản | bảng điểm chuẩn 2022 | Điểm chuẩn trúng tuyển 2022 | https://tuyensinh.ntu.edu.vn/tuyen-sinh/n/diem-chuan-trung-tuyen-nam-2022 | Trung bình | Lịch sử/đối chiếu | 12/09/2026 |
| Khoa học thủy sản | ngành | 7620303 | Chương trình chuẩn/đại trà | Ngành Khoa học thủy sản | bảng điểm chuẩn 2022 | Điểm chuẩn trúng tuyển 2022 | https://tuyensinh.ntu.edu.vn/tuyen-sinh/n/diem-chuan-trung-tuyen-nam-2022 | Trung bình | Lịch sử/đối chiếu | 12/09/2026 |
| Công nghệ chế tạo máy — CTĐT 2026 | chương trình | 7510202 | Chương trình chuẩn, K2026 | Đơn vị QL: Khoa Cơ khí; trình độ ĐH; chính quy; 4 năm; tổng TC 130; GD tổng quát 43; GD chuyên nghiệp 87 | mục I; mục VI | CTĐT Công nghệ chế tạo máy, PDF 169 | https://ctdt.ntu.edu.vn/ctdt/169.pdf | Cao | Đang áp dụng theo nguồn 2026 | 12/09/2026 |
| Công nghệ sinh học — CTĐT 2026 | chương trình | 7420201 | Chương trình chuẩn, K2026 | Đơn vị QL: Khoa CNSH; trình độ ĐH; chính quy; 4 năm; tổng TC 130; GD tổng quát 43; GD chuyên nghiệp 87; cơ sở ngành 37; ngành 45; tốt nghiệp 5 | mục I; mục VI | CTĐT Công nghệ sinh học, PDF 170 | https://ctdt.ntu.edu.vn/ctdt/170.pdf | Cao | Đang áp dụng theo nguồn 2026 | 12/09/2026 |
| Khoa học hàng hải — CTĐT 2026 | chương trình | 7840106 | Chương trình chuẩn, K2026 | Đơn vị QL: Khoa Kỹ thuật Biển; trình độ ĐH; chính quy; 4 năm; tổng TC 130 | mục I; mục VI | CTĐT Khoa học hàng hải, PDF 175 | https://ctdt.ntu.edu.vn/ctdt/175.pdf | Cao | Đang áp dụng theo nguồn 2026 | 12/09/2026 |
| Kinh tế thủy sản — CTĐT 2026 | chương trình | 7310101 | Chương trình Kinh tế thủy sản, K2026 | Đơn vị QL: Khoa Kinh tế; trình độ ĐH; chính quy; 3,5 năm; văn bằng Cử nhân Kinh tế | mục I | CTĐT Kinh tế thủy sản, PDF 180 | https://ctdt.ntu.edu.vn/ctdt/180.pdf | Cao | Đang áp dụng theo nguồn 2026 | 12/09/2026 |
| Kinh tế phát triển — CTĐT 2026 | chương trình | 7310105 | Chương trình chuẩn, K2026 | Đơn vị QL: Khoa Kinh tế; trình độ ĐH; chính quy; 3,5 năm; tổng TC 120; GD tổng quát 36; GD chuyên nghiệp 84; cơ sở ngành 36; ngành 43; tốt nghiệp 5 | mục I; mục VI | CTĐT Kinh tế phát triển, PDF 182 | https://ctdt.ntu.edu.vn/ctdt/182.pdf | Cao | Đang áp dụng theo nguồn 2026 | 12/09/2026 |
| Kỹ thuật cơ điện tử — CTĐT 2026 | chương trình | 7520114 | Chương trình chuẩn, K2026 | Đơn vị QL: Khoa Cơ khí; trình độ ĐH; chính quy; 4 năm; tổng TC 130 | mục I; mục VI | CTĐT Kỹ thuật cơ điện tử, PDF 184 | https://ctdt.ntu.edu.vn/ctdt/184.pdf | Cao | Đang áp dụng theo nguồn 2026 | 12/09/2026 |
| Kỹ thuật cơ khí — CTĐT 2026 | chương trình | 7520103 | Chương trình chuẩn, K2026 | Đơn vị QL: Khoa Cơ khí; trình độ ĐH; chính quy; 4 năm; văn bằng Cử nhân kỹ thuật cơ khí | mục I | CTĐT Kỹ thuật cơ khí, PDF 185 | https://ctdt.ntu.edu.vn/ctdt/185.pdf | Cao | Đang áp dụng theo nguồn 2026 | 12/09/2026 |
| Kỹ thuật điều khiển và tự động hoá — CTĐT 2026 | chương trình | 7520216 | Chương trình chuẩn, K2026 | Đơn vị QL: Khoa Điện và Điện tử; trình độ ĐH; chính quy; 4 năm; tổng TC 130; GD tổng quát 43; GD chuyên nghiệp 87; tốt nghiệp 5 | mục I; mục VI | CTĐT Kỹ thuật ĐK&TĐH, PDF 188 | https://ctdt.ntu.edu.vn/ctdt/188.pdf | Cao | Đang áp dụng theo nguồn 2026 | 12/09/2026 |
| Kỹ thuật hoá học — CTĐT 2026 | chương trình | 7520301 | Chương trình chuẩn, K2026 | Đơn vị QL: Khoa KTHH&MT; trình độ ĐH; chính quy; 4 năm; tổng TC 130; GD tổng quát 43; GD chuyên nghiệp 87; cơ sở ngành 36; ngành 46; tốt nghiệp 5 | mục I; mục VI | CTĐT Kỹ thuật Hoá học, PDF 189 | https://ctdt.ntu.edu.vn/ctdt/189.pdf | Cao | Đang áp dụng theo nguồn 2026 | 12/09/2026 |
| Kỹ thuật môi trường — CTĐT 2026 | chương trình | 7520320 | Chương trình chuẩn, K2026 | Đơn vị QL: Khoa KTHH&MT; trình độ ĐH; chính quy; 4 năm; tổng TC 130 | mục I; mục VI | CTĐT Kỹ thuật Môi trường, PDF 190 | https://ctdt.ntu.edu.vn/ctdt/190.pdf | Cao | Đang áp dụng theo nguồn 2026 | 12/09/2026 |
| Kỹ thuật nhiệt — CTĐT 2026 | chương trình | 7520115 | Chương trình chuẩn, K2026 | Đơn vị QL: Khoa Kỹ thuật Năng lượng; trình độ ĐH; chính quy; 4,0 năm; tổng TC 130 | mục I; mục VII | CTĐT Kỹ thuật nhiệt, PDF 191 | https://ctdt.ntu.edu.vn/ctdt/191.pdf | Cao | Đang áp dụng theo nguồn 2026 | 12/09/2026 |
| Kỹ thuật ô tô — CTĐT 2026 | chương trình | 7520130 | Chương trình chuẩn, K2026 | Đơn vị QL: Khoa Động lực và Ô tô; trình độ ĐH; chính quy; 4 năm | mục I | CTĐT Kỹ thuật ô tô, PDF 192 | https://ctdt.ntu.edu.vn/ctdt/192.pdf | Cao | Đang áp dụng theo nguồn 2026 | 12/09/2026 |
| Kỹ thuật xây dựng — CTĐT 2026 | chương trình | 7580201 | Chương trình chuẩn, K2026 | Đơn vị QL: Khoa Xây dựng; trình độ ĐH; chính quy; 4 năm | mục I | CTĐT Kỹ thuật xây dựng, PDF 194 | https://ctdt.ntu.edu.vn/ctdt/194.pdf | Cao | Đang áp dụng theo nguồn 2026 | 12/09/2026 |
| Kỹ thuật xây dựng công trình giao thông — CTĐT 2026 | chương trình | 7580205 | Chương trình chuẩn, K2026 | Đơn vị QL: Khoa Xây dựng; trình độ ĐH; chính quy; 4 năm; tổng TC 130; GD tổng quát 43; GD chuyên nghiệp 87; cơ sở ngành 39; ngành 43; tốt nghiệp 5 | mục I; mục VI | CTĐT Kỹ thuật XD CTGT, PDF 195 | https://ctdt.ntu.edu.vn/ctdt/195.pdf | Cao | Đang áp dụng theo nguồn 2026 | 12/09/2026 |
| Ngôn ngữ Anh — CTĐT 2026 | chương trình | 7220201 | Chương trình chuẩn, K2026 | Đơn vị QL: Khoa Ngoại ngữ; trình độ ĐH; chính quy; 4 năm; tổng TC 120; GD tổng quát 35; GD chuyên nghiệp 85; tốt nghiệp 5; 4 chuyên ngành | mục I; mục VI | CTĐT Ngôn ngữ Anh, PDF 199 | https://ctdt.ntu.edu.vn/ctdt/199.pdf | Cao | Đang áp dụng theo nguồn 2026 | 12/09/2026 |
| Quản lý thủy sản — CTĐT 2026 | chương trình | 7620305 | Chương trình chuẩn, K2026 | Đơn vị QL: Khoa Khoa học Thủy sản; trình độ ĐH; chính quy; 4 năm; văn bằng Cử nhân Quản lý Thủy sản | mục I | CTĐT Quản lý Thủy sản, PDF 201 | https://ctdt.ntu.edu.vn/ctdt/201.pdf | Cao | Đang áp dụng theo nguồn 2026 | 12/09/2026 |
| Danh mục CTĐT đại học chính quy | khái niệm | — | Khóa 63–68 | Cổng CTĐT có bảng danh sách CTĐT đại học chính quy với các cột khóa 63, 64, 65, 66, 67, 68 và Tên Khoa | tiêu đề và hàng tiêu đề bảng | Cổng CTĐT NTU | https://ctdt.ntu.edu.vn/daihoc | Trung bình | Chưa xác định | 12/09/2026 |

---

## 7. Bảng thực thể — Ngành tuyển sinh 2026 (mã ngành + chuyên ngành)

| Thực thể | Loại | Mã ngành | Chuyên ngành | Nội dung | Trích dẫn | Văn bản | Link | Mức độ tin cậy | Trạng thái hiệu lực | Ngày kiểm tra cuối |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Công nghệ sinh học | ngành | 7420201 | — | NTU tuyển sinh 2026 | bảng 1, TT 28 | Điểm chuẩn trúng tuyển 2026 | https://tuyensinh.ntu.edu.vn/thong-bao/diem-chuan-trung-tuyen-2026 | Cao | Áp dụng tuyển sinh 2026 | 12/09/2026 |
| Khoa học máy tính | ngành | 7480101 | Trí tuệ nhân tạo; Khoa học dữ liệu | NTU tuyển sinh 2026 | bảng 1, TT 29 | Điểm chuẩn trúng tuyển 2026 | https://tuyensinh.ntu.edu.vn/thong-bao/diem-chuan-trung-tuyen-2026 | Cao | Áp dụng tuyển sinh 2026 | 12/09/2026 |
| Công nghệ thông tin | ngành | 7480201 | Công nghệ phần mềm; Hệ thống thông tin; Truyền thông và Mạng máy tính | NTU tuyển sinh 2026 | bảng 1, TT 30 | Điểm chuẩn trúng tuyển 2026 | https://tuyensinh.ntu.edu.vn/thong-bao/diem-chuan-trung-tuyen-2026 | Cao | Áp dụng tuyển sinh 2026 | 12/09/2026 |
| Hệ thống thông tin quản lý | ngành | 7340405 | — | NTU tuyển sinh 2026 | bảng 1, TT 26 | Điểm chuẩn trúng tuyển 2026 | https://tuyensinh.ntu.edu.vn/thong-bao/diem-chuan-trung-tuyen-2026 | Cao | Áp dụng tuyển sinh 2026 | 12/09/2026 |
| Quản trị kinh doanh | ngành | 7340101 | — | NTU tuyển sinh 2026 | bảng 1, TT 20 | Điểm chuẩn trúng tuyển 2026 | https://tuyensinh.ntu.edu.vn/thong-bao/diem-chuan-trung-tuyen-2026 | Cao | Áp dụng tuyển sinh 2026 | 12/09/2026 |
| Marketing | ngành | 7340115 | — | NTU tuyển sinh 2026 | bảng 1, TT 21 | Điểm chuẩn trúng tuyển 2026 | https://tuyensinh.ntu.edu.vn/thong-bao/diem-chuan-trung-tuyen-2026 | Cao | Áp dụng tuyển sinh 2026 | 12/09/2026 |
| Kinh doanh thương mại | ngành | 7340121 | — | NTU tuyển sinh 2026 | bảng 1, TT 22 | Điểm chuẩn trúng tuyển 2026 | https://tuyensinh.ntu.edu.vn/thong-bao/diem-chuan-trung-tuyen-2026 | Cao | Áp dụng tuyển sinh 2026 | 12/09/2026 |
| Tài chính - Ngân hàng | ngành | 7340201 | Tài chính - Ngân hàng; Công nghệ tài chính | NTU tuyển sinh 2026 | bảng 1, TT 23 | Điểm chuẩn trúng tuyển 2026 | https://tuyensinh.ntu.edu.vn/thong-bao/diem-chuan-trung-tuyen-2026 | Cao | Áp dụng tuyển sinh 2026 | 12/09/2026 |
| Kế toán | ngành | 7340301 | — | NTU tuyển sinh 2026 | bảng 1, TT 24 | Điểm chuẩn trúng tuyển 2026 | https://tuyensinh.ntu.edu.vn/thong-bao/diem-chuan-trung-tuyen-2026 | Cao | Áp dụng tuyển sinh 2026 | 12/09/2026 |
| Kiểm toán | ngành | 7340302 | — | NTU tuyển sinh 2026 | bảng 1, TT 25 | Điểm chuẩn trúng tuyển 2026 | https://tuyensinh.ntu.edu.vn/thong-bao/diem-chuan-trung-tuyen-2026 | Cao | Áp dụng tuyển sinh 2026 | 12/09/2026 |
| Luật | ngành | 7380101 | Luật; Luật kinh tế | NTU tuyển sinh 2026 | bảng 1, TT 27 | Điểm chuẩn trúng tuyển 2026 | https://tuyensinh.ntu.edu.vn/thong-bao/diem-chuan-trung-tuyen-2026 | Cao | Áp dụng tuyển sinh 2026 | 12/09/2026 |
| Ngôn ngữ Anh | ngành | 7220201 | Biên-phiên dịch; Tiếng Anh du lịch; Giảng dạy tiếng Anh; Song ngữ Anh-Trung | NTU tuyển sinh 2026 | bảng 1, TT 16 | Điểm chuẩn trúng tuyển 2026 | https://tuyensinh.ntu.edu.vn/thong-bao/diem-chuan-trung-tuyen-2026 | Cao | Áp dụng tuyển sinh 2026 | 12/09/2026 |
| Ngôn ngữ Trung Quốc | ngành | 7220204 | — | NTU tuyển sinh 2026 | bảng 1, TT 17 | Điểm chuẩn trúng tuyển 2026 | https://tuyensinh.ntu.edu.vn/thong-bao/diem-chuan-trung-tuyen-2026 | Cao | Áp dụng tuyển sinh 2026 | 12/09/2026 |
| Kinh tế | ngành | 7310101 | Kinh tế thủy sản; Quản lý kinh tế | NTU tuyển sinh 2026 | bảng 1, TT 18 | Điểm chuẩn trúng tuyển 2026 | https://tuyensinh.ntu.edu.vn/thong-bao/diem-chuan-trung-tuyen-2026 | Cao | Áp dụng tuyển sinh 2026 | 12/09/2026 |
| Kinh tế phát triển | ngành | 7310105 | — | NTU tuyển sinh 2026 | bảng 1, TT 19 | Điểm chuẩn trúng tuyển 2026 | https://tuyensinh.ntu.edu.vn/thong-bao/diem-chuan-trung-tuyen-2026 | Cao | Áp dụng tuyển sinh 2026 | 12/09/2026 |
| Kỹ thuật cơ khí | ngành | 7520103 | Kỹ thuật cơ khí; Thiết kế và chế tạo số | NTU tuyển sinh 2026 | bảng 1, TT 32 | Điểm chuẩn trúng tuyển 2026 | https://tuyensinh.ntu.edu.vn/thong-bao/diem-chuan-trung-tuyen-2026 | Cao | Áp dụng tuyển sinh 2026 | 12/09/2026 |
| Kỹ thuật cơ điện tử | ngành | 7520114 | Kỹ thuật cơ điện tử; Hệ thống nhúng và IoT | NTU tuyển sinh 2026 | bảng 1, TT 33 | Điểm chuẩn trúng tuyển 2026 | https://tuyensinh.ntu.edu.vn/thong-bao/diem-chuan-trung-tuyen-2026 | Cao | Áp dụng tuyển sinh 2026 | 12/09/2026 |
| Kỹ thuật nhiệt | ngành | 7520115 | Kỹ thuật cơ điện lạnh; Điện lạnh; Cơ điện lạnh | NTU tuyển sinh 2026 | bảng 1, TT 34 | Điểm chuẩn trúng tuyển 2026 | https://tuyensinh.ntu.edu.vn/thong-bao/diem-chuan-trung-tuyen-2026 | Cao | Áp dụng tuyển sinh 2026 | 12/09/2026 |
| Kỹ thuật cơ khí động lực | ngành | 7520116 | — | NTU tuyển sinh 2026 | bảng 1, TT 35 | Điểm chuẩn trúng tuyển 2026 | https://tuyensinh.ntu.edu.vn/thong-bao/diem-chuan-trung-tuyen-2026 | Cao | Áp dụng tuyển sinh 2026 | 12/09/2026 |
| Kỹ thuật tàu thủy | ngành | 7520122 | — | NTU tuyển sinh 2026 | bảng 1, TT 36 | Điểm chuẩn trúng tuyển 2026 | https://tuyensinh.ntu.edu.vn/thong-bao/diem-chuan-trung-tuyen-2026 | Cao | Áp dụng tuyển sinh 2026 | 12/09/2026 |
| Kỹ thuật ô tô | ngành | 7520130 | — | NTU tuyển sinh 2026 | bảng 1, TT 37 | Điểm chuẩn trúng tuyển 2026 | https://tuyensinh.ntu.edu.vn/thong-bao/diem-chuan-trung-tuyen-2026 | Cao | Áp dụng tuyển sinh 2026 | 12/09/2026 |
| Kỹ thuật điện | ngành | 7520201 | Kỹ thuật điện; Kỹ thuật điện, điện tử | NTU tuyển sinh 2026 | bảng 1, TT 38 | Điểm chuẩn trúng tuyển 2026 | https://tuyensinh.ntu.edu.vn/thong-bao/diem-chuan-trung-tuyen-2026 | Cao | Áp dụng tuyển sinh 2026 | 12/09/2026 |
| Kỹ thuật biển | ngành | 7520206 | Giàn khoan; Tuabin gió | NTU tuyển sinh 2026 | bảng 1, TT 39 | Điểm chuẩn trúng tuyển 2026 | https://tuyensinh.ntu.edu.vn/thong-bao/diem-chuan-trung-tuyen-2026 | Cao | Áp dụng tuyển sinh 2026 | 12/09/2026 |
| Kỹ thuật điều khiển và tự động hóa | ngành | 7520216 | — | NTU tuyển sinh 2026 | bảng 1, TT 40 | Điểm chuẩn trúng tuyển 2026 | https://tuyensinh.ntu.edu.vn/thong-bao/diem-chuan-trung-tuyen-2026 | Cao | Áp dụng tuyển sinh 2026 | 12/09/2026 |
| Kỹ thuật hóa học | ngành | 7520301 | — | NTU tuyển sinh 2026 | bảng 1, TT 41 | Điểm chuẩn trúng tuyển 2026 | https://tuyensinh.ntu.edu.vn/thong-bao/diem-chuan-trung-tuyen-2026 | Cao | Áp dụng tuyển sinh 2026 | 12/09/2026 |
| Kỹ thuật môi trường | ngành | 7520320 | Kỹ thuật môi trường; Quản lý môi trường và ATVSLĐ | NTU tuyển sinh 2026 | bảng 1, TT 42 | Điểm chuẩn trúng tuyển 2026 | https://tuyensinh.ntu.edu.vn/thong-bao/diem-chuan-trung-tuyen-2026 | Cao | Áp dụng tuyển sinh 2026 | 12/09/2026 |
| Công nghệ thực phẩm | ngành | 7540101 | Công nghệ thực phẩm; Khoa học dinh dưỡng và ẩm thực | NTU tuyển sinh 2026 | bảng 1, TT 43 | Điểm chuẩn trúng tuyển 2026 | https://tuyensinh.ntu.edu.vn/thong-bao/diem-chuan-trung-tuyen-2026 | Cao | Áp dụng tuyển sinh 2026 | 12/09/2026 |
| Công nghệ chế biến thủy sản | ngành | 7540105 | Công nghệ chế biến thủy sản; Công nghệ sau thu hoạch | NTU tuyển sinh 2026 | bảng 1, TT 44 | Điểm chuẩn trúng tuyển 2026 | https://tuyensinh.ntu.edu.vn/thong-bao/diem-chuan-trung-tuyen-2026 | Cao | Áp dụng tuyển sinh 2026 | 12/09/2026 |
| Đảm bảo chất lượng và an toàn thực phẩm | ngành | 7540106 | — | NTU tuyển sinh 2026 | bảng 1, TT 45 | Điểm chuẩn trúng tuyển 2026 | https://tuyensinh.ntu.edu.vn/thong-bao/diem-chuan-trung-tuyen-2026 | Cao | Áp dụng tuyển sinh 2026 | 12/09/2026 |
| Kỹ thuật xây dựng | ngành | 7580201 | Kỹ thuật xây dựng; Quản lý xây dựng | NTU tuyển sinh 2026 | bảng 1, TT 46 | Điểm chuẩn trúng tuyển 2026 | https://tuyensinh.ntu.edu.vn/thong-bao/diem-chuan-trung-tuyen-2026 | Cao | Áp dụng tuyển sinh 2026 | 12/09/2026 |
| Kỹ thuật xây dựng CTGT | ngành | 7580205 | — | NTU tuyển sinh 2026 | bảng 1, TT 47 | Điểm chuẩn trúng tuyển 2026 | https://tuyensinh.ntu.edu.vn/thong-bao/diem-chuan-trung-tuyen-2026 | Cao | Áp dụng tuyển sinh 2026 | 12/09/2026 |
| Nuôi trồng thủy sản | ngành | 7620301 | Công nghệ NTTS; Quản lý sức khỏe ĐVTS; Quản lý NTTS | NTU tuyển sinh 2026 | bảng 1, TT 48 | Điểm chuẩn trúng tuyển 2026 | https://tuyensinh.ntu.edu.vn/thong-bao/diem-chuan-trung-tuyen-2026 | Cao | Áp dụng tuyển sinh 2026 | 12/09/2026 |
| Khoa học thủy sản | ngành | 7620303 | Khai thác thủy sản; Khoa học thủy sản | NTU tuyển sinh 2026 | bảng 1, TT 49 | Điểm chuẩn trúng tuyển 2026 | https://tuyensinh.ntu.edu.vn/thong-bao/diem-chuan-trung-tuyen-2026 | Cao | Áp dụng tuyển sinh 2026 | 12/09/2026 |
| Quản lý thủy sản | ngành | 7620305 | — | NTU tuyển sinh 2026 | bảng 1, TT 50 | Điểm chuẩn trúng tuyển 2026 | https://tuyensinh.ntu.edu.vn/thong-bao/diem-chuan-trung-tuyen-2026 | Cao | Áp dụng tuyển sinh 2026 | 12/09/2026 |
| Quản trị dịch vụ du lịch và lữ hành | ngành | 7810103 | — | NTU tuyển sinh 2026 | bảng 1, TT 51 | Điểm chuẩn trúng tuyển 2026 | https://tuyensinh.ntu.edu.vn/thong-bao/diem-chuan-trung-tuyen-2026 | Cao | Áp dụng tuyển sinh 2026 | 12/09/2026 |
| Quản trị khách sạn | ngành | 7810201 | — | NTU tuyển sinh 2026 | bảng 1, TT 52 | Điểm chuẩn trúng tuyển 2026 | https://tuyensinh.ntu.edu.vn/thong-bao/diem-chuan-trung-tuyen-2026 | Cao | Áp dụng tuyển sinh 2026 | 12/09/2026 |
| Khoa học hàng hải | ngành | 7840106 | Khoa học hàng hải; Quản lý hàng hải và Logistics | NTU tuyển sinh 2026 | bảng 1, TT 53 | Điểm chuẩn trúng tuyển 2026 | https://tuyensinh.ntu.edu.vn/thong-bao/diem-chuan-trung-tuyen-2026 | Cao | Áp dụng tuyển sinh 2026 | 12/09/2026 |

---


## 8. Bảng thực thể — Nguồn mở rộng mới được cho phép

### 8.1. Phòng Đảm bảo chất lượng và Khảo thí (`phongdbcl.ntu.edu.vn`)

| Thực thể | Loại | Nội dung | Quan hệ | Trích dẫn | Văn bản | Link | Mức độ tin cậy | Trạng thái hiệu lực | Ngày kiểm tra cuối |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Phòng Đảm bảo Chất lượng và Khảo thí | đơn vị | Theo trang chức năng nhiệm vụ hiện hành, Phòng tham mưu chiến lược bảo đảm chất lượng; đề xuất và theo dõi cải tiến sau kiểm định; quản lý hoạt động đổi mới phương pháp giảng dạy, kiểm tra đánh giá và e-learning. | thuộc → Trường ĐH Nha Trang | Điều 6, mục 1a–c | QĐ 600/QĐ-ĐHNT ngày 29/04/2025 được trang đơn vị dẫn chiếu | https://phongdbcl.ntu.edu.vn/en-us/gioi-thieu/chuc-nang-nhiem-vu | Cao | Hiện hành tại ngày kiểm tra | 12/09/2026 |
| Tự đánh giá 05 CTĐT năm 2025 | quy tắc | Ngày 12/06/2025, Phòng ĐBCL&KT tổ chức hoàn thiện báo cáo tự đánh giá 05 CTĐT: Kỹ thuật Môi trường, Kỹ thuật Cơ khí Động lực, Công nghệ Chế tạo Máy, Kỹ thuật Hóa học và Kinh tế. | áp dụng cho → 05 CTĐT | đoạn mở đầu bài viết | Tin Phòng ĐBCL&KT 13/06/2025 | https://phongdbcl.ntu.edu.vn/tin-tuc/truong-dai-hoc-nha-trang-to-chuc-hop-hoan-thien-bao-cao-tu-danh-gia-05-chuong-trinh-dao-tao-theo-thong-tu-04-2016-tt-bgddt | Trung bình | Lịch sử/đối chiếu | 12/09/2026 |
| Minh chứng chuẩn đầu ra CTĐT | khái niệm | Kho minh chứng kiểm định của Phòng ĐBCL&KT có danh mục “Chuẩn đầu ra các ngành đào tạo của Trường ĐHNT” theo trình độ; đây là nguồn lịch sử/đối chiếu, không tự động được coi là chuẩn đầu ra hiện hành nếu có CTĐT mới hơn. | dùng để → đối chiếu lịch sử | Tiêu chuẩn 3, mục “Chuẩn đầu ra các ngành đào tạo” | Kho minh chứng kiểm định | https://phongdbcl.ntu.edu.vn/kiem-%C4%91inh-chat-luong/minh-chung-kiem-%C4%91inh/tieu-chuan-3 | Cao | Hiện hành tại ngày kiểm tra | 12/09/2026 |

### 8.2. Phòng Đào tạo Sau đại học (`pdtsaudaihoc.ntu.edu.vn`)

| Thực thể | Loại | Nội dung | Quan hệ | Trích dẫn | Văn bản | Link | Mức độ tin cậy | Trạng thái hiệu lực | Ngày kiểm tra cuối |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Phòng Đào tạo Sau đại học | đơn vị | Chủ trì công tác học vụ và tổ chức đào tạo sau đại học; tuyển sinh; nhập học, quản lý hồ sơ học viên cao học và nghiên cứu sinh; phối hợp quản lý/cấp email và thẻ học viên; phát triển CTĐT sau đại học. | thuộc → Trường ĐH Nha Trang | mục A.1–6; B.1–5; C.1–2 | Trang chức năng nhiệm vụ | https://pdtsaudaihoc.ntu.edu.vn/gioi-thieu/chuc-nang-nhiem-vu | Cao | Hiện hành tại ngày kiểm tra | 12/09/2026 |
| Xét tốt nghiệp thạc sĩ — đợt 2/2026 | thủ tục | Điều kiện được công bố gồm: bảo vệ luận văn/đề án đạt; hoàn thành nộp luận văn; đạt đầu ra ngoại ngữ; đóng đủ học phí toàn khóa và kinh phí bổ sung (nếu có); hoàn thành khảo sát CTĐT; đăng ký xét tốt nghiệp qua tài khoản học viên. | áp dụng cho → học viên thạc sĩ | các mục 1–6 | Kế hoạch xét tốt nghiệp thạc sĩ Đợt 2 năm 2026 | https://pdtsaudaihoc.ntu.edu.vn/thong-bao/ke-hoach-xet-tot-nghiep-thac-si-dot-2-nam-2026 | Cao | Hiện hành tại ngày kiểm tra | 12/09/2026 |
| Đầu ra ngoại ngữ thạc sĩ | quy tắc | Học viên thạc sĩ phải đạt trình độ ngoại ngữ **bậc 4 (B2) trở lên** trước khi xét tốt nghiệp. Đây là **chuẩn đầu ra thạc sĩ**, không dùng để suy ra chuẩn đầu ra đại học hoặc chuẩn đầu vào tiến sĩ. | áp dụng cho → xét tốt nghiệp thạc sĩ | mục 4 “Điều kiện ngoại ngữ đầu ra thạc sĩ” | Trang Ngoại ngữ — Phòng ĐTSĐH | https://pdtsaudaihoc.ntu.edu.vn/hoc-vien-cao-hoc/ngoai-ngu | Cao | Hiện hành tại ngày kiểm tra | 12/09/2026 |
| Thạc sĩ CNTT — chuẩn đầu vào ngoại ngữ | quy tắc | CTĐT thạc sĩ CNTT 2022 quy định người dự tuyển có trình độ ngoại ngữ **bậc 3/6 hoặc tương đương trở lên**. | áp dụng cho → tuyển sinh thạc sĩ CNTT CTĐT 2022 | mục VI.1 | CTĐT thạc sĩ CNTT 2022 | https://pdtsaudaihoc.ntu.edu.vn/uploads/22/files/CTDT%202022/CNTT-UD-8_2022.pdf | Cao | Hiện hành tại ngày kiểm tra | 12/09/2026 |
| Thạc sĩ CNTT — chuẩn đầu ra ngoại ngữ | quy tắc | PLO2 của CTĐT thạc sĩ CNTT 2022 yêu cầu năng lực ngoại ngữ **bậc 4/6** theo Khung năng lực ngoại ngữ Việt Nam. | áp dụng cho → tốt nghiệp thạc sĩ CNTT CTĐT 2022 | mục IV, PLO2 | CTĐT thạc sĩ CNTT 2022 | https://pdtsaudaihoc.ntu.edu.vn/uploads/22/files/CTDT%202022/CNTT-UD-8_2022.pdf | Cao | Hiện hành tại ngày kiểm tra | 12/09/2026 |
| Đào tạo tiến sĩ từ khóa 2021 | quy tắc | Trang quy định đào tạo tiến sĩ ghi các quy chế tuyển sinh và đào tạo tiến sĩ áp dụng cho người học **từ khóa 2021 trở đi**. | áp dụng cho → NCS từ khóa 2021 | tiêu đề “ÁP DỤNG TỪ KHÓA 2021” | Trang Quy định đào tạo tiến sĩ | https://pdtsaudaihoc.ntu.edu.vn/for-phd-students/quy-%C4%91inh-%C4%91ao-tao-training-regulations | Cao | Hiện hành tại ngày kiểm tra | 12/09/2026 |

### 8.3. Trung tâm Đào tạo và Bồi dưỡng (`trungtamdtbd.ntu.edu.vn`)

| Thực thể | Loại | Nội dung | Quan hệ | Trích dẫn | Văn bản | Link | Mức độ tin cậy | Trạng thái hiệu lực | Ngày kiểm tra cuối |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Tuyển sinh VLVH/liên thông 2026 | thủ tục | NTU tuyển sinh đào tạo đại học hình thức vừa làm vừa học năm 2026 theo KH 1454/KH-ĐHNT ngày 31/12/2025; có 30 ngành được liệt kê. | áp dụng cho → tuyển sinh 2026 | mục 1 | Thông báo tuyển sinh hệ Đại học tại NTU năm 2026 | https://trungtamdtbd.ntu.edu.vn/tin-tuc/n | Cao | Áp dụng tuyển sinh 2026 | 12/09/2026 |
| Thời gian đào tạo VLVH/liên thông 2026 | quy tắc | Thông báo quy định các loại hình: liên thông từ đại học (VB2) 1,5 năm; liên thông từ cao đẳng 1,5 năm; liên thông từ trung cấp 2,5 năm; đại học vừa làm vừa học 4 năm. | áp dụng cho → các ngành trong thông báo tuyển sinh 2026 | bảng mục 1 | Thông báo tuyển sinh hệ Đại học tại NTU năm 2026 | https://trungtamdtbd.ntu.edu.vn/tin-tuc/n | Cao | Hiện hành tại ngày kiểm tra | 12/09/2026 |
| Đối tượng dự tuyển VLVH 2026 | quy tắc | Người tốt nghiệp THPT có thể dự tuyển loại hình VLVH 4 năm; người có bằng trung cấp/cao đẳng/đại học có thể dự tuyển các loại hình tương ứng theo điều kiện văn hóa THPT nêu trong thông báo. | áp dụng cho → tuyển sinh VLVH 2026 | mục 2 | Thông báo tuyển sinh hệ Đại học tại NTU năm 2026 | https://trungtamdtbd.ntu.edu.vn/tin-tuc/n | Cao | Áp dụng tuyển sinh 2026 | 12/09/2026 |
| Đợt xét tuyển VLVH 2026 | quy tắc | Xét tuyển vào các tháng **02, 05, 08 và 11 năm 2026**. | áp dụng cho → tuyển sinh VLVH 2026 | mục 4 | Thông báo tuyển sinh hệ Đại học tại NTU năm 2026 | https://trungtamdtbd.ntu.edu.vn/tin-tuc/n | Cao | Áp dụng tuyển sinh 2026 | 12/09/2026 |
| Trung tâm Đào tạo và Bồi dưỡng — liên hệ tuyển sinh | đơn vị | Địa điểm tiếp nhận đăng ký: Tòa nhà A3, số 02 Nguyễn Đình Chiểu, P. Bắc Nha Trang, Khánh Hòa; điện thoại 0258.2220913. | nộp tại → Trung tâm ĐTBD | mục 3 và mục 6 | Thông báo tuyển sinh hệ Đại học tại NTU năm 2026 | https://trungtamdtbd.ntu.edu.vn/tin-tuc/n | Cao | Hiện hành tại ngày kiểm tra | 12/09/2026 |

### 8.4. Danh mục ngành VLVH/liên thông tuyển sinh 2026

| Ngành | Loại | Mã ngành | Nội dung | Trích dẫn | Văn bản | Link | Trạng thái hiệu lực | Mức độ tin cậy | Ngày kiểm tra cuối |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Công nghệ chế biến thủy sản | ngành | 7540105 | Có trong danh mục tuyển sinh VLVH/liên thông 2026 | bảng mục 1, TT 1 | Thông báo tuyển sinh VLVH 2026 | https://trungtamdtbd.ntu.edu.vn/tin-tuc/n | Áp dụng tuyển sinh 2026 | Cao | 12/09/2026 |
| Kỹ thuật tàu thủy | ngành | 7520122 | Có trong danh mục tuyển sinh VLVH/liên thông 2026 | bảng mục 1, TT 2 | Thông báo tuyển sinh VLVH 2026 | https://trungtamdtbd.ntu.edu.vn/tin-tuc/n | Áp dụng tuyển sinh 2026 | Cao | 12/09/2026 |
| Nuôi trồng thủy sản | ngành | 7620301 | Có trong danh mục tuyển sinh VLVH/liên thông 2026 | bảng mục 1, TT 3 | Thông báo tuyển sinh VLVH 2026 | https://trungtamdtbd.ntu.edu.vn/tin-tuc/n | Áp dụng tuyển sinh 2026 | Cao | 12/09/2026 |
| Công nghệ sinh học | ngành | 7420201 | Có trong danh mục tuyển sinh VLVH/liên thông 2026 | bảng mục 1, TT 4 | Thông báo tuyển sinh VLVH 2026 | https://trungtamdtbd.ntu.edu.vn/tin-tuc/n | Áp dụng tuyển sinh 2026 | Cao | 12/09/2026 |
| Công nghệ thông tin | ngành | 7480201 | Có trong danh mục tuyển sinh VLVH/liên thông 2026 | bảng mục 1, TT 5 | Thông báo tuyển sinh VLVH 2026 | https://trungtamdtbd.ntu.edu.vn/tin-tuc/n | Áp dụng tuyển sinh 2026 | Cao | 12/09/2026 |
| Quản trị khách sạn | ngành | 7810201 | Có trong danh mục tuyển sinh VLVH/liên thông 2026 | bảng mục 1, TT 6 | Thông báo tuyển sinh VLVH 2026 | https://trungtamdtbd.ntu.edu.vn/tin-tuc/n | Áp dụng tuyển sinh 2026 | Cao | 12/09/2026 |
| Kế toán | ngành | 7340301 | Có trong danh mục tuyển sinh VLVH/liên thông 2026 | bảng mục 1, TT 7 | Thông báo tuyển sinh VLVH 2026 | https://trungtamdtbd.ntu.edu.vn/tin-tuc/n | Áp dụng tuyển sinh 2026 | Cao | 12/09/2026 |
| Quản trị kinh doanh | ngành | 7340101 | Có trong danh mục tuyển sinh VLVH/liên thông 2026 | bảng mục 1, TT 8 | Thông báo tuyển sinh VLVH 2026 | https://trungtamdtbd.ntu.edu.vn/tin-tuc/n | Áp dụng tuyển sinh 2026 | Cao | 12/09/2026 |
| Công nghệ thực phẩm | ngành | 7540101 | Có trong danh mục tuyển sinh VLVH/liên thông 2026 | bảng mục 1, TT 9 | Thông báo tuyển sinh VLVH 2026 | https://trungtamdtbd.ntu.edu.vn/tin-tuc/n | Áp dụng tuyển sinh 2026 | Cao | 12/09/2026 |
| Quản trị dịch vụ du lịch và lữ hành | ngành | 7810103 | Có trong danh mục tuyển sinh VLVH/liên thông 2026 | bảng mục 1, TT 10 | Thông báo tuyển sinh VLVH 2026 | https://trungtamdtbd.ntu.edu.vn/tin-tuc/n | Áp dụng tuyển sinh 2026 | Cao | 12/09/2026 |
| Quản lý thủy sản | ngành | 7620305 | Có trong danh mục tuyển sinh VLVH/liên thông 2026 | bảng mục 1, TT 11 | Thông báo tuyển sinh VLVH 2026 | https://trungtamdtbd.ntu.edu.vn/tin-tuc/n | Áp dụng tuyển sinh 2026 | Cao | 12/09/2026 |
| Kỹ thuật cơ khí | ngành | 7520103 | Có trong danh mục tuyển sinh VLVH/liên thông 2026 | bảng mục 1, TT 12 | Thông báo tuyển sinh VLVH 2026 | https://trungtamdtbd.ntu.edu.vn/tin-tuc/n | Áp dụng tuyển sinh 2026 | Cao | 12/09/2026 |
| Tài chính - Ngân hàng | ngành | 7340201 | Có trong danh mục tuyển sinh VLVH/liên thông 2026 | bảng mục 1, TT 13 | Thông báo tuyển sinh VLVH 2026 | https://trungtamdtbd.ntu.edu.vn/tin-tuc/n | Áp dụng tuyển sinh 2026 | Cao | 12/09/2026 |
| Kinh doanh thương mại | ngành | 7340121 | Có trong danh mục tuyển sinh VLVH/liên thông 2026 | bảng mục 1, TT 14 | Thông báo tuyển sinh VLVH 2026 | https://trungtamdtbd.ntu.edu.vn/tin-tuc/n | Áp dụng tuyển sinh 2026 | Cao | 12/09/2026 |
| Kỹ thuật ô tô | ngành | 7520130 | Có trong danh mục tuyển sinh VLVH/liên thông 2026 | bảng mục 1, TT 15 | Thông báo tuyển sinh VLVH 2026 | https://trungtamdtbd.ntu.edu.vn/tin-tuc/n | Áp dụng tuyển sinh 2026 | Cao | 12/09/2026 |
| Ngôn ngữ Anh | ngành | 7220201 | Có trong danh mục tuyển sinh VLVH/liên thông 2026 | bảng mục 1, TT 16 | Thông báo tuyển sinh VLVH 2026 | https://trungtamdtbd.ntu.edu.vn/tin-tuc/n | Áp dụng tuyển sinh 2026 | Cao | 12/09/2026 |
| Kỹ thuật xây dựng | ngành | 7580201 | Có trong danh mục tuyển sinh VLVH/liên thông 2026 | bảng mục 1, TT 17 | Thông báo tuyển sinh VLVH 2026 | https://trungtamdtbd.ntu.edu.vn/tin-tuc/n | Áp dụng tuyển sinh 2026 | Cao | 12/09/2026 |
| Kỹ thuật điện | ngành | 7520201 | Có trong danh mục tuyển sinh VLVH/liên thông 2026 | bảng mục 1, TT 18 | Thông báo tuyển sinh VLVH 2026 | https://trungtamdtbd.ntu.edu.vn/tin-tuc/n | Áp dụng tuyển sinh 2026 | Cao | 12/09/2026 |
| Hệ thống thông tin quản lý | ngành | 7340405 | Có trong danh mục tuyển sinh VLVH/liên thông 2026 | bảng mục 1, TT 19 | Thông báo tuyển sinh VLVH 2026 | https://trungtamdtbd.ntu.edu.vn/tin-tuc/n | Áp dụng tuyển sinh 2026 | Cao | 12/09/2026 |
| Kỹ thuật nhiệt | ngành | 7520115 | Có trong danh mục tuyển sinh VLVH/liên thông 2026 | bảng mục 1, TT 20 | Thông báo tuyển sinh VLVH 2026 | https://trungtamdtbd.ntu.edu.vn/tin-tuc/n | Áp dụng tuyển sinh 2026 | Cao | 12/09/2026 |
| Kỹ thuật cơ điện tử | ngành | 7520114 | Có trong danh mục tuyển sinh VLVH/liên thông 2026 | bảng mục 1, TT 21 | Thông báo tuyển sinh VLVH 2026 | https://trungtamdtbd.ntu.edu.vn/tin-tuc/n | Áp dụng tuyển sinh 2026 | Cao | 12/09/2026 |
| Marketing | ngành | 7340115 | Có trong danh mục tuyển sinh VLVH/liên thông 2026 | bảng mục 1, TT 22 | Thông báo tuyển sinh VLVH 2026 | https://trungtamdtbd.ntu.edu.vn/tin-tuc/n | Áp dụng tuyển sinh 2026 | Cao | 12/09/2026 |
| Kinh tế phát triển | ngành | 7310105 | Có trong danh mục tuyển sinh VLVH/liên thông 2026 | bảng mục 1, TT 23 | Thông báo tuyển sinh VLVH 2026 | https://trungtamdtbd.ntu.edu.vn/tin-tuc/n | Áp dụng tuyển sinh 2026 | Cao | 12/09/2026 |
| Khoa học thủy sản | ngành | 7620303 | Có trong danh mục tuyển sinh VLVH/liên thông 2026 | bảng mục 1, TT 24 | Thông báo tuyển sinh VLVH 2026 | https://trungtamdtbd.ntu.edu.vn/tin-tuc/n | Áp dụng tuyển sinh 2026 | Cao | 12/09/2026 |
| Luật | ngành | 7380101 | Có trong danh mục tuyển sinh VLVH/liên thông 2026 | bảng mục 1, TT 25 | Thông báo tuyển sinh VLVH 2026 | https://trungtamdtbd.ntu.edu.vn/tin-tuc/n | Áp dụng tuyển sinh 2026 | Cao | 12/09/2026 |
| Kỹ thuật môi trường | ngành | 7520320 | Có trong danh mục tuyển sinh VLVH/liên thông 2026 | bảng mục 1, TT 26 | Thông báo tuyển sinh VLVH 2026 | https://trungtamdtbd.ntu.edu.vn/tin-tuc/n | Áp dụng tuyển sinh 2026 | Cao | 12/09/2026 |
| Kỹ thuật hóa học | ngành | 7520301 | Có trong danh mục tuyển sinh VLVH/liên thông 2026 | bảng mục 1, TT 27 | Thông báo tuyển sinh VLVH 2026 | https://trungtamdtbd.ntu.edu.vn/tin-tuc/n | Áp dụng tuyển sinh 2026 | Cao | 12/09/2026 |
| Kỹ thuật cơ khí động lực | ngành | 7520116 | Có trong danh mục tuyển sinh VLVH/liên thông 2026 | bảng mục 1, TT 28 | Thông báo tuyển sinh VLVH 2026 | https://trungtamdtbd.ntu.edu.vn/tin-tuc/n | Áp dụng tuyển sinh 2026 | Cao | 12/09/2026 |
| Công nghệ chế tạo máy | ngành | 7510202 | Có trong danh mục tuyển sinh VLVH/liên thông 2026 | bảng mục 1, TT 29 | Thông báo tuyển sinh VLVH 2026 | https://trungtamdtbd.ntu.edu.vn/tin-tuc/n | Áp dụng tuyển sinh 2026 | Cao | 12/09/2026 |
| Kinh tế | ngành | 7310101 | Có trong danh mục tuyển sinh VLVH/liên thông 2026 | bảng mục 1, TT 30 | Thông báo tuyển sinh VLVH 2026 | https://trungtamdtbd.ntu.edu.vn/tin-tuc/n | Áp dụng tuyển sinh 2026 | Cao | 12/09/2026 |

### 8.5. Cổng xét tuyển/nhập học (`xettuyen.ntu.edu.vn`)

| Thực thể | Loại | Nội dung | Quan hệ | Trích dẫn | Văn bản | Link | Mức độ tin cậy | Trạng thái hiệu lực | Ngày kiểm tra cuối |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Tài khoản nhập học 2026 | quy tắc | Thí sinh trúng tuyển đăng nhập hệ thống nhập học với tên đăng nhập dạng `t26_XXXXXXXXX` (XXXXXXXXX là CMND/CCCD đã khai báo trên hệ thống Bộ GD&ĐT); mật khẩu là số CMND/CCCD. | đăng nhập → xettuyen.ntu.edu.vn/NhapHoc | phần “Hướng dẫn đăng nhập & Đóng học phí online” | Cổng xét tuyển NTU 2026 | https://xettuyen.ntu.edu.vn/ | Cao | Hết thời hạn áp dụng nêu trong record | 12/09/2026 |
| Xác nhận nhập học Bộ GD&ĐT 2026 | thủ tục | Thí sinh xác nhận nhập học trực tuyến trên hệ thống tuyển sinh của Bộ GD&ĐT từ **14/08/2026 đến 17:00 ngày 21/08/2026**. | áp dụng cho → thí sinh trúng tuyển 2026 | Bước 1, mục 2.1 | Quy trình tổ chức nhập học 2026 | https://xettuyen.ntu.edu.vn/ | Cao | Hết thời hạn áp dụng nêu trong record | 12/09/2026 |
| Đăng ký KTX khi nhập học 2026 | thủ tục | Thí sinh có nhu cầu đăng ký KTX tại `xettuyen.ntu.edu.vn/NhapHoc`. | thực hiện tại → xettuyen.ntu.edu.vn/NhapHoc | Bước 2, mục 2.1 | Quy trình tổ chức nhập học 2026 | https://xettuyen.ntu.edu.vn/ | Cao | Hết thời hạn áp dụng nêu trong record | 12/09/2026 |
| Tạm thu học phí nhập học 2026 | thủ tục | Sau bước đăng ký KTX (nếu có), thí sinh đóng học phí và các khoản khác online tại hệ thống nhập học; thời gian nộp từ **12/08/2026 đến hết 23/08/2026**. | thực hiện tại → xettuyen.ntu.edu.vn/NhapHoc | Bước 2, mục 2.1 | Quy trình tổ chức nhập học 2026 | https://xettuyen.ntu.edu.vn/ | Cao | Hết thời hạn áp dụng nêu trong record | 12/09/2026 |

### 8.6. `thanhnien.ntu.edu.vn`

Tên miền này hiện được phép crawl. Tuy nhiên, nguồn nổi bật tìm được về Quy chế đào tạo đại học là bài đăng lại **QĐ 753/2021**, mà QĐ 753 vẫn nằm trong danh sách văn bản người dùng yêu cầu loại khỏi căn cứ. Vì vậy **không đưa các quy tắc từ QĐ 753 vào bảng dữ liệu chính**; chỉ giữ tên miền trong whitelist để phục vụ các nguồn khác nếu tìm được sau này.

---

## 9. Bảng thực thể — Văn bản pháp quy (trong phạm vi nguồn cho phép)

| Thực thể | Loại | Nội dung | Quan hệ | Trích dẫn | Văn bản | Link | Trạng thái hiệu lực | Mức độ tin cậy | Ngày kiểm tra cuối |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| NĐ 238/2025/NĐ-CP | quy tắc | Chính sách học phí, miễn, giảm, hỗ trợ học phí, hỗ trợ chi phí học tập và giá dịch vụ trong lĩnh vực GD-ĐT; gồm 6 chương, 29 điều |  |  | NĐ 238/2025/NĐ-CP, 03/9/2025 | https://vanban.chinhphu.vn/?pageid=27160&docid=215169&classid=1 | Có hiệu lực/chưa thấy văn bản thay thế | Cao | 12/09/2026 |
| NĐ 179/2026/NĐ-CP | quy tắc | Chính sách học bổng cho người học ngành khoa học cơ bản, kỹ thuật then chốt và công nghệ chiến lược, ban hành ngày 20/5/2026 |  | mục “Văn bản của Thủ tướng” | Trang Văn bản Phòng CTSV | https://phongctsv.ntu.edu.vn/uploads/46/files/2026/269-179-ndcp.signed.pdf | Có hiệu lực/chưa thấy văn bản thay thế | Cao | 12/09/2026 |
| QĐ 1826/QĐ-BGDĐT | quy tắc | Danh mục ngành đào tạo khoa học cơ bản được áp dụng chính sách học bổng tại NĐ 179, ban hành ngày 26/6/2026 | căn cứ → NĐ 179/2026/NĐ-CP | mục “Văn bản của Thủ tướng” | Trang Văn bản Phòng CTSV | https://phongctsv.ntu.edu.vn/uploads/46/files/2026/269-qd-1826.pdf | Có hiệu lực/chưa thấy văn bản thay thế | Cao | 12/09/2026 |
| NĐ 57/2017/NĐ-CP | quy tắc | Chính sách ưu tiên tuyển sinh và hỗ trợ học tập đối với trẻ mẫu giáo, HS, SV dân tộc thiểu số rất ít người |  | mục “Chế độ”, mục 2 | Trang Chế độ Phòng CTSV | https://phongctsv.ntu.edu.vn/uploads/46/files/2021/N%C4%90%2057_2017_N%C4%90-CP.pdf | Chưa xác định | Cao | 12/09/2026 |
| QĐ 66/2013/QĐ-TTg | quy tắc | Chính sách hỗ trợ chi phí học tập đối với SV là người dân tộc thiểu số thuộc hộ nghèo, cận nghèo |  | mục “Chế độ”, mục 3 | Trang Chế độ Phòng CTSV | https://phongctsv.ntu.edu.vn/uploads/46/files/2021/quyet-dinh-66-2013-qd-ttg-thu-tuong-chinh-phu.pdf | Chưa xác định | Cao | 12/09/2026 |
| QĐ 1351/QĐ-ĐHNT | quy tắc | Quy định Văn hóa học đường, ban hành ngày 03/09/2025, áp dụng từ HKI 2025-2026 |  | mục “Văn bản của Trường” | Trang Văn bản Phòng CTSV | https://phongctsv.ntu.edu.vn/uploads/46/files/2025/269-Q%C4%90%201351_Q%C4%90%20V%C4%83n%20h%C3%B3a%20h%E1%BB%8Dc%20%C4%91%C6%B0%E1%BB%9Dng%202025.pdf | Có hiệu lực/chưa thấy văn bản thay thế | Cao | 12/09/2026 |
| QĐ 1022/QĐ-ĐHNT | quy tắc | Quy chế Công tác sinh viên, ban hành ngày 02/11/2015 |  | mục “Văn bản của Trường” | Trang Văn bản Phòng CTSV | https://phongctsv.ntu.edu.vn/uploads/46/files/cong-tac-sv/Quy%20che%20CTSV_021115.pdf | Chưa xác định | Cao | 12/09/2026 |
| QĐ 358/QĐ-ĐHNT | quy tắc | Quy định tổ chức đào tạo tin học cho SV, ban hành ngày 02/04/2019 |  | mục “Văn bản Trường”, dòng QĐ 358 | Trang Văn bản pháp quy Phòng Đào tạo | https://pdtdaihoc.ntu.edu.vn/uploads/38/files/Van-Ban-Truong/20190402_358QD_Quy%20dinh%20dao%20tao%20Tin%20hoc%20cho%20SV.pdf | Chưa xác định | Cao | 12/09/2026 |
| TB 106/TB-ĐHNT | quy tắc | Thông báo chuẩn đầu ra ngoại ngữ các CTĐT không chuyên ngữ ĐH liên thông, bằng 2, ban hành ngày 24/02/2020 |  | mục “Văn bản Trường”, dòng TB 106 | Trang Văn bản pháp quy Phòng Đào tạo | https://pdtdaihoc.ntu.edu.vn/uploads/38/files/Van-Ban-Truong/20200224_Chu%E1%BA%A9n%20%C4%91%E1%BA%A7u%20ra%20Ngo%E1%BA%A1i%20ng%E1%BB%AF%20li%C3%AAn%20th%C3%B4ng-B2.pdf | Chưa xác định | Cao | 12/09/2026 |
| QĐ 507/QĐ-ĐHNT | quy tắc | Quy định tổ chức đào tạo ngoại ngữ thứ hai cho SV ngành Ngôn ngữ Anh, ban hành ngày 17/05/2019 | áp dụng cho → ngành Ngôn ngữ Anh | mục “Văn bản Trường”, dòng QĐ 507 | Trang Văn bản pháp quy Phòng Đào tạo | https://pdtdaihoc.ntu.edu.vn/uploads/38/files/Van-Ban-Truong/20190517_507%20QD%20Dao%20t%E1%BA%A1o%20NN%20thu%202%20cho%20SV%20ng%C3%A0nh%20NNA.pdf | Chưa xác định | Cao | 12/09/2026 |
| QĐ 1128/QĐ-ĐHNT | quy tắc | Quy định đào tạo ngoại ngữ trong các CTĐT trình độ ĐH và CĐ không chuyên ngữ, ban hành ngày 20/09/2018 |  | mục “Văn bản Trường”, dòng QĐ 1128 | Trang Văn bản pháp quy Phòng Đào tạo | https://pdtdaihoc.ntu.edu.vn/uploads/38/files/Van-Ban-Truong/20180920_QD%201128_Quy%20dinh%20dao%20tao%20ngoai%20ngu%20khoi%20khong%20chuyen%20ngu.pdf | Chưa xác định | Cao | 12/09/2026 |
| QĐ 74/QĐ-ĐHNT | quy tắc | Quy định đào tạo tiếng Anh cho SV không chuyên ngữ, ban hành ngày 06/02/2017 |  | mục “Văn bản Trường”, dòng QĐ 74 | Trang Văn bản pháp quy Phòng Đào tạo | https://pdtdaihoc.ntu.edu.vn/uploads/38/files/Van-Ban-Truong/20170206_QD%20so%2074%20ngay%2006-2-2017%20-%20Quy%20dinh%20dao%20tao%20TA%20khong%20chuyen_.pdf | Chưa xác định | Cao | 12/09/2026 |
| QĐ 244 (20.02.2025) | quy tắc | Sửa đổi, bổ sung quy định đào tạo ngoại ngữ cho SV trường ĐH Nha Trang, ban hành ngày 20/02/2025 |  | mục “Danh mục” hàng 18 | Trang Văn bản pháp quy Phòng Đào tạo | https://pdtdaihoc.ntu.edu.vn/uploads/38/Doc/415/qd-244-(20.02.2025)-vv-sua-doi,-bo-sung-mot-so-quy-dinh-dao-tao-ngoai-ngu-cho-sv-truong-dhnt.pdf.pdf | Chưa xác định | Cao | 12/09/2026 |
| QĐ 1525/QĐ-ĐHNT | quy tắc | Quy định khối lượng và cấu trúc CTĐT trình độ đại học; áp dụng từ khóa 63. **Ngày trên PDF gốc: 13/10/2023**; bảng danh mục văn bản của Phòng Đào tạo hiển thị cột ngày 13/11/2023, được xem là sai lệch metadata của trang danh mục. | áp dụng cho → khóa 63 trở đi | Điều 1 khoản 2; trang đầu PDF | QĐ 1525/QĐ-ĐHNT, ngày 13/10/2023 | https://pdtdaihoc.ntu.edu.vn/uploads/38/Doc/311/qd-1525-%2813.10.2023%29-ban-hanh-quy-dinh-khoi-luong-va-cau-truc-ctdt-trinh-do-dai-hoc.pdf.pdf | Có hiệu lực/chưa thấy văn bản thay thế | Cao | 12/09/2026 |
| QĐ 754/QĐ-ĐHNT | quy tắc | Quy định khối lượng và cấu trúc CTĐT trình độ đại học, ban hành ngày 13/08/2021 |  |  | Trang Văn bản pháp quy Phòng Đào tạo | https://pdtdaihoc.ntu.edu.vn/van-ban-phap-quy/quan-ly-chuong-trinh-dao-tao | Chưa xác định; có QĐ 1525/2023 cùng chủ đề mới hơn | Cao | 12/09/2026 |
| QĐ 173/QĐ-ĐHNT | quy tắc | Quy định mở ngành và phát triển CTĐT, ban hành ngày 12/02/2025 |  |  | Trang Văn bản pháp quy Phòng Đào tạo | https://pdtdaihoc.ntu.edu.vn/tin-tuc/qd-173-ban-hanh-quy-dinh-mo-nganh-va-phat-trien-chuong-trinh-dao-tao--12-02-2025- | Có hiệu lực/chưa thấy văn bản thay thế | Cao | 12/09/2026 |
| QĐ 1889 | quy tắc | Quy định trao đổi SV, học viên cao học và nghiên cứu sinh giữa NTU và các cơ sở GD đại học trong nước, ban hành ngày 09/12/2025 |  | mục “Danh mục” hàng 27 | Trang Văn bản pháp quy Phòng Đào tạo | https://pdtdaihoc.ntu.edu.vn/uploads/38/Doc/808/qd-1889-ve-viec-ban-hanh-quy-dinh-trao-doi-sinh-vien--hoc-vien-cao-hoc-va-nghien-cuu-sinh-giua-truong-dai-hoc-nha-trang-va-cac-co-so-giao-duc-dai-hoc-trong-nuoc-pdf.pdf | Có hiệu lực/chưa thấy văn bản thay thế | Cao | 12/09/2026 |
| QĐ 520/QĐ-ĐHNT | quy tắc | Mẫu đề cương chi tiết học phần, ban hành ngày 08/04/2026 | quy định bởi → QĐ 520 | mục “Quản lý chương trình đào tạo” | Phòng Đào tạo Đại học | https://pdtdaihoc.ntu.edu.vn/en-us/van-ban-phap-quy/quan-ly-chuong-trinh-dao-tao | Có hiệu lực/chưa thấy văn bản thay thế | Cao | 12/09/2026 |
| QĐ 521/QĐ-ĐHNT | quy tắc | Mẫu đề cương học phần, ban hành ngày 08/04/2026 | quy định bởi → QĐ 521 | mục “Quản lý chương trình đào tạo” | Phòng Đào tạo Đại học | https://pdtdaihoc.ntu.edu.vn/en-us/van-ban-phap-quy/quan-ly-chuong-trinh-dao-tao | Có hiệu lực/chưa thấy văn bản thay thế | Cao | 12/09/2026 |
| KH 1100/KH-ĐHNT | quy tắc | Đánh giá và cập nhật Chương trình đào tạo, ban hành ngày 16/10/2025 | thực hiện theo → KH 1100 | mục “Quản lý chương trình đào tạo” | Phòng Đào tạo Đại học | https://pdtdaihoc.ntu.edu.vn/en-us/van-ban-phap-quy/quan-ly-chuong-trinh-dao-tao | Có hiệu lực/chưa thấy văn bản thay thế | Cao | 12/09/2026 |

---

## 10. Tên gọi khác

| Thực thể | Cách gọi dân dã thường gặp |
|---|---|
| Phòng Công tác Chính trị và Sinh viên | P. CTCT&SV, Phòng CTSV, Phòng Công tác Sinh viên, ctsv |
| Phòng Đào tạo Đại học | Phòng Đào tạo, P.ĐT, PDĐH, pdtdaihoc |
| Phòng Tài chính | Phòng KHTC, Phòng Kế hoạch Tài chính, phòng học phí, phongkhtc |
| Phòng Hạ tầng và Công nghệ Thông tin | Phòng CNTT, IT, phongcntt |
| Trung tâm Hỗ trợ Việc làm và Khởi nghiệp | Trung tâm việc làm, Trung tâm QHDN&HTSV, htdnhtsv |
| Trung tâm Thông tin và Tư liệu | Thư viện trường, thuvien |
| Giấy xác nhận đang học | giấy xác nhận sinh viên, giấy xác nhận đang học |
| Điểm rèn luyện | ĐRL, điểm RL |
| Học phí | HP |
| Hỗ trợ chi phí học tập | HTCPHT, hỗ trợ CPHT |
| Trợ cấp xã hội | TCXH |
| Bảo hiểm y tế | BHYT |
| Bảo hiểm thân thể | BHTT |
| Tuần sinh hoạt công dân – sinh viên | SHCD, tuần công dân, sinh hoạt công dân |
| Website sinh viên | cổng sinh viên, portal sinh viên, sinhvien.ntu.edu.vn |
| account.ntu.edu.vn | cổng tài khoản, trang đổi mật khẩu |
| ctdt.ntu.edu.vn | trang chương trình đào tạo, CTĐT online |
| Chương trình đào tạo | CTĐT |
| Khoa/Viện quản lý ngành | đơn vị quản lý ngành, khoa quản lý |
| Hệ thống nhúng và IoT | Embedded Systems and IoT |
| Kỹ thuật cơ điện tử | Mechatronics Engineering |
| Kỹ thuật điều khiển & tự động hoá | Control & Automation Engineering |
| Kỹ thuật ô tô | Automotive Engineering |
| Kỹ thuật xây dựng công trình giao thông | Transportation Engineering |
| Ngôn ngữ Anh | English Linguistics |
| Quản trị dịch vụ du lịch và lữ hành | Travel and Tourism Service Management |

---

## 11. Chưa tìm được / chưa thể khẳng định

| Thực thể | Tình trạng |
|---|---|
| Mức học phí cụ thể theo từng ngành/chương trình và từng khóa | Chưa lập được ma trận đầy đủ ngành × chương trình × khóa; QĐ 729 bị loại theo yêu cầu ban đầu |
| Gia hạn đóng học phí — quy định chung hiện hành | Đã có mẫu đơn, quy trình thu và thông báo HK1 2025-2026; chưa có văn bản hiện hành duy nhất khẳng định thời hạn tối đa cho mọi học kỳ |
| Tổng số tín chỉ của mọi CTĐT hiện hành 2026 | Đã xác minh nhiều CTĐT 2026 từ PDF; chưa đủ toàn bộ chương trình × khóa |
| Chuẩn đầu ra ngoại ngữ/tin học của từng ngành, từng khóa | Đã xác minh một số CTĐT 2026 và QĐ 244/2025, QĐ 358/2019; chưa đủ dữ liệu từng ngành × khóa |
| Giờ làm việc của toàn bộ đơn vị phục vụ sinh viên | Chưa có bảng chính thức hiện hành đầy đủ cho mọi đơn vị |
| KTX — giá phòng, điều kiện, ưu tiên, thời hạn đăng ký 2026-2027 | Đã xác minh thông tin KTX và việc đăng ký khi nhập học; chưa đủ văn bản/bảng giá hiện hành |
| Thư viện — giờ mở cửa hiện hành | Đã xác minh đầu mối và dịch vụ; chưa đủ bằng chứng về giờ phục vụ hiện hành |
| BHYT 2026-2027 — mức thu và mốc đóng | Có thông báo trên cổng SV nhưng chưa đủ nội dung trích xuất để khẳng định chính xác mức thu/mốc |
| Khen thưởng — tiêu chuẩn và mức thưởng | Có chức năng và đầu mối phụ trách; chưa có đầy đủ quy định/mức thưởng hiện hành |
| Kỷ luật — toàn bộ hành vi và mức xử lý | Có QĐ 1351/2025 và quy định VHHĐ; chưa trích xuất đầy đủ mọi dòng của phụ lục |
| Thẻ sinh viên — cấp lại, mất thẻ, lệ phí | Đã xác minh Phòng CT&SV phụ trách in/cấp thẻ; chưa đủ quy trình và biểu phí hiện hành |
| Tuần sinh hoạt công dân — quy chế điểm danh/hậu quả vắng | Đã xác minh lịch và đơn vị phụ trách; chưa có đủ quy định xử lý vắng/không hoàn thành |
| **ctdt.ntu.edu.vn — chưa xác minh đã thu thập toàn bộ chương trình/endpoint** | Cổng này có thể truy xuất và đã lấy được nhiều PDF CTĐT (`ctdt.ntu.edu.vn/ctdt/[số].pdf`). Cổng hiển thị danh mục CTĐT theo khóa 63–68 và khoa quản lý. Tuy nhiên, chưa thể khẳng định đã thu thập **toàn bộ** URL/chương trình ẩn phía sau giao diện. Cần duyệt thêm để hoàn thiện. |
| Danh mục đầy đủ biểu mẫu Phòng Đào tạo | Đã bị loại khỏi căn cứ theo yêu cầu ban đầu |
| Danh sách sinh viên / thông tin cá nhân | Không thu thập và không đưa vào dataset theo đúng phạm vi yêu cầu |

---

## 12. Kiểm soát chất lượng — Các điểm đã chỉnh sửa

1. **Làm rõ mã Khai thác thủy sản theo thời kỳ:** dữ liệu tuyển sinh 2022 dùng **7620304 = Khai thác thủy sản**; tuyển sinh 2026 dùng **7620303 = Khoa học thủy sản**, trong đó có chuyên ngành *Khai thác thủy sản*. Không dùng một mã duy nhất cho mọi năm.
2. **Mở rộng whitelist theo yêu cầu mới:** `phongdbcl.ntu.edu.vn`, `pdtsaudaihoc.ntu.edu.vn`, `thanhnien.ntu.edu.vn`, `trungtamdtbd.ntu.edu.vn`, `xettuyen.ntu.edu.vn` được phép crawl và bổ sung. Tuy nhiên QĐ 753 vẫn bị loại khỏi căn cứ theo yêu cầu riêng trước đó. Link NĐ 238/2025/NĐ-CP dùng `vanban.chinhphu.vn` chính thức.
3. **Xóa số liệu điểm rèn luyện 2013:** Sổ tay SV 2013 không được dùng làm quy tắc hiện hành. Đã giữ lại quy trình đánh giá rèn luyện hiện tại của Phòng CTSV.
4. **Tách CTĐT theo mã ngành + chương trình + khóa + phiên bản:** Bảng CTĐT (mục 6) đã tách riêng QTDVDL&LH (7810103, 7810103P), QTKD (7340101 với các phiên bản song ngữ/TT-CLC), CNTT (7480201 chuẩn, K65).
5. **Sửa mục “ctdt.ntu.edu.vn không crawl được”:** Đã thay bằng “chưa xác minh đã thu thập toàn bộ chương trình/endpoint”; ghi nhận cổng hiển thị danh mục CTĐT theo khóa 63–68.

---


## 13. Metadata, mức độ tin cậy và quy tắc hiệu lực

### 13.1. Quy tắc trạng thái hiệu lực

- **Đang áp dụng theo mốc nêu trong record**: thông báo/quy trình có mốc thời gian đang bao phủ ngày kiểm tra 12/09/2026.
- **Hết thời hạn áp dụng nêu trong record**: thông báo/học kỳ/đợt tuyển sinh đã kết thúc; nội dung vẫn được giữ làm dữ liệu lịch sử.
- **Có hiệu lực/chưa thấy văn bản thay thế**: chỉ dùng khi văn bản vẫn đang được NTU công khai/dẫn chiếu trong trang hiện hành và chưa xác minh được văn bản thay thế. Không suy ra hiệu lực chỉ từ năm ban hành.
- **Dự thảo**: nguồn tự ghi là dự thảo; không dùng như quy định/CTĐT đã ban hành.
- **Lịch sử/đối chiếu**: nguồn cũ hoặc kho minh chứng, chỉ dùng để so sánh theo thời kỳ.
- **Chưa xác định**: không đủ bằng chứng về hiệu lực hiện tại.

### 13.2. Phân biệt chuẩn ngoại ngữ

| Nhóm chuẩn | Ví dụ trong file | Ý nghĩa |
|---|---|---|
| Chuẩn đầu ra đại học | CNTT chuẩn 2026: PLO2 ngoại ngữ bậc 4/6 | Yêu cầu của một CTĐT đại học cụ thể; không suy rộng sang ngành/khóa khác |
| Chuẩn đầu vào thạc sĩ | Thạc sĩ CNTT 2022: ngoại ngữ bậc 3/6 | Điều kiện dự tuyển/đầu vào của CTĐT thạc sĩ |
| Chuẩn đầu ra thạc sĩ | Phòng ĐTSĐH: bậc 4/B2 trước xét tốt nghiệp | Điều kiện tốt nghiệp thạc sĩ |
| Chuẩn tuyển sinh/đầu vào tiến sĩ | Chỉ ghi khi tìm được quy chế/đề án tiến sĩ có điều khoản trực tiếp | Không được lấy chuẩn thạc sĩ hoặc chuẩn đại học để suy ra |

### 13.3. Mức độ tin cậy

> Cột `Mức độ tin cậy` được áp dụng cho **tất cả bảng fact từ mục 1 đến mục 9**, bao gồm danh mục 30 ngành VLVH và bảng văn bản pháp quy.

- **Cao**: PDF/văn bản gốc, CTĐT gốc, trang chức năng nhiệm vụ hiện hành, thông báo chính thức có ngày và nội dung cụ thể.
- **Trung bình**: trang tổng hợp/danh mục, bài viết của đơn vị chính thức, thông tin lịch sử cần đối chiếu với văn bản gốc.
- **Thấp**: nguồn lịch sử cũ không xác định được trạng thái hoặc chỉ có snippet/metadata chưa đủ. Record loại này không nên dùng để trả lời khẳng định hiện hành.

> Khi chuyển file này sang cơ sở dữ liệu/RAG, nên thêm các trường vật lý: `Năm học`, `Khóa áp dụng`, `Trình độ`, `Loại chuẩn`, `Trạng thái hiệu lực`, `Mức độ tin cậy`, `Ngày kiểm tra cuối = 12/09/2026`. Trong bản Markdown đọc bằng mắt, các bảng được tách theo chủ đề để tránh một bảng 200+ dòng.

### 13.4. Chuẩn hóa URL

- URL trong các bảng fact đã được chuẩn hóa phần path/query bằng **percent-encoding UTF-8** khi có khoảng trắng hoặc ký tự Unicode, đồng thời giữ nguyên các escape `%xx` đã có.
- Mục tiêu là tăng độ ổn định khi dùng với crawler, HTTP client, parser Markdown và pipeline RAG.
- Trong lần chuẩn hóa này có **6 URL** được thay đổi biểu diễn; nội dung nguồn không thay đổi.

## 14. Audit — dữ liệu bị loại/không nhập lại

| Mục | Xử lý | Lý do |
|---|---|---|
| `Kiến trúc máy tính` / `An toàn mạng` từng được nhắc trong nhận xét cũ | Không tái nhập | File nguồn hiện tại không chứa hai record này; không có bằng chứng trong file mới nhất để xác định nguồn gốc của chúng. Nếu tìm được đề cương học phần chính thức sau này, nên nhập với loại `học phần`, không phải `ngành`. |
| QĐ 753/2021 qua `thanhnien.ntu.edu.vn` | Không dùng làm căn cứ chính | Tên miền nay được phép nhưng văn bản QĐ 753 vẫn thuộc danh sách người dùng yêu cầu loại khỏi căn cứ. |
| Mục “Học bổng” của Phòng Tài chính | Không dùng làm nguồn cho học bổng SV khuyết tật | Các thông báo/quyết định về học bổng SV khuyết tật được xác minh ở `phongctsv.ntu.edu.vn`; không có căn cứ để gán nội dung này cho `phongkhtc.ntu.edu.vn`. |
| QĐ 1525 — cột ngày trên danh mục | Giữ ghi chú sai lệch | PDF gốc ghi 13/10/2023; danh mục web hiện hiển thị 13/11/2023. Ưu tiên ngày trên văn bản gốc. |


### 14.1. Audit bổ sung ngày 12/09/2026

- **BHYT/BHTT 2026-2027:** đã tái xác minh trực tiếp trên `sinhvien.ntu.edu.vn`; BHTT tự nguyện 150.000 đồng/năm. Mức BHYT và thời hạn đóng chi tiết vẫn chưa được trích đầy đủ nên tiếp tục để ở “Chưa tìm được”.
- **Điểm rèn luyện:** trang chính thức của Phòng CTSV xác nhận quy trình nhiều bước; các mốc tuần 2–7 của bản cũ chưa tái xác minh đầy đủ nên đã loại khỏi fact chính và hạ mức tin cậy record quy trình xuống **Trung bình**.
- **Thạc sĩ CNTT 2022:** PDF CTĐT trực tiếp xác nhận chuẩn đầu vào ngoại ngữ **bậc 3/6** và PLO2 đầu ra **bậc 4/6**.
- **Kiến trúc máy tính:** CTĐT thạc sĩ CNTT 2022 có học phần bổ sung kiến thức `INS331 Kiến trúc máy tính`, 3(2-1) tín chỉ. Nếu nhập vào knowledge graph, loại đúng là `học phần`, không phải `ngành`. Record `An toàn mạng` với mã NEC355 của nhận xét cũ vẫn chưa có nguồn tương ứng trong bản này; không tự khôi phục.

- **Danh mục VLVH/liên thông 2026:** bảng nguồn chính thức liệt kê TT 1–30; do đó phát biểu chính xác là “Thông báo tuyển sinh VLVH/liên thông 2026 liệt kê **30 ngành**”, không suy rộng thành “NTU chỉ có 30 ngành VLVH”.
- **Thống kê fact:** số 196/187 của bản v2 không còn được sử dụng. Sau khi đếm toàn bộ bảng fact mục 1–9 theo quy tắc công khai ở mục 16, bản này có 204/204.

## 15. Ghi chú thay đổi so với `ntu_thong_tin_hoc_vu_master_2026-09-12.md`

1. Mở rộng whitelist thêm `phongdbcl`, `pdtsaudaihoc`, `thanhnien`, `trungtamdtbd`, `xettuyen`; tiếp tục cho phép `ctdt` theo yêu cầu crawl trước đó.
2. Bổ sung dữ liệu hiện hành từ Phòng ĐBCL&KT: chức năng nhiệm vụ theo QĐ 600/2025 và hoạt động tự đánh giá 05 CTĐT năm 2025.
3. Bổ sung dữ liệu sau đại học: chức năng Phòng ĐTSĐH, điều kiện xét tốt nghiệp thạc sĩ 2026, chuẩn đầu ra ngoại ngữ B2/bậc 4, ví dụ đầu vào/đầu ra thạc sĩ CNTT.
4. Bổ sung tuyển sinh VLVH/liên thông 2026: 30 ngành, mã ngành, nhóm thời gian đào tạo, đối tượng và các tháng xét tuyển.
5. Bổ sung quy trình nhập học 2026 từ `xettuyen.ntu.edu.vn`, gồm quy tắc tài khoản, đăng ký KTX và mốc tạm thu học phí.
6. Xác minh QĐ 1525: ưu tiên ngày **13/10/2023 trên PDF gốc**; ghi chú danh mục web đang hiển thị 13/11/2023.
7. Phân biệt rõ chuẩn ngoại ngữ đầu vào/đầu ra và trình độ áp dụng; không dùng chuẩn sau đại học để chứng minh chuẩn đại học.
8. Xác nhận nguồn học bổng SV khuyết tật ở Phòng CT&SV, không gán cho Phòng Tài chính.
9. Áp dụng trực tiếp cột `Mức độ tin cậy` cho các bảng fact; không chỉ mô tả thang điểm ở phần hướng dẫn.
10. Ghi Audit cho record học phần cũ; xác minh lại `INS331 Kiến trúc máy tính` từ CTĐT thạc sĩ CNTT 2022 và tiếp tục không khôi phục `An toàn mạng` khi chưa có nguồn tương ứng.

11. Tái xác minh trực tiếp BHYT/BHTT 2026-2027 trên cổng sinh viên; giữ BHTT 150.000 đồng/năm với mức tin cậy Cao.
12. Loại các mốc tuần 2–7 khỏi fact chính về điểm rèn luyện do chưa tái xác minh đầy đủ trong lần kiểm tra này.
13. Đổi loại các record mô tả CTĐT cụ thể từ `ngành` sang `chương trình` trong bảng CTĐT.

14. Chuẩn hóa metadata: mọi bảng fact mục 1–9 đều có `Trạng thái hiệu lực`, `Mức độ tin cậy`, `Ngày kiểm tra cuối`.
15. Chuẩn hóa URL bằng percent-encoding đối với đường dẫn có khoảng trắng/ký tự Unicode.
16. Thống kê lại toàn bộ file: 204 fact record và 204 fact độc lập theo khóa dedupe được công bố ở mục 16; số 196/187 của bản trước được thay thế vì phương pháp đếm cũ chưa bao phủ đầy đủ tất cả bảng fact.
17. Ghi rõ quy tắc entity–fact: cùng một thực thể có thể có nhiều fact khác nhau mà không bị coi là duplicate.
18. Bổ sung `Trạng thái hiệu lực` cho bảng văn bản pháp quy và giữ trạng thái thận trọng `Chưa xác định` khi chưa đủ bằng chứng về thay thế/hết hiệu lực.

## 16. Thống kê fact độc lập và phương pháp đếm

**Định nghĩa:** mỗi dòng dữ liệu trong các bảng fact từ mục 1 đến mục 9 = 1 `fact record`.

**Khóa dedupe chính xác:** toàn bộ trường nội dung cốt lõi của dòng sau khi chuẩn hóa Unicode NFC và gom khoảng trắng. Ba trường audit `Trạng thái hiệu lực`, `Mức độ tin cậy`, `Ngày kiểm tra cuối` không tham gia khóa dedupe. Không gộp hai dòng chỉ vì cùng `Thực thể`.

| Mục | Số fact record |
|---|---:|
| Mục 1 | 24 |
| Mục 2 | 15 |
| Mục 3 | 18 |
| Mục 4 | 7 |
| Mục 5 | 5 |
| Mục 6 | 30 |
| Mục 7 | 37 |
| Mục 8 | 48 |
| Mục 9 | 20 |
| **Tổng** | **204** |

- **Dòng fact trước dedupe:** 204.
- **Fact độc lập sau dedupe chính xác:** 204.
- **Duplicate chính xác bị loại theo quy tắc trên:** 0.
- Không tính: bảng alias, “Chưa tìm được”, Audit, bảng ví dụ metadata và các đoạn ghi chú không phải bảng fact.
- Một entity có thể có nhiều fact hợp lệ. Ví dụ `Phòng Tài chính` có thể có một dòng về liên hệ và một dòng về chức năng; hai dòng này **không phải duplicate** nếu nội dung khác nhau.

## Phạm vi hiện tại

- **Nguồn trọng tâm:** `ntu.edu.vn`, `pdtdaihoc.ntu.edu.vn`, `phongctsv.ntu.edu.vn`, `phongkhtc.ntu.edu.vn`, `phongcntt.ntu.edu.vn`, `tuyensinh.ntu.edu.vn`, `sinhvien.ntu.edu.vn`, `htdnhtsv.ntu.edu.vn`, `thuvien.ntu.edu.vn`, `ctdt.ntu.edu.vn`, `phongdbcl.ntu.edu.vn`, `pdtsaudaihoc.ntu.edu.vn`, `thanhnien.ntu.edu.vn`, `trungtamdtbd.ntu.edu.vn`, `xettuyen.ntu.edu.vn` và văn bản Nhà nước được NTU dẫn chiếu (`vanban.chinhphu.vn`), cùng nguồn pháp lý bổ sung được chấp nhận như `chinhphu.vn`, `xaydungchinhsach.chinhphu.vn` và cổng Bộ GD&ĐT khi NTU dẫn chiếu.
- **Trạng thái:** Đây là bản tổng hợp đã được mở rộng nguồn và kiểm chứng thêm ngày 12/09/2026. Chưa nên coi là bộ dữ liệu “100% đầy đủ” cho mọi CTĐT × khóa × học phí × chuẩn đầu ra; các khoảng trống được giữ trong mục “Chưa tìm được”.
