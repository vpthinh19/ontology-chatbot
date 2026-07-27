# Kế hoạch nâng cấp dataset SPARQL v2

Trạng thái: **Giai đoạn A–F đã hoàn thành; release v2 đã đóng băng và trở thành
dataset mặc định; dataset v1 không bị sửa**. Kết quả Stage F nằm tại
`reports/dataset_review_v2/stage_f_report.md`.

Tài liệu này là checklist thi công cho đợt nâng cấp chất lượng dữ liệu tiếp
theo. Nó cụ thể hóa contract tại `DATASET_BENCHMARK_SPEC.md`; không thay đổi
kiến trúc đã khóa trong `PROJECT_SPEC.md`.

## 1. Mục tiêu

Tạo release `sparql_v2` có câu hỏi tiếng Việt tự nhiên, target đúng và độ phủ
đủ để so sánh công bằng BARTpho với ViT5. Chất lượng của từng semantic family
quan trọng hơn tổng số record.

Đợt nâng cấp phải giải quyết:

- câu sai nghĩa, mơ hồ, gượng hoặc nhồi nhiều ý không tự nhiên;
- `family_id` gom sai hoặc làm rò paraphrase giữa các split;
- `register` không đúng với cách người dùng thực sự nói;
- target SPARQL đúng cú pháp nhưng không đúng nhu cầu thông tin;
- phân bố chỉ dày ở vài target trong khi thiếu dạng query hoặc dữ liệu khác;
- benchmark quá nhỏ, trùng gần hoặc đã bị dùng để điều chỉnh dữ liệu.

Không đặt mục tiêu phải vượt một số lượng như 1.000. Record không sửa được một
cách chắc chắn phải bị loại; family chỉ được bổ sung khi coverage chứng minh
đang thiếu.

## 2. Những contract không được thay đổi trong giai đoạn này

- Ontology canonical là `resources/ontology/ontology_v12.ttl`. V11 được giữ
  nguyên để tái lập audit Stage A–B.
- Model sinh trực tiếp một câu `SELECT` SPARQL canonical trên một dòng.
- Backend không có QueryPlan, fuzzy matching, traversal riêng hoặc DTO theo
  schema ontology.
- Hai model chính là `vinai/bartpho-syllable` và `VietAI/vit5-base`.
- ViT5 dùng tokenizer đã vá có thể tái lập; BARTpho dùng tokenizer đã pin.
- Dynamic padding, BF16/TF32 và `torch.compile=False`.
- Input lưu trong dataset là câu nguyên bản; normalizer chỉ chạy lúc
  train/inference.
- Release không có field `origin` hoặc `split` trong từng record.
- Schema chung là `id`, `family_id`, `register`, `query_shape`, `input`,
  `target`.
- Object property chỉ nối graph; projection cuối là label, literal hoặc
  aggregate.
- `content` trả hướng dẫn tổng quát; property cụ thể trả nhu cầu cụ thể.

Nếu cần đổi bất kỳ contract nào ở trên, phải dừng nâng cấp, sửa
`PROJECT_SPEC.md`, được duyệt rồi mới tiếp tục.

## 3. Quan hệ giữa v1 và v2

- `sparql_v1` là baseline bất biến, không sửa tại chỗ.
- Công việc mới tạo `resources/datasets/sparql_v2/` khi bắt đầu biên tập.
- Train/val v1 là đầu vào để kiểm kê, không được mặc định là dữ liệu tốt.
- Test v1 đã được dùng trong thí nghiệm và phân tích trước đây, vì vậy không
  dùng điểm test v1 để quyết định giữ, sửa hay bổ sung record v2.
- V2 cần test mới ở cấp semantic family. Test này chỉ được mở để chấm sau khi
  ontology, normalizer, train/val, hyperparameter và checkpoint đã khóa.
- Không chép hoặc paraphrase câu test v1 sang train/val v2.

## 4. Định nghĩa dùng chung

### `family_id`

Một family chứa các cách diễn đạt khác nhau của **cùng nhu cầu thông tin, cùng
ràng buộc và cùng target**. Thay đổi thuộc tính cần hỏi, thực thể, điều kiện
lọc, số nhánh hoặc kết quả mong muốn thì phải là family khác.

Family không phải chủ đề rộng. Ví dụ “nội dung bảo lưu” và “phòng xử lý bảo
lưu” cùng nói về bảo lưu nhưng khác family vì target khác nhau.

### `register`

- `formal`: câu đầy đủ, lịch sự, gần văn bản hành chính;
- `neutral`: câu tự nhiên, rõ, không quá trang trọng;
- `colloquial`: ngôn ngữ nói đời thường nhưng chính tả vẫn hiểu được;
- `noisy`: viết tắt, thiếu dấu hoặc lỗi gõ có chủ ý nhưng vẫn xác định được
  đúng một nhu cầu.

Không tạo noisy bằng cách phá chữ ngẫu nhiên. Một câu không còn đọc chắc nghĩa
thì là dữ liệu hỏng, không phải noisy tốt.

### `query_shape`

Giữ taxonomy nhỏ hiện tại:

- `direct`;
- `graph_hop`;
- `multi_column`;
- `aggregate`;
- `aggregate_filter`.

Đây là metadata phân tích, không phải nhãn model phải sinh. Chỉ mở rộng danh
sách khi xuất hiện cấu trúc SPARQL thật sự không thuộc năm nhóm trên.

## 5. Quy trình thi công

### Giai đoạn A — Khóa baseline và sinh báo cáo kiểm kê

Trạng thái: **hoàn thành** tại `reports/dataset_audit_v1/`.

Chỉ đọc v1, chưa sửa câu hỏi.

1. Xác minh checksum v1 và ontology v11 dùng trong audit lịch sử; các bản sửa
   v2 được thực thi lại trên ontology v12 canonical.
2. Sinh bảng thống kê theo split, family, register, query shape, target, IRI,
   property, độ dài source/target và kích thước family.
3. Liệt kê exact duplicate sau normalizer trên toàn release.
4. Liệt kê near-duplicate làm ứng viên review; thuật toán không được tự xóa
   hoặc tự gộp family.
5. Liệt kê target hiếm, family đơn lẻ, phân bố bất thường và target không có
   đủ biến thể ngôn ngữ.
6. Lập ma trận ontology coverage: thực thể/property nào có thể trả cho người
   dùng, cái nào đã có target và cái nào chưa được hỏi.

Đầu ra bắt buộc:

- một báo cáo máy đọc được để tái chạy;
- một báo cáo Markdown ngắn cho người review;
- danh sách family cần `keep`, `fix`, `drop` hoặc `review`.

Script ở giai đoạn này chỉ đo và phát hiện ứng viên, không sinh câu tiếng Việt
và không quyết định thay con người.

### Giai đoạn B — Review target và ý nghĩa family

Trạng thái: **hoàn thành**. Đủ 401 family đã được review; 28 `fix`, 5 `merge`
và 1 `split` thuộc phạm vi train/val v2 đã được áp dụng vào semantic draft.
164 family test v1 chỉ là audit-only. Bốn mâu thuẫn ontology đã được giải quyết
ở v12; toàn bộ 87 target trong draft đã được thực thi lại và có kết quả.

Thứ tự review của mỗi family:

1. Đọc dữ liệu thật trong ontology.
2. Xác định câu hỏi muốn lấy label, datatype literal hay aggregate nào.
3. Chạy target và đọc kết quả thực tế.
4. Kiểm tra target có trả đúng nhu cầu, không chỉ tình cờ trả cùng một giá trị
   trên ontology nhỏ.
5. Xác nhận mọi record trong family có cùng target và cùng ràng buộc.
6. Đánh dấu quyết định `keep`, `fix`, `split`, `merge` hoặc `drop`, kèm lý do
   trong working report.

Target phải tuân theo toàn bộ quy tắc ở `DATASET_BENCHMARK_SPEC.md`. Không sửa
target sai bằng heuristic runtime.

### Giai đoạn C — Review ngôn ngữ thủ công

Trạng thái: **hoàn thành**. Đã đọc đủ 948 input, viết lại 87, loại 83 và giữ
865 record thuộc 217 family. Review chéo không còn meta-language, filler,
exact/near duplicate, target rỗng hoặc `<unk>` trên hai tokenizer.

Với từng record đã có target đúng:

1. Giữ câu tự nhiên và đúng nghĩa nếu đã tốt.
2. Sửa câu gượng, thừa ngữ cảnh hoặc dùng từ không giống người dùng thật.
3. Giữ các cách nói đời thường như “đóng tiền học sao”, “tui rớt môn rồi, học
   lại sao giờ” khi nhu cầu vẫn rõ.
4. Không để câu hỏi lộ IRI, tên property hoặc cấu trúc SPARQL.
5. Không để normalizer trở thành công cụ cứu câu hỏng.
6. Gán lại register theo định nghĩa ở mục 4.
7. Review riêng câu noisy sau khi chạy normalizer để chắc chắn nghĩa không đổi.

Không dùng template/script/LLM để sinh hàng loạt rồi mặc định đưa vào release.
Công cụ có thể đề xuất hoặc phát hiện lỗi, nhưng từng câu thêm/sửa phải được
đọc và duyệt.

### Giai đoạn D — Bổ sung coverage có mục tiêu

Trạng thái: **hoàn thành**. Đã thêm 71 record có review, tạo 17 family mới và
hoàn thiện family đơn lẻ của Stage C. `coverage_draft.jsonl` hiện có 936 record,
234 family, 102 target và đúng 234 câu cho mỗi register. Ma trận cùng các quyết
định thêm/hoãn nằm tại `reports/dataset_review_v2/stage_d_coverage.json` và
`stage_d_decisions.json`.

Chỉ bổ sung sau khi báo cáo A–C chỉ ra lỗ hổng cụ thể.

Ưu tiên theo thứ tự:

1. nhu cầu người dùng có dữ liệu trong ontology nhưng chưa có target;
2. query shape khó có quá ít family để học và đánh giá;
3. target có dữ liệu nhưng chỉ xuất hiện dưới một kiểu diễn đạt;
4. cách nói colloquial/noisy hợp lý còn thiếu;
5. câu nhiều thuộc tính hoặc nhiều nhánh thực sự hữu ích.

Không cân bằng bằng cách nhân paraphrase máy móc. Aggregate/filter ít nhưng
đúng và đa dạng tốt hơn nhiều câu cùng một khuôn.

### Giai đoạn E — Chia train/val/test ở cấp family

Trạng thái: **hoàn thành**. 234 family được chia thành 164 train, 35 validation
và 35 test bằng thuật toán deterministic seed 42. Mỗi split đủ năm query shape,
không rò family/câu chuẩn hóa và không thiếu ontology term trong train.
Validation/test mỗi tập khóa năm compositional holdout, đúng một target cho mỗi
query shape; các target còn lại đều đã có family độc lập trong train.

1. Chốt toàn bộ family trước khi chia.
2. Dùng một seed cố định và ghi seed vào manifest.
3. Stratify gần đúng theo target/query shape/register khi dữ liệu cho phép;
   không phá family để đạt tỷ lệ đẹp.
4. Bảo đảm mọi family nằm đúng một split.
5. Bảo đảm không có input trùng sau normalizer giữa các split.
6. Review thủ công near-duplicate qua biên split.
7. Train chứa đủ vocabulary/schema cần học; val dùng chọn cấu hình/checkpoint;
   test chỉ dùng báo cáo cuối.

Tỷ lệ cụ thể được chốt sau báo cáo kiểm kê. Mặc định tham khảo là 70/15/15
theo family, nhưng coverage và độ độc lập của test quan trọng hơn tỷ lệ chính
xác.

### Giai đoạn F — Cổng kiểm định release

Trạng thái: **hoàn thành**. Toàn bộ cổng cấu trúc và tokenizer đều đạt;
`manifest.json` đã chuyển từ `stage_e_candidate` sang `frozen`. Audit khóa tại
`reports/dataset_review_v2/stage_f_audit.json`.

Một release chỉ được đóng băng khi đạt tất cả:

- ba file `train.jsonl`, `val.jsonl`, `test.jsonl` có cùng schema;
- ID duy nhất trên toàn release;
- không có family hoặc câu hỏi chuẩn hóa rò giữa split;
- mỗi family có đúng một target;
- input Unicode/khoảng trắng hợp lệ và không rỗng;
- target một dòng, canonical và không bị tokenizer cắt;
- 100% target parse được và chỉ là query đọc;
- mọi IRI/property tồn tại trong ontology canonical;
- 100% target thực thi được và trả kết quả đã review;
- mọi cột kết quả là label, literal hoặc aggregate, không lộ URIRef/BNode;
- BARTpho và ViT5 round-trip toàn bộ unique target, không `<unk>`;
- source sau normalizer nằm trong budget hoặc có quyết định review rõ ràng;
- báo cáo phân bố không có lỗ hổng không được giải thích;
- manifest ghi schema version, ontology checksum, normalizer version, split
  seed, số liệu phân bố và checksum từng file.

Sau khi đóng băng, sửa lỗi dữ liệu bằng release mới; không âm thầm sửa file.

### Giai đoạn G — Nghiệm thu bằng model

1. Chạy tokenizer audit trên toàn bộ unique target.
2. Chạy learning audit nhỏ, phủ đủ năm query shape và các kiểu projection.
3. Cả BARTpho và ViT5 phải học gần hoàn toàn audit nhỏ trước khi train lớn.
4. Chạy một lượt chẩn đoán trên train/val; chỉ dùng val để điều chỉnh.
5. Khóa cấu hình, train chính thức nhiều seed cho cả hai model.
6. Chọn checkpoint bằng val.
7. Chấm test v2 một lần cho báo cáo cuối.
8. Báo cáo parse, execution, answer exact, canonical exact, kết quả theo
   register/query shape, lỗi, thời gian và VRAM.

Không dùng điểm test để quay lại sửa data, normalizer, hyperparameter hoặc
chọn checkpoint trong cùng release.

## 6. Công cụ và môi trường Fedora

Máy tham chiếu tại thời điểm khóa kế hoạch:

- Fedora Linux 44 Workstation, x86_64;
- Bash;
- `uv 0.11.32`;
- Python 3.12.13;
- NVIDIA GeForce RTX 4050 Laptop 6 GB.

Fedora có thể được nâng phiên bản về sau. Mỗi lượt train chính thức phải ghi
lại phiên bản Fedora/kernel, Python, `uv`, NVIDIA driver, CUDA, PyTorch và
Transformers thực tế vào report; không mặc định chúng giống thời điểm viết kế
hoạch.

Tận dụng công cụ Linux sẵn có khi phù hợp:

- `rg`/`rg --files` để tìm kiếm;
- `jq` để kiểm tra và biến đổi JSONL cơ học;
- `sort`, `uniq`, `comm`, `cut`, `wc` để đối chiếu tập hợp và số lượng;
- `sha256sum` để khóa checksum;
- `diff` và Git để review thay đổi;
- `nvidia-smi` để ghi GPU/driver/VRAM;
- `uv` để khóa và chạy môi trường Python;
- RDFLib validator cho kiểm tra SPARQL/ontology có ý nghĩa.

Các phép biến đổi cơ học phải deterministic, chạy lại được và được kiểm tra
Git diff. Không dùng shell để tự động viết câu hỏi tự nhiên. Đường dẫn/script
được phép giả định filesystem Linux phân biệt hoa thường; không cần thêm lớp
tương thích Windows nếu nó làm code phức tạp hơn.

Training tận dụng CUDA, BF16 và TF32. CTranslate2 CPU không được coi là cần
CUDA; chỉ dùng CUDA inference khi phép đo cụ thể yêu cầu.

## 7. Cấu trúc artifact dự kiến

Trong Stage B–D, dữ liệu làm việc chưa được chia split:

```text
resources/datasets/sparql_v2/
├── draft.jsonl
├── language_draft.jsonl
├── coverage_draft.jsonl
└── README.md
```

Sau Stage E, release chính thức mới có dạng:

```text
resources/datasets/sparql_v2/
├── train.jsonl
├── val.jsonl
├── test.jsonl
├── manifest.json
└── README.md
```

Báo cáo làm việc và danh sách review không nằm trong record release. Chúng đặt
dưới một thư mục artifact/report có tên rõ ràng và chỉ commit nếu nhỏ, ổn định,
có giá trị tái lập. File tạm, cache và bản sinh trung gian phải được dọn trước
khi commit.

## 8. Các mốc commit

Mỗi mốc phải có validator/test đạt và không kèm thay đổi ngoài phạm vi:

1. công cụ audit cùng báo cáo baseline v1;
2. rubric review và quyết định theo family;
3. semantic draft đã sửa ngôn ngữ/target;
4. coverage additions đã review;
5. split v2 cùng validator và manifest;
6. learning audit hai model;
7. train/benchmark chính thức và báo cáo.

Không commit artifact model lớn. Không thêm AI vào `Co-authored-by` hoặc metadata
tác giả nghiên cứu.

## 9. Definition of done

Dataset v2 chỉ hoàn thành khi:

1. toàn bộ cổng ở giai đoạn F đạt;
2. mọi family đã có quyết định review rõ ràng;
3. coverage matrix không còn lỗ hổng quan trọng không giải thích;
4. test v2 độc lập và chưa được dùng để tuning;
5. cả hai model vượt learning audit;
6. lệnh tái lập validator, train và benchmark được ghi trong README release;
7. test code đạt, Git diff sạch ngoài thay đổi người dùng đã biết;
8. kết quả chính thức được báo cáo với nhiều seed và giới hạn nghiên cứu.

## 10. Điểm bắt đầu của lượt triển khai kế tiếp

Bắt đầu **Giai đoạn G** bằng learning audit nhỏ trên train/validation v2 cho
BARTpho và ViT5. Chưa chấm test v2 khi đang kiểm tra khả năng học hoặc chọn cấu
hình. Chỉ sau khi cấu hình/checkpoint đã khóa mới train nhiều seed và mở test
một lần cho báo cáo cuối.
