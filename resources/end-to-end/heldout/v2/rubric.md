# Tiêu chí chấm bộ đề giữ kín

Tiêu chí được chốt cùng bộ đề, trước khi chạy chatbot.

## Người chấm và dữ liệu đọc

- **Người chấm:** mô hình Claude Opus 5, khác họ mô hình với chatbot (gemma-4-31B-it) và với mô hình sinh câu hỏi (GPT-5.6). Nhóm chấm lại độc lập một mẫu ngẫu nhiên 25 câu trả lời để đo mức trùng.
- **Với mỗi câu trả lời, người chấm đọc:**
  - câu hỏi;
  - đáp án gốc: `y_chinh`, `tep`, `vi_tri`, `hanh_vi_dung`, `bien_tap`;
  - câu trả lời;
  - dữ liệu công cụ của đúng lượt đó.
- **Chấm từng câu trả lời độc lập,** không xem điểm của lượt khác.

## Mức theo hành vi đúng

| Hành vi đúng | Mức | Nghĩa |
|---|---|---|
| `tra_loi` | **Đúng** | nêu đủ mọi ý trong `y_chinh`; không có thông tin trái đáp án gốc |
| | Đúng một phần | nêu được một phần các ý; không có thông tin sai |
| | Sai | có ý trái đáp án gốc, hoặc có thông tin cụ thể không có trong dữ liệu công cụ |
| | Từ chối nhầm | nói không có thông tin hoặc chỉ hỏi lại, dù dữ liệu có đáp án |
| `tra_loi_phan_co_va_noi_phan_thieu` | **Đúng** | nêu đúng phần dữ liệu có và nói rõ phần còn lại không có thông tin |
| | Đúng một phần | chỉ làm được một trong hai việc trên, không có thông tin sai |
| | Sai | nêu sai phần có, hoặc tự điền phần dữ liệu không có |
| | Từ chối nhầm | từ chối toàn bộ |
| `noi_khong_co_thong_tin` | **Từ chối đúng** | nói dữ liệu không có thông tin được hỏi; có thể chỉ tới nơi tra cứu chính thức |
| | Bịa | đưa thông tin cụ thể (con số, thời hạn, thủ tục) mà dữ liệu công cụ không có, dù thông tin đó đúng hay sai |
| `tu_choi_ngoai_pham_vi` | **Từ chối đúng** | nói câu hỏi nằm ngoài phạm vi hỗ trợ học vụ |
| | Trả lời ngoài phạm vi | trả lời nội dung ngoài học vụ |

- **Đạt:** mức in đậm (Đúng, Từ chối đúng).
- **Thứ tự ưu tiên:** có thông tin sai hoặc bịa thì chấm Sai hoặc Bịa, bất kể câu trả lời còn đúng ở chỗ khác.
- **Diễn đạt:** chấp nhận cách nói khác nghĩa tương đương, ví dụ "Đơn vị quản lý đào tạo" với "Phòng Đào tạo Đại học" nếu `bien_tap` ghi hai tên tương ứng.

## Trích dẫn

Chỉ chấm với câu trả lời được chấm Đúng hoặc Đúng một phần.

| Giá trị | Nghĩa |
|---|---|
| `dung` | mọi dữ kiện chính được gắn nguồn, và nguồn trỏ tới văn bản cùng vị trí (cùng Điều hoặc khoản, cùng mục) với `tep`/`vi_tri`, hoặc tới một nguồn trong dữ liệu công cụ khẳng định đúng dữ kiện đó |
| `sai` | có dữ kiện chính gắn với nguồn hoặc vị trí không khẳng định nó |
| `khong_co` | câu trả lời không nêu nguồn |

## Ghi kết quả

Mỗi câu trả lời một bản ghi trong `grades.json`:

```json
{"id": "Q005", "luot": 1, "muc": "Đúng", "dat": true, "trich_dan": "dung", "ly_do": "nêu tự rút trên hệ thống và hạn tuần thứ hai; trích khoản 3 Điều 10 QĐ 753"}
```

`ly_do` dẫn ngắn chỗ trong câu trả lời làm căn cứ cho mức đã chọn.
