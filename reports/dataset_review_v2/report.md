# Báo cáo Stage B — Review target và semantic family

Trạng thái: **đã review đủ worksheet; chưa sửa dataset v1**.

## Phạm vi và phương pháp

- 401/401 family đã được đọc theo nhóm target.
- 80/80 target SPARQL đã chạy lại trên ontology v11.
- Mọi target thực thi có kết quả; tổng cộng 173 hàng kết quả tham chiếu.
- Mỗi family được đối chiếu input, projection, constraint và kết quả thật.
- Không đọc điểm test/benchmark để quyết định giữ hoặc sửa.
- 164 family test v1 chỉ được audit reference, không là nguồn train/val v2.

## Kết quả quyết định

| Quyết định | Toàn bộ | Candidate train/val v2 | Test v1 audit-only |
|---|---:|---:|---:|
| `keep` | 346 | 203 | 143 |
| `fix` | 49 | 28 | 21 |
| `merge` | 5 | 5 | 0 |
| `split` | 1 | 1 | 0 |
| `drop` | 0 | 0 | 0 |
| **Tổng** | **401** | **237** | **164** |

Không có family nào bị loại chỉ vì model từng học kém. `drop=0` không có nghĩa
mọi record đã sẵn sàng phát hành: các quyết định `fix/split/merge` phải được áp
dụng và review lại trong draft v2.

## Bốn vấn đề ontology ảnh hưởng trực tiếp đến target

### 1. Điều kiện xét tốt nghiệp

`:condition` có 5 literal, trong khi `:content` còn nêu không bị kỷ luật,
GDQP-AN và GDTC. Có 16 family liệt kê, đếm hoặc ghép cột điều kiện bị đánh dấu
`fix` cho đến khi chốt phần nào là danh sách canonical.

### 2. Điều kiện xét học bổng

`:content` yêu cầu không bị kỷ luật từ mức khiển trách, nhưng tiêu chí này
không có trong `:condition`. 10 family dùng danh sách điều kiện bị đánh dấu
`fix`.

### 3. Kết quả xét học bổng

`:outcome` nói sinh viên nhận học bổng nếu đủ điều kiện, còn `:content` nói chỉ
trao theo thứ tự điểm đến khi hết chỉ tiêu. 5 family bị đánh dấu `fix` để tránh
trả lời rằng đạt ngưỡng là chắc chắn nhận học bổng.

### 4. Đơn vị xử lý chuyển ngành

`:handledBy` trỏ `UndergraduateEducationOffice`, nhưng `:content` nói hồ sơ đi
qua Phòng Công tác Chính trị và Sinh viên. 5 family hỏi số điện thoại đơn vị xử
lý chưa thể xác nhận đúng trước khi đồng bộ ontology.

Bốn vấn đề trên chi phối 36 family. Không sửa query bằng heuristic để che mâu
thuẫn dữ liệu nguồn.

## Lỗi semantic ở cấp family

13 family khác cần sửa riêng, nổi bật:

- câu hỏi “ngoài lý do sức khỏe” nhưng target trả cả lý do sức khỏe;
- câu hỏi các ngành “ngoài Ô tô” nhưng target vẫn trả Ô tô;
- câu hỏi riêng đơn xin học trở lại nhưng target trả cả hai biểu mẫu bảo lưu;
- câu hỏi dùng Condition/Outcome như class/cá thể dù v11 đã chuyển thành
  datatype property;
- câu hỏi “cách đăng ký học phần” nhưng `content` chỉ có giới hạn tín chỉ;
- câu hỏi vị trí biểu mẫu nhưng target chỉ trả nhãn;
- câu hỏi đồng thời số lượng và danh sách nhưng target chỉ trả danh sách.

## Cấu trúc family

- 5 family gần trùng được yêu cầu merge vào family tương ứng.
- `cap-066-f01` cần split: `prod-0262` hỏi cả số lượng lẫn danh sách nhóm học
  phí, ba record còn lại chỉ hỏi danh sách.
- Chưa áp dụng merge/split vào ID hoặc split v1; Stage E sẽ chia lại draft v2 ở
  cấp family sau khi Stage C–D hoàn tất.

## Cổng chuyển sang Stage C

Stage C chỉ được biên tập ngôn ngữ trên các target đã xác nhận. Với 49 family
`fix`, cần thực hiện theo thứ tự:

1. giải quyết bốn mâu thuẫn ontology nêu trên;
2. sửa target quá rộng/hẹp hoặc projection thiếu;
3. áp dụng merge/split;
4. chạy lại target và review bảng kết quả;
5. sau đó mới sửa câu gượng, register và noisy.

Nguồn chi tiết là `family_decisions.jsonl`; báo cáo này không thay thế lý do ở
từng dòng.
