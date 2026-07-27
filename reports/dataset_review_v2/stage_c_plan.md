# Stage C — kế hoạch và nhật ký review ngôn ngữ

Trạng thái: **hoàn thành**. Kết quả nằm tại `stage_c_report.md`.

## Phạm vi khóa

- Đầu vào: `resources/datasets/sparql_v2/draft.jsonl` sau Stage B.
- 948 record, 233 semantic family, 87 target.
- Không đổi target trừ khi review phát hiện lỗi ngữ nghĩa mới có bằng chứng.
- Không bổ sung coverage, không chia split và không train trong Stage C.

## Rubric từng record

1. Câu hỏi đúng nhu cầu và mọi ràng buộc của target.
2. Đọc tự nhiên ở góc độ sinh viên/người dùng, không nói về ontology, class,
   cá thể, IRI, hệ thống lưu trữ hoặc thao tác “trả về”.
3. `formal` đầy đủ và hành chính vừa phải; `neutral` là câu hỏi thông thường;
   `colloquial` là lời nói đời thường có thể đọc được; `noisy` dùng viết tắt,
   thiếu dấu hoặc lỗi gõ thực tế nhưng vẫn chắc nghĩa.
4. Noisy không được tạo bằng phá chữ ngẫu nhiên và phải giữ nghĩa sau
   normalizer.
5. Các câu trong cùng family phải khác cách diễn đạt nhưng cùng target; câu gần
   trùng không được giữ chỉ để tăng số lượng.
6. Không để tên property/schema xuất hiện trong input; tên thật của quy trình,
   phòng ban, ngành, khóa và văn bản vẫn được phép dùng.

## Thứ tự review

- [x] `cap-001`–`cap-010`
- [x] `cap-011`–`cap-020`
- [x] `cap-021`–`cap-030`
- [x] `cap-031`–`cap-040`
- [x] `cap-041`–`cap-050`
- [x] `cap-051`–`cap-060`
- [x] `cap-061`–`cap-074`
- [x] aggregate và aggregate-filter thủ công
- [x] review chéo toàn bộ register, duplicate và normalizer

Mỗi cụm chỉ được đánh dấu hoàn thành sau khi đã đọc mọi input và ghi quyết định
keep/rewrite/drop/register. Các phép sửa được lưu bằng record ID để có thể tái
lập và review diff.
