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

### Chấm: gom lô, và nền trọng số theo adapter

Bộ chấm sinh **theo lô**, mặc định 16 câu một lượt, tự hạ khi tràn VRAM. Đổi bằng
biến `BENCH_BATCH`. Sinh chữ bị chặn bởi băng thông bộ nhớ — mỗi bước giải mã đọc
toàn bộ trọng số dù đang xử lý một câu hay ba mươi hai câu — nên sinh từng câu là
để card chạy không tải. Đo trên card 6 GB, 32 câu validation: **4,8 giây/câu ở lô
1 xuống 2,3 giây/câu ở lô 16** (thực tế tự hạ về 4 vì card nhỏ).

**Nền trọng số gốc chọn theo lượt đã huấn luyện adapter, không theo máy đang
chạy.** Bộ chấm đọc `training_metrics.json` nằm cạnh adapter. Adapter học cách bù
cho một nền trọng số cụ thể; chấm nó trên nền khác là chấm một model khác, và
triệu chứng duy nhất là con số hơi lệch mà không ai biết vì sao — cùng một họ lỗi
với việc ghim bản model ở dưới. Adapter không có tệp đó thì bộ chấm **dừng và
hỏi** chứ không đoán; chỉ rõ bằng `--base-precision 4bit|bf16`.

Nén 4-bit sinh ra cho card 6 GB. Trên card lớn nó chỉ làm chậm: bitsandbytes giải
nén trọng số ở mỗi lượt truyền xuôi, mà giải mã tuần tự từng token thì phần đó
lấn át — đo được **6,9 giây/câu ở 4-bit so với 5,0 ở bf16**.

### Khuôn nhắc lúc chấm phải là khuôn lúc dạy

**Model đã tinh chỉnh thì KHÔNG nhắc ví dụ.** Bộ chấm bọc câu hỏi đúng như lúc
huấn luyện: lời hệ thống + câu hỏi trần, phần trả lời bắt đầu sau khối `<think>`
rỗng. Chỉ khi chấm model **gốc chưa tinh chỉnh** nó mới dựng khuôn nhắc 12 ví dụ,
vì lúc đó ví dụ là thứ duy nhất nói cho model biết phải làm gì. Cờ `--shots`
không có tác dụng khi có `--adapter`, và báo cáo ghi lại là không dùng.

Vì sao phải viết hẳn ra: lượt chấm 16/8 hỏi adapter bằng khuôn nhắc — khuôn dài
**2.253 token** trong khi khuôn huấn luyện chỉ **61 token**, lại thiếu cả lời hệ
thống lẫn khối `<think>`. Model không câm. Nó trả lời gần đúng, chỉ trượt **đúng
một token** ở cùng một chỗ trong **150 trên 399 câu**, và một token đó đủ để truy
vấn rơi khỏi danh mục — kéo cả ba chỉ số xuống cùng lúc, trông như model kém chứ
không như thước đo hỏng.

Có một phép kiểm so khuôn chấm với khuôn huấn luyện **tới từng token**. Nó cần
model trong cache, không có thì tự bỏ qua.

> **Khi nào nối LLM vào đường phục vụ thì dùng lại đúng lớp sinh đó.** Hôm nay
> đường phục vụ chỉ chạy seq2seq nên chưa dính, nhưng dựng lại khuôn nhắc ở chỗ
> mới là lặp lại đúng lỗi này ngoài production.

> **Gom lô đổi vài dự đoán, và đó là chuyện bình thường.** Phép nhân ma trận theo
> lô cộng dồn theo thứ tự khác lúc chạy một câu, nên chỗ hai token gần ngang điểm
> có thể lật. Đo trên 32 câu validation: **30/32 giống hệt từng ký tự**, hai câu
> lệch đều là câu model đoán bừa và sai ở cả hai đường. Hệ quả thực dụng: **so hai
> lượt chấm thì phải cùng cỡ lô** — vì vậy cỡ lô được ghi vào báo cáo.

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
