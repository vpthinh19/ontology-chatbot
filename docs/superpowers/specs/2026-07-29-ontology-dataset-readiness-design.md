# Nghiệm thu ontology và xây dataset chính thức

> **Trạng thái triển khai:** Cổng 1 đã hoàn tất với ontology canonical và
> `resources/ontology/answer_inventory.json`. Cổng 2 và Cổng 3 chưa hoàn tất;
> catalogue cùng 455 câu hiện tại vẫn là candidate pool.

## Mục tiêu

Khóa lại trạng thái đúng của dự án trước khi tiếp tục huấn luyện:

- ontology hiện tại là graph được dựng từ nguồn chính thức nhưng chưa được coi
  là canonical cho đến khi lớp chỉ mục ngữ nghĩa được rà xong;
- 455 câu hiện tại là nguồn ứng viên phục vụ smoke và curation, không phải
  dataset production chính thức;
- catalogue và dataset chính thức phải được suy ra từ toàn bộ dữ liệu quan
  trọng mà ontology có thể trả lời, với các quy trình học vụ là trọng tâm;
- một model seq2seq duy nhất tiếp tục sinh SPARQL hoặc marker
  `không có thông tin`.

Không full fine-tune, benchmark ba model, chuyển CTranslate2 hoặc nghiệm thu web
trước khi hoàn tất các cổng ontology, catalogue và dataset trong đặc tả này.

## Nguồn sự thật

Ontology chỉ dùng các nguồn sau:

- `NTUdocs/Qd1052.md`;
- `NTUdocs/Qd729.md`;
- `NTUdocs/huong_dan_dong_hoc_phi.md`;
- `NTUdocs/bieumau_url.txt`;
- `bieumau_url.html` cho tiêu đề và URL tải biểu mẫu.

`test.html` và `test_preprocess.py` không phải nguồn dữ kiện học vụ. Chúng chỉ
là nguồn quan sát cách người dùng hỏi và hành vi chuẩn hóa đã từng hữu ích.

## Trạng thái đã kiểm chứng

Lớp nguồn của `resources/ontology/ontology.ttl` đã có nền tảng tốt:

- 32 điều và Phụ lục 1–3 của Quyết định 1052;
- dữ liệu học phí và 41 ngành của Quyết định 729;
- hướng dẫn thanh toán và danh mục tải biểu mẫu;
- 414 literal `officialText@vi` đối chiếu được với đúng nguồn sau chuẩn hóa;
- mọi class, property và named individual có `rdfs:label@vi`;
- các bảng định lượng và quy đổi chứng chỉ có provenance trực tiếp.

Kết quả này xác nhận lớp nguồn, không tự động xác nhận lớp chỉ mục ngữ nghĩa
hoặc phạm vi câu hỏi production.

## Cổng 1: ontology canonical

Ontology chỉ được khóa IRI sau khi có một audit machine-readable gồm ba phần.

### Trung thành với nguồn

1. Mọi literal nghiệp vụ khớp một đoạn trong nguồn chính thức sau chuẩn hóa.
2. Mọi quy trình, quy tắc và dữ liệu số có `sourceDocument` và
   `sourceProvision` hợp lệ.
3. Không có dữ kiện suy đoán, nội dung cũ không có nguồn hoặc URL ghép sai.
4. Label tiếng Việt, IRI tiếng Anh và language tag tuân thủ quy ước hiện tại.

### Đúng vai trò ngữ nghĩa

Mỗi liên kết `eligibilityProvision`, `instructionProvision`,
`deadlineProvision` và `resultProvision` phải được đọc lại trong văn bản nguồn.
Không dùng một provision làm “kết quả” chỉ vì nó nằm gần quy trình.

Các khoảng trống đã biết phải được quyết định rõ:

- Điều 30 về nghỉ ốm đối với nghỉ học, nghỉ học tạm thời và hoãn thi;
- Điều 29 về học liên thông;
- Điều 20 về cảnh báo kết quả học tập và buộc thôi học;
- vai trò `resultProvision` của `ClassAbsenceRequestProcedure`;
- property không có dữ liệu như `documentUrl`.

Một khoảng trống có thể được xử lý bằng cách thêm chỉ mục ngữ nghĩa, dùng trực
tiếp provision nguồn hoặc ghi quyết định không hỗ trợ. Không được im lặng bỏ
qua rồi để catalogue quyết định ngược lại phạm vi ontology.

### Inventory khả năng trả lời

Tạo inventory từ graph, trong đó mỗi mục ghi:

- chủ đề/thực thể người dùng có thể nhắc tới;
- dữ liệu cuối cùng được phép trả: label, literal hoặc giá trị tổng hợp;
- đường SPARQL từ anchor tới dữ liệu;
- provenance;
- trạng thái `supported` hoặc `excluded` kèm lý do.

Inventory là cầu nối bắt buộc giữa ontology và catalogue. Số triple hoặc số
individual không được dùng thay cho độ phủ câu hỏi.

## Cổng 2: catalogue SPARQL

Catalogue chính thức phải phủ mọi mục `supported` trong inventory. Validator
phải kiểm tra theo chiều:

```text
ontology inventory → catalogue → train/validation/test
```

Không chấp nhận cách kiểm tra vòng tròn trong đó catalogue tự liệt kê một tập
IRI nhỏ rồi validator chỉ xác nhận dataset phủ đúng tập nhỏ đó.

Catalogue cần ưu tiên:

1. toàn bộ khía cạnh có nguồn của các quy trình học vụ;
2. học phí chuẩn và kiểm định theo ngành, khối ngành, khóa, loại học phần và
   trình độ;
3. biểu mẫu, URL tải và quan hệ biểu mẫu–quy trình;
4. quy tắc học lực, năm đào tạo, tốt nghiệp và quy mô lớp;
5. mọi ngữ cảnh quy đổi chứng chỉ: chương trình chuẩn, chương trình đặc biệt,
   ngành Ngôn ngữ Anh, miễn học và chuẩn đầu ra;
6. actor/quyền quyết định khi nguồn thật sự cung cấp câu trả lời.

Mỗi template phải parse, an toàn, chạy có kết quả trên ontology và chỉ project
label/literal/giá trị tổng hợp. Template động phải có test biên cho mọi nhánh
lọc và fallback, đặc biệt là học phí theo khối ngành.

## Cổng 3: dataset chính thức

### Candidate pool

Giữ nguyên 455 câu hiện tại làm nguồn ứng viên. Mỗi câu phải được rà lại sau
khi ontology và catalogue được khóa:

- giữ nếu câu tự nhiên, target đúng và thuộc một ô coverage cần thiết;
- sửa nếu ý định hữu ích nhưng target hoặc cách diễn đạt chưa đúng;
- loại nếu máy móc, lặp ý, mơ hồ ngoài chủ đích hoặc dựa trên catalogue cũ.

Không có câu nào được tự động kế thừa trạng thái “official”. Không tạo khái
niệm version cho dataset hoặc checkpoint.

### Coverage trong miền

Dataset được biên soạn theo ma trận:

```text
query family × entity/slot × cách diễn đạt × register × split
```

Trong đó:

- train chứa toàn bộ schema, IRI hữu hạn, operator và kiểu kết quả production;
- validation/test giữ lại cách diễn đạt chưa thấy, không giữ lại schema mới;
- mọi query family xuất hiện trong cả ba split;
- train phủ formal, neutral, colloquial và noisy cho từng family;
- các family quy trình trọng tâm phủ đủ bốn register trong từng split;
- validation/test được cân bằng theo miền và register, không lặp lại tình trạng
  một split gần như chỉ formal/colloquial còn split kia gần như chỉ
  neutral/noisy;
- câu tổng quát, câu hỏi một khía cạnh, câu nhiều điều kiện và câu nhiều kết
  quả đều được phủ khi ontology trả lời trọn vẹn.

Quy mô cuối không được chọn trước bằng một con số tùy ý. Dataset chỉ dừng tăng
khi mọi ô coverage bắt buộc đã có đủ cách diễn đạt độc lập và audit lỗi không
còn chỉ ra vùng trắng quan trọng.

### Ngôn ngữ người dùng và preprocessing

Dataset lưu câu raw. Trainer, benchmark và runtime dùng duy nhất
`normalize_model_input`.

Nguồn ngôn ngữ gồm:

- câu hành chính rõ ràng;
- cách hỏi phổ thông và ngôn ngữ nói thường ngày;
- viết tắt chắc nghĩa, không dấu, lỗi gõ có thể hiểu được và câu rút gọn;
- toàn bộ input có ý nghĩa từ `test.html` và các phiên test tay sau này;
- các cặp có cùng ý nghĩa trước/sau chuẩn hóa để kiểm tra preprocessing không
  làm đổi intent.

`hp → học phần` là quyết định đã chốt. Preprocessing chỉ làm biến đổi chắc
nghĩa; không dò intent, không fuzzy-match entity và không sinh IRI.

### Ngoài miền

Một model duy nhất học từ chối bằng marker chính xác. Tập ngoài miền phải lớn
theo độ phủ hành vi, không phình bằng câu vô nghĩa sinh hàng loạt. Checklist
phải bao phủ ít nhất:

- chào hỏi và trò chuyện xã hội;
- chủ đề không liên quan;
- câu gần miền nhưng ontology thiếu dữ liệu;
- câu mơ hồ thiếu anchor;
- noisy nhưng vẫn có thể nhận ra là ngoài miền;
- câu hỗn hợp có một nhánh không được hỗ trợ;
- hard negative dùng từ học vụ nhưng hỏi quan hệ không tồn tại;
- các cách nói tự nhiên quan sát được trong test tay.

Mỗi nhóm có formal, neutral, colloquial và noisy trong cả ba split. Số lượng
được quyết định bởi checklist và độ đa dạng ngữ nghĩa; tài liệu luôn báo cả số
tuyệt đối lẫn tỷ lệ để tránh accuracy tổng che mất false acceptance.

### Chất lượng biên soạn

Script chỉ được dùng để kiểm tra, thống kê, chia deterministic và sinh
checksum. Không dùng script ghép từ đồng nghĩa/template hàng loạt để thay thế
curation. Mọi câu phải đọc tự nhiên và target phải được thực thi đối chiếu với
ontology.

## Trạng thái tài liệu

Tài liệu công khai phải phân biệt rõ:

- **đã kiểm chứng:** lớp nguồn ontology và contract runtime;
- **đang nghiệm thu:** semantic index và inventory khả năng trả lời;
- **candidate:** catalogue và 455 câu hiện tại;
- **chưa thực hiện:** full fine-tuning, benchmark chính thức và lựa chọn model
  production trên dataset mới.

Các con số 455/339/58/58 chỉ được mô tả là snapshot của candidate pool. Không
được gọi chúng là release production hoặc bằng chứng model sẵn sàng triển khai.

Kế hoạch `2026-07-29-official-production-dataset.md` là bản triển khai đã tạo
candidate pool; nó không còn là nguồn quyết định cho tiêu chí nghiệm thu
dataset chính thức. Đặc tả này thay thế các tuyên bố trái ngược về trạng thái.

## Thứ tự triển khai

1. Sửa tài liệu công khai và đánh dấu đúng trạng thái hiện tại.
2. Audit/chỉnh semantic index của ontology rồi khóa inventory khả năng trả lời.
3. Mở rộng và kiểm thử catalogue theo inventory.
4. Rà 455 câu ứng viên, sau đó biên soạn dataset chính thức.
5. Chạy audit leakage, coverage, tokenizer và ontology execution.
6. Chỉ khi các cổng trên qua mới fine-tune một model nghiệm thu.
7. Sau khi dataset ổn định mới fine-tune/benchmark ba kiến trúc theo giao thức
   nghiên cứu đã chốt.
