# Kế hoạch chuyển đổi sang SPARQL trực tiếp

Các bước được thực hiện theo thứ tự vì mỗi bước tạo contract cho bước sau.
Không mở rộng code QueryPlan trong thời gian chuyển đổi.

## Giai đoạn 1 — Ontology mới

Trạng thái: **hoàn thành với ontology v11**.

1. Tạo phiên bản ontology mới từ `ontology_v10.ttl`.
2. Giữ `content` và toàn bộ dữ liệu có giá trị.
3. Chuyển `Condition`/`Outcome` sang literal `condition`/`outcome`.
4. Xóa wrapper và quan hệ cũ sau khi đối chiếu không mất giá trị.
5. Review URI, `rdfs:label@vi` và `skos:altLabel@vi`.
6. Parse bằng RDFLib, chạy OWL-RL nếu cần và kiểm tra các query mẫu.
7. Sinh báo cáo mapping v10 → phiên bản mới để dataset chuyển đổi có căn cứ.

Hoàn thành khi số liệu trước/sau chứng minh không mất nội dung trả lời và mọi
IRI/property canonical đã được khóa.

## Giai đoạn 2 — Runtime SPARQL tối giản

Trạng thái: **hoàn thành**.

1. Tạo canonicalizer/prefix prologue dùng chung.
2. Validate chỉ `SELECT`, chặn update và `SERVICE`.
3. Thực thi bằng RDFLib.
4. Đổi Literal sang primitive Python.
5. Trả `list[dict[str, primitive]]` và từ chối URIRef/BNode ở projection.
6. Viết renderer chung cho zero row, một cột và nhiều cột.
7. Xóa dependency runtime vào QueryPlan/traversal sau khi test mới đạt.

Hoàn thành khi các query mẫu trong `CONCEPT.md` chạy đúng và code chính không
import kiến trúc cũ.

## Giai đoạn 3 — Tokenizer và trainer

Trạng thái: **hoàn thành và có test tái lập**.

1. Viết script chuẩn bị tokenizer ViT5 theo
   `MODEL_TOKENIZER_SPEC.md`.
2. Thêm manifest và test tái lập.
3. Thống nhất canonical spacing cho target của cả hai model.
4. Thu gọn trainer còn BARTpho và ViT5; dynamic padding, không compile.
5. Chạy smoke train và learning audit trên các query shape đại diện.

Hoàn thành khi cả hai tokenizer round-trip toàn target không `<unk>` và cả hai
model học được tập audit nhỏ.

## Giai đoạn 4 — Chuyển dataset

Trạng thái: **hoàn thành với dataset và benchmark SPARQL v1 tách biệt**.

1. Kiểm kê khoảng 1.000 câu hỏi cũ theo semantic family.
2. Lập mapping target cũ → nhu cầu thông tin mới để hỗ trợ review.
3. Gán target SPARQL theo ontology đã khóa.
4. Review thủ công từng nhóm; bỏ/sửa câu mơ hồ và target sai.
5. Chia lại train/validation theo family.
6. Chạy validator syntax, execution, ontology ID, tokenizer và leakage.

Hoàn thành khi mọi record có target được duyệt và thực thi được. Không đặt số
lượng 1.000 làm release gate.

## Giai đoạn 5 — Benchmark và train chính thức

Trạng thái: **hoàn thành với 2 model × 3 seed**.

1. Xây benchmark SPARQL độc lập, phủ direct data, graph hop, multi-column,
   multi-branch, filter và aggregate.
2. Đóng băng benchmark/manifest sau review.
3. Chọn hyperparameter bằng validation, không dùng benchmark cuối.
4. Train BARTpho và ViT5 với nhiều seed.
5. Báo cáo parse, execution, answer exact, canonical exact, register, shape,
   thời gian và VRAM.
6. Chỉ sau đó tối ưu CTranslate2/deployment nếu cần.

Báo cáo giao thức, kết quả và giới hạn nằm tại
`docs/SPARQL_EXPERIMENT_V1.md`. ViT5 đạt trung bình 78,05% answer exact và
BARTpho đạt 75,00% trên benchmark v1; cả hai đều phù hợp VRAM 6 GB.

## Giai đoạn 6 — Artifact và runtime triển khai

Trạng thái: **hoàn thành và đã smoke test đầu-cuối**.

1. Chọn model/seed bằng validation, không chọn bằng benchmark.
2. Convert checkpoint sang CTranslate2 và ghi manifest checksum.
3. Chấm lại artifact quantized trên benchmark đóng băng.
4. Nối runtime tối giản model → SPARQL → RDFLib → text.
5. Thay API, Docker và web UI còn phụ thuộc kiến trúc cây cũ.

ViT5 seed 42 là artifact mặc định. Hướng dẫn và acceptance metric nằm tại
`docs/DEPLOYMENT.md`.

## Thứ tự dọn code cũ

Trạng thái: **hoàn thành sau khi release SPARQL v1 được khóa**.

Không xóa code/dataset cũ trước khi đã lấy xong câu hỏi và mapping cần thiết.
Sau mỗi giai đoạn, xóa hoặc chuyển lịch sử những thành phần đã có bản thay thế:

1. QueryPlan parser/engine/test;
2. capability catalog và benchmark QueryPlan;
3. trainer/evaluator ba model cũ;
4. artifact hoặc lệnh tài liệu không thể tái lập.

Mỗi lần dọn phải chạy test và kiểm tra Git diff để không xóa thay đổi không
liên quan của người dùng.

## Giai đoạn 7 — Nâng cấp chất lượng dataset v2

Trạng thái: **đã duyệt phương hướng; chưa chỉnh sửa nội dung**.

Không mở lại các giai đoạn chuyển đổi kiến trúc đã hoàn thành. Dataset v1 được
giữ làm baseline; mọi audit, review family, bổ sung coverage, chia test mới và
nghiệm thu hai model cho v2 tuân theo checklist duy nhất tại
`docs/DATASET_UPGRADE_PLAN.md`.

Lượt triển khai kế tiếp chỉ bắt đầu bằng audit read-only v1. Không sửa dataset,
sinh câu hoặc train trước khi báo cáo audit được duyệt.
