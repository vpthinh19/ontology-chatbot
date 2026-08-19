# Chatbot hỏi đáp học vụ dựa trên ontology

Ontology học vụ là nguồn dữ kiện duy nhất của hệ thống. Mô hình seq2seq sinh
truy vấn SPARQL để đọc ontology. LLM dùng kết quả đó để trả lời người học, kèm
trích dẫn văn bản gốc, và từ chối khi ontology không có câu trả lời.

---

## Tóm tắt

Công trình xây dựng ontology học vụ để giữ dữ kiện và nguồn, rồi đánh giá các mô
hình seq2seq sinh truy vấn SPARQL từ cụm từ khoá tiếng Việt. Seq2seq nhận một
chuỗi chữ và viết ra chuỗi khác. Bốn mô hình được tinh chỉnh (*fine-tune*) để
viết truy vấn. Đây là đóng góp khoa học chính của dự án.

LLM chỉ là lớp giao tiếp: gọi công cụ tra ontology và diễn đạt dữ kiện trả về.
Cách tách này tránh để LLM tự suy đoán từ văn bản quy chế.

Bốn mô hình seq2seq cùng học trên một bộ dữ liệu gồm 6.308 câu hỏi, trong đó
5.518 câu thuộc `train`, và cùng được đánh giá bằng một bộ thước đo. **T5Gemma-2 thắng
rõ rệt**: nó chọn đúng mục cần tra trong đồ thị ở 77,9% số câu, dựng đúng khuôn
truy vấn ở 81,2%, và quyết định đúng giữa trả lời và từ chối ở 91,0%.

Sau khi chọn mô hình seq2seq tốt nhất, lớp giao tiếp được đánh giá `end-to-end`
trên 85 câu hỏi, từ lúc người dùng gõ đến khi câu trả lời hoàn tất. Trong 60 câu
học vụ, phép dò tự động cho thấy 59 câu không nêu con số hay chữ viết tắt nào mà
dữ liệu vừa tra không có; phép dò này không đọc hiểu nội dung. Trong 23 câu mà
ontology thực sự không trả lời được, 21 câu được nói thẳng là không có. Một nửa
số câu được trả lời trong vòng sáu giây rưỡi.

Các giới hạn chính:

- Đồ thị hiện có 16 văn bản và 50 dạng câu hỏi. Ngoài phạm vi đó, câu trả lời
  đúng duy nhất là "tôi không có thông tin này".
- Dữ liệu được chia theo câu hỏi, nên điểm số đo **khả năng hiểu một cách hỏi
  mới về việc đã biết**. Đo khả năng xoay xở với mục chưa từng thấy là một thí
  nghiệm khác, công trình này chưa làm.
- Mỗi mô hình chỉ chạy một lượt, và ba trong bốn mô hình vẫn đang khá lên khi
  hết ngân sách huấn luyện. Chỉ nên tin những khoảng cách lớn.

---

## 1. Bài toán

Quy chế đặt ra quy tắc đào tạo; thủ tục học vụ quy định điều kiện, hồ sơ và các
bước thực hiện. Phạm vi còn gồm biểu mẫu, học phí, chứng chỉ ngoại ngữ và bảng
tra cứu.

Người học không hỏi theo cách văn bản viết. Họ hỏi *"nghỉ ngang một kỳ có sao
không ạ"* chứ không hỏi *"thủ tục nghỉ học tạm thời"*. Họ gõ thiếu dấu, viết tắt,
hỏi cụt lủn, hoặc hỏi hai chuyện trong một câu. Hệ thống phải hiểu đúng ý định,
tìm đúng mục trong đồ thị, và chỉ lấy dữ kiện có nguồn.

Hệ thống tuân theo hai ràng buộc:

1. **Câu trả lời trong phạm vi phải bám vào văn bản của trường.** Không được lấy
   quy định của trường khác, dù mô hình ngôn ngữ lớn có "nhớ" quy định đó.
2. **Câu ngoài phạm vi phải bị từ chối rõ ràng.** Một câu trả lời sai về hạn nộp
   đơn gây hại hơn hẳn một câu "tôi không có thông tin này".

Bài toán khoa học chính là sinh truy vấn SPARQL có ràng buộc từ cụm từ khoá và
quyết định khi nào **không** trả lời, không phải sinh văn bản tự do.

---

## 2. Tổng quan hệ thống

Ontology học vụ và mô hình seq2seq sinh SPARQL là phần lõi. Trợ lý mà người dùng
trò chuyện là một mô hình ngôn ngữ lớn (LLM). LLM là lớp giao tiếp: nhận câu hỏi
tự nhiên, rút thành cụm từ khoá, gọi công cụ và diễn đạt dữ kiện trả về. Lớp này
cần thiết vì seq2seq chỉ nhận cụm từ khoá ngắn và không thể đối thoại trực tiếp
với người dùng.

Với mọi câu hỏi học vụ, LLM phải gọi công cụ tra cứu trước khi trả lời; công cụ
chỉ trả về dữ kiện từ ontology.

![Kiến trúc tổng quan của hệ thống](docs/images/kien-truc.png)

![Luồng xử lý một câu hỏi](docs/images/luong-xu-ly.png)

Hệ thống gồm ba tầng:

| Tầng | Ai làm | Trách nhiệm |
|---|---|---|
| Hội thoại | Mô hình ngôn ngữ lớn | Hiểu câu hỏi, rút thành từ khoá, viết câu trả lời cuối |
| Tra cứu | Mô hình chuỗi-chuỗi đã tinh chỉnh | Biến từ khoá thành truy vấn SPARQL |
| Dữ kiện | Đồ thị tri thức | Giữ nội dung và nguồn, trả về đúng những gì được hỏi |

Tầng dữ kiện và tầng tra cứu tạo ra kết quả kiểm chứng được. Tầng hội thoại chỉ
chuyển câu hỏi tự nhiên thành đầu vào phù hợp và trình bày kết quả cho người dùng.

**Công cụ nhận từ khoá thay vì cả câu hỏi.** LLM có thể gửi hai tới ba cách gọi
của cùng một chủ đề để bao quát khác biệt giữa cách hỏi và tên trong ontology.

**Truy vấn phải thuộc một trong 50 dạng đã khai báo.** Truy vấn không khớp dạng
nào bị loại để tránh trả về dữ liệu không đúng câu hỏi.

---

## 3. Ontology

Ontology là mô hình khái niệm mô tả thực thể, thuộc tính và quan hệ học vụ; đây
là cơ sở dữ liệu duy nhất cho mọi truy vấn.

![Lược đồ ontology học vụ](docs/images/so-do-ontology.png)

Đồ thị có **hai tầng, đều trả lời được trực tiếp**:

- **Tầng văn bản** giữ nguyên văn công văn, chia theo Chương → Điều → Khoản →
  Điểm, cộng Phụ lục và Bảng. Người hỏi *"điểm a khoản 2 Điều 15 nói gì"* được
  trả lời từ tầng này.
- **Tầng tri thức** giữ dữ kiện đã bóc tách: thủ tục, bước thực hiện, điều kiện,
  thời hạn, biểu mẫu, ngành đào tạo, chứng chỉ. Người hỏi *"nghỉ tạm thời cần
  làm gì"* được trả lời từ tầng này.

Mỗi dữ kiện trỏ về phần văn bản chứng minh nó, nên câu trả lời có thể kèm trích
dẫn và đường dẫn để đối chiếu.

| Thành phần | Quy mô |
|---|---:|
| Phát biểu trong tệp ontology | 6.355 |
| Phát biểu trong đồ thị lúc chạy | 7.711 |
| Lớp khái niệm | 56 |
| Mục cụ thể (cá thể) | 686 |
| Quan hệ giữa hai thực thể | 29 |
| Thuộc tính mang giá trị chữ hoặc số | 55 |
| Văn bản gốc đã số hoá | 16 |

Con số lúc chạy cao hơn vì lúc nạp, hệ thống bổ sung bản ghi nguồn cho từng mục
trả lời được.

Nội dung được bóc tách từ 16 văn bản chính thức, gồm sáu quyết định của Hiệu
trưởng: **Quyết định 1052**, **Quyết định 317**, cùng 626, 729, 753 và 1965; ba
quy chế kèm theo; và bảy trang thông tin chính thức. Mọi dữ kiện đều mang nguồn
trỏ về một trong 16 văn bản này. Nhờ đó, lớp giao tiếp có thể kèm trích dẫn và
đường dẫn để người dùng đối chiếu.

---

## 4. Hình dạng dữ liệu

Một câu hỏi đổi hình sáu lần từ đầu vào đến câu trả lời.

![Hình dạng dữ liệu qua từng bước](docs/images/hinh-dang-du-lieu.png)

### 4.1 Một dòng dữ liệu huấn luyện

Mỗi dòng ghép câu hỏi tiếng Việt với truy vấn đúng, mã số, dạng câu hỏi và nhãn
phong cách. Với câu ngoài phạm vi, đích là "không có thông tin". Ví dụ trả lời
được sau dùng câu hỏi gõ không dấu và truy vấn về cố vấn học tập:

```json
{
  "id": "question-000013",
  "query_id": "academic-actor-facts",
  "register": "noisy",
  "input": "co van hoc tap la ai",
  "target": "SELECT ?thuoctinh ?giatri ?nguon ?duongdan WHERE { { :AcademicAdvisor ?p ?giatri . FILTER(isLiteral(?giatri)) ?p rdfs:label ?thuoctinh OPTIONAL{:AcademicAdvisor :sourceCitation ?nguon;:sourceLink ?duongdan} } UNION { :AcademicAdvisor ?l ?con . ?con ?p ?giatri . FILTER(isLiteral(?giatri)) ?p rdfs:label ?thuoctinh OPTIONAL{?con :sourceCitation ?nguon;:sourceLink ?duongdan} } FILTER(?p!=skos:altLabel&&?p!=:sourceCitation&&?p!=:sourceLink) }"
}
```

Ví dụ phải từ chối:

```json
{
  "id": "question-005274",
  "query_id": "no-information",
  "register": "formal",
  "input": "Xin cho biết chào bạn.",
  "target": "không có thông tin"
}
```

### 4.2 Kết quả công cụ trả về

Công cụ luôn trả về cùng một khuôn: trạng thái dữ liệu, hướng dẫn, danh sách
nguồn và từ khoá không tìm thấy. Mỗi dữ kiện nằm trong nguồn đã khẳng định nó,
nhờ vậy dữ kiện và trích dẫn không bị tách rời.

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

Khi không từ khoá nào khớp, trạng thái là không có thông tin và danh sách nguồn
rỗng.

---

## 5. Tập dữ liệu

![Từ văn bản gốc tới điểm số](docs/images/luong-du-lieu.png)

Dữ liệu được sinh từ ontology theo 50 dạng thông tin trả lời được; mỗi mục sinh
bốn cách hỏi. Đáp án đúng là truy vấn chạy được. Vì dữ liệu đóng kín trong
ontology, phép đo chưa kiểm tra khả năng xử lý nội dung chưa gặp; đây là giới
hạn ở mục 10.

![Thành phần bộ dữ liệu](docs/images/bo-du-lieu.png)

| Phần dữ liệu | Số dòng | Vai trò |
|---|---:|---|
| `train` | 5.518 | Học ánh xạ từ câu hỏi sang truy vấn hoặc từ chối |
| `val` | 400 | Theo dõi quá trình học, chọn điểm dừng |
| `test` | 390 | Đánh giá cuối, sau khi mọi lựa chọn đã cố định |
| **Toàn bộ** | **6.308** | Không áp dụng |

Ba tập có vai trò khác nhau. `train` để mô hình học cách đổi câu hỏi thành truy
vấn. `val` dùng trong lúc học để theo dõi kết quả và chọn điểm dừng. `test` chỉ
dùng một lần ở cuối, sau khi mọi lựa chọn đã cố định. Nếu vừa điều chỉnh vừa xem
điểm `test`, người làm sẽ vô thức chọn cấu hình hợp với chính bộ đề đó, khiến con
số cuối thành tự khen.

Ba tập được chia **theo câu hỏi**: không câu ở `val` hoặc `test` xuất hiện ở
`train`. Ba tập vẫn dùng chung 567 câu trả lời đúng, nên 390 câu `test` rơi vào
những đáp án 5.518 câu `train` đã phủ. Vì thế, điểm số đo **khả năng hiểu cách
hỏi mới về việc đã biết**, không đo khả năng xử lý mục chưa gặp; thí nghiệm sau
chưa được thực hiện.

Dữ liệu phủ **50 dạng câu hỏi** và **567 câu trả lời đúng khác nhau**, gồm 566
câu truy vấn và một câu từ chối dùng chung cho mọi câu ngoài phạm vi. Một nửa số câu hỏi
dài từ 10 từ trở xuống, trung bình là 11,2 từ; câu ngắn nhất vỏn vẹn 1 từ, câu
dài nhất 33 từ.

Trong toàn bộ dữ liệu có **884 câu phải từ chối**, chiếm 14,0%: 773 câu `train`,
56 câu `val` và 55 câu `test`. Công trình chưa thử tỷ lệ khác nên chưa biết đây
có phải mức tốt nhất không.

Bốn phong cách câu hỏi kiểm tra khả năng giữ đúng ý định khi bề mặt câu thay đổi:

| Phong cách | Số dòng | Nghĩa |
|---|---:|---|
| thân mật | 1.799 | cách người học nhắn tin hàng ngày |
| trung tính | 1.640 | câu hỏi bình thường, đủ dấu |
| gõ nhiễu | 1.486 | thiếu dấu, sai chính tả, dính chữ |
| trang trọng | 1.383 | văn phong đơn từ |

---

## 6. Thiết lập thực nghiệm

### 6.1 Bốn mô hình đem so

Bốn mô hình chuỗi-chuỗi của bốn tổ chức cùng giải một bài. **Tham số** là các giá
trị quyết định hoạt động của mô hình; nhiều tham số thường cần nhiều tài nguyên
hơn. Khi tinh chỉnh, chỉ một **lớp mỏng** gắn thêm được học.

| Mô hình | Tổ chức | Tham số mô hình nền | Tham số thực sự được học |
|---|---|---:|---:|
| T5Gemma-2 (`google/t5gemma-2-270m-270m`) | Google | 786 M | 15,2 M |
| mBART (`facebook/mbart-large-cc25`) | Meta AI | 611 M | 17,3 M |
| BARTpho (`vinai/bartpho-syllable`) | VinAI | 396 M | 17,3 M |
| ViT5 (`VietAI/vit5-base`) | VietAI | 226 M | 13,0 M |

Phần tinh chỉnh chiếm từ 1,9% (T5Gemma-2) đến 5,7% (ViT5); trọng số nền giữ
nguyên.

### 6.2 Điều kiện chạy

Bốn mô hình dùng **cùng điều kiện**:

- **Cùng một bộ dữ liệu**, không mô hình nào được thấy thêm hay bớt câu nào.
- **Cùng tám lượt học.** Một lượt là một lần đọc hết `train`.
- **Cùng một điểm khởi đầu ngẫu nhiên.** Công trình chưa chạy lặp để kiểm chứng
  kết quả có trùng khít hay không.
- **Cùng cách viết câu trả lời.** Mỗi chữ chọn phương án khả dĩ nhất, không bốc
  thăm, nên cùng câu hỏi cho cùng truy vấn.
- **Cùng một máy**: card đồ hoạ 24 GB.

Bản có kết quả `val` tốt nhất được giữ lại. `test` chỉ được dùng một lần, sau
khi mọi lựa chọn đã cố định.

### 6.3 Ba chỉ số chính

**Chọn đúng mục trong đồ thị.** Truy vấn phải trỏ đúng tập mục câu hỏi nhắm tới;
lấy đúng mục nhưng kèm mục thừa vẫn tính sai.

**Dựng đúng khuôn truy vấn.** Trong 50 dạng, truy vấn phải khớp khuôn chuẩn và
điền đúng chỗ trống, trừ tên mục. Truy vấn viết khác nhưng cùng kết quả vẫn tính
sai. Chỉ tính câu trong phạm vi.

**Quyết định trả lời hay từ chối.** Câu trong phạm vi cần truy vấn thuộc một
trong 50 dạng; câu ngoài phạm vi cần đúng câu từ chối chuẩn. Đầu ra khác câu
chuẩn nhưng không trả lời vẫn tính sai. Đây là thước duy nhất tính cả hai nhóm.

Ba thước tách riêng để phân biệt các dạng lỗi. Phép đánh giá còn tính mức trùng
khớp giữa bảng kết quả và bảng đúng, nhưng chỉ dùng để dò lỗi vì cho điểm từng
phần.

---

## 7. Kết quả thực nghiệm

### 7.1 Bảng so sánh bốn mô hình

![Ba chỉ số chính trên test](docs/images/so-sanh-mo-hinh.png)

Kết quả trên **`test`** (390 câu, chỉ dùng một lần):

| Mô hình | Chọn đúng mục | Đúng dạng truy vấn | Từ chối đúng | Bộ nhớ card lúc đỉnh | Thời gian huấn luyện | Tốc độ `test` |
|---|---:|---:|---:|---:|---:|---:|
| **T5Gemma-2** | **77,9%** | **81,2%** | 91,0% | 9,19 GiB | 29,8 phút | 0,46 s/câu |
| mBART | 66,3% | 75,2% | 88,7% | 10,46 GiB | 24,7 phút | 0,23 s/câu |
| BARTpho | 55,2% | 65,4% | **91,8%** | 3,18 GiB | 15,1 phút | 0,18 s/câu |
| ViT5 | 33,7% | 46,0% | 74,4% | 3,53 GiB | 19,0 phút | 0,41 s/câu |

Kết quả trên **`val`** (400 câu, dùng trong lúc phát triển):

| Mô hình | Chọn đúng mục | Đúng dạng truy vấn | Từ chối đúng |
|---|---:|---:|---:|
| **T5Gemma-2** | **81,7%** | **84,0%** | **96,8%** |
| mBART | 70,9% | 75,9% | 93,0% |
| BARTpho | 59,0% | 69,5% | 94,2% |
| ViT5 | 34,3% | 45,1% | 73,8% |

![Ba chỉ số chính trên val](docs/images/so-sanh-mo-hinh-kiem-dinh.png)

T5Gemma-2 dẫn đầu năm trong sáu cột. Trên `test`, BARTpho hơn nó 0,8 điểm ở
từ chối; trên `val`, T5Gemma-2 hơn BARTpho 2,5 điểm. T5Gemma-2 hơn mô hình
thứ hai 11,6 điểm ở chọn đúng mục.

BARTpho đạt 91,8% ở từ chối, hơn T5Gemma-2 0,8 điểm, nhưng thua 22,7 điểm ở chọn
đúng mục; không thể gộp ba chỉ số thành một điểm.

Thứ hạng trùng khít với quy mô: 786 M > 611 M > 396 M > 226 M. Vì vậy chưa thể
kết luận T5Gemma-2 thắng nhờ kiến trúc, dữ liệu huấn luyện trước hay đơn giản vì
lớn nhất. BARTpho chuyên tiếng Việt vẫn xếp sau hai mô hình đa ngữ lớn hơn.

![Chính xác đổi lấy bộ nhớ và thời gian](docs/images/danh-doi.png)

Với phần cứng eo hẹp, BARTpho cho 55,2% với 3,18 GiB và 15 phút huấn luyện: một
phần ba bộ nhớ và một nửa thời gian của T5Gemma-2.

### 7.2 Diễn biến huấn luyện

![loss trên train](docs/images/hao-hut-hoc.png)

![loss trên val](docs/images/hao-hut-kiem-dinh.png)

Đồ thị theo dõi `loss` sau mỗi lượt học; đường đi xuống biểu thị cải thiện.
T5Gemma-2 thấp nhất ở lượt thứ năm, nên giữ bản này thay vì bản cuối. Ba mô hình
còn lại vẫn cải thiện khi hết tám lượt, nên kết quả chỉ là mức đạt trong thời
gian học đó. Cả bốn chạy dừng ở trần tám lượt; chưa biết chúng cải thiện tới đâu
nếu học lâu hơn.

### 7.3 Kết quả theo lĩnh vực

Bảng tách kết quả T5Gemma-2 theo lĩnh vực câu hỏi.

| Lĩnh vực | Số câu | Chọn đúng mục | Đúng dạng | Từ chối đúng |
|---|---:|---:|---:|---:|
| Quy chế đào tạo | 131 | 84,7% | 87,8% | 97,7% |
| Học phí | 25 | 84,0% | 84,0% | 96,0% |
| Tra cứu văn bản | 57 | 78,9% | 86,0% | 96,5% |
| Chứng chỉ ngoại ngữ | 31 | 77,4% | 77,4% | 90,3% |
| Thủ tục học vụ | 49 | 69,4% | 73,5% | 93,9% |
| Biểu mẫu | 42 | 61,9% | 64,3% | 100,0% |
| Ngoài phạm vi | 55 | Không áp dụng | Không áp dụng | 58,2% |

**Biểu mẫu yếu nhất** (61,9%) vì mã hành chính như "Mẫu số 5", "Phụ lục 4" khác
cách gọi theo công dụng như "đơn xin chuyển ngành".

**Câu ngoài phạm vi khó nhất** (58,2%). Số này khác 91,0% ở bảng tổng vì 91,0%
tính trên 390 câu, chủ yếu là câu trong phạm vi. Trong 55 câu ngoài phạm vi, 32
câu từ chối đúng: **58,2%**. Hai truy vấn rỗng nữa khiến **34/55 = 61,8% bị
chặn**; **21/55 = 38,2%** vẫn lọt.

### 7.4 Kết quả theo cách hỏi và độ khó truy vấn

![Độ chính xác theo phong cách](docs/images/theo-phong-cach.png)

| Mô hình | Trang trọng | Trung tính | Thân mật | Gõ nhiễu |
|---|---:|---:|---:|---:|
| T5Gemma-2 | 84,7% | 91,9% | 76,8% | **57,3%** |
| mBART | 83,5% | 76,7% | 64,6% | **39,0%** |
| BARTpho | 67,1% | 61,6% | 51,2% | **40,2%** |
| ViT5 | 32,9% | 39,5% | 30,5% | 31,7% |

**Câu gõ nhiễu tụt sâu nhất:** ba mô hình khá nhất giảm **26,8 tới 44,5 điểm**;
T5Gemma-2 từ 91,9% xuống 57,3%, mBART từ 83,5% xuống 39,0%, BARTpho từ 67,1%
xuống 40,2%. Câu thân mật đủ dấu chỉ mất 15,0 tới 18,9 điểm. Nhóm nhiễu đồng thời
thiếu dấu, sai chính tả, dính chữ và đổi cách diễn đạt nên chưa tách được nguyên
nhân. ViT5 ở 30–40% ở **cả bốn** cách hỏi, cho thấy mô hình chưa học được bài
toán. Cần phép thử riêng cho việc khôi phục dấu tiếng Việt.

![Độ chính xác theo độ khó truy vấn](docs/images/theo-dac-diem-truy-van.png)

`test` có khuôn cơ bản trỏ một mục (301 câu) và khuôn nhiều cạnh (34 câu,
trong đó 30 câu phải liệt kê giá trị):

| Mô hình | Khuôn cơ bản | Khuôn nhiều cạnh | Chênh |
|---|---:|---:|---:|
| T5Gemma-2 | 82,1% | 73,5% | −8,5 |
| mBART | 75,7% | 70,6% | −5,2 |
| BARTpho | 67,8% | 44,1% | −23,7 |
| ViT5 | 51,2% | **0,0%** | −51,2 |

Hai mô hình khá nhất chỉ mất 5 tới 9 điểm ở khuôn nhiều cạnh; BARTpho mất gần
24 điểm, còn ViT5 **không dựng đúng câu nào trong 34 câu**. Sinh SPARQL bằng mô
hình chuỗi-chuỗi không bảo đảm cấu trúc; ràng buộc đầu ra khớp một trong 50 khuôn
có thể xoá nhóm lỗi này.

### 7.5 Độ chính xác câu trả lời `end-to-end`

Ba thước trên đánh giá riêng mô hình sinh truy vấn. Phần này đánh giá
`end-to-end` của lớp giao tiếp sau khi đã chọn mô hình seq2seq tốt nhất.

Mỗi câu trả lời được chính người viết báo cáo soi tay để xác định đúng hoặc sai.
Không có người chấm thứ hai. Phần tự động chỉ dò con số từ hai chữ số trở lên và
chữ viết tắt in hoa, rồi kiểm tra chúng có trong dữ liệu công cụ vừa trả về hay
không. Phép dò này không đọc hiểu nội dung và không xác nhận câu trả lời là đúng.

Phép đo gồm 85 lượt trò chuyện riêng. Trong đó, 60 câu học vụ được lấy ngẫu nhiên
từ `test` và chia đều cho bốn cách hỏi. Có 15 câu mà `test` đánh dấu là ontology
không trả lời được. Còn 10 câu tự viết nhắm vào chỗ ontology còn trống.

Hai câu trong 25 câu ở hai nhóm sau bị gắn nhãn sai. Một câu hỏi về biểu mẫu
chuyển chương trình, câu kia hỏi số điện thoại phòng ban. Ontology có cả hai, nên
nhóm không trả lời được còn 23 câu.

![Chất lượng câu trả lời end-to-end](docs/images/chat-luong-tra-loi.png)

| Điều được đếm | Kết quả |
|---|---|
| Câu học vụ có tra cứu trước khi trả lời | 57/60 (95,0%) |
| Mục cần tìm nằm trong số mục công cụ lấy về | 43/60 (71,7%) |
| Lấy đúng mục cần tìm và không lấy thừa mục nào | 20/60 (33,3%) |
| Câu trả lời không nêu con số hay viết tắt nào ngoài dữ liệu | 59/60 (98,3%) |
| Câu ontology không trả lời được, được nói thẳng là không có | 21/23 (91,3%) |

Bốn hàng về tra cứu, mục lấy về và từ chối được soi tay từng câu. Riêng hàng
"không nêu con số hay viết tắt nào ngoài dữ liệu" là phép dò tự động bổ sung về
mức bám dữ liệu. Vì phép dò không đọc hiểu nội dung và không phát hiện mọi sai
sót, 59/60 chỉ là mức sàn.

71,7% và 33,3% là hai cách đếm: 71,7% chỉ đòi mục cần tìm **có mặt**; trong 43
câu đó, 23 câu có mục thừa. Đếm chặt còn 20/60, so được với 77,9% và thấp hơn
phép đo từng phần. Ba câu không tra cứu đều cụt hoặc quá rộng; trợ lý hỏi lại,
dù `test` tính là sai. Hai câu trả lời sai trong 23 câu ngoài dữ liệu lần lượt
thêm chi tiết không được tra và ghép hai dữ kiện thành quan hệ mới; mục 8.2 phân
tích hai ca này.

### 7.6 Thời gian phản hồi

![Phân bố thời gian phản hồi](docs/images/thoi-gian-phan-hoi.png)

Đo trên 85 lượt ở mục trên, từ lúc gửi câu hỏi đến khi viết xong, từng câu một.
`p95` là mức mà 95 trong 100 câu nhanh hơn.

| | Trung vị | `p95` | Lâu nhất |
|---|---:|---:|---:|
| Toàn bộ 85 câu | 6,5 giây | 10,8 giây | 20,3 giây |
| 76 lượt có tra cứu đồ thị | 6,9 giây | 11,6 giây | 20,3 giây |
| 9 lượt không tra cứu | 1,2 giây | 3,3 giây | 3,3 giây |

Chín lượt không tra cứu chủ yếu là câu ngoài phạm vi rõ ràng hoặc quá cụt. Trong
25 câu âm tính, 19 câu vẫn gọi công cụ trước khi kết luận không có dữ liệu.

Phần máy chủ được đo lại trên 76 lượt tra cứu, bằng máy để bàn tám nhân không
dùng card đồ hoạ:

| Chặng bên trong công cụ | Trung vị | `p95` |
|---|---:|---:|
| Mô hình viết truy vấn (2,4 từ khoá mỗi lượt) | 3,77 giây | 5,66 giây |
| Chạy truy vấn trên đồ thị | 0,02 giây | 1,13 giây |
| **Cả công cụ** | **3,83 giây** | **7,11 giây** |
| Tính riêng cho một từ khoá | 1,83 giây | 1,92 giây |

**Đồ thị không phải chỗ chậm:** đọc đồ thị mất hai phần trăm giây, dưới 1% thời
gian công cụ. Mỗi từ khoá mất khoảng 1,8 giây để viết truy vấn và được xử lý lần
lượt, nên ba từ khoá mất gấp ba lần một từ. Xử lý cùng lúc làm kết quả thay đổi
theo từ khoá đi kèm, nên hệ thống chọn ổn định. Trong khoảng bảy giây chờ, chừng
bốn giây là viết truy vấn và chừng ba giây là hai lượt hỏi mô hình qua mạng.
Trong lượt đầu, 22 trong 85 câu bị chặn vì gửi nhanh; thời gian là của lượt hỏi
thành công.

---

## 8. Phân tích trường hợp trả lời sai

### 8.1 Lỗi của tầng sinh truy vấn

![Lỗi phân theo loại](docs/images/loai-loi.png)

Trên 390 câu của `test`:

| Loại lỗi | T5Gemma-2 | mBART | BARTpho | ViT5 |
|---|---:|---:|---:|---:|
| Trỏ sai mục trong đồ thị | 62 | 93 | 124 | 168 |
| Trả lời câu lẽ ra phải từ chối | 21 | 18 | 21 | 53 |
| Truy vấn thiếu nhánh | 9 | 5 | 11 | 15 |
| Truy vấn thừa nhánh | 3 | 13 | 12 | 0 |
| Từ chối đúng ý nhưng sai câu chuẩn | 2 | 3 | 0 | 0 |
| Từ chối nhầm câu trả lời được | 1 | 3 | 3 | 0 |
| Truy vấn sai cú pháp | 0 | 1 | 1 | 41 |

**Trỏ sai mục áp đảo mọi loại lỗi khác** ở cả bốn mô hình. Sai cú pháp gần như
không xảy ra trừ ViT5. Điều này cho thấy các mô hình học được *hình dạng* của
SPARQL khá dễ, nhưng học được *cái tên phải điền vào* thì khó.

Vài ca sai thật của T5Gemma-2:

| Câu hỏi | Mô hình làm gì | Đáng lẽ |
|---|---|---|
| "Đề nghị hướng dẫn Sinh viên có trách nhiệm cụ thể ra sao." | trỏ tới chính sách trách nhiệm sinh viên | thực thể sinh viên |
| "co nhung dieu gi can hieu khi nhac toi tin chi z?" | trỏ tới thủ tục công nhận tín chỉ | khái niệm tín chỉ |
| "nói chuyện với mình đi ạ?" | chấp nhận và sinh truy vấn | từ chối |
| "Xin hỏi chữ viết tắt DELF tương ứng với tên đầy đủ nào…" | trỏ tới bảng chữ viết tắt, thừa một nhánh | chứng chỉ được hỏi |
| "khá chương trình chuẩn được bao nhiêu v ạ?" | từ chối | trả lời, vì đồ thị có mức học bổng |

Hai ca đầu cùng một dạng: hai mục trong đồ thị có tên gần giống nhau, và mô hình
chọn mục bao quanh thay vì mục được hỏi. Mô hình chọn *thủ tục công nhận tín chỉ* khi
người hỏi muốn biết *tín chỉ* là gì, chọn *chính sách trách nhiệm sinh viên* khi
người hỏi muốn biết về *sinh viên*.

**Nhưng nhóm lỗi lớn nhất lại không hẳn là lỗi của mô hình.** Cùng một thủ tục
học vụ có mặt trong đồ thị dưới ba hình: bản thân thủ tục, biểu mẫu phải nộp, và
mục danh mục để tải biểu mẫu ấy. Trong 74 câu mà T5Gemma-2 chọn sai mục, **21 câu
là chọn nhầm giữa ba hình này**. Trong phần lớn số đó, mô hình trả về đúng cái mục
mà đáp án chuẩn trỏ tới. Hỏi *"đơn xin học trở lại cung cấp biểu mẫu cụ thể ra
sao"*, đáp án chuẩn đòi mục danh mục, còn mô hình đưa ra biểu mẫu. Đó chính là
biểu mẫu mà mục danh mục ấy liên kết tới.

Bộ đáp án chuẩn còn tự mâu thuẫn: câu *"mẫu đơn học song ngành"* được gán đích là
thủ tục, trong khi câu *"đăng ký chương trình thứ hai sao ta"* lại được gán đích
là biểu mẫu; cách gán này ngược với chiều mà chữ nghĩa gợi ra. Không lượng huấn
luyện nào
dạy được mô hình đoán trúng cả hai. Nói cách khác, con số 77,9% ở mục 7.1 đang
thấp hơn năng lực thật, và phần chênh nằm ở cách gán nhãn chứ không ở mô hình.

### 8.2 Lỗi của cả trợ lý

Hai câu trong 23 câu mà đồ thị thực sự không trả lời được đã bị trả lời sai. Cả
hai đều đáng phân tích kỹ vì chúng *không* phải bịa đặt trắng trợn. Dạng bịa đặt
này dễ phát hiện, còn hai dạng dưới đây thì không.

**Ca thứ nhất: ghép hai dữ kiện thành một quan hệ mà không dữ kiện nào nói.**
Được hỏi *"đăng ký môn có ảnh hưởng học bổng của tôi không?"*, trợ lý trả lời
rằng có ảnh hưởng, thông qua điều kiện đăng ký tối thiểu 14 tín chỉ. Điều kiện 14
tín chỉ là thật và có trong dữ liệu. Nhưng đồ thị **không** có quan hệ nhân quả
giữa việc đăng ký môn và việc xét học bổng; trợ lý tự suy ra rồi trình bày như
một quy định.

**Ca thứ hai: thêm một chi tiết đúng nhưng không nằm trong dữ liệu vừa nhận.**
Được hỏi về ảnh hưởng của việc nghỉ học tới học bổng, trợ lý nêu thêm rằng điểm
Giáo dục thể chất và Giáo dục quốc phòng không tính vào điểm xét học bổng. Chi
tiết này có thật trong đồ thị, nhưng lượt tra cứu đó lấy về mục *thủ tục xét học
bổng*, không lấy mục *tiêu chuẩn học bổng* chứa câu ấy. Chi tiết đúng nhưng
không truy ngược được về nguồn đã trả về, nên với người đọc thì không có cách nào
kiểm chứng.

Cùng một bài học từ cả hai ca: **rào chắn phải đặt ở "có nằm trong dữ liệu vừa
nhận không", không phải ở "có đúng không"**. Một câu đúng mà không truy ngược
được vẫn là một câu không kiểm được.

Phép đo còn phát hiện một chuyện đáng nói khác: **hai câu bị gắn nhãn sai, và cả
hai đều bị gắn theo hướng bất lợi cho trợ lý.** Câu *"Đơn xin chuyển Chương trình
đào tạo cung cấp biểu mẫu cụ thể ra sao?"* bị `test` đánh dấu là ngoài
phạm vi, nhưng đồ thị có đúng biểu mẫu ấy kèm đường dẫn tải, và trợ lý trả lời
đúng. Câu *"Số điện thoại của phòng Công tác sinh viên là số nào?"* do chính
người viết báo cáo đặt ra như một câu đồ thị không có, nhưng hoá ra đồ thị có
đúng số điện thoại đó.

Hệ quả: con số 58,2% ở nhóm ngoài phạm vi tại mục 7.3 hơi thấp hơn thực tế. Bộ
câu hỏi `test` cũng phải được soát, không thể mặc định là đúng.

---

## 9. Giao diện

Giao diện là lớp trình bày kết quả tra cứu, không tham gia sinh SPARQL hoặc lưu
dữ kiện. Người dùng thấy một khung chat bình thường; câu trả lời hiện dần theo
từng chữ.

![Trợ lý trả lời kèm nguồn](docs/images/giao-dien.png)

Câu trả lời kèm trích dẫn và đường dẫn tới văn bản gốc để người đọc tự đối chiếu.
Trong 57 câu học vụ tra được dữ liệu ở phép đo trên, 54 câu có đủ cả hai; ba câu
còn lại thiếu đường dẫn hoặc thiếu cả hai.

Trong lúc tra cứu, giao diện hiện đúng những cụm từ khoá mà trợ lý đang gửi cho
công cụ:

![Trạng thái đang tra cứu](docs/images/giao-dien-tra-cuu.png)

Hiện từ khoá đang tra cứu giúp người dùng phát hiện khi trợ lý gửi cả câu hỏi dài
thay vì từ khoá ngắn, khiến công cụ tra không trúng dù câu trả lời cuối vẫn trôi
chảy.

Khi câu hỏi nằm ngoài phạm vi, trợ lý nói thẳng thay vì điền một câu trả lời suy
đoán:

![Trợ lý từ chối câu ngoài phạm vi](docs/images/giao-dien-tu-choi.png)

---

## 10. Hạn chế

Bốn điều dưới đây giới hạn phạm vi của mọi con số trong báo cáo.

**Bộ câu hỏi đóng kín trong chính đồ thị.** Câu hỏi được sinh ra từ đồ thị rồi
chia theo câu hỏi, nên cả 272 câu trả lời đúng khác nhau của `test` đều đã có
mặt ở `train`. Điểm số ở mục 7 vì thế đo khả năng nhận ra một cách
hỏi mới về việc đã học, chứ không đo khả năng xoay xở với một mục hay một dạng
truy vấn chưa từng thấy. Cũng chưa có tập câu hỏi nào do người học thật gõ ra.
Đây là hạn chế lớn nhất.

**Không có mốc dưới, và mỗi mô hình chỉ chạy một lượt.** Bảng so sánh chỉ có bốn
mô hình đã tinh chỉnh, không có mô hình chưa huấn luyện hay một cách dò từ khoá
đơn giản làm mốc, nên chưa biết việc tinh chỉnh đóng góp bao nhiêu. Vì mỗi mô
hình chạy đúng một lượt, không có khoảng tin cậy: kể cả khoảng cách 11,6 điểm
cũng là con số quan sát ở một lượt chạy, và ba mô hình vẫn đang khá lên khi hết
tám lượt.

**Thước đo chặt hơn thực tế ở chỗ này, lỏng hơn ở chỗ kia.** Thước "dựng đúng
khuôn" so với khuôn chuẩn, nên truy vấn viết khác mà vẫn trả về đúng dữ liệu bị
tính sai. Gán nhãn giữa thủ tục, biểu mẫu và mục danh mục không nhất quán, khiến
21 lỗi ở mục 8.1 bị tính nặng hơn thực tế. Ngược lại, phép dò tự động chỉ kiểm
tra con số và chữ viết tắt, không đọc hiểu nội dung; 59/60 vì vậy là mức sàn.

**Phép đo `end-to-end` nhỏ và không tái lập lại được nguyên vẹn.** 85 câu đủ để
thấy xu hướng và bắt được ca hỏng thật, nhưng chưa đủ để báo cáo sai số hẹp. Hai
câu trong đó đã phải loại vì gắn nhãn sai. Dữ liệu công cụ từng lượt không được
lưu cùng kết quả. Việc phân loại đúng hoặc sai do chính người viết báo cáo làm;
không có người chấm thứ hai. LLM có thể cho câu trả lời khác khi hỏi lại. Thời
gian phản hồi chỉ tính lượt hỏi thành công, chưa tính lúc dịch vụ quá tải.

Ngoài các giới hạn của phép đo, ontology hiện chỉ phản ánh 16 văn bản và 50 dạng
câu hỏi; câu hỏi về nội dung chưa có trong ontology phải bị từ chối. Ở lớp giao
tiếp, **38,2% câu ngoài phạm vi vẫn lọt**, **biểu mẫu là lĩnh vực kém nhất**, và
**trợ lý vẫn có thể ghép hai dữ kiện thành một quan hệ mới** như ở mục 8.2.

---

## 11. Hướng cải tiến

Xếp theo mức lợi ích trên công sức, dựa trên chính các số liệu ở trên.

**1. Chuẩn hoá ranh giới giữa thủ tục, biểu mẫu và mục danh mục.** Đây là nhóm
lỗi lớn nhất còn có thể giảm: 21 trong 74 lỗi của mô hình tốt nhất, trong đó phần
lớn câu trả lời hợp lý vẫn bị tính sai. Cần gán nhãn nhất quán theo đối tượng mà
câu hỏi nhắm tới; không cần huấn luyện lại.

**2. Ràng buộc tên mục đầu ra theo ontology.** Trong 74 lỗi có 9 lỗi mô hình sinh
tên không tồn tại. Ràng buộc đầu ra theo danh sách tên trong ontology có thể loại
nhóm lỗi này. Kết hợp với hướng 1, hai thay đổi có thể giảm 30 lỗi mà không đổi
mô hình.

**3. Bổ sung cho ontology các tên mà người học thực sự dùng.** Lỗi trỏ sai mục
vẫn chiếm phần lớn lỗi còn lại; biểu mẫu yếu nhất vì tên hành chính khác tên
người học dùng. Bổ sung tên gọi thay thế cho từng mục ít tốn kém hơn đổi mô hình.

**4. Dựng bộ câu hỏi `test` thật sự mới.** Đây là ưu tiên khoa học cao nhất vì xử
lý hạn chế lớn nhất ở mục 10. Bộ mới cần có câu hỏi mà đáp án chưa từng xuất hiện
trong `train`, cùng một tập câu hỏi do người học gõ ra. Khi đó mới biết hệ thống
làm được gì với nội dung chưa gặp.

**5. Lặp lại phép huấn luyện, và học tới khi không khá lên được nữa.** Chạy lại mỗi mô hình vài lượt
sẽ cho phép công bố khoảng thay vì một con số đơn lẻ. Cho ba mô hình còn lại học
tới khi ngừng cải thiện sẽ giúp bảng so sánh phản ánh khả năng mô hình thay vì
thời gian đã cấp. Cả hai đều tốn máy, nên xếp sau cùng.

Hai hướng nhỏ hơn cũng có số liệu hỗ trợ: khôi phục dấu tiếng Việt trước khi đưa
câu cho mô hình, vì nhóm gõ nhiễu chiếm 35 trong 74 lỗi; và ràng buộc đầu ra theo
50 khuôn đã khai báo để loại lỗi thiếu nhánh và thừa nhánh.
