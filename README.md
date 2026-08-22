# Chatbot hỏi đáp học vụ dựa trên ontology

Ontology (mô hình khái niệm gồm thực thể, thuộc tính và quan hệ) học vụ là nguồn
dữ kiện duy nhất của hệ thống. Mô hình phân loại chọn một truy vấn SPARQL (ngôn
ngữ truy vấn đồ thị tri thức) trong danh mục dựng sẵn. Mô hình ngôn ngữ lớn (LLM)
dùng kết quả tra cứu để trả lời người học, kèm trích dẫn văn bản gốc. Khi ontology
không có câu trả lời, hệ thống được thiết kế để từ chối.

---

## Tóm tắt

Hệ thống dự đoán một trong 344 nhãn từ câu hỏi tiếng Việt. Mỗi nhãn ánh xạ tất
định tới một truy vấn SPARQL đã kiểm định hoặc hành động từ chối; LLM chỉ thực
hiện giao tiếp, gọi công cụ và diễn đạt dữ kiện trả về.

Năm mô hình được đánh giá trên 6.313 câu hỏi: bốn bộ mã hoá văn bản đã tiền huấn
luyện, và một mốc so sánh chỉ đếm tần suất cụm ký tự. Trên 390 câu của tập đánh giá
độc lập, mô hình đa ngữ XLM-R base chọn đúng nhãn ở **86,9%** số câu, cao hơn mốc so
sánh 6,6 điểm phần trăm.

Khoảng cách giữa các mô hình tập trung ở những nhãn có rất ít câu huấn luyện: 57
trong 344 nhãn có dưới năm câu, và ở nhóm hiếm nhất, mô hình tốt nhất giữ được 75%
trong khi mô hình yếu nhất về 0%. Định nghĩa đầy đủ các chỉ số nằm ở mục 6.

Phép đo chỉ phản ánh cách hỏi mới về các nội dung đã xuất hiện trong dữ liệu huấn
luyện; khả năng xử lý nội dung chưa từng thấy và độ biến thiên giữa nhiều lần
huấn luyện chưa được đánh giá.

---

## 1. Bài toán

Quy chế đặt ra quy tắc đào tạo; thủ tục học vụ quy định điều kiện, hồ sơ và các
bước thực hiện. Phạm vi còn gồm biểu mẫu, học phí, chứng chỉ ngoại ngữ và bảng
tra cứu.

Người học có thể hỏi *"nghỉ ngang một kỳ có sao không ạ"* thay vì *"thủ tục nghỉ
học tạm thời"*. Câu hỏi cũng có thể thiếu dấu, viết tắt, ngắn hoặc chứa nhiều ý.
Hệ thống cần nhận diện đúng ý định, chọn đúng mục trong đồ thị và chỉ lấy dữ kiện
có nguồn.

Hệ thống tuân theo hai ràng buộc:

1. **Câu trả lời trong phạm vi phải bám vào văn bản của trường.** Dữ kiện từ nguồn
   khác không được sử dụng thay cho dữ kiện trong ontology.
2. **Câu ngoài phạm vi phải bị từ chối rõ ràng.** Chính sách này hạn chế câu trả
   lời không có căn cứ về các thông tin học vụ quan trọng.

Bài toán được quy về chọn truy vấn SPARQL đã định nghĩa và quyết định từ chối câu
ngoài phạm vi, thay vì sinh văn bản trả lời trực tiếp từ tham số mô hình.

---

## 2. Tổng quan hệ thống

Ontology học vụ và mô hình phân loại truy vấn là phần lõi. LLM rút cụm từ khoá
từ câu hỏi, gọi công cụ và diễn đạt dữ kiện trả về. Mô hình phân loại chỉ nhận
cụm từ khoá ngắn, không đối thoại trực tiếp với người dùng.

Khuôn nhắc yêu cầu LLM gọi công cụ tra cứu trước khi trả lời câu hỏi học vụ. Công
cụ chỉ trả về dữ kiện từ ontology.

![Kiến trúc tổng quan của hệ thống](docs/images/kien-truc.png)

![Luồng xử lý một câu hỏi](docs/images/luong-xu-ly.png)

Hệ thống gồm ba tầng:

| Tầng | Thành phần | Trách nhiệm |
|---|---|---|
| Hội thoại | Mô hình ngôn ngữ lớn | Rút từ khoá và diễn đạt câu trả lời cuối |
| Tra cứu | Encoder kết hợp bộ phân loại | Chọn một trong 344 nhãn |
| Dữ kiện | Đồ thị tri thức | Lưu nội dung và nguồn, thực thi truy vấn dựng sẵn |

Bộ phân loại dự đoán một trong 344 nhãn. Trong đó, 343 nhãn ánh xạ tới truy vấn
SPARQL và một nhãn ánh xạ tới hành động từ chối. Các truy vấn được tạo từ bốn
khuôn cố định và chỉ tham chiếu thực thể có trong ontology.

Công cụ nhận từ khoá thay vì toàn bộ câu hỏi. LLM có thể gửi nhiều cụm từ khoá
của cùng một chủ đề để bao quát khác biệt giữa cách hỏi và tên trong ontology.

---

## 3. Ontology

Ontology mô tả các thực thể, thuộc tính và quan hệ học vụ, đồng thời là cơ sở dữ
liệu nội dung duy nhất cho mọi truy vấn.

![Lược đồ ontology học vụ](docs/images/so-do-ontology.png)

Đồ thị có hai tầng trả lời trực tiếp:

- **Tầng văn bản** giữ nguyên văn công văn, chia theo Chương → Điều → Khoản →
  Điểm, cùng Phụ lục và Bảng.
- **Tầng tri thức** giữ dữ kiện đã bóc tách về thủ tục, bước thực hiện, điều kiện,
  thời hạn, biểu mẫu, ngành đào tạo và chứng chỉ.

Mỗi dữ kiện liên kết tới phần văn bản chứng minh, cho phép câu trả lời kèm trích
dẫn và đường dẫn đối chiếu.

| Thành phần | Quy mô |
|---|---:|
| Phát biểu khai báo trực tiếp | 6.350 |
| Toàn bộ phát biểu trong đồ thị khi vận hành | 7.704 |
| Lớp khái niệm | 56 |
| Mục cụ thể (cá thể) | 685 |
| Quan hệ giữa hai thực thể | 29 |
| Thuộc tính mang giá trị chữ hoặc số | 55 |
| Văn bản gốc đã số hoá | 16 |

Phần chênh lệch 1.354 bộ ba phát sinh do đồ thị khi vận hành bổ sung cặp trích
dẫn–đường dẫn cho các mục trả lời được.

Nội dung được bóc tách từ 16 văn bản chính thức: sáu quyết định của Hiệu trưởng,
gồm **Quyết định 1052**, **Quyết định 317**, 626, 729, 753 và 1965; ba quy chế
kèm theo; cùng bảy trang thông tin chính thức.

---

## 4. Hình dạng dữ liệu

Hình dưới mô tả sáu biểu diễn của một yêu cầu, từ đầu vào đến câu trả lời.

![Hình dạng dữ liệu qua từng bước](docs/images/hinh-dang-du-lieu.png)

### 4.1 Một dòng dữ liệu huấn luyện

Mỗi mẫu gồm câu hỏi, mã nhóm, nhãn phong cách và IRI (Internationalized Resource
Identifier, định danh của thực thể) đích. IRI được dùng thay cho chuỗi SPARQL để
tách dữ liệu khỏi khuôn truy vấn; mẫu ngoài phạm vi có đích rỗng.

Ví dụ trả lời được, dùng câu hỏi gõ không dấu:

```json
{
  "id": "question-000013",
  "query_id": "academic-actor-facts",
  "register": "noisy",
  "input": "co van hoc tap la ai",
  "target": [":AcademicAdvisor"]
}
```

Ví dụ thuộc nhóm phải từ chối:

```json
{
  "id": "question-005274",
  "query_id": "no-information",
  "register": "formal",
  "input": "Xin cho biết chào bạn.",
  "target": []
}
```

Nhãn chuẩn của một mẫu là cặp `(query_id, target)`. `query_id` xác định khía cạnh
được hỏi, còn `target` xác định thực thể. Cặp này định danh duy nhất một trong 344
nhãn.

### 4.2 Kết quả công cụ trả về

Công cụ trả về trạng thái dữ liệu, hướng dẫn, danh sách nguồn và từ khoá không
tìm thấy. Mỗi dữ kiện nằm trong nguồn đã khẳng định nó, do đó dữ kiện và trích dẫn
được duy trì cùng nhau.

```json
{
  "trang_thai": "co_du_lieu",
  "huong_dan": "Đây là toàn bộ dữ liệu tìm thấy. Đọc hết du_lieu. Nếu chi tiết được hỏi không xuất hiện, dữ liệu hiện có không chứa chi tiết đó; không tra lại cùng chủ đề. Mỗi mục trong nguon gồm trích dẫn, đường dẫn, và các dữ kiện mà nguồn đó khẳng định.",
  "nguon": [
    {
      "trich_dan": "Điều 12 Quy chế đào tạo trình độ đại học, ban hành kèm Quyết định 1052/QĐ-ĐHNT ngày 17/7/2025",
      "duong_dan": "https://pdtdaihoc.ntu.edu.vn/uploads/38//245-Quyet dinh 1052.pdf",
      "du_lieu": [
        { "thuoc_tinh": "tên gọi", "gia_tri": "Thủ tục công nhận kết quả học tập và chuyển đổi tín chỉ" },
        { "thuoc_tinh": "nội dung bước", "gia_tri": "Sau khi trúng tuyển, thực hiện chương trình đào tạo và đăng ký học tập theo kế hoạch chung." },
        { "thuoc_tinh": "thứ tự bước", "gia_tri": 2 }
      ]
    }
  ],
  "tu_khoa_khong_thay": ["hồ sơ liên thông"]
}
```

Khi không từ khoá nào khớp, trạng thái cho biết không có thông tin và danh sách
nguồn rỗng.

---

## 5. Tập dữ liệu

![Từ văn bản gốc tới điểm số](docs/images/luong-du-lieu.png)

Dữ liệu được xây dựng từ ontology theo 49 nhóm câu hỏi trả lời được và một nhóm
từ chối. Trong 566 đích, 258 đích xuất hiện ở cả bốn cách hỏi. Tập dữ liệu gồm
`train` (tập học tham số), `validation` (tập theo dõi huấn luyện) và `test` (tập
đánh giá độc lập).

![Thành phần bộ dữ liệu; tỷ lệ từ chối là 13,1%](docs/images/bo-du-lieu.png)

| Phần dữ liệu | Số dòng | Vai trò |
|---|---:|---|
| `train` | 5.523 | Học ánh xạ từ câu hỏi sang nhãn hoặc từ chối |
| `validation` (`val`) | 400 | Theo dõi quá trình huấn luyện |
| `test` | 390 | Đánh giá độc lập |
| **Toàn bộ** | **6.313** | — |

Không câu nào ở `validation` hoặc `test` trùng nguyên văn với `train`. Tuy nhiên,
ba phần dùng chung bộ đích; vì vậy phép đo phản ánh khả năng nhận diện cách hỏi
mới về nội dung đã biết, không phản ánh khả năng xử lý mục chưa gặp.

Dữ liệu phủ 50 nhóm câu hỏi và 566 đích, gồm 565 đích truy vấn cùng một đích từ
chối. Sau khi gộp Khoản và Điểm lên Điều, mô hình phân biệt 344 nhãn. Độ dài câu
hỏi có trung vị 11 từ, trung bình 11,54 từ, nhỏ nhất 1 từ và lớn nhất 36 từ.

Toàn bộ dữ liệu có 829 câu mang nhãn từ chối, chiếm 13,1%: 730 câu `train`, 50
câu `validation` và 49 câu `test`.

Bốn phong cách câu hỏi biểu diễn biến thiên bề mặt của cùng ý định:

| Phong cách | Số dòng | Mô tả |
|---|---:|---|
| thân mật | 1.800 | cách diễn đạt hội thoại |
| trung tính | 1.640 | câu hỏi đủ dấu, cấu trúc thông dụng |
| gõ nhiễu | 1.490 | thiếu dấu, sai chính tả hoặc viết dính |
| trang trọng | 1.383 | văn phong hành chính |

---

## 6. Thiết lập thực nghiệm

### 6.1 Năm mô hình đem so

Bốn encoder được fine-tune, tức tiếp tục huấn luyện trên bài toán phân loại hiện
tại. Baseline TF-IDF + LinearSVC kết hợp TF-IDF (*term frequency–inverse document
frequency*, trọng số phản ánh mức đặc trưng của n-gram) với bộ phân loại tuyến
tính biên lớn LinearSVC. Baseline không dùng biểu diễn tiền huấn luyện và khai
thác n-gram ký tự cùng n-gram từ; đặc trưng ký tự phù hợp với câu thiếu dấu và
sai chính tả trong tập dữ liệu.

| Mô hình | Tổ chức | Loại |
|---|---|---|
| XLM-R base (`FacebookAI/xlm-roberta-base`) | Meta AI | encoder đa ngữ |
| PhoBERT-v2 (`vinai/phobert-base-v2`) | VinAI | encoder tiếng Việt |
| BamiBERT (`Qualcomm-AI-Research/BamiBERT`) | Qualcomm AI Research | encoder đa ngữ |
| ViSoBERT (`uitnlp/visobert`) | UIT-NLP | encoder tiếng Việt cho mạng xã hội |
| TF-IDF + LinearSVC | — | baseline tuyến tính |

### 6.2 Điều kiện chạy

Cả năm mô hình dùng cùng ba phần dữ liệu. Một epoch là một lượt xử lý toàn bộ tập
`train`; bốn encoder được fine-tune trong 32 epoch. Checkpoint là trạng thái mô
hình được lưu tại một epoch; checkpoint ở epoch cuối được đánh giá trên `test`.
Baseline được huấn luyện một lần. `Test` không tham gia lựa chọn mô hình hoặc
điều chỉnh tham số.

### 6.3 Các chỉ số và cách tính

Mỗi câu được chấm bằng cách so nhãn dự đoán với nhãn chuẩn. Accuracy dùng toàn bộ
390 câu. Precision macro, recall macro và F1 macro cho mỗi nhãn trọng số bằng
nhau; F1 weighted lấy trung bình F1 theo số mẫu của từng nhãn. Các chỉ số theo
phạm vi còn báo riêng 341 câu trả lời được và 49 câu ngoài phạm vi; trên
`validation`, hai nhóm tương ứng có 350 và 50 câu.

Nhãn dự đoán được ánh xạ tất định tới truy vấn dựng sẵn khi hệ thống phục vụ.
Thực nghiệm bộ phân loại không chấm phép sinh chuỗi truy vấn hoặc thực thi SPARQL.

### 6.4 Cách tiến hành phép đo

**Chia dữ liệu.** 6.313 câu được chia thành 5.523 câu `train`, 400 câu
`validation` và 390 câu `test`. Không có câu trùng nguyên văn giữa ba phần.

**Huấn luyện và chấm nhãn.** Bốn encoder chạy 32 epoch; checkpoint cuối được dùng
để dự đoán nhãn trên `test`. Baseline được huấn luyện trên `train` rồi áp dụng
cùng phép chấm nhãn.

**Chấm end-to-end.** End-to-end là toàn bộ luồng từ câu hỏi đến câu trả lời. Phép
đo đưa 85 câu qua trợ lý hoàn chỉnh, gồm 60 câu trong phạm vi, 15 câu ngoài phạm
vi và 10 câu hỏi về dữ liệu ontology chưa có. Mỗi lượt ghi câu hỏi, dữ liệu công
cụ và câu trả lời cuối.

**Thời gian phản hồi.** Thời gian được đo từ lúc nhận câu hỏi đến khi có câu trả
lời cuối. Trung vị và p95 được lấy theo thứ hạng; p95 là phần tử thứ
⌈0,95 × n⌉ của dãy đã sắp xếp.

---

## 7. Kết quả thực nghiệm

### 7.1 Bảng so sánh năm mô hình

![So sánh năm mô hình trên tập test](docs/images/model-comparison.png)

Kết quả trên 390 câu `test` với 344 nhãn:

| Mô hình | Accuracy | Precision macro | Recall macro | F1 macro | F1 weighted |
|---|---:|---:|---:|---:|---:|
| **XLM-R base** | **86,9%** | **81,5%** | **85,5%** | **82,3%** | **84,9%** |
| BamiBERT | 84,4% | 79,6% | 83,2% | 80,4% | 83,1% |
| PhoBERT-v2 | 81,8% | 73,0% | 79,1% | 74,5% | 79,1% |
| ViSoBERT | 80,3% | 76,2% | 81,8% | 77,5% | 78,2% |
| TF-IDF + LinearSVC | 80,3% | 74,4% | 79,5% | 75,6% | 78,3% |

XLM-R cao hơn baseline 6,6 điểm accuracy và 6,7 điểm F1 macro. Phân tích theo
tần suất nhãn cho thấy phần lớn chênh lệch xuất hiện ở các nhãn hiếm.

Tách theo phạm vi câu hỏi:

| Mô hình | Trong phạm vi<br>(341 câu) | Ngoài phạm vi<br>(49 câu) | Thời gian huấn luyện |
|---|---:|---:|---:|
| XLM-R base | 87,7% <br><sub>299/341</sub> | 81,6% <br><sub>40/49</sub> | 177 s |
| BamiBERT | 85,0% <br><sub>290/341</sub> | 79,6% <br><sub>39/49</sub> | 179 s |
| PhoBERT-v2 | 81,5% <br><sub>278/341</sub> | 83,7% <br><sub>41/49</sub> | 175 s |
| ViSoBERT | 84,5% <br><sub>288/341</sub> | 51,0% <br><sub>25/49</sub> | 236 s |
| TF-IDF + LinearSVC | 82,7% <br><sub>282/341</sub> | 63,3% <br><sub>31/49</sub> | 4 s |

Hai cột phản ánh hai phía của quyết định từ chối và cần được đọc riêng. Nhóm ngoài
phạm vi chỉ có 49 câu được tạo từ bảy khuôn, nên không đủ để ước lượng chắc chắn
thứ hạng mô hình theo khả năng từ chối.

#### Kết quả theo tần suất nhãn

![Độ chính xác theo số câu huấn luyện](docs/images/accuracy-by-frequency.png)

| Mô hình | 1–2 câu | 3–4 câu | 5–9 câu | 10–19 câu | ≥20 câu |
|---|---:|---:|---:|---:|---:|
| XLM-R base | 75% | 80% | 78% | 92% | 88% |
| BamiBERT | 50% | 40% | 78% | 89% | 85% |
| PhoBERT-v2 | 0% | 20% | 68% | 87% | 89% |
| ViSoBERT | 75% | 60% | 76% | 88% | 76% |
| TF-IDF + LinearSVC | 0% | 60% | 78% | 82% | 83% |

Chênh lệch lớn nhất xuất hiện ở nhóm nhãn có 1–2 mẫu huấn luyện. Ở các nhóm còn
lại, mức chênh lệch thay đổi theo nhóm tần suất. Có 57/344 nhãn dưới năm mẫu
huấn luyện; kết quả này, cùng các chỉ số tổng thể, là cơ sở lựa chọn XLM-R.

### 7.2 Diễn biến huấn luyện

Loss là cross-entropy trung bình trên mỗi mẫu. Cross-entropy đo mức phân bố xác
suất dự đoán lệch khỏi nhãn chuẩn; giá trị thấp hơn biểu thị mức khớp tốt hơn trên
cùng tập dữ liệu.

![Training loss và validation loss trong 32 epoch](docs/images/loss-curves.png)

Bốn encoder đều chạy 32 epoch. ViSoBERT có training loss thấp nhất nhưng
validation loss cao nhất ở epoch cuối, trong khi XLM-R có validation loss thấp
nhất. Baseline không có vòng lặp epoch và được huấn luyện một lần.

### 7.3 Kết quả theo lĩnh vực

Kết quả của XLM-R trên `test`:

| Lĩnh vực | Accuracy | Số câu |
|---|---:|---:|
| Thủ tục học vụ | 91,8% | 49 |
| Biểu mẫu | 91,7% | 48 |
| Văn bản và điều khoản | 87,7% | 57 |
| Chứng chỉ ngoại ngữ | 87,1% | 31 |
| Quy tắc học vụ | 86,3% | 131 |
| Ngoài phạm vi | 81,6% | 49 |
| Học phí | 80,0% | 25 |

Nhóm Học phí có 25 câu; một lỗi làm thay đổi 4,0 điểm phần trăm, nên so sánh theo
lĩnh vực cần được diễn giải thận trọng. Nhóm Quy tắc học vụ có 131 câu và đạt
86,3%, gần accuracy tổng thể.

### 7.4 Kết quả theo cách hỏi

| Mô hình | Trang trọng | Trung tính | Thân mật | Gõ nhiễu |
|---|---:|---:|---:|---:|
| **XLM-R base** | **94,9%** | **93,9%** | **85,6%** | **72,9%** |
| BamiBERT | 92,9% | 92,9% | 81,4% | 69,8% |
| PhoBERT-v2 | 89,8% | 86,9% | 78,4% | 71,9% |
| ViSoBERT | 86,7% | 88,9% | 80,4% | 64,6% |
| TF-IDF + LinearSVC | 85,7% | 85,9% | 77,3% | 71,9% |

Ở cả năm mô hình, accuracy thấp nhất ở nhóm gõ nhiễu; chênh lệch trang trọng–gõ
nhiễu của XLM-R là 22,0 điểm phần trăm. Baseline đạt 71,9% ở nhóm gõ nhiễu, bằng
PhoBERT và thấp hơn XLM-R 1,0 điểm.

### 7.5 Độ chính xác câu trả lời `end-to-end`

Kết quả end-to-end không đồng nhất với §7.1: §7.1 là phép đo từng phần, chỉ đánh
giá tầng chọn nhãn; phép đo này còn gồm rút từ khoá, tra cứu và diễn đạt của LLM.
Vì vậy accuracy chọn nhãn không đại diện trực tiếp cho chất lượng end-to-end.

Bộ đo gồm 85 câu chia làm hai loại, và **hai loại này phải đọc riêng**. Với 61 câu
trong phạm vi, hành vi đúng là đưa ra được thứ được hỏi. Với 24 câu còn lại — 14 câu
ngoài phạm vi và 10 câu chạm khoảng trống của ontology — hành vi đúng là **từ chối**;
trả lời được chúng nghĩa là đã suy diễn ngoài dữ liệu. Gộp cả 85 câu vào một mẫu số
sẽ khiến mỗi lần hệ thống từ chối đúng lại làm tỷ lệ "đúng" giảm xuống.

Bốn kiểm tra tất định trên 61 câu trong phạm vi:

| Tiêu chí | Kết quả |
|---|---:|
| Gọi công cụ trước khi trả lời | 93,4% <br><sub>57/61</sub> |
| Lấy đúng mục trong đồ thị | 77,0% <br><sub>47/61</sub> |
| Không nêu số hoặc tên ngoài dữ liệu vừa tra | 95,1% <br><sub>58/61</sub> |
| **Đúng mục và bám dữ liệu đồng thời** | **75,4%** <br><sub>46/61</sub> |

Với câu ontology không trả lời được:

| Nhóm | Nói rõ dữ liệu không có |
|---|---:|
| 14 câu ngoài phạm vi | 57,1% <br><sub>8/14</sub> |
| 10 câu chạm khoảng trống ontology | 90,0% <br><sub>9/10</sub> |

Cột này dò theo cụm từ chối trong câu trả lời nên chỉ bắt được cách nói đã liệt kê;
phép chấm bên dưới đọc cả câu và cho 12/14 ở cùng nhóm này.

Chất lượng câu trả lời do một mô hình ngôn ngữ lớn chấm dựa trên câu hỏi, dữ liệu
công cụ và câu trả lời, xếp vào năm mức:

| Nhóm câu hỏi | Hành vi đúng | Tỷ lệ đạt |
|---|---|---:|
| 61 câu trong phạm vi | đưa ra được thứ được hỏi | **75,4%** <br><sub>46/61</sub> |
| 24 câu không trả lời được | từ chối | **87,5%** <br><sub>21/24</sub> |

Phân bố đầy đủ:

| Mức | Trong phạm vi<br>(61 câu) | Không trả lời được<br>(24 câu) |
|---|---:|---:|
| đúng | 46 | 3 |
| từ chối | 12 | 21 |
| thiếu | 3 | 0 |
| sai | 0 | 0 |
| lạc đề | 0 | 0 |

Ba câu được trả lời trong nhóm lẽ ra phải từ chối đều thuộc cùng một dạng: câu hỏi
nhắm vào một thực thể có thật nhưng hỏi một thuộc tính ontology không lưu, và câu
trả lời được ghép từ hai dữ kiện rời.

Phép chấm này do máy thực hiện, không phải người. Mỗi phán quyết được đối chiếu với
ba tín hiệu tất định của cùng bản ghi — có lấy đúng mục không, công cụ trả về bao
nhiêu dòng, có nêu số ngoài dữ liệu không; **6/85 phán quyết mâu thuẫn với các tín
hiệu đó**. Chín trường hợp trải đều các mức đã được kiểm bằng tay và cả chín đều
khớp với phán quyết của máy, nhưng con số vẫn cần được đối chứng bằng chấm người
trước khi dùng làm kết luận.

### 7.6 Thời gian phản hồi

Phép đo trên 85 câu bao gồm thời gian gọi LLM qua mạng:

| Thống kê | Giây |
|---|---:|
| Trung vị | **2,5** |
| p95 | 4,7 |
| Dài nhất | 6,9 |
| Ngắn nhất | 0,7 |

Trung vị với tra cứu là 2,6 giây, so với 1,2 giây khi không tra cứu.

Đo riêng bên trong công cụ, trên 76 lượt tra cứu thật:

| Giai đoạn | Trung vị | p95 |
|---|---:|---:|
| Chọn truy vấn | **3,9 ms** | 5,7 ms |
| Chạy truy vấn trên đồ thị | 17,5 ms | 1.510,6 ms |
| Toàn bộ công cụ | 22,5 ms | 1.514,4 ms |

Tầng chọn truy vấn tốn **3,9 ms**, tức khoảng 0,16% thời gian phản hồi. Toàn bộ công
cụ, gồm cả việc chạy SPARQL trên đồ thị, chiếm chưa tới 1%. Phần còn lại là LLM đọc
dữ liệu và viết câu trả lời.

Hệ quả cho việc triển khai: thời gian phản hồi của hệ thống bị chi phối bởi lớp giao
tiếp chứ không phải phần lõi. Muốn nhanh hơn thì tối ưu ở LLM hoặc rút ngắn khuôn
nhắc; tối ưu bộ phân loại không còn dư địa đáng kể.

Giá trị p95 của bước chạy truy vấn cao hơn trung vị hai bậc độ lớn vì một số truy
vấn trả về toàn văn bảng biểu dài; đó là đặc điểm của dữ liệu, không phải của mô hình.

## 8. Phân tích trường hợp trả lời sai

Hai tầng có thể sai độc lập: tầng tra cứu chọn nhầm nhãn, hoặc tầng giao tiếp diễn
đạt sai dù nhận đúng dữ liệu.

### 8.1 Lỗi của tầng chọn truy vấn

![Ma trận nhầm lẫn theo nhóm câu hỏi; nhãn thanh toán được diễn giải là “Phí theo phương thức thanh toán” và “Thông tin phương thức thanh toán”](docs/images/confusion-matrix.png)

XLM-R sai 51/390 câu `test`; trong số đó, 42 lỗi đổi nhóm câu hỏi và 9 lỗi chọn
sai thực thể trong cùng nhóm.

Sáu trường hợp tiêu biểu:

| Câu hỏi | Đích đúng | Mô hình chọn |
|---|---|---|
| điểm đã đạt muốn học lại cho cao hơn sao ạ | Học cải thiện điểm | Học lại học phần |
| rot mon thi dang ky hoc lai o ky sau sao vay | Học lại học phần | Mục tải biểu mẫu |
| nganh co khi goi sao | Ngành Kỹ thuật cơ khí | Bảng danh mục ngành |
| co nhung dieu gi can hieu khi nhac toi tin chi z? | Khái niệm tín chỉ | Giảng viên học phần |
| xin tot nghiep som thi nop don cho phong nao vay a | Thủ tục xét tốt nghiệp sớm | *từ chối* |
| muon dang ky datn thi lien he phong nao? | Thủ tục đăng ký đồ án | *từ chối* |

Hai nhãn “Học lại học phần” và “Học cải thiện điểm” có từ vựng chồng lấp trong
câu hỏi, dẫn đến nhầm lẫn. Một số lỗi khác nhầm giữa thực thể và bảng chứa nó,
hoặc từ chối câu viết tắt không dấu.

![Không gian biểu diễn câu hỏi trên tập test, chiếu xuống hai chiều bằng UMAP](docs/images/umap.png)

Hình trên chiếu vector biểu diễn của 390 câu hỏi tập test xuống hai chiều bằng UMAP,
một phép giảm chiều phi tuyến giữ lại quan hệ lân cận. Mỗi điểm là một câu hỏi, màu
theo nhóm câu hỏi. Các nhóm tách thành cụm rời nhau, nghĩa là mô hình học được biểu
diễn phân tách theo nhóm chứ không chỉ ghi nhớ từng câu.

Nhóm ngoài phạm vi tách thành nhiều cụm rời chứ không gộp làm một. Điều này phù hợp
với việc dữ liệu chứa nhiều loại câu ngoài phạm vi khác nhau — lời chào, câu hỏi
thuộc lĩnh vực khác, câu hỏi đúng chủ đề nhưng đòi dữ kiện ontology không lưu — và
mô hình phân biệt được chúng.

### 8.2 Lỗi của cả trợ lý

Trong 85 câu end-to-end, không câu nào bị máy chấm là nêu dữ kiện sai. Dạng hỏng
còn lại nằm ở chỗ khác: **câu hỏi chỉ nêu chủ thể mà không nêu cần biết gì về chủ
thể đó**. Cả bốn câu trong phạm vi mà trợ lý không tra cứu đều thuộc dạng này:

> **Hỏi:** "Trường Đại học Nha Trang?" — "Sinh viên thế nào ạ?" —
> "Mình cần tra cứu các thông tin liên quan đến Trình độ đại học?"
>
> **Trả lời:** trợ lý liệt kê các nhóm chủ đề tra được rồi mời hỏi cụ thể hơn.

Hành vi này hợp lý với người dùng nhưng không tạo ra câu trả lời, nên phép đo xếp
vào mức từ chối. Câu thứ tư cùng nhóm hỏi "trường hợp nằm viện, tai nạn được mô tả
trong quy định này" — đại từ "này" không có tiền ngữ trong lượt hỏi đơn lẻ.

Đây là lỗi tầng giao tiếp chứ không phải lỗi chọn truy vấn: với cả bốn câu, nhãn
đúng vẫn tồn tại trong danh mục, chỉ là trợ lý không gửi từ khoá nào đi tra.

## 9. Giao diện

Giao diện trình bày kết quả tra cứu và không tham gia chọn truy vấn.

![Trợ lý trả lời kèm nguồn](docs/images/giao-dien.png)

Tiêu chí có đường dẫn được xác định bằng sự xuất hiện của URL trong câu trả lời.
Có 67/85 câu đáp ứng tiêu chí này, tương ứng 78,8%. Trong các câu có dữ liệu trả
về, 67/76 câu có URL, tương ứng 88,2%.

Trong lúc tra cứu, giao diện hiển thị các cụm từ khoá được gửi tới công cụ:

![Trạng thái đang tra cứu](docs/images/giao-dien-tra-cuu.png)

Thông tin này cho phép đối chiếu cụm từ khoá với câu hỏi đầu vào khi kết quả tra
cứu không phù hợp.

Khi câu hỏi nằm ngoài phạm vi, giao diện trình bày thông báo không có thông tin:

![Trợ lý từ chối câu ngoài phạm vi](docs/images/giao-dien-tu-choi.png)

---

## 10. Hạn chế

**Phạm vi câu hỏi đóng.** Câu hỏi được xây dựng từ đồ thị và mọi nhãn của `test`
đều có trong `train`. Phép đo chưa đánh giá mục chưa từng thấy hoặc câu hỏi do
người học cung cấp.

**Gộp nhãn làm giảm độ chi tiết truy xuất.** Gộp Khoản và Điểm lên Điều làm số
nhãn giảm từ 566 xuống 344 và tỷ lệ nhãn có dưới năm mẫu huấn luyện giảm từ 55%
xuống 17%. Hệ quả là truy vấn ở cấp Điểm có thể trả về toàn bộ Điều, với trung vị
10 dòng; trích dẫn vẫn định vị dữ kiện ở cấp Điểm.

**Thiếu ước lượng biến thiên.** Mỗi mô hình được huấn luyện một lần; do đó chưa
thể ước lượng khoảng tin cậy hoặc kiểm định các chênh lệch nhỏ.

**Nhãn chuẩn chỉ công nhận một đáp án.** Một câu hỏi có thể được trả lời bằng
nhiều truy vấn thu được dữ kiện tương đương, nhưng phép chấm nhãn chỉ công nhận
một nhãn chuẩn. Ảnh hưởng của hiện tượng này chưa được lượng hoá bằng tệp kết quả
có thể tái lập.

**Dữ liệu tổng hợp còn hạn chế về ngôn ngữ và nhãn phong cách.** Một số câu mang
dấu vết của khuôn soạn hoặc có phong cách không tách bạch. Mức ảnh hưởng chưa có
kết quả kiểm tra theo từng mẫu.

**Đánh giá từ chối có cỡ mẫu nhỏ.** Có 49 câu ngoài phạm vi trong `test`, được tạo
từ bảy khuôn; các biến thể cùng khuôn không phải phép thử độc lập.

**Nhãn từ chối cần kiểm tra thực thi có bằng chứng nguồn.** Kiểm tra cần lưu quy
tắc, danh sách mã mẫu và mã băm dữ liệu trước khi dùng để công bố số lượng trường
hợp sai nhãn.

**Phép đo end-to-end có quy mô nhỏ.** Mẫu 85 câu chưa đủ để báo cáo sai số hẹp;
phần chấm chất lượng do mô hình ngôn ngữ lớn thực hiện và chưa được đối chứng với
người chấm.

Trên `test`, XLM-R không từ chối đúng 9/49 câu ngoài phạm vi, tương ứng 18,4%;
Học phí có accuracy thấp nhất trong bảy lĩnh vực, đạt 80,0%.

---

## 11. Hướng cải tiến

1. Xây dựng quy tắc chấm cho trường hợp nhiều truy vấn trả về dữ kiện tương đương,
   đồng thời lưu kết quả thực thi theo từng câu.
2. Hiệu chỉnh lỗi câu chữ và nhãn phong cách bằng quy trình kiểm tra có quy tắc,
   danh sách mã mẫu và mã băm dữ liệu.
3. Bổ sung tên gọi thay thế và viết tắt tiếng Việt cho các thực thể dễ nhầm lẫn,
   tập trung vào nhóm gõ nhiễu.
4. Mở rộng bộ đánh giá từ chối theo chủ đề độc lập thay vì chỉ tăng biến thể câu
   trong cùng khuôn.
5. Lặp huấn luyện với nhiều hạt giống để ước lượng biến thiên và khoảng tin cậy.
6. Xây dựng tập đánh giá từ câu hỏi thực tế của người học, tách biệt với quá trình
   xây dựng ontology và dữ liệu huấn luyện.
