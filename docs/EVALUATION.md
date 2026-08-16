# Đánh giá model sinh SPARQL

Thước v3 nằm trong `src/ontchatbot/research/evaluation.py`. Causal LLM và seq2seq
đi qua **cùng một lệnh chấm**, nên chúng được đo trên cùng chuỗi đầu ra, cùng
catalogue, cùng ontology và cùng ba định nghĩa:

1. **Đúng node** (`node_selection`): model neo vào đúng tập thực thể/bảng mà
   câu chuẩn yêu cầu.
2. **Đúng dạng** (`query_shape`): query khớp đúng họ catalogue; tham số không
   phải node, nếu có, cũng phải đúng. Giá trị IRI dùng để neo được chấm ở chỉ số
   đúng node thay vì tính hai lần trong định nghĩa đúng dạng.
3. **Từ chối đúng** (`rejection_decision`): câu ngoài miền phải sinh đúng marker
   `không có thông tin`; câu trong miền phải sinh một query mà runtime chấp nhận
   (hợp cú pháp và thuộc catalogue).

Không có điểm tổng hợp. Artifact ghi rõ `composite_score: null`. Các số
`answer_exact`, precision/recall/F1 trên tập kết quả và exact string cũ vẫn còn
để chẩn đoán tương thích, nhưng `metric_policy` đánh dấu chúng **không phải chỉ
số chính**.

## Mẫu số và đối soát các split held-out

`coverage_accounting` phân hoạch mọi dòng vào đúng một trong ba nhóm. Hai split
hiện có các mẫu số khác nhau và đều được dẫn xuất trực tiếp từ JSONL:

| Nhóm | Validation | Test | Tiêu chí được chấm |
|---|---:|---:|---|
| Query có node cụ thể | 296 | 287 | đúng node, đúng dạng, từ chối đúng |
| Ngoài miền (`no-information`) | 52 | 50 | từ chối đúng |
| **Tổng đối soát** | **348** | **337** | mọi dòng xuất hiện trong ít nhất một mẫu số |

Chỉ còn HAI nhóm. Nhóm thứ ba - hỏi năng lực - đã bị bỏ khỏi thiết kế ngày
2026-08-14: công cụ chỉ có hai việc là truy ra dữ kiện đã có hoặc nói không có
thông tin, còn việc giới thiệu phạm vi trả lời là của LLM lớn gọi nó.

## “Đúng node” khi SPARQL có nhiều cách viết

Thước không so chuỗi query và cũng không dùng tập kết quả để quyết định đúng
node. Sau khi query qua phép kiểm cú pháp, RDFLib phân tích nó thành cây cú pháp.
Thước thu các IRI ontology xuất hiện tường minh, bỏ predicate và class (đó là từ
vựng của dạng query), rồi so **đúng tập** node còn lại với oracle. Vì vậy các
cách viết sau không làm thay đổi điểm node:

- đổi tên biến;
- đổi thứ tự nhánh;
- neo cùng IRI bằng `BIND`, `VALUES`, hoặc đặt IRI trực tiếp trong triple;
- viết một hay nhiều node bảng trong `VALUES`.

Query sai cú pháp nhận điểm sai, không bị bỏ khỏi mẫu số. Query có đúng node
nhưng viết ngoài shape catalogue có thể đạt “đúng node” và trượt “đúng dạng”;
đây là chủ ý để hai lỗi không bị nhập làm một. Query chỉ dò node gián tiếp bằng
nhãn, không nêu IRI neo, không đạt hợp đồng “chọn node” của kiến trúc và bị tính
sai ở chỉ số này.

## Cùng thước cho causal LLM và seq2seq

Đầu vào của thước chỉ là danh sách record chuẩn và danh sách chuỗi model sinh
ra. Nó không đọc logits, loss, tokenizer hay kiến trúc model. Causal LLM chưa
tinh chỉnh dùng prompt nhắc ví dụ; bản đã tinh chỉnh dùng đúng khuôn đã dạy nó;
seq2seq nhận thẳng câu hỏi. Sau bước generate cả ba giao cùng một chuỗi cho
`evaluate_predictions`.
Vì vậy so sánh ba chỉ số có cùng ý nghĩa khi dùng đúng cùng split. Thời gian,
VRAM, số shot và thông tin checkpoint được ghi riêng, không tham gia điểm.

## Câu người thật — NỘI BỘ, không nằm trong báo cáo này

`resources/cases/user_queries.json` giữ các câu do người thật gõ vào chatbot,
nhãn do chủ dự án tự xác nhận từng câu. Chúng **không thuộc train/val/test** nên
**không xuất hiện trong báo cáo benchmark**: báo cáo chỉ đo trên đúng ba tập của
release hiện hành.

Đo riêng bằng `scripts/danh-gia-noi-bo.py`. Tệp chỉ có oracle
`expected_query_id`, không có target SPARQL/node, nên chỉ báo được
`query_id_accuracy` và từng case.

## Lệnh chạy

Chấm causal LLM:

```bash
uv run benchmark_llm --model Qwen/Qwen3.5-2B --split val --shots 12 --output artifacts/llm-benchmark/qwen-val.json
```

Sinh theo lô 16 câu, tự hạ khi tràn VRAM (`--batch-size`). Nền trọng số gốc mặc
định lấy theo lượt đã huấn luyện adapter, không theo máy đang chạy
(`--base-precision`). Cả hai được ghi vào báo cáo, vì **hai lượt chấm khác cỡ lô
không so được với nhau đến từng câu** — xem `docs/TRAINING.md`.

Chấm checkpoint seq2seq đã có — **cùng lệnh, cùng thước** với LLM:

```bash
uv run benchmark_llm --seq2seq-model artifacts/seq2seq-<mốc>/model --split test --output artifacts/seq2seq-test.json
```

Trước đây mỗi họ model có một bộ chấm riêng, và bộ chấm CTranslate2 còn dùng một
tập benchmark khác hẳn. Ba thước đo ba kiểu thì số của hai họ không đặt cạnh
nhau được, mà đặt cạnh nhau chính là lý do chạy phép so. Nay chỉ còn một đường.

Báo cáo nhóm kết quả theo **giọng nói** (`by_register`), **đặc điểm truy vấn**
(`by_query_feature`), **họ truy vấn** (`by_query_id`), **miền** (`by_domain`) và
**kiểu tên node** (`by_anchor_kind`: `table` hỏi bằng nội dung · `document-part`
hỏi bằng toạ độ · `named` tên mang nghĩa).

Chấm file prediction có sẵn:

```bash
uv run benchmark_sparql --benchmark resources/dataset/val.jsonl --predictions artifacts/val-predictions.jsonl --details --output artifacts/evaluation/val.json
```

Lệnh offline ở trên vẫn chạy toàn bộ validation trước khi chấm. Có thể
smoke-test riêng thước bằng unit test sau (đây không phải kết quả model):

```bash
.venv/bin/python -m pytest tests/research/test_evaluation.py -q
```

## Vùng mù còn lại

- Đúng node chỉ xác nhận IRI neo, không chứng minh mọi nhánh, filter, cột nguồn
  hay thứ tự bảng đều đúng; phần đó thuộc đúng dạng/catalogue và các phép kiểm
  dữ liệu tĩnh.
- Đúng dạng yêu cầu query thuộc catalogue production. Một SPARQL tương đương về
  toán học nhưng ngoài catalogue vẫn sai dạng vì runtime cũng sẽ từ chối nó.
- Tập kết quả bằng nhau có thể che lỗi khi hai query tình cờ trả cùng dữ liệu;
  vì vậy nó chỉ là chẩn đoán. Ngược lại, nó vẫn hữu ích để tìm query đúng
  node/dạng nhưng lỗi thực thi hoặc lấy thiếu dữ liệu.
- Ba chỉ số này đánh giá sinh và truy xuất SPARQL, chưa đo độ trung thành của câu
  trả lời tự nhiên do LLM tổng hợp từ context.
- Câu người thật chỉ có oracle họ truy vấn và mẫu rất nhỏ; chưa đo được đúng
  node, đúng literal, hay độ bền trên phân phối người dùng rộng hơn. Chúng được
  đo riêng và không nằm trong báo cáo này.
- Một query có thể nêu đúng IRI neo nhưng thêm logic vô nghĩa; đúng node vẫn đạt,
  còn đúng dạng sẽ trượt nếu logic đó làm query ra ngoài catalogue.

## Trạng thái metric

Repository chưa công bố metric model v3. Các mẫu số ở trên mô tả hợp đồng chấm
và release hiện hành, không phải kết quả inference. `reports/provenance.json`
đánh dấu cả metric model và deployment là `stale` so với baseline v0.4.1; chỉ
artifact benchmark có fingerprint input hiện hành mới được dùng để công bố số.
