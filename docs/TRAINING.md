# Huấn luyện

## Đường đang dùng: QLoRA cho LLM sinh SPARQL

Một model nhân quả được tinh chỉnh bằng QLoRA để sinh truy vấn SPARQL từ câu hỏi
tiếng Việt. Chatbot là **công cụ cho một LLM lớn gọi**, không phải người trả lời:
nó truy ra trọn vẹn một node rồi để LLM lớn đọc và tự viết câu.

### Chạy trên máy có GPU

```bash
uv sync --extra train
bash scripts/train-and-report.sh --smoke-test --allow-download   # lần đầu
bash scripts/train-and-report.sh                                  # chạy thật
```

Script ghi bối cảnh máy, phiên bản thư viện, commit, **vân tay SHA256 của từng
tập dữ liệu**, rồi huấn luyện, chấm cả validation lẫn test, và gói mọi thứ thành
một `.tar.gz`. Vân tay là phần quan trọng nhất: thiếu nó thì không ai chứng minh
được một con số thuộc về bản dataset nào.

Chấm lại một adapter đã có, khỏi huấn luyện lại:

```bash
ADAPTER=artifacts/run-<mốc>/adapter bash scripts/train-and-report.sh --skip-train
```

### Hai thứ tự điều chỉnh theo máy

**Gradient checkpointing** bật khi VRAM dưới 16 GiB và tắt khi trên. Nó đổi bộ nhớ
lấy tốc độ: bỏ activation rồi tính lại ở lượt truyền ngược. Kết quả huấn luyện
không đổi. Ép tay bằng `--gradient-checkpointing on|off`.

**Lô vật lý** tự lùi khi hết bộ nhớ, và **lô hiệu dụng luôn giữ nguyên 8** nhờ
tích luỹ gradient — nên một lượt chạy trên card 6 GB và một lượt trên card 24 GB
so sánh được với nhau.

### Số đo tham chiếu

Lượt huấn luyện ngày 15/8/2026 trên NVIDIA L4 24 GB: **79 phút**, 2.046 bước,
3 epoch, lô vật lý 4, checkpointing tắt, VRAM đỉnh 13,43 GiB, 3,445 mẫu/giây,
mất mát 1,928 → 0,0018.

### Ghim bản model

Cả đường huấn luyện lẫn đường chấm đều hỏi **cùng một commit** của model gốc.
Không ghim thì thư viện hỏi nhánh `main`, và nếu nhánh đó nhích đi thì adapter bị
chấm trên một model khác với model nó đã học — số thu về vô nghĩa mà không có dấu
hiệu nào báo sai.

### Model không tự tải về

Cả hai đường đều từ chối tải model nếu cache chưa có. Tải âm thầm 4,57 GB trên
máy tính tiền theo giờ là chuyện không nên xảy ra. Cho phép bằng
`--allow-download` khi đã biết mình đang làm gì.

---

## Quy trình huấn luyện lịch sử (v2, đã ngừng)

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
