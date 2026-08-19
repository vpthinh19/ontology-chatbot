# Chatbot hỏi đáp học vụ dựa trên ontology

Trợ lý trả lời câu hỏi học vụ của Trường Đại học Nha Trang bằng dữ kiện đọc từ
một đồ thị tri thức, kèm trích dẫn về văn bản gốc, và từ chối khi đồ thị không
có câu trả lời.

---

## Tóm tắt

Chatbot học vụ thường được dựng bằng cách đưa văn bản quy chế cho một mô hình
ngôn ngữ lớn rồi để nó tự trả lời. Cách đó cho câu văn trôi chảy nhưng không ai
kiểm được câu trả lời đúng hay sai, và mô hình có thói quen lấp chỗ trống bằng
suy đoán nghe rất thuyết phục.

Công trình này tách đôi trách nhiệm. **Đồ thị tri thức giữ dữ kiện**, mỗi dữ kiện
gắn ngược về đúng Điều, Khoản, Điểm đã sinh ra nó. **Mô hình ngôn ngữ lớn giữ
việc diễn đạt**, và nó chỉ được nói những gì đồ thị vừa đưa cho. Cầu nối giữa hai
bên là một **mô hình chuỗi-chuỗi** — loại mô hình nhận vào một chuỗi chữ và viết
ra một chuỗi chữ khác, giống như một máy dịch. Ở đây nó "dịch" cụm từ khoá tiếng
Việt sang truy vấn SPARQL, tức là ngôn ngữ dùng để hỏi một đồ thị tri thức. Bốn
mô hình như vậy được đem so trong công trình này, và mỗi mô hình được **tinh
chỉnh**: lấy một mô hình đã học sẵn tiếng người, rồi dạy thêm cho nó riêng việc
viết truy vấn.

Bốn mô hình chuỗi-chuỗi cùng học trên một bộ dữ liệu gồm 6.308 câu hỏi, trong đó
5.518 câu dùng để dạy, và cùng được chấm bằng một bộ thước đo. **T5Gemma-2 thắng
rõ rệt**: nó chọn đúng mục cần tra trong đồ thị ở 77,9% số câu, dựng đúng khuôn
truy vấn ở 81,2%, và quyết định đúng giữa trả lời và từ chối ở 91,0%.

Trợ lý hoàn chỉnh chạy trên mô hình đó được đo tiếp trên 85 câu hỏi, lần này
chạy hết cả đường từ lúc người dùng gõ tới lúc câu trả lời viết xong. Trong 60
câu học vụ, 59 câu không nêu ra một con số hay chữ viết tắt nào mà dữ liệu vừa
tra không có. Trong 23 câu mà đồ thị thực sự không trả lời được, 21 câu được nói
thẳng là không có. Một nửa số câu được trả lời trong vòng sáu giây rưỡi.

Ba điều cần nói ngay để không đọc quá lời:

- Đồ thị hiện có 16 văn bản và 50 dạng câu hỏi. Ngoài phạm vi đó, câu trả lời
  đúng duy nhất là "tôi không có thông tin này".
- Dữ liệu được chia theo câu hỏi, nên điểm số đo **khả năng hiểu một cách hỏi
  mới về việc đã biết**. Đo khả năng xoay xở với mục chưa từng thấy là một thí
  nghiệm khác, công trình này chưa làm.
- Mỗi mô hình chỉ chạy một lượt, và ba trong bốn mô hình vẫn đang khá lên khi
  hết ngân sách huấn luyện. Chỉ nên tin những khoảng cách lớn.

---

## 1. Bài toán

Quy chế là văn bản đặt ra quy tắc đào tạo. Thủ tục học vụ là chuỗi điều kiện, hồ
sơ và bước mà người học phải thực hiện. Quanh hai loại nội dung đó còn có biểu
mẫu, học phí, chứng chỉ ngoại ngữ và nhiều bảng tra cứu.

Người học không hỏi theo cách văn bản viết. Họ hỏi *"nghỉ ngang một kỳ có sao
không ạ"* chứ không hỏi *"thủ tục nghỉ học tạm thời"*. Họ gõ thiếu dấu, viết tắt,
hỏi cụt lủn, hoặc hỏi hai chuyện trong một câu. Hệ thống phải hiểu đúng ý định,
tìm đúng mục trong đồ thị, và chỉ lấy dữ kiện có nguồn.

Hai ràng buộc chi phối toàn bộ thiết kế:

1. **Câu trả lời trong phạm vi phải bám vào văn bản của trường.** Không được lấy
   quy định của trường khác, dù mô hình ngôn ngữ lớn có "nhớ" quy định đó.
2. **Câu ngoài phạm vi phải bị từ chối rõ ràng.** Một câu trả lời sai về hạn nộp
   đơn gây hại hơn hẳn một câu "tôi không có thông tin này".

Vì vậy đây không phải bài toán sinh văn bản. Đây là bài toán sinh truy vấn có
ràng buộc, cộng với việc quyết định khi nào **không** nên trả lời.

---

## 2. Tổng quan hệ thống

Người học nói chuyện với một mô hình ngôn ngữ lớn. Mô hình đó không được phép tự
trả lời câu hỏi học vụ; muốn biết dữ kiện thì phải gọi công cụ tra cứu, và công
cụ chỉ trả về những gì đọc được từ đồ thị.

![Luồng xử lý một câu hỏi](docs/images/luong-xu-ly.png)

Ba tầng, mỗi tầng làm đúng một việc:

| Tầng | Ai làm | Trách nhiệm |
|---|---|---|
| Hội thoại | Mô hình ngôn ngữ lớn | Hiểu câu hỏi, rút thành từ khoá, viết câu trả lời cuối |
| Tra cứu | Mô hình chuỗi-chuỗi đã tinh chỉnh | Biến từ khoá thành truy vấn SPARQL |
| Dữ kiện | Đồ thị tri thức | Giữ nội dung và nguồn, trả về đúng những gì được hỏi |

Hai điểm trong thiết kế đáng nêu vì chúng quyết định chất lượng:

**Công cụ nhận một danh sách từ khoá, không nhận cả câu hỏi.** Mô hình
chuỗi-chuỗi được dạy trên những cụm ngắn, còn người học thì viết câu dài và lịch
sự. Cho mô hình ngôn ngữ lớn gửi vài cách gọi của cùng một chủ đề trong một lần
tra — đo được là thường hai tới ba cụm — thì việc "thử vài cách gọi" gói gọn
trong một lượt, thay vì tra đi tra lại. Người hỏi và đồ thị hay gọi cùng một thứ
bằng hai cái tên khác nhau, nên gửi kèm cách gọi thứ hai làm tăng khả năng trúng.

**Truy vấn phải thuộc một trong 50 dạng đã khai báo.** Một câu truy vấn đúng ngữ
pháp vẫn có thể ghép một mục với một thuộc tính mà không dạng nào cho phép; nó
chạy trót lọt và trả về dữ liệu mà câu hỏi không hề hỏi. Truy vấn nào không khớp
dạng nào thì bị bỏ, và công cụ coi như tra không ra.

---

## 3. Ontology

Ontology là mô hình khái niệm mô tả các thực thể học vụ, thuộc tính và quan hệ
giữa chúng. Ở đây nó đóng vai cơ sở dữ liệu duy nhất mà mọi truy vấn đọc.

![Lược đồ ontology học vụ](docs/images/so-do-ontology.png)

Đồ thị có **hai tầng, cả hai đều trả lời được trực tiếp**:

- **Tầng văn bản** giữ nguyên văn công văn, chia theo Chương → Điều → Khoản →
  Điểm, cộng Phụ lục và Bảng. Người hỏi *"điểm a khoản 2 Điều 15 nói gì"* được
  trả lời từ tầng này.
- **Tầng tri thức** giữ dữ kiện đã bóc tách: thủ tục, bước thực hiện, điều kiện,
  thời hạn, biểu mẫu, ngành đào tạo, chứng chỉ. Người hỏi *"nghỉ tạm thời cần
  làm gì"* được trả lời từ tầng này.

Mỗi dữ kiện ở tầng tri thức trỏ ngược về phần văn bản nhỏ nhất chứng minh nó.
Nhờ vậy câu trả lời nào cũng kèm được trích dẫn và đường dẫn để người đọc tự đối
chiếu.

| Thành phần | Quy mô |
|---|---:|
| Phát biểu trong tệp ontology | 6.355 |
| Phát biểu trong đồ thị lúc chạy | 7.711 |
| Lớp khái niệm | 56 |
| Mục cụ thể (cá thể) | 686 |
| Quan hệ giữa hai thực thể | 29 |
| Thuộc tính mang giá trị chữ hoặc số | 55 |
| Văn bản gốc đã số hoá | 16 |

Con số lúc chạy cao hơn con số trong tệp vì khi nạp, hệ thống dựng thêm cho mỗi
mục trả lời được một bản ghi nguồn gọn — nhờ đó mọi truy vấn lấy trích dẫn theo
cùng một cách, thay vì mỗi dạng câu hỏi tự đi tìm nguồn một kiểu.

Nội dung được bóc tách từ 16 văn bản chính thức của nhà trường, gồm sáu quyết
định của Hiệu trưởng — **Quyết định 1052** ban hành Quy chế đào tạo trình độ đại
học, **Quyết định 317** ban hành Quy chế tuyển sinh, cùng các Quyết định 626,
729, 753 và 1965 — ba quy chế kèm theo, và bảy trang thông tin chính thức về học
phí, học bổng, tuyển sinh và cơ cấu tổ chức. Không có kho dữ liệu song song nào khác, nên
mọi dữ kiện mà công cụ lấy ra đều mang sẵn nguồn trỏ về một trong 16 văn bản
này. Việc trợ lý có chép lại nguồn đó vào câu trả lời hay không lại là chuyện
khác — mục 9 nêu con số đo được.

---

## 4. Hình dạng dữ liệu

Một câu hỏi đổi hình sáu lần trên đường đi. Biết mỗi bước nhận gì và trả gì là
cách nhanh nhất để hiểu hệ thống, và cũng là cách nhanh nhất để tìm ra chỗ hỏng.

![Hình dạng dữ liệu qua từng bước](docs/images/hinh-dang-du-lieu.png)

### 4.1 Một dòng dữ liệu huấn luyện

Mỗi dòng dữ liệu là một cặp: một câu hỏi tiếng Việt, và câu truy vấn đúng mà mô
hình phải viết ra khi gặp câu hỏi đó. Kèm theo là mã số của dòng, tên dạng câu
hỏi, và nhãn cho biết câu được viết theo cách nói nào. Với câu ngoài phạm vi,
đích không phải truy vấn mà là đúng một dòng chữ: "không có thông tin".

Dưới đây là một dòng thật, thuộc loại trả lời được. Câu hỏi gõ không dấu, và
đích là câu truy vấn hỏi đồ thị về cố vấn học tập:

```json
{
  "id": "question-000013",
  "query_id": "academic-actor-facts",
  "register": "noisy",
  "input": "co van hoc tap la ai",
  "target": "SELECT ?thuoctinh ?giatri ?nguon ?duongdan WHERE { { :AcademicAdvisor ?p ?giatri . FILTER(isLiteral(?giatri)) ?p rdfs:label ?thuoctinh OPTIONAL{:AcademicAdvisor :sourceCitation ?nguon;:sourceLink ?duongdan} } UNION { :AcademicAdvisor ?l ?con . ?con ?p ?giatri . FILTER(isLiteral(?giatri)) ?p rdfs:label ?thuoctinh OPTIONAL{?con :sourceCitation ?nguon;:sourceLink ?duongdan} } FILTER(?p!=skos:altLabel&&?p!=:sourceCitation&&?p!=:sourceLink) }"
}
```

Và một dòng thật thuộc loại phải từ chối:

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

Công cụ luôn trả về kết quả theo một khuôn cố định, kể cả khi không tìm thấy gì.
Khuôn đó gồm bốn phần: một dòng cho biết có dữ liệu hay không, một dòng dặn mô
hình phải dùng kết quả thế nào, danh sách các nguồn, và danh sách những cụm từ
khoá tra không ra gì.

Điểm đáng chú ý nhất trong khuôn này: **mỗi dữ kiện nằm bên trong chính cái
nguồn đã khẳng định nó**, chứ không nằm rời ra rồi trỏ tới nguồn bằng một mã số.
Nhờ vậy mô hình không có cách nào gán nhầm một con số cho một văn bản khác — hai
thứ đi liền nhau trong cùng một khối. Còn danh sách cụm tra không ra thì để mô
hình biết cụm nào trượt, khỏi tra lại cả loạt.

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

Khi không cụm từ khoá nào khớp, khuôn trả về vẫn y hệt, chỉ khác ở chỗ dòng đầu
báo là không có thông tin và danh sách nguồn rỗng. Mô hình đọc dòng đó để quyết
định thử thêm một lần với cách gọi khác, hay dừng lại và nói là không tìm thấy.

---

## 5. Tập dữ liệu

![Từ văn bản gốc tới điểm số](docs/images/luong-du-lieu.png)

Dữ liệu không được viết tay từng dòng. Nó được sinh ra từ chính đồ thị, theo ba
bước. Trước hết, người làm rút ra 50 dạng thông tin mà đồ thị trả lời được — ví
dụ "các bước của một thủ tục", "điều kiện của một thủ tục", "biểu mẫu cần nộp".
Với mỗi dạng, hệ thống lấy từng mục cụ thể trong đồ thị thuộc dạng ấy. Cuối
cùng, mỗi mục sinh ra bốn câu hỏi viết theo bốn cách nói khác nhau.

Cách làm này có một ưu điểm và một nhược điểm, cả hai đều đáng nói. Ưu điểm: câu
trả lời đúng luôn là một truy vấn chạy được, và không câu nào trỏ tới thứ không
tồn tại — không có chuyện dạy mô hình một đáp án sai. Nhược điểm: dữ liệu đóng
kín trong chính đồ thị, nên nó chưa kiểm được mô hình xoay xở thế nào với những
thứ nằm ngoài. Mục 10 nói kỹ về hệ quả của nhược điểm này.

![Thành phần bộ dữ liệu](docs/images/bo-du-lieu.png)

| Phần dữ liệu | Số dòng | Vai trò |
|---|---:|---|
| Tập dạy | 5.518 | Học ánh xạ từ câu hỏi sang truy vấn hoặc từ chối |
| Tập kiểm định | 400 | Theo dõi quá trình học, chọn điểm dừng |
| Tập chấm | 390 | Đánh giá cuối, sau khi mọi lựa chọn đã cố định |
| **Toàn bộ** | **6.308** | |

Dữ liệu được chia **theo câu hỏi**: không một câu hỏi nào ở phần đem chấm hay
phần kiểm định từng xuất hiện ở phần đem dạy. Đổi lại, ba phần dùng chung kho câu
trả lời đúng — đồ thị chỉ trả lời được 567 thứ khác nhau, nên 390 câu đem chấm
tất yếu rơi vào những đáp án mà 5.518 câu đem dạy đã phủ.

Đây là một lựa chọn thiết kế, và nó quyết định phải đọc điểm số ra sao. Cách chia
này đo **khả năng hiểu một cách hỏi mới về việc đã biết** — đúng tình huống thật,
khi người học hỏi đi hỏi lại về mười sáu văn bản ấy bằng vô số cách diễn đạt.
Cách chia còn lại, giữ hẳn một số mục không cho mô hình thấy lúc học, đo một năng
lực khác: xoay xở với thứ chưa từng gặp. Đó là thí nghiệm riêng, và công trình
này chưa làm.

Dữ liệu phủ **50 dạng câu hỏi** và **567 câu trả lời đúng khác nhau** — gồm 566
câu truy vấn, cộng một câu từ chối dùng chung cho mọi câu ngoài phạm vi. Một nửa số câu hỏi
dài từ 10 từ trở xuống, trung bình là 11,2 từ; câu ngắn nhất vỏn vẹn 1 từ, câu
dài nhất 33 từ.

Trong toàn bộ dữ liệu có **884 câu phải từ chối**, chiếm 14,0% — chia ra 773 câu
ở phần đem dạy, 56 câu ở phần kiểm định và 55 câu ở phần đem chấm. Tỷ lệ này được chọn để mô hình có đủ ví dụ học ranh giới mà
không biến việc từ chối thành phản xạ mặc định; công trình chưa thử các tỷ lệ
khác nên chưa biết đây có phải mức tốt nhất không.

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

Bốn mô hình chuỗi-chuỗi của bốn tổ chức, cùng giải một bài. Chúng khác nhau về
quy mô, về ngôn ngữ được huấn luyện trước và về kiến trúc, nên bảng so sánh cho
biết bài toán này thực sự cần gì.

Vài chữ cần hiểu trước khi đọc bảng. **Tham số** là các con số bên trong mô
hình, thứ quyết định nó cư xử ra sao; càng nhiều tham số thì mô hình càng có sức
chứa lớn, và cũng càng tốn máy. Khi tinh chỉnh, công trình không sửa toàn bộ
tham số của mô hình nền mà chỉ gắn thêm một **lớp mỏng** rồi chỉ dạy riêng lớp
ấy — vừa nhanh hơn, vừa giữ nguyên được những gì mô hình đã biết.

| Mô hình | Tổ chức | Tham số mô hình nền | Tham số thực sự được học |
|---|---|---:|---:|
| T5Gemma-2 (`google/t5gemma-2-270m-270m`) | Google | 786 M | 15,2 M |
| mBART (`facebook/mbart-large-cc25`) | Meta AI | 611 M | 17,3 M |
| BARTpho (`vinai/bartpho-syllable`) | VinAI | 396 M | 17,3 M |
| ViT5 (`VietAI/vit5-base`) | VietAI | 226 M | 13,0 M |

Cột cuối cho thấy phần được tinh chỉnh rất nhỏ so với mô hình nền: từ 1,9%
(T5Gemma-2) đến 5,7% (ViT5). Trọng số nền giữ nguyên; chỉ một lớp thích ứng mỏng
được học.

### 6.2 Điều kiện chạy

Bốn mô hình được đặt vào **hoàn toàn cùng một điều kiện**, để chênh lệch kết quả
chỉ có thể đến từ bản thân mô hình:

- **Cùng một bộ dữ liệu**, không mô hình nào được thấy thêm hay bớt câu nào.
- **Cùng tám lượt học.** Một lượt học là một lần mô hình đọc hết toàn bộ phần
  dữ liệu đem dạy.
- **Cùng một điểm khởi đầu ngẫu nhiên.** Việc học có dùng số ngẫu nhiên; cố định
  điểm khởi đầu này là điều kiện cần để người khác chạy lại được thí nghiệm.
  Công trình chưa chạy lặp để kiểm chứng kết quả có trùng khít hay không.
- **Cùng cách viết câu trả lời.** Ở mỗi chữ, mô hình luôn chọn phương án nó cho
  là khả dĩ nhất chứ không bốc thăm, nên cùng một câu hỏi cho ra cùng một truy
  vấn.
- **Cùng một máy**: card đồ hoạ 24 GB.

Điểm dừng không chọn theo số lượt học mà theo kết quả trên phần dữ liệu kiểm
định: khi mô hình bắt đầu học thuộc thay vì học hiểu, kết quả trên phần này xấu
đi, và bản tốt nhất trước đó được giữ lại. Phần dữ liệu đem chấm chỉ được chạm
đúng một lần, sau khi mọi lựa chọn đã cố định — nếu chạm nhiều lần, nó không còn
là phép thử độc lập nữa.

### 6.3 Ba chỉ số chính

**Chọn đúng mục trong đồ thị.** Truy vấn mà mô hình viết ra có trỏ tới đúng mục
mà câu hỏi nhắm tới hay không. Đây là thước đo quan trọng nhất, vì trỏ sai mục
thì mọi thứ phía sau đều sai, dù câu truy vấn có đẹp đến đâu. Cách chấm rất
nghiêm: tập mục mà truy vấn trỏ tới phải trùng khít tập mục đúng — lấy đúng mục
cần tìm nhưng kèm thêm một mục thừa vẫn bị tính là sai.

**Dựng đúng khuôn truy vấn.** Trong 50 dạng câu hỏi đã khai báo, mỗi dạng có một
khuôn truy vấn chuẩn với vài chỗ trống phải điền. Thước này hỏi: mô hình có nhận
ra đúng dạng, và có điền đúng những chỗ trống ấy không — trừ chỗ trống dành cho
tên mục, vì đó là việc của thước thứ nhất. Đây là phép so với khuôn chuẩn: một
câu truy vấn viết cách khác mà vẫn cho ra cùng kết quả vẫn bị tính là sai. Chỉ
tính trên câu trong phạm vi.

**Quyết định trả lời hay từ chối.** Với câu trong phạm vi, đúng nghĩa là mô hình
viết ra một truy vấn thuộc một trong 50 dạng đã khai báo. Với câu ngoài phạm vi,
đúng nghĩa là mô hình viết ra **đúng** câu từ chối chuẩn. Cách chấm này chặt hơn
hành vi thật của hệ thống một chút: một đầu ra khác câu chuẩn nhưng vẫn dẫn tới
việc không trả lời gì thì vẫn bị tính là sai. Đây là thước duy nhất tính cả câu
trong lẫn ngoài phạm vi.

Ba thước được tách riêng có chủ đích. Gộp lại thành một điểm tổng thì một mô
hình từ chối bừa vẫn có thể được điểm cao, và không ai biết nó hỏng ở khâu nào.

Ngoài ba thước trên, phép đánh giá còn tính mức trùng khớp giữa bảng kết quả mà
truy vấn của mô hình trả về và bảng kết quả đúng. Những con số đó **chỉ dùng để
dò lỗi**, không được dùng làm kết quả chính, vì chúng cho điểm từng phần: một
truy vấn lấy về đủ dữ liệu cần nhưng kèm nhiều dòng thừa vẫn được điểm khá cao.

---

## 7. Kết quả thực nghiệm

### 7.1 Bảng so sánh bốn mô hình

![Ba chỉ số chính trên tập chấm](docs/images/so-sanh-mo-hinh.png)

Kết quả trên **tập chấm** (390 câu, chỉ chạm một lần):

| Mô hình | Chọn đúng mục | Đúng dạng truy vấn | Từ chối đúng | Bộ nhớ card lúc đỉnh | Thời gian huấn luyện | Tốc độ chấm |
|---|---:|---:|---:|---:|---:|---:|
| **T5Gemma-2** | **77,9%** | **81,2%** | 91,0% | 9,19 GiB | 29,8 phút | 0,46 s/câu |
| mBART | 66,3% | 75,2% | 88,7% | 10,46 GiB | 24,7 phút | 0,23 s/câu |
| BARTpho | 55,2% | 65,4% | **91,8%** | 3,18 GiB | 15,1 phút | 0,18 s/câu |
| ViT5 | 33,7% | 46,0% | 74,4% | 3,53 GiB | 19,0 phút | 0,41 s/câu |

Kết quả trên **tập kiểm định** (400 câu, dùng trong lúc phát triển):

| Mô hình | Chọn đúng mục | Đúng dạng truy vấn | Từ chối đúng |
|---|---:|---:|---:|
| **T5Gemma-2** | **81,7%** | **84,0%** | **96,8%** |
| mBART | 70,9% | 75,9% | 93,0% |
| BARTpho | 59,0% | 69,5% | 94,2% |
| ViT5 | 34,3% | 45,1% | 73,8% |

![Ba chỉ số chính trên tập kiểm định](docs/images/so-sanh-mo-hinh-kiem-dinh.png)

Ba nhận xét:

**T5Gemma-2 dẫn đầu ở năm trong sáu cột của hai bảng.** Cột duy nhất nó không
dẫn đầu là cột từ chối trên tập chấm, nơi BARTpho hơn nó 0,8 điểm — và ngay cột
đó thì trên tập kiểm định T5Gemma-2 lại hơn BARTpho 2,5 điểm, tức thứ hạng ở cột
này đảo qua đảo lại tuỳ tập. Ở hai cột còn lại thì khoảng cách rất rộng: hơn mô
hình thứ hai 11,6 điểm ở việc chọn đúng mục.

**BARTpho từ chối tốt nhất nhưng vẫn thua chung cuộc.** Nó đạt 91,8% ở cột từ
chối, hơn T5Gemma-2 0,8 điểm, trong khi thua 22,7 điểm ở cột chọn đúng mục. Đây
chính là lý do không gộp ba chỉ số thành một điểm: chọn theo một cột thì chọn
nhầm mô hình.

**Thứ hạng trùng khít với quy mô mô hình, nên thí nghiệm này chưa tách được hai
nguyên nhân.** Xếp theo tham số mô hình nền: 786 M > 611 M > 396 M > 226 M — đúng
bằng thứ hạng kết quả, không sai một bậc. Vì vậy không thể kết luận T5Gemma-2
thắng nhờ kiến trúc hay nhờ dữ liệu huấn luyện trước; nó cũng đơn giản là mô hình
lớn nhất. Muốn tách hai nguyên nhân thì phải so các mô hình cùng cỡ.

Điều bảng này **có** cho biết: BARTpho được huấn luyện trước riêng cho tiếng
Việt, nhưng vẫn xếp sau hai mô hình đa ngữ lớn hơn. Ở bài toán sinh truy vấn,
"chuyên tiếng Việt" không tự nó thắng — phần khó nằm ở việc chọn đúng tên mục
trong đồ thị, không nằm ở việc hiểu tiếng Việt.

![Chính xác đổi lấy bộ nhớ và thời gian](docs/images/danh-doi.png)

Nếu phần cứng eo hẹp, BARTpho cho 55,2% với 3,18 GiB và 15 phút huấn luyện —
bằng một phần ba bộ nhớ và một nửa thời gian của T5Gemma-2. Đó là mức đánh đổi
rõ ràng, không phải một lựa chọn tệ.

### 7.2 Diễn biến huấn luyện

![Hao hụt trên tập dạy](docs/images/hao-hut-hoc.png)

![Hao hụt trên tập kiểm định](docs/images/hao-hut-kiem-dinh.png)

Hai đồ thị này theo dõi mức sai của mô hình sau mỗi lượt học. Đường đi xuống
nghĩa là mô hình đang khá lên. Trục dọc co lại theo bậc để nhìn được cả đoạn tụt
rất nhanh lúc đầu lẫn đoạn đi ngang về sau.

**Chỉ T5Gemma-2 ngừng khá lên trước khi hết giờ.** Mức sai của nó trên phần kiểm
định thấp nhất ở lượt thứ năm rồi đi ngang ở mức cao hơn suốt ba lượt cuối, nên
bản được giữ lại là bản sau lượt thứ năm chứ không phải bản cuối. Ba mô hình còn
lại vẫn đang khá dần lên khi hết tám lượt, nên bản được giữ là bản cuối; kết quả
của chúng phải đọc là "đạt được trong ngần ấy thời gian học", không phải "khả
năng tối đa".

Cả bốn lượt chạy đều kết thúc vì chạm trần tám lượt đã đặt sẵn. Vì vậy chưa lượt
nào trả lời được câu hỏi các mô hình còn khá lên tới đâu nếu được học lâu hơn.

### 7.3 Kết quả theo lĩnh vực

Bảng dưới tách kết quả của T5Gemma-2 theo lĩnh vực câu hỏi. Nó cho biết nên bổ
sung dữ liệu ở đâu.

| Lĩnh vực | Số câu | Chọn đúng mục | Đúng dạng | Từ chối đúng |
|---|---:|---:|---:|---:|
| Quy chế đào tạo | 131 | 84,7% | 87,8% | 97,7% |
| Học phí | 25 | 84,0% | 84,0% | 96,0% |
| Tra cứu văn bản | 57 | 78,9% | 86,0% | 96,5% |
| Chứng chỉ ngoại ngữ | 31 | 77,4% | 77,4% | 90,3% |
| Thủ tục học vụ | 49 | 69,4% | 73,5% | 93,9% |
| Biểu mẫu | 42 | 61,9% | 64,3% | 100,0% |
| Ngoài phạm vi | 55 | — | — | 58,2% |

**Biểu mẫu là chỗ yếu nhất** (61,9%). Tên biểu mẫu trong đồ thị là mã hành chính
— "Mẫu số 5", "Phụ lục 4" — còn người học gọi bằng công dụng — "đơn xin chuyển
ngành". Hai cách gọi này xa nhau về mặt chữ nghĩa hơn hẳn các lĩnh vực khác.

**Câu ngoài phạm vi khó nhất** (58,2%). Con số này không mâu thuẫn với cột "từ
chối đúng" 91,0% ở bảng tổng: 91,0% tính trên cả 390 câu, mà phần lớn là câu
trong phạm vi, nơi mô hình chỉ cần không từ chối nhầm.

Riêng nhóm 55 câu ngoài phạm vi thì phải phân biệt ba con số. Mô hình phát ra
đúng nguyên văn câu từ chối chuẩn ở 32 câu — **58,2%**, đó là con số trong bảng.
Hai câu nữa nó viết ra truy vấn, nhưng truy vấn chạy về rỗng nên hệ thống vẫn
không đưa ra dữ kiện nào: tính theo hành vi thật thì **34/55 = 61,8% bị chặn**.
Số câu thực sự lọt — được trả lời trong khi lẽ ra phải từ chối — là **21/55 =
38,2%**.

### 7.4 Kết quả theo cách hỏi và độ khó truy vấn

![Độ chính xác theo phong cách](docs/images/theo-phong-cach.png)

| Mô hình | Trang trọng | Trung tính | Thân mật | Gõ nhiễu |
|---|---:|---:|---:|---:|
| T5Gemma-2 | 84,7% | 91,9% | 76,8% | **57,3%** |
| mBART | 83,5% | 76,7% | 64,6% | **39,0%** |
| BARTpho | 67,1% | 61,6% | 51,2% | **40,2%** |
| ViT5 | 32,9% | 39,5% | 30,5% | 31,7% |

**Câu gõ nhiễu là chỗ tụt sâu nhất.** Ở ba mô hình khá nhất, nhóm này kéo kết
quả xuống **26,8 tới 44,5 điểm** so với cách hỏi mà chính mô hình đó làm tốt
nhất: T5Gemma-2 rơi từ 91,9% xuống 57,3%, mBART rơi từ 83,5% xuống 39,0%,
BARTpho rơi từ 67,1% xuống 40,2%. Câu thân mật nhưng đủ dấu chỉ mất 15,0 tới
18,9 điểm, tức dễ hơn hẳn.

Nhóm gõ nhiễu khác ba nhóm kia ở nhiều điểm cùng lúc — thiếu dấu, sai chính tả,
dính chữ, và cả cách diễn đạt — nên số liệu này chưa tách được riêng phần lỗi do
việc thiếu dấu gây ra.

ViT5 là ngoại lệ, và ngoại lệ ấy nói lên điều khác: nó nằm quanh 30–40% ở **cả
bốn** cách hỏi. Một mô hình kém đều như vậy không kém vì cách người ta hỏi; nó
chưa học được bài toán.

Hướng đáng thử trước tiên là chuẩn hoá đầu vào: khôi phục dấu tiếng Việt trước
khi đưa câu cho mô hình. Nó rẻ hơn hẳn việc huấn luyện lại, nhưng phải có một
phép thử riêng mới biết nó lấy lại được bao nhiêu trong khoảng tụt trên.

![Độ chính xác theo độ khó truy vấn](docs/images/theo-dac-diem-truy-van.png)

Tập chấm có hai dạng truy vấn: khuôn cơ bản trỏ tới một mục (301 câu), và khuôn
phải đi qua nhiều cạnh của đồ thị (34 câu, trong đó 30 câu còn phải liệt kê giá
trị). Kết quả không giống dự đoán thông thường:

| Mô hình | Khuôn cơ bản | Khuôn nhiều cạnh | Chênh |
|---|---:|---:|---:|
| T5Gemma-2 | 82,1% | 73,5% | −8,5 |
| mBART | 75,7% | 70,6% | −5,2 |
| BARTpho | 67,8% | 44,1% | −23,7 |
| ViT5 | 51,2% | **0,0%** | −51,2 |

**Khuôn khó không phải bức tường chung — nó là chỗ phân loại mô hình.** Hai mô
hình khá nhất chỉ mất 5 tới 9 điểm khi phải dựng truy vấn nhiều cạnh, tức là
chúng thực sự học được khuôn đó. BARTpho mất gần 24 điểm, còn ViT5 **không dựng
đúng nổi một câu nào trong 34 câu** — nó chỉ thuộc được khuôn phổ biến nhất.

Đây cũng là giới hạn của cách sinh truy vấn bằng mô hình chuỗi-chuỗi: mô hình
viết ra cả câu SPARQL như viết một câu văn, nên không có gì bảo đảm cấu trúc
đóng mở đúng. Ép mô hình chỉ được viết ra những truy vấn khớp một trong 50 khuôn đã khai báo
sẽ xoá hẳn nhóm lỗi này.

### 7.5 Độ chính xác câu trả lời đầu-cuối

Ba thước ở trên chấm mô hình chuỗi-chuỗi khi nó được đưa sẵn câu hỏi. Trợ lý
thật không chạy như vậy: từ khoá do mô hình ngôn ngữ lớn tự rút ra, và câu trả
lời cuối cũng do nó viết. Phần này đo **cả hệ thống**, từ lúc người dùng gõ câu
hỏi tới lúc đọc được câu trả lời.

Phép đo gồm 85 câu, mỗi câu là một lượt trò chuyện riêng với trợ lý đang phục
vụ. Chia ba nhóm:

- **60 câu học vụ mà đồ thị trả lời được**, lấy ngẫu nhiên từ phần dữ liệu đem
  chấm, chia đều cho bốn cách hỏi.
- **15 câu mà phần dữ liệu đem chấm đánh dấu là đồ thị không trả lời được.**
- **10 câu tự viết, nhắm đúng vào những chỗ đồ thị còn trống** — hỏi những điều
  nghe rất hợp lý nhưng đồ thị không hề có, chẳng hạn chuẩn ngoại ngữ đầu ra
  của riêng một ngành, hay học phí một năm của riêng một ngành.

Soi lại từng câu thì **hai câu trong 25 câu ở hai nhóm sau bị gắn nhãn sai**:
một câu hỏi biểu mẫu của thủ tục chuyển chương trình, và một câu hỏi số điện
thoại của một phòng ban — đồ thị có cả hai. Chúng bị loại khỏi nhóm này thay vì
được tính là thành công, nên nhóm câu đồ thị thực sự không trả lời được còn 23
câu.

![Chất lượng câu trả lời đầu-cuối](docs/images/chat-luong-tra-loi.png)

| Điều được đếm | Kết quả |
|---|---|
| Câu học vụ có tra cứu trước khi trả lời | 57/60 — 95,0% |
| Mục cần tìm nằm trong số mục công cụ lấy về | 43/60 — 71,7% |
| Lấy đúng mục cần tìm và không lấy thừa mục nào | 20/60 — 33,3% |
| Câu trả lời không nêu con số hay viết tắt nào ngoài dữ liệu | 59/60 — 98,3% |
| Câu đồ thị không trả lời được, được nói thẳng là không có | 21/23 — 91,3% |

**Cách chấm.** Phần trung thực chạy tự động: mọi con số từ hai chữ số trở lên và
mọi chữ viết tắt in hoa trong câu trả lời được dò xem có mặt trong dữ liệu công
cụ vừa trả về hay không. Phép dò này chỉ bắt được chi tiết dạng con số và tên
viết tắt, không kiểm được ý nghĩa, nên 59/60 là mức sàn chứ không phải bằng
chứng câu trả lời hoàn toàn trung thực. Phần phân loại — câu trả lời có nói rõ
là dữ liệu không có hay không — thì soi tay từng câu, do chính người viết báo
cáo làm, không có người chấm thứ hai.

**Ba con số cần đọc kỹ:**

*71,7% và 33,3% là hai cách đếm cùng một việc.* Con số 71,7% chỉ đòi mục cần tìm
**có mặt** trong những mục công cụ lấy về; trong 43 câu đó, 23 câu còn lấy kèm
mục thừa. Đếm chặt — lấy đúng và không thừa gì — thì còn 20/60. Con số chặt này
mới so được với 77,9% ở bảng trên, vì đó cũng là cách chấm nghiêm; nó cho biết
đo cả hệ thống thì kết quả thấp hơn đo từng phần.

*Ba câu không tra cứu.* Cả ba đều cụt hoặc quá rộng — *"Sinh viên thế nào ạ?"*,
*"Trường Đại học Nha Trang?"*, và một câu nhắc tới *"quy định này"* mà không kèm
tên văn bản nào. Trợ lý hỏi lại cho rõ thay vì đoán. Phần dữ liệu đem chấm tính
đây là sai vì nó chờ một truy vấn; xét theo cách một người trực tư vấn sẽ làm
thì hỏi lại mới đúng.

*Hai câu trả lời sai trong 23 câu đồ thị không có dữ liệu.* Một câu thêm một chi
tiết có thật trong đồ thị nhưng không nằm trong dữ liệu vừa tra; một câu ghép hai
dữ kiện thành một quan hệ mà không dữ kiện nào nói. Cả hai đều không phải bịa
trắng trợn, và mục 8.2 phân tích kỹ vì đó mới là dạng nguy hiểm.

### 7.6 Thời gian phản hồi

![Phân bố thời gian phản hồi](docs/images/thoi-gian-phan-hoi.png)

Đo trên chính 85 lượt trò chuyện ở mục trên, tính từ lúc gửi câu hỏi tới lúc câu
trả lời viết xong. Phép đo hỏi từng câu một, không gửi chồng nhau, để con số
không bị ảnh hưởng bởi việc nhiều câu tranh nhau cùng một máy. Cột "chậm hơn 95%
số câu" nghĩa là: 95 trong 100 câu được trả lời nhanh hơn mức đó.

| | Trung vị | Chậm hơn 95% số câu | Lâu nhất |
|---|---:|---:|---:|
| Toàn bộ 85 câu | 6,5 giây | 10,8 giây | 20,3 giây |
| 76 lượt có tra cứu đồ thị | 6,9 giây | 11,6 giây | 20,3 giây |
| 9 lượt không tra cứu | 1,2 giây | 3,3 giây | 3,3 giây |

Chín lượt không tra cứu chủ yếu là câu hỏi ngoài phạm vi rõ ràng và câu quá cụt,
trợ lý trả lời thẳng trong hơn một giây. **Phần lớn câu ngoài phạm vi vẫn được
tra cứu trước:** trong 25 câu thuộc hai nhóm âm tính, 19 câu trợ lý gọi công cụ
rồi mới kết luận là không có dữ liệu — đó là hành vi đúng, vì phần lớn những câu
ấy nghe như câu học vụ bình thường.

Phần chạy trên máy chủ được đo riêng, bằng cách chạy lại đúng 76 lượt tra cứu
thật ở trên, trên máy để bàn tám nhân và không dùng card đồ hoạ:

| Chặng bên trong công cụ | Trung vị | Chậm hơn 95% số lượt |
|---|---:|---:|
| Mô hình viết truy vấn (2,4 từ khoá mỗi lượt) | 3,77 giây | 5,66 giây |
| Chạy truy vấn trên đồ thị | 0,02 giây | 1,13 giây |
| **Cả công cụ** | **3,83 giây** | **7,11 giây** |
| Tính riêng cho một từ khoá | 1,83 giây | 1,92 giây |

**Đồ thị không phải chỗ chậm.** Việc đọc dữ liệu từ đồ thị chỉ mất hai phần trăm
giây, chưa tới 1% thời gian của công cụ. Gần như toàn bộ thời gian nằm ở khâu mô
hình chuỗi-chuỗi viết ra câu truy vấn: mỗi từ khoá khoảng 1,8 giây, và các từ
khoá được xử lý lần lượt, nên tra ba từ khoá tốn gấp ba lần tra một từ.

Việc xử lý lần lượt là lựa chọn có chủ đích. Nếu gộp các từ khoá lại xử lý cùng
lúc thì kết quả của một từ khoá sẽ đổi theo những từ khoá đi kèm — hiện tượng đã
đo được, do cách máy tính làm tròn khi xử lý nhiều câu một lượt. Câu trả lời cho
*"học bổng"* không được phép khác đi chỉ vì người dùng hỏi kèm *"học phí"*, nên
hệ thống chấp nhận chậm hơn để đổi lấy sự ổn định.

Ghép hai phép đo lại: trong khoảng bảy giây người dùng chờ, chừng bốn giây là
máy chủ viết truy vấn, chừng ba giây là hai lượt hỏi mô hình ngôn ngữ lớn qua
mạng. Muốn nhanh hơn thì phải rút ngắn khâu viết truy vấn — chạy trên card đồ
hoạ, hoặc làm cho câu truy vấn cần viết ra ngắn lại — chứ không phải tối ưu đồ
thị.

Trong lượt chạy đầu, 22 trong 85 câu bị nhà cung cấp mô hình ngôn ngữ lớn chặn
vì gửi quá nhanh; chúng được hỏi lại và đồng hồ tính từ đầu cho lần thành công.
Các con số trên vì thế là thời gian của một lượt hỏi trót lọt.

---

## 8. Phân tích trường hợp trả lời sai

### 8.1 Lỗi của tầng sinh truy vấn

![Lỗi phân theo loại](docs/images/loai-loi.png)

Trên 390 câu của tập chấm:

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
không xảy ra trừ ViT5 — nghĩa là các mô hình học được *hình dạng* của SPARQL khá
dễ, nhưng học được *cái tên phải điền vào* thì khó.

Vài ca sai thật của T5Gemma-2:

| Câu hỏi | Mô hình làm gì | Đáng lẽ |
|---|---|---|
| "Đề nghị hướng dẫn Sinh viên có trách nhiệm cụ thể ra sao." | trỏ tới chính sách trách nhiệm sinh viên | thực thể sinh viên |
| "co nhung dieu gi can hieu khi nhac toi tin chi z?" | trỏ tới thủ tục công nhận tín chỉ | khái niệm tín chỉ |
| "nói chuyện với mình đi ạ?" | chấp nhận và sinh truy vấn | từ chối |
| "Xin hỏi chữ viết tắt DELF tương ứng với tên đầy đủ nào…" | trỏ tới bảng chữ viết tắt, thừa một nhánh | chứng chỉ được hỏi |
| "khá chương trình chuẩn được bao nhiêu v ạ?" | từ chối | trả lời, vì đồ thị có mức học bổng |

Hai ca đầu cùng một dạng: hai mục trong đồ thị có tên gần giống nhau, và mô hình
chọn mục bao quanh thay vì mục được hỏi — chọn *thủ tục công nhận tín chỉ* khi
người hỏi muốn biết *tín chỉ* là gì, chọn *chính sách trách nhiệm sinh viên* khi
người hỏi muốn biết về *sinh viên*.

**Nhưng nhóm lỗi lớn nhất lại không hẳn là lỗi của mô hình.** Cùng một thủ tục
học vụ có mặt trong đồ thị dưới ba hình: bản thân thủ tục, biểu mẫu phải nộp, và
mục danh mục để tải biểu mẫu ấy. Trong 74 câu mà T5Gemma-2 chọn sai mục, **21 câu
là chọn nhầm giữa ba hình này** — và phần lớn số đó, mô hình trả về đúng cái mục
mà đáp án chuẩn trỏ tới. Hỏi *"đơn xin học trở lại cung cấp biểu mẫu cụ thể ra
sao"*, đáp án chuẩn đòi mục danh mục, mô hình đưa ra biểu mẫu — chính là biểu mẫu
mà mục danh mục ấy liên kết tới.

Bộ đáp án chuẩn còn tự mâu thuẫn: câu *"mẫu đơn học song ngành"* được gán đích là
thủ tục, trong khi câu *"đăng ký chương trình thứ hai sao ta"* lại được gán đích
là biểu mẫu — ngược đúng chiều mà chữ nghĩa gợi ra. Không lượng huấn luyện nào
dạy được mô hình đoán trúng cả hai. Nói cách khác, con số 77,9% ở mục 7.1 đang
thấp hơn năng lực thật, và phần chênh nằm ở cách gán nhãn chứ không ở mô hình.

### 8.2 Lỗi của cả trợ lý

Hai câu trong 23 câu mà đồ thị thực sự không trả lời được đã bị trả lời sai. Cả
hai đều đáng phân tích kỹ, vì chúng *không* phải bịa đặt trắng trợn — dạng bịa
trắng trợn dễ phát hiện, còn hai dạng dưới đây thì không.

**Ca thứ nhất — ghép hai dữ kiện thành một quan hệ mà không dữ kiện nào nói.**
Được hỏi *"đăng ký môn có ảnh hưởng học bổng của tôi không?"*, trợ lý trả lời
rằng có ảnh hưởng, thông qua điều kiện đăng ký tối thiểu 14 tín chỉ. Điều kiện 14
tín chỉ là thật và có trong dữ liệu. Nhưng đồ thị **không** có quan hệ nhân quả
giữa việc đăng ký môn và việc xét học bổng; trợ lý tự suy ra rồi trình bày như
một quy định.

**Ca thứ hai — thêm một chi tiết đúng nhưng không nằm trong dữ liệu vừa nhận.**
Được hỏi về ảnh hưởng của việc nghỉ học tới học bổng, trợ lý nêu thêm rằng điểm
Giáo dục thể chất và Giáo dục quốc phòng không tính vào điểm xét học bổng. Chi
tiết này có thật trong đồ thị — nhưng lượt tra cứu đó lấy về mục *thủ tục xét học
bổng*, không lấy mục *tiêu chuẩn học bổng* chứa câu ấy. Chi tiết đúng nhưng
không truy ngược được về nguồn đã trả về, nên với người đọc thì không có cách nào
kiểm chứng.

Cùng một bài học từ cả hai ca: **rào chắn phải đặt ở "có nằm trong dữ liệu vừa
nhận không", không phải ở "có đúng không"**. Một câu đúng mà không truy ngược
được vẫn là một câu không kiểm được.

Phép đo còn phát hiện một chuyện đáng nói khác: **hai câu bị gắn nhãn sai, và cả
hai đều bị gắn theo hướng bất lợi cho trợ lý.** Câu *"Đơn xin chuyển Chương trình
đào tạo cung cấp biểu mẫu cụ thể ra sao?"* bị dữ liệu chấm đánh dấu là ngoài
phạm vi, nhưng đồ thị có đúng biểu mẫu ấy kèm đường dẫn tải, và trợ lý trả lời
đúng. Câu *"Số điện thoại của phòng Công tác sinh viên là số nào?"* do chính
người viết báo cáo đặt ra như một câu đồ thị không có, nhưng hoá ra đồ thị có
đúng số điện thoại đó.

Hệ quả: con số 58,2% ở nhóm ngoài phạm vi tại mục 7.3 hơi thấp hơn thực tế. Và
một bài học chung — bộ câu hỏi dùng để chấm cũng phải được soát, không thể mặc
định là nó đúng.

---

## 9. Giao diện

Người dùng thấy một khung chat bình thường. Câu trả lời hiện dần theo từng chữ.

![Trợ lý trả lời kèm nguồn](docs/images/giao-dien.png)

Câu trả lời kết thúc bằng trích dẫn và đường dẫn tới văn bản gốc, để người đọc
tự đối chiếu chứ không phải tin lời trợ lý. Đây là mục tiêu thiết kế và nó gần
đạt chứ chưa tuyệt đối: trong 57 câu học vụ tra được dữ liệu ở phép đo trên, 54
câu có đủ cả trích dẫn lẫn đường dẫn; ba câu còn lại nêu được tên văn bản nhưng
thiếu đường dẫn, hoặc thiếu cả hai.

Trong lúc tra cứu, giao diện hiện đúng những cụm từ khoá mà trợ lý đang gửi cho
công cụ:

![Trạng thái đang tra cứu](docs/images/giao-dien-tra-cuu.png)

Đây không phải chi tiết trang trí. Chỗ hỏng khó thấy nhất của kiến trúc này là
trợ lý gửi cả câu hỏi dài thay vì từ khoá ngắn, công cụ tra trượt, mà câu trả lời
cuối vẫn trôi chảy nên không ai biết. Hiện từ khoá ra là cách rẻ nhất để nhìn
thấy điều đó.

Khi câu hỏi nằm ngoài phạm vi, trợ lý nói thẳng thay vì điền một câu trả lời suy
đoán:

![Trợ lý từ chối câu ngoài phạm vi](docs/images/giao-dien-tu-choi.png)

---

## 10. Hạn chế

Bốn điều dưới đây giới hạn phạm vi của mọi con số trong báo cáo.

**Bộ câu hỏi đóng kín trong chính đồ thị.** Câu hỏi được sinh ra từ đồ thị rồi
chia theo câu hỏi, nên cả 273 câu trả lời đúng khác nhau của phần đem chấm đều
đã có mặt ở phần đem dạy. Điểm số ở mục 7 vì thế đo khả năng nhận ra một cách
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
khuôn" so với khuôn chuẩn chứ không so kết quả, nên một truy vấn viết khác mà
vẫn trả về đúng dữ liệu vẫn bị tính sai; cách gán nhãn giữa thủ tục, biểu mẫu và
mục danh mục lại không nhất quán, khiến 21 lỗi ở mục 8.1 bị tính nặng hơn thực
tế. Ngược lại, phép đo trung thực của câu trả lời chỉ dò được con số và chữ viết
tắt, không đọc hiểu nội dung, nên 59/60 là mức sàn.

**Phép đo đầu-cuối nhỏ và không tái lập lại được nguyên vẹn.** 85 câu đủ để thấy
xu hướng và bắt được ca hỏng thật, chưa đủ để báo cáo sai số hẹp — và hai câu
trong đó đã phải loại vì gắn nhãn sai. Dữ liệu công cụ trả về từng lượt không
được lưu cùng kết quả; việc phân loại đúng sai do chính người viết báo cáo làm,
không có người chấm thứ hai. Mô hình ngôn ngữ lớn cũng không cho kết quả cố
định, nên hỏi lại có thể ra câu trả lời khác. Thời gian phản hồi tính trên lượt
hỏi trót lọt, chưa tính lúc dịch vụ quá tải.

Về hệ thống, ba chỗ yếu còn lại đã nêu bằng số ở trên: **38,2% câu ngoài phạm vi
vẫn lọt**, **biểu mẫu là lĩnh vực kém nhất**, và **trợ lý vẫn có thể ghép hai dữ
kiện thành một quan hệ mới** như hai ca ở mục 8.2. Ngoài ra kết quả chỉ phản ánh
16 văn bản và 50 dạng câu hỏi hiện có: câu hỏi về điều chưa đưa vào đồ thị vẫn
phải bị từ chối, kể cả khi nhà trường thực sự có quy định đó.

---

## 11. Hướng cải tiến

Xếp theo mức lợi ích trên công sức, dựa trên chính các số liệu ở trên.

**1. Gỡ chỗ mơ hồ giữa thủ tục, biểu mẫu và mục danh mục.** Đây là nhóm lỗi lớn
nhất còn chữa được: 21 trong 74 lỗi của mô hình tốt nhất, và phần lớn trong số đó
mô hình trả lời hợp lý mà vẫn bị tính sai. Việc cần làm là quyết định dứt khoát
câu hỏi nào nhắm tới hình nào, rồi gán lại nhãn cho nhất quán. Không cần huấn
luyện lại.

**2. Buộc mô hình chỉ được gọi tên mục có thật trong đồ thị.** Trong 74 lỗi ấy có
9 lỗi mô hình viết ra một cái tên không tồn tại. Ràng buộc lúc sinh chữ theo đúng
danh sách tên của đồ thị xoá hẳn nhóm này. Cùng với việc trên, hai thay đổi này
chữa 30 lỗi mà không đụng tới mô hình.

**3. Dạy đồ thị các tên mà người học thực sự dùng.** Lỗi trỏ sai mục vẫn chiếm
phần lớn số lỗi còn lại, và biểu mẫu là lĩnh vực kém nhất vì tên hành chính của
biểu mẫu khác hẳn tên mà người học gọi nó. Bổ sung tên gọi thay thế cho từng mục
rẻ hơn nhiều so với đổi mô hình.

**4. Dựng một bộ câu hỏi kiểm tra thật sự mới.** Đây là việc quan trọng nhất về
mặt khoa học, vì nó vá đúng hạn chế lớn nhất nêu ở mục 10. Cần hai thứ: một phần
câu hỏi mà câu trả lời đúng chưa từng xuất hiện lúc dạy, và một tập câu hỏi do
chính người học gõ ra. Chỉ khi đó mới biết hệ thống làm được gì trước những điều
nó chưa gặp. Đi kèm là một mốc dưới — một phương pháp dò từ khoá không huấn
luyện, chấm bằng đúng bộ chỉ số này — để biết việc tinh chỉnh đóng góp bao nhiêu.

**5. Chạy lại mỗi mô hình vài lượt và cho ba mô hình còn lại học tới khi hết khá
lên.** Việc đầu cho phép công bố một khoảng thay vì một con số trần trụi; việc
sau khiến bảng so sánh nói về khả năng của các mô hình thay vì về lượng thời gian
đã bỏ ra. Cả hai đều tốn máy, nên xếp sau cùng.

Hai hướng nhỏ hơn đã có số liệu đỡ lưng: khôi phục dấu tiếng Việt trước khi đưa
câu cho mô hình, vì nhóm gõ nhiễu chiếm 35 trong 74 lỗi; và ràng buộc đầu ra theo
đúng 50 khuôn đã khai báo, để xoá nhóm lỗi thiếu nhánh và thừa nhánh.
