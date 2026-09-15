Nhiệm vụ: xây một bộ câu hỏi kiểm thử độc lập để đánh giá một chatbot hỏi đáp học vụ dành cho sinh viên Trường Đại học Nha Trang. Bạn không thấy chatbot và không cần biết nó hoạt động thế nào.

NGUỒN DUY NHẤT: các tệp trong thư mục hiện tại. Đây là văn bản chính thức của Trường. Không dùng kiến thức bên ngoài, không truy cập web, không đọc tệp ngoài thư mục này. Đọc kỹ phần liên quan trước khi viết.

## Chủ đề và số câu (tổng 35 câu)

| Mã | Chủ đề | Tệp gợi ý | co_dap_an | khong_co_trong_van_ban |
|---|---|---|---:|---:|
| A1 | Đăng ký học phần, lớp học phần bị xóa, học lại, học cải thiện; **sinh viên tự hủy hoặc rút học phần đã đăng ký** (các tệp hiện không quy định việc này: 2 câu loại khong_co_trong_van_ban phải hỏi về hủy/rút học phần) | Qd1052.md (Điều 8–11, Phụ lục 1) | 4 | 2 |
| A2 | Học cùng lúc hai chương trình (song ngành), văn bằng thứ hai, học liên thông | Qd1052.md (Điều 28, 29), Qd626.md | 4 | 1 |
| A3 | Học phí: mức học phí, cách tính, thời hạn, quy trình thu, cách đóng học phí | Qd729.md, Qd1314.md, huong_dan_dong_hoc_phi.md, DongHocPhi_VCB_2021.md | 4 | 1 |
| A4 | Chương trình đặc biệt và chương trình chuẩn (đại trà): khác nhau về khối lượng học tập, chuẩn ngoại ngữ, học phí… | Qd1052.md, Qd1965.md, Qd729.md | 4 | 1 |
| B1 | Nghỉ học tạm thời, thôi học, nghỉ ốm, chuyển ngành, chuyển trường | Qd1052.md (Điều 24–26, 30) | 2 | 1 |
| B2 | Thi, đánh giá học phần, điểm, cảnh báo học tập, buộc thôi học | Qd1052.md (Điều 15–20) | 2 | 1 |
| B3 | Tốt nghiệp, xếp loại tốt nghiệp, chuẩn ngoại ngữ và tin học | Qd1052.md (Điều 22–23, Phụ lục 2–3), Qd1965.md | 2 | 1 |
| B4 | Học bổng khuyến khích học tập | Qd317.md, tieu-chuan-hoc-bong.txt | 2 | 1 |
| C | Ngoài học vụ | — | 0 | 0 (2 câu loại ngoai_hoc_vu) |

## Ba loại câu

**co_dap_an** — văn bản trả lời được đầy đủ câu hỏi.
- `y_chinh`: 1–4 ý mà một câu trả lời đúng bắt buộc phải có; mỗi ý ngắn, trung thành với văn bản (con số, đơn vị, điều kiện, tên đơn vị, số mẫu đơn phải đúng từng chữ).
- `tep`: tên tệp chứa căn cứ.
- `vi_tri`: chỗ nhỏ nhất trong văn bản, ví dụ "điểm a khoản 1 Điều 28", "Phụ lục 2, dòng IELTS"; với tài liệu không chia điều thì ghi mục hoặc bước.
- `trich_nguyen_van`: 1–3 đoạn trích liên tục, **sao chép nguyên văn từng ký tự** từ tệp (giữ dấu, giữ ký hiệu như ** nếu có trong đoạn), mỗi đoạn tối đa 300 ký tự; các đoạn này cộng lại phải chứng minh được mọi ý trong `y_chinh`.
- Một số câu (khoảng 1/4) nên cần ghép hai chỗ của văn bản, ví dụ điều kiện và thủ tục.

**khong_co_trong_van_ban** — câu sinh viên thật sự có thể hỏi về chủ đề đó, nhưng các tệp **không** trả lời, kể cả một phần.
- Chỉ xếp loại này sau khi đã tìm trong các tệp; không được đoán.
- `y_chinh`: một ý dạng "Văn bản không quy định …".
- `tep`, `vi_tri`: phần gần nhất đã kiểm tra (hoặc null); `trich_nguyen_van`: [].
- `ghi_chu`: đã kiểm tra những phần nào, nội dung gần nhất là gì.
- Có thể là câu về thông tin riêng của một sinh viên hoặc một đợt cụ thể (ví dụ học phí của em kỳ này, lịch đăng ký học phần tuần sau).

**ngoai_hoc_vu** — không liên quan học vụ (trò chuyện, kiến thức chung) hoặc không nêu yêu cầu rõ ràng. `y_chinh`: ["Ngoài phạm vi học vụ"]; `tep`, `vi_tri`: null; `trich_nguyen_van`: [].

## Độ chính xác của đáp án gốc

- Qd1965.md sửa đổi, bổ sung Phụ lục của Qd1052.md. Nội dung nào đã được sửa trong Qd1965.md thì đáp án gốc dùng giá trị của Qd1965.md (`tep` = Qd1965.md).
- Với bảng (học phí, quy đổi chứng chỉ, mức học bổng): đọc tiêu đề bảng, tiêu đề cột và phạm vi áp dụng (khóa, loại chương trình, khối ngành, năm học) trước khi lấy số; ghi phạm vi áp dụng vào `y_chinh`.
- Văn bản có thời hạn (mức học phí của một học kỳ, mức học bổng của một năm học): nêu học kỳ hoặc năm học áp dụng trong `y_chinh`.
- Mỗi câu hỏi chỉ có một cách hiểu hợp lý. Nếu cách nói đời thường có thể chỉ hai quy định khác nhau (ví dụ "văn bằng 2" vừa có thể là học cùng lúc hai chương trình, vừa có thể là liên thông văn bằng 2 cho người đã tốt nghiệp đại học), câu hỏi phải nêu rõ tình huống.
- Loại khong_co_trong_van_ban: tối đa 3 câu trong cả bộ hỏi thông tin riêng của một sinh viên (điểm, học phí, danh sách của riêng em); các câu còn lại phải hỏi một quy định hoặc thủ tục mà văn bản không nêu. Không chọn câu mà văn bản trả lời được một phần (ví dụ văn bản có liệt kê một số ngành thì không hỏi "có những ngành nào").
- `phong_cach` = khong_dau nghĩa là viết hoàn toàn không dấu.

## Cách viết câu hỏi

Viết như sinh viên thật nhắn tin cho chatbot của trường, không như người soạn đề:
- Phong cách (`phong_cach`), phân bố xấp xỉ: đời thường 40%, không dấu 20%, viết tắt hoặc lỗi gõ 20% (hp, đk, sv, ctđt, tc, hk…), trang trọng 20%.
- Ít nhất một nửa số câu mô tả tình huống hoặc dùng từ đời thường thay cho thuật ngữ của văn bản (ví dụ "em muốn học thêm 1 ngành nữa song song" thay vì "học cùng lúc hai chương trình"; "em rớt môn thì sao" thay vì "học phần có điểm dưới 5,0").
- Không nhắc số điều, số khoản hay số hiệu văn bản, trừ tối đa 2 câu trong cả bộ.
- Mỗi câu đứng độc lập (không dựa vào câu trước), một yêu cầu chính, tối đa hai vế.
- Không trùng lặp hoặc chỉ đổi vài chữ giữa các câu; đa dạng độ khó.

## Đầu ra

Chỉ trả về JSON theo schema đã cho, đúng 35 phần tử. Kiểm tra lại từng `trich_nguyen_van` bằng cách tìm trong tệp trước khi trả kết quả.

## Các câu đã có trong bộ — không viết lại câu cùng ý hoặc cùng chỗ văn bản với cùng góc hỏi

- Em học lực trung bình trở lên ở chương trình 4 năm, kỳ tới đăng ký 28 tín chỉ được không?
- Em rớt một môn bắt buộc dưới 5 thì phải đk học lại thế nào?
- Lop hp tu chon em da dang ky bi xoa vi it nguoi, em lam gi bay gio?
- Khi học lại đúng môn để kéo điểm, trường ghi nhận điểm lần nào?
- Em lỡ đăng ký nhầm môn, giờ tự hủy học phần đó trên hệ thống được không?
- Em muốn rút một hp đã đk giữa kỳ thì có được hoàn tiền không?
- Em muốn học thêm một ngành song song từ năm hai, cần điều kiện học lực gì?
- Hoc song nganh ma diem TB hk cua nganh 1 xuong 5,4 thi sao a?
- Muốn học văn bằng thứ hai thì đăng ký lúc nào và dùng mẫu nào?
- Người đã tốt nghiệp cao đẳng muốn học liên thông lên đại học thì đăng ký vào thời điểm nào?
- Đợt này trường đang mở song ngành những ngành nào vậy?
- Em học CNTT khóa 65, học phần cơ sở và chuyên ngành của chương trình kiểm định tính bao nhiêu tiền một tín chỉ?
- Học phần giáo dục tổng quát bậc đại học khối kinh doanh và quản lý đóng bao nhiêu, còn môn cơ sở/chuyên ngành thì sao?
- Dong hoc phi qua VNPAY thi tai khoan can gi, VCB va ngan hang khac co phi khac nhau khong?
- Sau khi em đóng học phí thành công thì hóa đơn được gửi ở đâu?
- Học phí chính xác kỳ này của riêng em là bao nhiêu?
- CT đặc biệt theo đặt hàng doanh nghiệp được đăng ký tối đa bao nhiêu TC một kỳ, có khác CT 4 năm thường không?
- Em học chương trình đặc biệt Quản trị kinh doanh, IELTS 5.0 đã đạt mức yêu cầu chưa?
- Học bổng loại giỏi của chương trình đặc biệt khác chương trình chuẩn bao nhiêu?
- Chứng chỉ ngoại ngữ quốc tế của sinh viên chương trình đặc biệt được tính như thế nào?
- Năm nay trường có những ngành nào là chương trình đặc biệt vậy?
- Em học được một kỳ rồi, có việc cá nhân muốn nghỉ tạm thì điều kiện và đơn thế nào?
- Em bi om, nghi hoc 3 ngay thi nop giay to va bao cho ai trong bao lau?
- Nếu được chuyển ngành thì em có phải đóng lại học phí các môn đã học không?
- Kỳ đầu mà điểm trung bình dưới bao nhiêu thì bị cảnh báo học tập?
- Mon ly thuyet nghi qua nhieu thi co du dieu kien thi khong, nghi co ly do phai nop don bao lau?
- Điểm thi cuối kỳ của em đã có trên hệ thống chưa?
- Tôi muốn xét tốt nghiệp sớm thì ngoài điều kiện học tập cần nộp mẫu gì và gửi đơn vị nào?
- Nếu điểm tổng kết loại giỏi nhưng phải học lại nhiều môn, xếp loại tốt nghiệp có bị hạ không?
- Em dang thieu chung chi tin hoc nao de du dieu kien ra truong?
- HBKK loại xuất sắc của hệ chính quy và chương trình đặc biệt mỗi học kỳ là bao nhiêu?
- Muốn được xét học bổng khuyến khích thì một kỳ em phải đăng ký ít nhất bao nhiêu tín chỉ và điểm các môn lần đầu tối thiểu bao nhiêu?
- Tôi có tên trong danh sách nhận học bổng kỳ này không?
- Hôm nay ở Nha Trang có mưa không?
- Ke em nghe mot cau chuyen vui di
