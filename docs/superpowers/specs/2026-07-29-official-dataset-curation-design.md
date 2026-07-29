# Biên soạn dataset chính thức bằng các agent độc lập

## Mục tiêu

Xây dataset chính thức cho chatbot ontology từ ontology và query catalogue đã
khóa. Dataset phải dạy một model seq2seq thực hiện trọn quyết định:

- câu được ontology hỗ trợ → sinh một SPARQL `SELECT` canonical;
- câu không được hỗ trợ → sinh chính xác `không có thông tin`.

Chất lượng được ưu tiên hơn số lượng. Quy mô cuối được quyết định bằng độ phủ
và lỗi quan sát được, không bằng một con số đặt trước. Nhiều agent được dùng để
tăng tốc và cô lập ngữ nghĩa, nhưng không agent nào được tự sửa dataset chính
thức hoặc tự duyệt dữ liệu do mình viết.

## Nguồn sự thật và phạm vi

Nguồn dữ kiện duy nhất là:

- `resources/ontology/ontology.ttl`;
- `resources/dataset/main/catalogue.jsonl`;
- các tài liệu chính thức đã được ontology dẫn nguồn.

`test.html`, `resources/cases/user_queries.txt` và các phiên test tay chỉ cung
cấp cách diễn đạt của người dùng. Chúng không được dùng làm nguồn dữ kiện học
vụ. Preprocessing chỉ chuẩn hóa biến thể chắc nghĩa, gồm quyết định
`hp → học phần`; nó không suy luận intent, IRI hoặc SPARQL.

Catalogue hiện có 51 họ truy vấn. Trong đó có 19 slot IRI hữu hạn, tương ứng
khoảng 307 trường hợp neo IRI trước khi tính các trường hợp số và giá trị biên.
455 câu hiện có chỉ là candidate pool, mới phủ 24/51 họ; từng câu phải được giữ,
sửa hoặc loại sau audit, không tự động trở thành dữ liệu chính thức.

## Ba lớp dữ liệu

Quá trình biên soạn tách thành ba lớp:

```text
ontology + query catalogue
            │
            ▼
coverage ledger: danh sách những gì bắt buộc phải dạy
            │
            ▼
shard độc lập: dữ liệu ứng viên được viết và kiểm tra theo miền
            │
            ▼
train.jsonl + val.jsonl + test.jsonl chính thức
```

### Coverage ledger

Coverage ledger là bảng công việc sinh xác định từ catalogue, không phải input
của model. Mỗi mục theo dõi:

- `query_id` và miền;
- IRI hữu hạn hoặc nhóm trường hợp số cần phủ;
- split và register cần có;
- số câu đã viết, đã kiểm tra, bị loại và còn thiếu.

Các query số phải có giá trị thông thường, giá trị sát các ngưỡng và giá trị
không hợp lệ. Ledger phải mô tả các ca bắt buộc này bằng giá trị cụ thể trước
khi biên soạn câu hỏi; agent không tự chọn ngưỡng theo trí nhớ.

### Shard biên soạn

Trong quá trình làm việc, dữ liệu được tách theo miền:

```text
staging/
├── procedure/
├── tuition-academic-rule/
├── certificate-form-document/
└── out-of-domain/
```

Mỗi shard có ba split và dùng cùng năm trường của dataset cuối:
`id`, `query_id`, `register`, `input`, `target`. ID trong staging được đặt theo
miền để không xung đột. Metadata kiểm tra và nhóm OOD nằm ở báo cáo phụ, không
làm phình schema input của model.

Agent chỉ sửa shard được giao. Không agent nào được sửa ontology, catalogue,
shard khác hoặc ba split chính thức. Staging là tài nguyên xây dựng tạm thời;
sau nghiệm thu chỉ giữ những báo cáo cần cho khả năng tái lập và tài liệu công
khai.

### Dataset chính thức

Agent chính hợp nhất các shard đã duyệt, đánh lại ID và tạo ba split canonical.
`manifest.json`, checksum và báo cáo phân bố phải được sinh từ file thật sau
lần kiểm tra cuối, không điền tay.

## Phân công agent

Ba agent biên soạn làm việc độc lập:

1. **Quy trình**: quy trình, chính sách và quan hệ với biểu mẫu.
2. **Học phí và quy tắc**: học phí, thanh toán và quy tắc học vụ định lượng.
3. **Chứng chỉ và văn bản**: chứng chỉ, quy đổi, biểu mẫu độc lập và metadata
   văn bản có thể trả lời.

Agent chính phụ trách coverage ledger, OOD, câu người dùng thực tế, hợp nhất và
nghiệm thu toàn cục. Sau vòng biên soạn, các agent đổi miền để kiểm tra chéo;
tác giả không tự duyệt shard của mình.

Mỗi agent nhận một prompt độc lập chỉ chứa contract, miền được giao, file được
phép sửa và kết quả phải bàn giao. Agent không cần kế thừa toàn bộ lịch sử trò
chuyện. Cách này giảm nhiễu ngữ nghĩa và ngăn một giả định sai lan ra mọi miền.

## Quy trình ba lượt

### Lượt 1: kiểm kê

1. Sinh coverage ledger từ 51 họ catalogue.
2. Chỉ rõ mọi target hữu hạn phải có trong train.
3. Chỉ rõ các ca số thường, sát biên và không hợp lệ.
4. Audit 455 candidate hiện tại theo ba quyết định `keep`, `revise`, `drop`.
5. Lập danh sách câu người dùng thật cần gán nhãn và hồi quy.

Lượt này không viết hàng loạt câu hỏi. Mục đích là khóa danh sách công việc để
không thể đạt số lượng lớn nhưng vẫn bỏ sót ontology.

### Lượt 2: biên soạn

Mỗi câu phải thỏa cả ba điều kiện:

1. dữ kiện chỉ đến từ ontology;
2. cách diễn đạt tự nhiên và phù hợp register;
3. target khớp đúng một họ catalogue và thực thi được.

Train chứa mọi IRI, operator, dạng SPARQL và ranh giới từ chối cần dùng trong
production. Validation và test kiểm tra cách diễn đạt mới cho những chức năng
đã được dạy; chúng không giữ lại schema chưa từng xuất hiện trong train.

Bốn register gồm `formal`, `neutral`, `colloquial` và `noisy`. Câu noisy chỉ
được chấp nhận nếu người Việt vẫn có thể hiểu một cách hợp lý. Không tạo dữ
liệu bằng việc ghép từ đồng nghĩa hoặc hoán đổi template hàng loạt. Script chỉ
được dùng để kiểm tra, thống kê, hợp nhất xác định và sinh checksum.

### Lượt 3: kiểm tra chéo và hợp nhất

Reviewer đọc lại toàn bộ shard của agent khác theo hai trục:

- **đúng nghĩa**: câu hỏi thực sự tương ứng target và ranh giới ontology;
- **chất lượng ngôn ngữ**: tự nhiên, độc lập giữa split và đúng register.

Bản ghi chưa chắc chắn được đưa vào khu vực cách ly kèm lý do. Nó không được tự
động gán nhãn hoặc hợp nhất. Lỗi được trả về đúng agent tác giả để sửa; reviewer
kiểm tra lại sau mỗi vòng sửa.

## Độ phủ trong miền

Ma trận đích là:

```text
query family × target instance × register × split
```

Các yêu cầu bắt buộc:

- đủ 51 họ trong train, validation và test;
- mọi target hữu hạn và dạng SPARQL production xuất hiện trong train;
- mọi family có đủ bốn register trong train;
- các quy trình học vụ trọng tâm có đủ bốn register trong từng split;
- validation/test có các operator và kiểu kết quả đã học, nhưng dùng câu chữ
  độc lập;
- các target số có ca thường, sát biên và không hợp lệ;
- câu tổng quát, câu hỏi một khía cạnh, câu nhiều điều kiện và câu nhiều kết
  quả được phủ khi ontology trả lời trọn vẹn.

Không ấn định tổng số câu. Dataset dừng tăng khi ma trận không còn vùng trắng
quan trọng và vòng chẩn đoán model không còn chỉ ra thiếu hụt có hệ thống.

## Ngoài miền và ranh giới từ chối

OOD lớn theo độ đa dạng hành vi, không theo tỷ lệ cố định. Bảy nhóm bắt buộc:

1. chào hỏi và trò chuyện xã hội;
2. chủ đề không liên quan;
3. gần miền học vụ nhưng ontology thiếu dữ liệu;
4. mơ hồ hoặc thiếu anchor bắt buộc;
5. noisy nhưng vẫn nhận ra là ngoài miền;
6. câu hỗn hợp có ít nhất một nhánh không được hỗ trợ;
7. hard negative dùng đúng từ khóa học vụ nhưng hỏi quan hệ không tồn tại.

Mỗi nhóm có bốn register trong cả ba split. Mỗi họ truy vấn trong miền phải có
ca ranh giới gần đúng nhưng không thể trả lời, để model học phạm vi dữ liệu thay
vì chỉ học từ khóa. Câu hỗn hợp không được trả lời một phần; toàn bộ target là
`không có thông tin`.

Số OOD chỉ tăng khi ma trận còn thiếu hoặc chẩn đoán cho thấy false acceptance
ở một nhóm cụ thể. Không cân bằng bằng cách thêm câu vô nghĩa dễ phân biệt, và
không để OOD áp đảo khiến model từ chối quá mức.

## Câu người dùng thật

Mọi input có ý nghĩa trong `test.html`, `resources/cases/user_queries.txt` và
các phiên test tay phải được gán nhãn dựa trên ontology hiện tại. Câu nguyên bản
được giữ làm ca hồi quy; train nhận các cách diễn đạt tương đương, không sao
chép nguyên câu test.

Nếu một câu thật được đưa vào split chính thức, toàn bộ câu gần trùng của nó
phải nằm cùng split. Nguồn câu thật không cấp quyền thêm dữ kiện hoặc capability
mới vào catalogue.

## Kiểm soát chất lượng

Trước khi hợp nhất, mọi bản ghi phải vượt các kiểm tra sau:

1. schema, ID, `query_id` và register hợp lệ;
2. target trong miền khớp catalogue;
3. SPARQL parse, vượt contract an toàn, chạy trên ontology và trả đúng kiểu dữ
   liệu;
4. target ngoài miền trùng chính xác `không có thông tin`;
5. không trùng sau preprocessing giữa các split;
6. không có câu gần trùng cùng ý định nằm ở hai split;
7. câu qua tokenizer production mà không hỏng token cấu trúc hoặc bị cắt;
8. coverage ledger không còn mục bắt buộc chưa phủ;
9. mọi shard đã được reviewer khác duyệt;
10. không còn bản ghi lỗi nghiêm trọng trong khu vực cách ly.

Validator tự động không thay thế kiểm tra nghĩa. Một target chạy được vẫn có thể
sai nếu câu hỏi không cùng ý nghĩa với target.

## Vòng phản hồi từ model

Sau khi dataset vượt cổng dữ liệu, thực hiện một lần fine-tuning chẩn đoán theo
giao thức đã khóa. Phân tích lỗi theo `query_id`, register, target instance và
nhóm OOD. Chỉ bổ sung đúng vùng thiếu có bằng chứng từ train/validation hoặc bộ
ca chẩn đoán.

Test chính thức được đóng băng trước vòng nghiệm thu cuối. Không sửa dataset,
chọn checkpoint hoặc dò tham số bằng kết quả test. Sau khi dataset ổn định mới
đánh giá System Answer Exact cùng các chỉ số trong miền, marker exact, false
acceptance và từ chối câu hỗn hợp. Mục tiêu hệ thống là System Answer Exact lớn
hơn 90%, nhưng không dùng con số tổng để che một miền lỗi nghiêm trọng.

## Tiêu chí hoàn tất

Dataset chính thức hoàn tất khi:

- mọi yêu cầu coverage trong và ngoài miền đều đạt;
- candidate cũ và câu người dùng thật đều có quyết định rõ ràng;
- mọi kiểm tra tự động vượt qua;
- kiểm tra chéo không còn lỗi nghiêm trọng;
- manifest, checksum và báo cáo được sinh lại từ release thật;
- vòng fine-tuning chẩn đoán không còn chỉ ra lỗ hổng coverage có hệ thống;
- tài liệu công khai mô tả trạng thái thật, không lộ staging hoặc lịch sử phát
  triển không cần thiết.

Fine-tuning chẩn đoán ở trên chỉ là cổng phát hiện lỗ hổng bằng train/validation;
không phải kết quả nghiên cứu cuối. Chỉ sau cổng này mới chạy fine-tuning và
benchmark nghiệm thu trên test đã đóng băng. Không merge nhánh trước khi
dataset, code liên quan và tài liệu đồng bộ hoàn toàn.
