# Quy trình huấn luyện lịch sử

> **Đã ngừng. Không phải baseline.** Tài liệu này chỉ giải thích quy trình v2
> còn dấu vết trong mã nguồn. Dataset dùng cho các lượt huấn luyện đó hỏng, nên
> mọi metric, bảng kết quả, kết luận chọn model và số liệu triển khai đều vô giá
> trị. Model cũ không phải phương án lui cho v3.

## Mục đích lưu lại

Code huấn luyện vẫn giúp truy vết một quyết định kỹ thuật trong lịch sử dự án:
một model seq2seq được dạy để sinh SPARQL từ câu hỏi tiếng Việt. Giữ mô tả quy
trình giúp đọc code và hiểu vì sao repository còn các dependency huấn luyện,
nhưng không hợp thức hoá checkpoint hay kết quả cũ.

## Luồng thí nghiệm đã dùng

Quy trình lịch sử gồm:

1. kiểm tra ontology, danh mục khả năng trả lời và danh mục truy vấn;
2. chia dữ liệu thành train, validation và test;
3. fine-tune các model sinh chuỗi bằng adapter;
4. chọn checkpoint dựa trên validation;
5. hợp nhất adapter rồi mới đánh giá;
6. chuyển model đã chọn sang runtime tối ưu nếu cần.

Nguyên tắc chống rò rỉ vẫn đúng về phương pháp: test không tham gia chọn checkpoint.
Test chỉ được mở sau khi model, prompt, hyperparameter và tiêu chí
chọn đã cố định.

## Điều không còn được công bố

Tài liệu không giữ:

- kích thước dataset v2;
- hyperparameter và thời gian chạy của các lượt vô hiệu;
- metric validation/test;
- so sánh hoặc xếp hạng model;
- metric runtime và latency;
- liên kết tới báo cáo hay biểu đồ model đã xoá.

`reports/provenance.json` vẫn giữ fingerprint và đánh dấu
`model_metrics.status` cùng `deployment_metrics.status` là `stale`. Các trạng
thái đó không biến metric cũ thành lịch sử dùng được; chúng chỉ ngăn artifact cũ
bị hiểu là kết quả hiện hành.

## Quan hệ với v3

V3 dùng chatbot ontology như công cụ cho một LLM lớn. Hình dạng truy xuất chính
là trọn node; bảng được trả nguyên văn. Nếu sau này huấn luyện một thành phần
ánh xạ mới, giao thức phải được thiết kế và phê duyệt lại từ đầu trên dataset đã
đồng bộ, không kế thừa điểm số hay quyết định chọn model v2.

Cho tới khi chuỗi artifact xanh, không chạy lại huấn luyện và không công bố
benchmark.
