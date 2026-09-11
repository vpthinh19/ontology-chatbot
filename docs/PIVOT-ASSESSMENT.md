# Đánh giá hướng chuyển sang ontology CRUD và tra cứu theo nhãn

*Lập ngày 11/09/2026, dựa trên `resources/ontology/ontology.ttl` tại commit
`04ac51c`. Mọi con số dưới đây được đếm lại bằng script trên đúng tệp đó.*

Hướng mới: bỏ bộ phân loại, checkpoint, dataset huấn luyện và benchmark. Ontology
trở thành cơ sở dữ liệu sửa được (CRUD) qua giao diện quản trị. Engine truy vấn
tách khỏi kho dữ liệu. LLM rút từ khoá, công cụ khớp mờ từ khoá với nhãn và nhãn
phụ của phần tử ontology, rồi đọc dữ kiện bằng SPARQL.

## 1. Kết luận

1. **Bỏ bộ phân loại là đúng, và là điều bắt buộc chứ không chỉ để gọn.** Không
   gian nhãn bị đóng băng lúc huấn luyện. Mỗi lần thêm hoặc sửa một thực thể phải
   sinh lại dataset, huấn luyện lại, xuất ONNX, đẩy lên HF và dựng lại ảnh Docker.
   Cách đó không sống được với CRUD.
2. **Chính dữ liệu cũ cho thấy bộ phân loại vốn chỉ đang tra IRI.** 344 nhãn ứng
   với 340 bộ IRI khác nhau; chỉ 4 IRI phương thức thanh toán thuộc hai họ. 36/50
   họ truy vấn dùng chung một khuôn SPARQL, chỉ khác IRI điền vào. Tra thẳng
   nhãn → IRI là bỏ khâu trung gian, không làm mất khả năng nào.
3. **Khớp mờ hợp với quy mô này, nhưng không dùng được một scorer rapidfuzz
   "trần".** Thử trên 899 chuỗi tên thật (mục 2): mỗi scorer hỏng theo một kiểu,
   và có kiểu hỏng làm hệ thống "khớp" với chủ đề ontology không hề có. Cần một bộ
   khớp nhiều tầng. Tốc độ không phải vấn đề: 1,65 ms/từ khoá với `WRatio`. Tìm
   thêm trên triple đã diễn đạt thành câu (mục 2.3) đưa kết quả lên ngang bộ phân
   loại và bắt được câu hỏi theo giá trị, theo quan hệ.
4. **Về lý do bỏ hybrid search, nên nói là chất lượng chứ không phải chi phí.**
   model2vec là embedding tĩnh, tính rất rẻ. Cái yếu thật là BM25 và embedding tĩnh
   không phân biệt tốt trên nhãn 2-6 từ, thêm phụ thuộc, và phải tái chỉ mục mỗi
   lần CRUD. Trước hội đồng, lập luận này chắc hơn "tốn kém".
5. **Phần việc lớn nhất nằm ở ontology, không nằm ở engine.** Khoảng 1.550/6.350
   bộ ba (≈24%) là dữ liệu dẫn xuất đang được lưu tay. 33% ký tự nguyên văn bị lặp
   giữa Điều và Khoản/Điểm. Chưa có lược đồ ràng buộc để sinh form hay kiểm tra khi
   ghi. Nhiều IRI mang dữ liệu có thể đổi. Sửa tay dữ liệu kiểu này qua CRUD sẽ
   sinh bất nhất ngay (mục 4).

## 2. Thử khớp mờ trên nhãn thật

Tập tên gồm `rdfs:label` và `skos:altLabel` của 685 cá thể, tức 899 chuỗi; so trên
chuỗi đã bỏ dấu. Script: 12 từ khoá điển hình, 3 scorer.

| Từ khoá | Scorer | Kết quả đứng đầu | Kiểu hỏng |
|---|---|---|---|
| `khoản 2 điều 12 quy chế 1052` | `WRatio` | `khoa` → `:FacultyOrInstitute`, điểm 90 | nhãn rất ngắn khớp một phần với mọi câu |
| `thời tiết nha trang` | `WRatio` | 86 với "Thời hạn hiệu lực của học phần…" | không có ngưỡng từ chối sạch |
| `xác nhận sinh viên`, `thẻ sinh viên` | `token_set_ratio` | 100 với `Sinh viên` → `:Student` | chủ đề **chưa có** vẫn được coi là khớp tuyệt đối |
| `học phí` | `token_set_ratio` | 16 kết quả đạt 100, đứng đầu là "Nộp học phí - cách 1/2/3" | từ khoá chung trả về node con vô nghĩa |
| `điểm đ khoản 1 điều 22` | cả hai | điểm d và điểm đ cùng 100 | bỏ dấu gộp `đ` với `d` (4 cặp trùng trong dữ liệu hiện tại) |
| `cntt`, `chuyển khoản` | cả ba | không có đích đúng | thiếu tên gọi khác |
| `bảo lưu` | `ratio` | 64 | scorer chặt thì trượt khi từ khoá là cụm con |

Thiết kế bộ khớp đề xuất, theo thứ tự ưu tiên:

1. **Toạ độ văn bản đi đường riêng.** Regex nhận "điểm/khoản/Điều/Chương/Phụ lục"
   cùng số hiệu văn bản rồi tra có cấu trúc, không khớp mờ. Hiện có 321/563 đích
   trả lời là phần văn bản, nên nhánh này rất lớn.
2. **Chuẩn hoá hai khoá.** NFC, casefold, bung viết tắt (tái dùng
   `runtime/text.py`: `cntt`, `hp`, `đkhp`…). Giữ cả khoá có dấu và khoá bỏ dấu;
   khớp có dấu được điểm cao hơn, để `đ`/`d`, `hoãn`/`hoàn` không hoà nhau.
3. **Khớp chính xác tên hoặc nhãn phụ** được điểm tuyệt đối và đứng trên mọi
   điểm mờ.
4. **Khớp mờ có hướng.** Cho phép tên ứng viên chứa từ khoá; không cho từ khoá
   chứa một tên ứng viên ngắn hơn nhiều (chặn `khoa`, `Sinh viên`). Phạt chênh lệch
   độ dài và tính tỷ lệ token của từ khoá được phủ.
5. **Chỉ đánh chỉ mục "điểm vào".** Gồm thủ tục, biểu mẫu, quy tắc, khái niệm,
   đơn vị, ngành, văn bản, bảng. Bước và điều kiện quy về thủ tục cha; gộp điểm
   theo thực thể (lấy max qua các tên của nó).
6. **Hiệu chỉnh ngưỡng trên một bộ từ khoá có nhãn**, không cần huấn luyện. Có
   thể dựng nhanh vài trăm cặp từ khoá → IRI từ `target` và `short_frames` của
   dataset cũ, giữ làm test hồi quy trước khi xoá dataset.
7. **Ghi lại từ khoá trượt** và hiện nó trong giao diện quản trị để người biên
   soạn thêm `altLabel`. Đây là vòng phản hồi thay cho việc huấn luyện lại, và là
   điểm đáng trình bày trước hội đồng.

### 2.1 Đo trên từ khoá mà LLM thật đã rút

Nguồn: `resources/end-to-end/results.json` lưu 141 từ khoá LLM đã gửi cho 61 câu
có đích; 4 câu LLM không gọi công cụ. Tính "đúng đích" khi node đích nằm trong
kết quả của ít nhất một từ khoá của lượt đó, giống cách README tính cho đường cũ.

| Cách tìm | Đúng đích | Chỉ lấy node khác | Không khớp gì |
|---|---:|---:|---:|
| Bộ phân loại cũ | 48/61 | - | - |
| `WRatio`, top-1, luôn trả kết quả | 42/61 | 15 | 0 |
| `token_set_ratio`, top-1 | 37/61 | 20 | 0 |
| Nguyên mẫu nhiều tầng, ngưỡng 70, top-3 | 48/61 | 7 | 2 |
| Nguyên mẫu nhiều tầng, ngưỡng 80, top-3 | 44/61 | 5 | 8 |
| Nguyên mẫu nhiều tầng, ngưỡng 90, top-3 | 34/61 | 7 | 16 |

Đọc bảng:

- **Scorer trần không an toàn.** Nó luôn trả một kết quả, nên 15-20/61 câu chỉ
  lấy node sai. Nguyên mẫu chưa tinh chỉnh đã ngang đường cũ ở ngưỡng 70.
- **Khi đường cũ lấy sai, LLM thường từ chối chứ không bịa.** 13 câu lấy sai
  hoặc thiếu node: 7 câu vẫn trả lời đúng, 6 câu từ chối, 0 câu sai. Điều kiện là
  công cụ trả kèm tên và loại của node đã khớp, để LLM thấy chỗ lệch.
- **Chủ đề chưa có dữ liệu cho kết quả rỗng** thay vì bị ép vào nhãn gần nhất:
  bảo hiểm y tế, giá ký túc xá, lịch thi, điểm chuẩn, học phí theo ngành. Bộ phân
  loại đóng không làm được việc này.
- **13 câu trượt ở ngưỡng 80:**
  - 8 câu sửa được bằng dữ liệu: nhãn phụ, hoặc tên sinh theo lớp như
    "ngành {tên}", "chứng chỉ tiếng Nga".
  - 2 câu lấy cả Điều thay vì Khoản; vẫn trả lời được.
  - 3 câu cần quan hệ chưa có, hoặc từ khoá không nêu toạ độ.
- **Rủi ro còn lại giống hệ cũ.** Ví dụ `chuẩn đầu ra tiếng Anh` khớp đúng bảng
  nhưng là bảng của chương trình đặc biệt. Phải chặn bằng quan hệ trong dữ liệu
  và quy tắc prompt, không chặn được bằng so chuỗi.
- **Ổn định khi thêm dữ liệu.** Thêm 27 tên biểu mẫu Phòng CTCT&SV: 0/141 từ khoá
  đổi kết quả top-1, không từ khoá nào mất đích.
- **Không ổn định khi sửa luật khớp.** Bản thứ hai thêm hai luật: "từ hiếm nhất
  của từ khoá phải có trong tên" và "độ phủ token một chiều".
  - Vá được 4 lỗi: `thẻ sinh viên` hết khớp nhầm "lớp sinh viên" (87 điểm);
    `hoàn thi` có dấu hết bị coi là "hoãn thi"; `vắng thi` và
    `tỷ trọng điểm ngoại ngữ` tìm đúng.
  - Làm hỏng 1 ca: `nghi hoc tam thoi` từ đúng thành rỗng, vì bước bung viết tắt
    đổi "hoc" thành "học" nên luật dấu đoán sai.

Hệ quả: an toàn và ổn định là thuộc tính của **quy trình**, không phải của thuật
toán.

- Giữ một bộ kiểm hồi quy từ khoá → IRI, gồm cả ca âm như `thẻ sinh viên` → rỗng.
  Bắt đầu từ 141 từ khoá thật ở trên.
- Chạy bộ kiểm mỗi lần đổi luật khớp và mỗi lần quản trị viên công bố ontology;
  không đạt thì không công bố.
- Ưu tiên sửa bằng dữ liệu (nhãn phụ) trước khi thêm luật.

### 2.2 Câu hỏi dạng quan hệ

Khớp mờ chỉ tìm **thực thể**. Quan hệ ("phòng nào xử lý…") được trả lời bằng duyệt
đồ thị **sau khi** tìm được thực thể. Kiểm trên dữ liệu hiện tại:

- **Chiều thuận** ("nghỉ học tạm thời nộp ở đâu"): tìm được thủ tục, nhưng khuôn
  `*-facts` hiện trả `"thuoctinh": "tên gọi", "giatri": "Phòng Công tác Chính trị
  và Sinh viên"`. Tên quan hệ "nộp tại" bị mất; "Hiệu trưởng" (`decidedBy`) cũng
  chỉ còn là "tên gọi". Người thực hiện từng bước cách 3 bước nhảy nên không lấy
  được.
- **Chiều ngược** ("Phòng CTCT&SV xử lý những việc gì"): có 15 cạnh trỏ vào phòng
  này (12 `submittedTo`, 2 `performedBy`, 1 `reviewedBy`), nhưng khuôn chỉ trả
  thông tin liên hệ. Ontology không khai `owl:inverseOf` hay nhãn chiều ngược nào.
- **"Phòng nào xử lý vấn đề X"** trả lời được khi X là tên hoặc nhãn phụ của một
  thủ tục. Nếu X chỉ nằm trong nguyên văn (`stepText`, `officialText`) thì nhãn
  không tìm ra. Khi đó cần thêm nhãn phụ, hoặc một tầng tìm toàn văn tuỳ chọn trên
  các trường chữ dài (nơi BM25 làm tốt, khác với nhãn ngắn).
- **Câu lọc hoặc tổng hợp nhiều thực thể** không có neo ("thủ tục nào không cần
  biểu mẫu") nằm ngoài cách này.

Việc cần làm cho truy vấn mô tả thay khuôn `*-facts`:

- Trả bộ (tên quan hệ, tên đích, loại đích) cho cả chiều đi lẫn chiều về.
- Đi sâu vào bước, điều kiện và người thực hiện.
- Khai nhãn chiều ngược cho từng quan hệ (ví dụ `submittedTo`: "nộp tại" /
  "tiếp nhận hồ sơ của").
- Thêm cạnh còn thiếu, như ngành → loại chương trình → bảng chuẩn đầu ra.

### 2.3 Tìm trên triple, không chỉ trên tên

Đề xuất của nhóm: đánh chỉ mục cả nhãn cá thể lẫn triple. Triple object property
và datatype property được diễn đạt thành câu bằng nhãn quan hệ, ví dụ "Thôi học
nộp tại Phòng Công tác Chính trị và Sinh viên" hay "Khối lượng đăng ký của sinh
viên học lực yếu kém số tín chỉ tối đa 18".

Thí nghiệm có:
- 693 tên;
- 654 câu triple ngắn: bỏ `basedOn`/`inDocument`/`partOf`, URL, số thứ tự, trích
  dẫn;
- thêm 336 câu nguyên văn Điều/bảng ở biến thể D.

Ngoài 141 từ khoá thật, có 16 câu thăm dò tự soạn (đích lấy bằng SPARQL; bộ này
do người đánh giá soạn nên có thiên lệch, chỉ để minh hoạ):
- 8 câu hỏi theo **giá trị** (số tín chỉ tối đa, email phòng, phí nộp ngoại tỉnh…);
- 8 câu hỏi theo **quan hệ** (thủ tục nộp tại phòng X, ai quyết định Y…). Tính
  riêng "đáp án" (thực thể trả lời) và "neo" (thực thể được nêu, từ đó duyệt đồ
  thị ra đáp án).

| Biến thể | 61 câu có đích: đúng / chỉ node khác / rỗng | Từ khoá phải từ chối có khớp | Câu giá trị | Câu quan hệ: đáp án / neo | ms/từ khoá |
|---|---|---:|---:|---:|---:|
| A. chỉ tên | 44 / 5 / 8 | 24/48 | 3/8 | 0/8 / 0/8 | 3,6 |
| B. tên + triple, chấm fuzzy ký tự | 45 / 4 / 8 | 24/48 | 3/8 | 0/8 / 1/8 | 40,9 |
| C. tên (fuzzy) + triple (độ phủ từ theo độ hiếm) | **48 / 7 / 2** | 25/48 | **7/8** | 2/8 / 3/8 | 3,9 |
| D. như C + nguyên văn Điều/bảng | 48 / 9 / 0 | 35/48 | 7/8 | 3/8 / 4/8 | 4,3 |

Đọc bảng:

- **Hướng tìm trên triple đúng.** C lên ngang bộ phân loại (48/61) chỉ với 2 câu
  rỗng. Câu hỏi theo giá trị từ 3/8 lên 7/8. Chỉ tên thì không tìm được "số tín chỉ
  tối đa" hay "email phòng công tác sinh viên", vì các từ đó nằm trong triple chứ
  không nằm trong tên.
- **Triple phải chấm theo từ, không theo ký tự.** Fuzzy ký tự trên câu triple (B)
  không tăng chất lượng mà chậm hơn 10 lần. Câu triple dài, nên đây là chỗ đúng
  cho kiểu chấm từ khoá có trọng số (họ BM25). Nhãn ngắn thì vẫn dùng fuzzy.
- **Không trộn nguyên văn dài vào cùng chỉ mục.** D không bao giờ rỗng, và từ khoá
  của câu phải từ chối khớp 35/48 thay vì 25/48. Nếu cần, để nguyên văn thành tầng
  dự phòng riêng, chỉ chạy khi hai tầng trên rỗng, và gắn cờ "khớp trong nguyên
  văn".
- **Nhiễu từ nút trung tâm.**
  - Trong C, từ khoá `sinh viên` khớp 65 thực thể (A: 8), `học phí` khớp 18 (A: 3).
  - `:Student` đứng thứ hai cho `học phí`, vì "Nộp học phí do ai thực hiện Sinh
    viên" cộng điểm cho cả hai đầu.

  Luật cần có: chỉ cộng điểm cho đầu mút có tên thực sự bị từ khoá phủ.
- **5/8 câu quan hệ vẫn trượt vì lệch từ vựng**, không phải vì cách tìm: từ khoá
  dùng "thủ tục", "dùng", "duyệt", "tiếp nhận", còn câu triple dùng "cần biểu mẫu",
  "nộp tại" và đã bỏ chữ "Thủ tục" khỏi tên. Cách sửa nằm ở dữ liệu:
  - thêm `skos:altLabel` cho **thuộc tính** (ví dụ `submittedTo`: "nộp ở đâu",
    "nơi tiếp nhận"; `decidedBy`: "ai ký", "ai duyệt"; `requiresForm`: "dùng mẫu
    nào");
  - đưa nhãn lớp vào câu triple.

Cách làm đề xuất:

1. Tầng tên chấm fuzzy; tầng triple chấm độ phủ từ; gộp điểm theo thực thể, điểm
   khớp tên nhỉnh hơn.
2. Trả cho LLM cả **triple đã khớp** (làm bằng chứng) lẫn **mô tả hai chiều** của
   thực thể neo.

Tìm theo triple là cửa vào; duyệt đồ thị hai chiều, nhiều bước, kèm `basedOn` là
thứ tạo ra câu trả lời. Cả hai cùng thể hiện sức mạnh của ontology.

### 2.4 Có nên dùng bm25s và model2vec?

Kho tài nguyên theo cấu trúc nhóm đề xuất, một dòng mỗi mục:

- `<nhãn cá thể>` (kể cả nhãn phụ)
- `<nhãn cá thể> | <nhãn thuộc tính dữ liệu>`, biến thể thứ hai có thêm `| <giá trị>`
- `<nhãn cá thể> | <nhãn quan hệ> | <nhãn cá thể>`

Kho có 1.213 dòng (thêm giá trị: 1.238). Mọi phương pháp dùng chung tầng toạ độ
văn bản và luật chỉ cộng điểm cho đầu mút được từ khoá nhắc tới.

Ngoài 61 câu với từ khoá thật, có hai bộ tự soạn (thiên lệch, nhỏ, chỉ để minh
hoạ):
- 14 câu **diễn đạt khác chữ**, như "rớt môn thì phải làm gì" ↔ học lại, "email" ↔
  "hộp thư";
- 20 từ khoá về **chủ đề ontology không có**: bảo hiểm y tế, ký túc xá, thẻ sinh
  viên, thời tiết… Phương pháp an toàn phải trả rỗng.

Kết quả trên kho có giá trị literal:

| Phương pháp | 61 câu: đúng / sai / rỗng | Diễn đạt khác chữ | Chủ đề vắng mặt vẫn khớp | ms/từ khoá |
|---|---|---:|---:|---:|
| M1 fuzzy tên + độ phủ từ | 49 / 6 / 2 | 4/14 | 1/20 | 8,0 |
| M2 bm25s, chặn độ phủ từ ≥ 0,8 | 48 / 7 / 2 | 3/14 | 1/20 | 0,9 |
| M3 model2vec, cos ≥ 0,6 | 50 / 7 / 0 | 10/14 | **10/20** | 2,5 |
| M3 model2vec, cos ≥ 0,7 | 47 / 5 / 5 | 8/14 | 3/20 | 2,5 |
| M4 hybrid bm25s + model2vec gộp RRF | 51 / 6 / 0 | 13/14 | **20/20** | 5,2 |
| M5 M1, rỗng thì model2vec cos ≥ 0,75 | 49 / 8 / 0 | 7/14 | 3/20 | 8,7 |

Chi phí model2vec (`potion-multilingual-128M`): model 507 MB trên đĩa, nạp 1,9 s,
đỉnh RAM tăng khoảng 1,7 GB lúc nạp (đo bằng `ru_maxrss`). Dựng chỉ mục cho cả kho
chỉ tốn 61 ms với model2vec và 26 ms với bm25s, nên cả hai đều theo kịp CRUD.

Đọc bảng:

- **Với từ khoá LLM thật, ngữ nghĩa gần như không giúp:** 47-51/61, chênh nhau vài
  câu. LLM đã rút từ khoá sát từ vựng của dữ liệu. Không có giá trị literal thì kết
  quả tương tự (M1 48/4/5, M3 50/7/0).
- **Embedding thắng rõ khi người hỏi dùng từ khác dữ liệu** (8-13/14 so với
  1-4/14), nhưng phải trả giá bằng khả năng từ chối:
  - RRF chỉ gộp theo thứ hạng nên mất điểm tuyệt đối. Nó khớp 20/20 chủ đề vắng
    mặt, ví dụ "bảo hiểm y tế sinh viên" → `:Student`, "giá phòng ký túc xá" →
    `:FinalAssessment`, "lịch thi học kỳ 1" → thủ tục hoãn thi.
  - Ngưỡng cosine 0,6 vẫn khớp 10/20; nâng lên 0,7 thì hết lợi thế với từ khoá thật.
- **bm25s và độ phủ từ cho kết quả tương đương**, nhưng bm25s nhanh gấp khoảng 10
  lần. Điểm BM25 không có mốc tuyệt đối, nên vẫn cần chặn bằng độ phủ từ để còn
  trả "không có thông tin".
- **Thêm giá trị literal vào dòng** giảm số câu rỗng (5 → 2 ở M1) mà không tăng
  khớp nhầm.

Khuyến nghị:

1. **Dùng bm25s** cho kho dòng triple, chặn bằng độ phủ từ có trọng số độ hiếm.
   Giữ rapidfuzz cho tên (lỗi gõ, bỏ dấu). Dòng dữ liệu nên kèm giá trị literal
   ngắn; nguyên văn dài để ngoài.
2. **Không đưa model2vec vào đường trả lời chính.** Nó không tăng chất lượng với
   từ khoá thật, làm hỏng khả năng từ chối, và thêm khoảng 0,5 GB ảnh cùng 1,7 GB
   RAM trên Cloud Run.
3. **Không gộp bằng RRF** ở bước quyết định. Nếu gộp thì gộp điểm đã qua ngưỡng,
   không gộp thứ hạng.
4. **Nếu muốn khai thác ngữ nghĩa, dùng ở chỗ có người duyệt.** Trong giao diện
   quản trị, model2vec gợi ý thực thể gần nghĩa cho các từ khoá trượt đã ghi log,
   quản trị viên bấm chấp nhận để thêm `altLabel`. Chatbot vẫn chạy thuần từ vựng
   và dữ liệu vẫn là nguồn duy nhất.
5. **Phương án dự phòng:** M5 chỉ gọi model2vec khi hai tầng từ vựng rỗng, và gắn
   kết quả là "gợi ý, cần hỏi lại người dùng". Chỉ bật khi log cho thấy nhiều câu
   trượt vì diễn đạt khác chữ.

### 2.5 Hình dạng công cụ

Hình dạng công cụ cho LLM: giữ **một** công cụ như hiện nay. Với mỗi từ khoá, trả
dữ kiện đầy đủ của tối đa 2-3 thực thể trên ngưỡng. Khi điểm các ứng viên sát
nhau, thêm danh sách `ung_vien_khac` (nhãn + loại) để LLM hỏi lại người dùng. Tách
thành hai công cụ `tim` → `xem` chính xác hơn nhưng thêm một vòng gọi LLM (≈1-2 s),
nên chỉ nên làm khi đo thấy cần.

## 3. Kiến trúc đề xuất

Đã chốt ngày 11/09/2026: ontology lưu trên **Google Cloud Storage**, **chỉ quản trị
viên** được sửa.

```text
Giao diện quản trị ─► API quản trị ─ nạp → sửa → kiểm → ghi (ifGenerationMatch) ─► GCS: ontology.ttl
                                                                                    │ (object versioning)
Web chat ─► API chat ─► LLM ─► công cụ tra cứu ─► rdflib Graph trong bộ nhớ ◄─ nạp lại khi generation đổi
                                                  + chỉ mục tên và triple
```

- **Kho dữ liệu là một object trên GCS**, tách khỏi engine truy vấn.
  - Bật object versioning để có lịch sử và khôi phục miễn phí.
  - Số `generation` của object chính là version của ontology.
  - Quản trị viên ghi với điều kiện `ifGenerationMatch`: hai tab cùng sửa thì một
    tab bị từ chối thay vì âm thầm đè.
  - Mỗi instance dịch vụ chat hỏi `generation` theo chu kỳ (chỉ đọc metadata),
    thấy đổi thì dựng Graph mới, dựng lại chỉ mục, rồi mới thay tham chiếu cũ.
    Nạp toàn bộ ontology hiện tại bằng rdflib mất khoảng 130 ms.
  - Không cần triplestore chạy thường trực. Không nên chuyển sang CSDL quan hệ:
    làm vậy mất chính đóng góp ontology, và các quan hệ như `basedOn`, `partOf`
    vốn là duyệt đồ thị.
- **Thư viện là rdflib (đã chốt),** cho cả dịch vụ chat lẫn API quản trị: một API
  cho duyệt triple, SPARQL, cập nhật, ghi Turtle đã sắp xếp và pySHACL. Kho lưu phía
  dưới nên để đổi được bằng cấu hình. Đo trên ontology hiện tại:

  | Việc | rdflib, kho mặc định | rdflib + `oxrdflib` (`Graph(store="Oxigraph")`) |
  |---|---:|---:|
  | `import rdflib` | 58 ms | 59 ms |
  | Nạp tệp Turtle | 132 ms | 208 ms |
  | Truy vấn SPARQL đầu tiên (dựng bộ phân tích) | 72 ms | ≈0 ms |
  | Truy vấn đơn (bước của một thủ tục) | 1,46 ms | 0,089 ms |
  | Mô tả hai chiều một thực thể (26 dòng) | 16,6 ms | 0,52 ms |
  | Thêm + xoá một triple | 0,06 ms | 0,07 ms |
  | Ghi lại toàn bộ thành Turtle | 97 ms | 171 ms |

  - **Quy mô hiện tại:** kho mặc định đủ nhanh. Một lượt tra cứu vài từ khoá tốn
    cỡ 50 ms truy vấn, nhỏ so với 2-3 s chờ LLM.
  - **Khi dữ liệu tăng:** engine SPARQL của rdflib viết bằng Python thuần nên chậm
    đi trước. Lúc đó chuyển sang `Graph(store="Oxigraph")` qua `oxrdflib` (đã có
    trong dependency của dự án): giữ nguyên API rdflib, truy vấn mô tả nhanh hơn
    khoảng 30 lần. Vì vậy mọi mã chỉ nên gọi API rdflib, không gọi thẳng API riêng
    của kho nào.
  - **pySHACL** chạy trên rdflib, dùng ở bước kiểm trước khi công bố của API quản
    trị.
- **Chú thích sẽ mất.** Không thư viện nào giữ 356 dòng chú thích `#` hiện có.
  Trước lần ghi đầu tiên, chuyển những chú thích mang tri thức vào `rdfs:comment`
  hoặc `docs/ONTOLOGY.md`. Từ đó `ontology.ttl` là tệp sinh ra, không sửa tay.
- **Dữ liệu dẫn xuất sinh lúc nạp.** Gồm nhãn toạ độ, trích dẫn,
  `sourceCitation`/`sourceLink`, `inDocument`. Chúng không lưu trong tệp trên GCS,
  nên không cần named graph trong tệp. Runtime hiện đã làm việc này trong
  `_add_source_projection`; chỉ cần mở rộng.
- **Form sinh từ shape.** Dùng tập con SHACL: `sh:targetClass`, `sh:path`,
  `sh:datatype`, `sh:class`, `sh:minCount`, `sh:maxCount`, `sh:name`, `sh:order`,
  `sh:group`. Cùng một tệp vừa kiểm dữ liệu khi ghi (pySHACL, chỉ phía quản trị)
  vừa cho giao diện biết mỗi lớp có trường nào. Có thể sinh bản đầu tự động từ hồ
  sơ thuộc tính theo lớp (mục 4.D).
- **Phiên bản và kiểm vết.**
  - Khai `owl:Ontology` kèm `owl:versionInfo`; tăng version sau mỗi lần công bố.
  - Mỗi thực thể có `dcterms:modified` và trạng thái `draft`/`published`.
  - Nhật ký thay đổi chỉ ghi thêm: ai, lúc nào, diff, bằng chứng.
  - Xuất snapshot Turtle vào git ở mỗi lần công bố.

  Kết quả deep research đi vào trạng thái `draft`, chờ người duyệt.
- **Chỉ mục tên và triple** là cấu trúc trong bộ nhớ (vài nghìn câu ngắn), dựng
  lại mỗi lần nạp lại ontology.

## 4. Kiểm tra cấu trúc ontology cho CRUD

### 4.A Dữ liệu dẫn xuất đang lưu tay

| Dữ liệu | Số bộ ba | Suy ra từ đâu | Rủi ro khi CRUD |
|---|---:|---|---|
| `documentUrl` trên phần văn bản | 336/337 trùng URL tài liệu | `inDocument` của phần | đổi URL tài liệu phải sửa 336 chỗ |
| `inDocument` | 293 suy được từ chuỗi `partOf`, 0 mâu thuẫn | đi `partOf` tới gốc | chuyển một khoản sang điều khác dễ quên sửa |
| `articleNumber`, `clauseNumber` trên Khoản/Điểm | 330, chép y từ cha | toạ độ của cha | đánh số lại một Điều phải sửa mọi con |
| `rdfs:label` của Khoản/Điểm | 222/222 đúng khuôn "điểm x khoản y Điều z …" | toạ độ + tên tài liệu | người nhập phải gõ tay chuỗi dài |
| `citationLabel` | 354 | toạ độ + số hiệu/ngày văn bản | như trên |
| `rdf:type` lớp cha lặp lại | 19 (Certificate kèm lớp con) | `rdfs:subClassOf` | thừa |

Đề xuất: xoá khỏi tệp lưu trên GCS và sinh lại mỗi lần nạp (mục 3). Chỉ mục nhãn
dựng sau bước sinh, nên tra cứu không bị ảnh hưởng.

### 4.B Nguyên văn lặp giữa cấp cha và cấp con

Cả 222 Khoản/Điểm đều có `officialText` nằm nguyên văn trong `officialText` của
cấp cha: 58.917/176.547 ký tự (33%) bị lưu hai lần. Sửa một khoản mà quên sửa Điều
là có hai phiên bản mâu thuẫn. Đề xuất: chỉ lưu nguyên văn ở cấp lá, thêm
`leadText` cho phần mở đầu của Điều; nguyên văn cả Điều được ghép khi nạp.

Bảng đang có cả `officialText` phẳng lẫn `verbatimTableText`. Bản phẳng vốn đã bị
loại khỏi inventory, nên bỏ hẳn.

### 4.C IRI mang dữ liệu

- 449/685 IRI chứa số: toạ độ văn bản, thứ tự, số hiệu.
- Cả 48/48 bước lưu thứ tự **ba lần**: trong IRI (`…Step01`), trong nhãn
  ("Liên thông - bước 1") và trong `stepOrder`. Chèn một bước vào giữa buộc phải
  đổi IRI và nhãn của các bước sau.

Đề xuất:

- **Thực thể mới:** IRI mờ do hệ thống sinh (tiền tố lớp + mã ngắn); nghĩa nằm ở
  nhãn, thứ tự chỉ nằm ở `stepOrder`/`requirementOrder`.
- **Thực thể hiện có:** không đổi tên hàng loạt. IRI toạ độ văn bản
  (`Regulation1052Article24Clause01`) là khoá tự nhiên, không đổi trong một phiên
  bản văn bản, nên giữ được.

### 4.D Lược đồ chưa đủ để sinh form và kiểm tra

- Không có khai báo `owl:Ontology`, nên không có định danh phiên bản.
- 27/84 thuộc tính thiếu `rdfs:domain`, trong đó có `basedOn`, `submittedTo`,
  `summaryText`, `hasRequirement`. Không có ràng buộc số lượng.
- `sourceCitation`/`sourceLink` được khai nhưng chỉ sinh lúc chạy.

Hồ sơ thuộc tính theo lớp cho thấy dữ liệu thực tế đã khá đều, đủ để sinh shape
đầu tiên. Ví dụ:

- `AcademicProcedure` (24/24 có): `basedOn`, `hasStep`, `summaryText`, nhãn,
  nhãn phụ.
- Tuỳ chọn: `hasRequirement` 19, `requiresForm` 16, `submittedTo` 15,
  `hasOutcome` 11, `hasDeadline` 9, `decidedBy` 9.

### 4.E Nhãn — thứ quyết định chất lượng tra cứu

**Tiền tố kỹ thuật trong nhãn** kéo điểm khớp và làm nhãn hiển thị xấu:

- `Mục tải:` ở 18 nhãn;
- `Thủ tục ` ở 24 nhãn;
- 48 nhãn bước dạng "… - bước n" hoặc "… - cách n".

Loại thông tin này thuộc về lớp, không thuộc về tên.

**Nhãn phụ** là cách duy nhất để khớp mờ bắc cầu được đồng nghĩa, nhưng đang phủ
rất lệch:

| Lớp | Có `altLabel` | Ví dụ tên gọi thiếu |
|---|---:|---|
| AcademicProcedure | 24/24 | - |
| AcademicProgram | 0/41 | CNTT, QTKD, kế toán kiểm toán |
| FormDocument | 0/16 | "đơn nghỉ học tạm thời", "mẫu 09" |
| FormCatalogueEntry | 1/18 | tên không có tiền tố |
| Certificate | 3/18 | "tiếng Anh B1", "chứng chỉ tin học quốc tế" |
| PaymentMethod | 0/4 | "chuyển khoản", "quét mã" |
| Deadline, Outcome, quy tắc | gần như 0 | "hạn rút môn", "bị cảnh báo học vụ" |

Giao diện CRUD nên đặt ô `altLabel` ngay cạnh nhãn chính và hiện các từ khoá trượt
liên quan (mục 2, bước 7).

### 4.F Kiểu dữ liệu không đồng nhất

- `downloadUrl` là `xsd:string` trong khi `documentUrl`, `webPageUrl` là
  `xsd:anyURI`.
- `officeLocation` lẫn chuỗi thường với `@vi`.
- `effectiveFromAcademicYear` là chữ ("2025-2026"), không so sánh được.
- `documentNumber` là `langString`.

Shape nên chốt một kiểu cho mỗi thuộc tính.

### 4.G Lớp quá vụn

21 lớp chỉ có 1-3 cá thể; 3 lớp không có cá thể nào (`OfficialDocument` và
`DocumentPart` là lớp cha trừu tượng, `ThresholdBand` không dùng). So tập thuộc
tính mà cá thể thực sự dùng (ngoài loại, nhãn, `basedOn`), 16 lớp rơi vào 4 nhóm
có hình dạng **giống hệt nhau**:

| Nhóm | Lớp | Thuộc tính riêng |
|---|---|---|
| Định nghĩa | `AcademicConcept` (7), `CourseType` (9), `AssessmentComponent` (2), `DeliveryMode` (2), `SemesterType` (2), `TrainingMode` (2) | chỉ `definitionText` |
| Quy tắc chữ | `DismissalRule` (2), `AcademicWarningRule` (3), `AcademicRule` (1) | chỉ `ruleText` |
| Quy tắc có trần % | `GraduationHonoursPenaltyRule` (2), `OnlineTrainingRule` (1) | `ruleText`, `maximumPercentage` |
| Danh mục | `Bank` (3), `EducationLevel` (1), `DisciplineGroup` (4), `BillingUnit` (1), `ComputerCertificate` (3) | không có |

Bốn lớp quy tắc còn lại chỉ thêm 1-2 trường số tuỳ chọn.

Về độ rõ: mức **khái niệm** đã rõ, mức **ràng buộc** chưa chặt.

- Rõ: 0 blank node; 685/685 cá thể có nhãn; 0 vi phạm `rdfs:range`; chỉ 2 vi phạm
  `rdfs:domain` (`citationLabel` dùng trên văn bản dù khai cho phần văn bản;
  `title` dùng trên một Điều); quan hệ đều có nhãn tiếng Việt; hai tầng tách bạch.
- Chưa chặt: xem 4.A-4.D.

Khuyến nghị:

- Gộp 6 lớp định nghĩa thành `AcademicConcept` kèm `conceptType`.
- Gộp 9 lớp quy tắc thành `AcademicRule` kèm `ruleType` và các trường số tuỳ chọn.
- Giữ các lớp danh mục, nhưng giao diện quản trị xử lý chung dạng "danh mục" (nhãn
  + nhãn phụ).
- Bỏ `ThresholdBand`.

Kết quả là khoảng 56 → 42 lớp. `conceptType` và `ruleType` là khái niệm SKOS nằm
trong dữ liệu, nên quản trị viên thêm được loại mới qua CRUD mà không phải sửa lược
đồ; phân loại cũ vẫn giữ nguyên dưới dạng dữ liệu. Nên làm ngay, vì catalogue — thứ
duy nhất phụ thuộc tên các lớp này — sắp bị xoá.

### 4.H Chưa có mô hình hiệu lực

- Chỉ có 1 quan hệ `amends` và 4 `minimumCohortNumber`.
- `effectiveFromAcademicYear` là chữ, không so sánh được.
- Học phí theo khoá trong QĐ729 ("áp dụng từ khóa 63/65/66/67 trở về sau") hiện
  không biểu diễn được.
- Thông báo theo học kỳ (hạn đóng học phí, hạn nộp hồ sơ miễn giảm) sẽ đổ vào
  nhiều.

Đề xuất thuộc tính chung: `validFrom`, `validUntil`, `appliesFromCohort`,
`appliesToCohort`, `status` (`current`/`historical`/`temporary`) và
`supersededBy`.

### 4.I Literal lặp nên tách thành thực thể dùng chung

- Địa chỉ "02 Nguyễn Đình Chiểu…" lặp ở 3 đơn vị.
- Cùng một `assessmentText` lặp ở 5 học phần ngoại ngữ.
- `criterionText` lặp ở 3 mức học bổng mỗi chương trình.

### 4.J Thứ tự chuyển đổi đề xuất

1. Thêm `owl:Ontology`/version; sinh shape từ hồ sơ thuộc tính; chạy kiểm shape
   trên dữ liệu hiện tại.
2. Viết bước sinh dữ liệu dẫn xuất lúc nạp, rồi xoá dữ liệu dẫn xuất khỏi tệp
   (4.A, 4.B). Kiểm lại bằng cách so kết quả SPARQL trước và sau.
3. Chuyển chú thích `#` mang tri thức vào `rdfs:comment` hoặc tài liệu; từ đây tệp
   do chương trình ghi, không sửa tay.
4. Gộp lớp (4.G) nếu được xác nhận; làm sạch nhãn, bổ sung nhãn phụ (4.E).
5. Áp chính sách IRI cho thực thể mới; thêm mô hình hiệu lực (4.C, 4.H).
6. Mới đến nhập dữ liệu từ deep research.

## 5. Khoảng trống dữ liệu

### 5.1 Nhập được ngay, không cần deep research

- **Mức học phí theo khối ngành, nhóm ngành và khoá** — Phụ lục I QĐ729, đã có
  trong `references/Qd729.md`. Ontology mới mô hình hoá Phụ lục II (danh mục
  ngành). Đây đúng là thứ người dùng thật đã hỏi ("hc phí k65 cntt", "học phí
  k67").
- **Quy trình thu học phí** — QĐ1314 (`references/Qd1314.md`, bản OCR, cần đối
  chiếu PDF). Có bước lập danh sách người học chưa hoàn thành nghĩa vụ và bước
  xoá học phần đã đăng ký.
- **QĐ1618/QĐ1619** chỉ được lấy phần căn cứ và tiêu chí. Hai văn bản có danh
  sách sinh viên, **không được nhập phần đó**.

### 5.2 Tín hiệu nhu cầu đã có trong repo

- 10 câu "đồ thị không có" của phép đo toàn hệ thống:
  - chuẩn tiếng Anh đầu ra theo ngành;
  - học phí theo ngành;
  - tín chỉ toàn khoá;
  - giá ký túc xá;
  - giờ làm việc của phòng;
  - lịch thi;
  - miễn học phần tiếng Anh;
  - mức học bổng theo ngành.
- Khuôn từ chối `adjacent-domain`: ký túc xá, cấp lại thẻ sinh viên, bảo hiểm y
  tế, giờ mở cửa thư viện, việc làm, học bổng tân sinh viên.

### 5.3 Có trên trang chính thức nhưng ontology chưa có

- Trang
  [biểu mẫu Phòng CTCT&SV](https://phongctsv.ntu.edu.vn/van-ban-bieu-mau/bieu-mau)
  có 27 mục. Gần như chưa mục nào có trong ontology:
  - xác nhận đang học; xác nhận để hưởng ưu đãi;
  - vay vốn; giấy giới thiệu;
  - miễn giảm học phí theo NĐ 238/2025; hỗ trợ chi phí học tập; trợ cấp xã hội;
    chính sách cho sinh viên khuyết tật và dân tộc thiểu số;
  - gia hạn đóng học phí;
  - phiếu đánh giá điểm rèn luyện; bản tường trình;
  - xác nhận hộ khẩu; xác nhận hoàn cảnh khó khăn.

  Trang còn có bộ đơn "2026" (chuyển trường, chuyển ngành, nghỉ học tạm thời,
  thôi học…), đánh số khác Phụ lục QĐ1052.
- [Văn bản pháp quy Phòng Đào tạo](https://pdtdaihoc.ntu.edu.vn/van-ban-phap-quy)
  có các văn bản chưa mô hình hoá:
  - QĐ 244 (20/02/2025), sửa đổi quy định đào tạo ngoại ngữ;
  - QĐ 782 (12/07/2023), quy định thực tập;
  - QĐ 1286 (02/12/2021), hướng dẫn công tác tốt nghiệp;
  - QĐ 1889 (09/12/2025), trao đổi sinh viên trong nước;
  - TB 94 (27/01/2026), điều chỉnh tổ chức thực hiện đào tạo.
- Ngay trong ontology có mục tải nhưng không có thủ tục đi kèm:
  - "Phiếu điều chỉnh điểm";
  - "Phiếu báo điểm bổ sung";
  - "Đơn xin bảo lưu học phần";
  - "Đơn xin chuyển học phần thay thế trong CTĐT";
  - "Đơn xin cấp bản sao bằng".
- Đơn vị: chỉ 3 đơn vị cụ thể có liên hệ. Phòng Kế hoạch - Tài chính, Phòng CNTT,
  Trung tâm Phục vụ trường học (ký túc xá), thư viện, Trung tâm Hỗ trợ việc làm và
  Khởi nghiệp, các khoa/viện đều chưa có. Chưa đơn vị nào có giờ làm việc.
- Ngành: 41 ngành chỉ có tên và khối ngành; chưa có mã ngành, khoa quản lý, số tín
  chỉ, thời gian đào tạo.

Các chủ đề cần vét bằng deep research và prompt tương ứng nằm tại
[`ONTOLOGY-DEEP-RESEARCH-PROMPT.md`](ONTOLOGY-DEEP-RESEARCH-PROMPT.md).

## 6. Giữ và bỏ khi refactor

| Giữ | Bỏ |
|---|---|
| vòng `AgentLoop`, client LLM, API SSE, `TurnGate` | `runtime/classifier.py`, `onnx_classifier.py`, `cards.py`, `generator.py`, cache phân loại |
| hợp đồng JSON gom theo nguồn (`render.py`) | `catalogue.py` + `catalogue.jsonl` (thay bằng truy vấn mô tả theo lớp) |
| chuẩn hoá và bung viết tắt (`text.py`) | `research/` (dataset, labels, classifier, evaluation, reporting, export) |
| webui, proxy Vercel | `resources/dataset`, `provenance`, `reports`, phần lớn `end-to-end` |
| `tests/ontology` (chuyển dần thành kiểm shape và kiểm nguồn) | CLI train/export/publish/benchmark/report, bước tải model trong Dockerfile và CI |
| `references/` | extra `research` và `onnxruntime`, `tokenizers` khỏi `inference` |

Nên giữ lại trước khi xoá: một bộ vài trăm cặp từ khoá → IRI (mục 2, bước 6) và
khoảng 85 câu của phép đo toàn hệ thống, làm kiểm tra hồi quy nhẹ. Không có chúng
thì không chứng minh được hướng mới tốt hơn hay kém hơn hướng cũ.

## 7. Quyết định

| Câu hỏi | Trạng thái |
|---|---|
| Nơi lưu ontology | Đã chốt: Google Cloud Storage, nạp vào rdflib Graph trong bộ nhớ (mục 3) |
| Thư viện RDF | Đã chốt: rdflib; kho phía dưới đổi được sang Oxigraph qua `oxrdflib` khi cần tốc độ (mục 3) |
| Cách tìm | Tên (rapidfuzz) + dòng `nhãn \| thuộc tính \| nhãn/giá trị` (bm25s, chặn độ phủ từ), gộp theo thực thể; nguyên văn dài chỉ là tầng dự phòng (mục 2.3, 2.4) |
| model2vec | Khuyến nghị không đưa vào đường trả lời; nếu dùng thì ở giao diện quản trị để gợi ý nhãn phụ (mục 2.4); chờ xác nhận |
| Ai được sửa | Đã chốt: chỉ quản trị viên. Kết quả deep research vẫn vào trạng thái `draft` để quản trị viên duyệt |
| Gộp lớp vụn | Khuyến nghị gộp nhóm định nghĩa và nhóm quy tắc (4.G); chờ xác nhận |
