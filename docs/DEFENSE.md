# Bộ câu hỏi phản biện khó và hướng trả lời

Tài liệu này không cung cấp “câu trả lời để học thuộc”. Mỗi mục nêu kết luận
ngắn nhất có thể bảo vệ bằng artifact trong repository, đồng thời chỉ rõ phần
phải thừa nhận là giới hạn. Khi trả lời, nên nói kết luận trước, giới hạn sau và
mở đúng bằng chứng; không mở đầu bằng chi tiết cài đặt.

## A. Bản chất và đóng góp

### 1. Đây thực chất chỉ là chatbot gọi database, đóng góp khoa học nằm ở đâu?

**Trả lời:** Đóng góp không phải một thuật toán ontology mới. Đó là thiết kế và
đánh giá một chuỗi có ranh giới trách nhiệm: LLM xử lý giao tiếp, bộ phân loại
chọn hành động trong tập đóng, catalogue giới hạn SPARQL, ontology giữ dữ kiện và
provenance. Giá trị nghiên cứu nằm ở khả năng kiểm định từng tầng và phân tích
đánh đổi giữa kiểm soát với độ phủ.

**Bằng chứng:** sơ đồ và bảng trách nhiệm ở [README](../README.md); mã runtime ở
`src/ontchatbot/runtime/`.

### 2. Tại sao cần ontology thay vì một bảng SQL hoặc tìm kiếm văn bản?

**Trả lời:** Dự án cần đồng thời biểu diễn cấu trúc Điều-Khoản-Điểm, quan hệ thủ
tục-bước-điều kiện-trường hợp và căn cứ của từng dữ kiện. RDF phù hợp với các
đường quan hệ không đồng nhất này. Nghiên cứu chưa có thí nghiệm đối chứng với
SQL hay RAG văn bản, nên chỉ có thể nói ontology phù hợp yêu cầu biểu diễn, không
thể nói đã chứng minh nó tốt hơn mọi phương án khác.

**Bằng chứng:** [ontology](ONTOLOGY.md) và `basedOn`, `hasStep`, `scopedToCase`
trong `resources/ontology/ontology.ttl`.

### 3. Ontology khác knowledge graph ở đây như thế nào?

**Trả lời:** Tệp có cả TBox (lớp, property, quan hệ lớp con) và ABox (cá thể cùng
dữ kiện), nên có thể gọi là ontology được hiện thực thành đồ thị tri thức. Tên
gọi không làm thay đổi đơn vị đánh giá: runtime truy vấn tập triple đã nạp.

### 4. Tại sao không để LLM sinh câu trả lời trực tiếp từ tài liệu?

**Trả lời:** Mục tiêu thiết kế là thu hẹp hành động: mô hình chỉ chọn truy vấn đã
kiểm, không tự tạo IRI/SPARQL. Điều này loại một số lỗi cú pháp và truy vấn ngoài
catalogue. Nó không loại lỗi chọn nhầm truy vấn hoặc lỗi diễn đạt của LLM.

**Bằng chứng:** `runtime/classifier.py`, `runtime/cards.py` và kiểm catalogue ở
`runtime/pipeline.py`.

### 5. Đóng góp nào đã được chứng minh, đóng góp nào mới là kỳ vọng?

**Trả lời:** Đã kiểm được tính nhất quán của snapshot, coverage catalogue, khả
năng thực thi mọi đích và kết quả benchmark mới nhất trên tập đã công bố. Hiệu
quả trên phân bố câu hỏi thật, ưu thế so với RAG và mức giảm hallucination trong
triển khai chưa được chứng minh.

## B. Ontology và nguồn

### 6. “Ontology là nguồn duy nhất” có phải coi dữ liệu tự xây là chân lý không?

**Trả lời:** Không. Văn bản chính thức là thẩm quyền bên ngoài; ontology chỉ là
nguồn nội dung duy nhất **bên trong runtime**, nhằm tránh hai kho vận hành nói
khác nhau. Nếu ontology mâu thuẫn nguồn chính thức thì ontology sai.

### 7. Vì sao chọn đúng 17 nguồn? Có chứng minh chúng đầy đủ không?

**Trả lời:** Chúng được chọn theo phạm vi chức năng mục tiêu: đào tạo, tuyển sinh,
học phí/học bổng, biểu mẫu, chứng chỉ và tổ chức. Dự án chưa có danh mục toàn bộ
nghiệp vụ của trường để tính coverage nguồn, nên không tuyên bố 17 nguồn là đầy
đủ.

**Bằng chứng:** bảng nguồn ở [README](../README.md) và các cá thể `Decision`,
`Regulation`, `GuidanceDocument`, `FormCatalogue` trong ontology.

### 8. Quy trình biến PDF/web thành ontology có tái lập được không?

**Trả lời:** Chỉ tái kiểm được một phần, chưa tái lập đầu-cuối. Một phần văn bản
và toàn bộ bảng được test đối chiếu với snapshot nguồn; tầng nghiệp vụ được viết
tay. Repository không còn pipeline nhận 17 nguồn thô và sinh lại toàn bộ Turtle.

**Bằng chứng:** `tests/ontology/test_source_fidelity.py` và
`tests/ontology/test_drafting_rules.py`.

### 9. Bóc tách thủ công thì làm sao tránh thiên kiến người xây dựng?

**Trả lời:** Dự án giảm lỗi bằng schema, `basedOn`, quy tắc biên soạn và test các
lỗi từng gặp. Tuy nhiên chưa có hai chuyên gia gán độc lập hoặc đo agreement, nên
thiên kiến/diễn giải chủ quan vẫn là đe doạ còn mở.

### 10. `basedOn` có chứng minh dữ kiện đúng không?

**Trả lời:** Không. Nó chứng minh khả năng lần theo căn cứ mà người biên soạn đã
chọn. Test còn kiểm số xuất hiện trong đoạn nguồn và node nghiệp vụ có căn cứ,
nhưng không chứng minh việc diễn giải quan hệ là duy nhất hay đúng pháp lý.

### 11. Tại sao giữ cả văn bản gốc và dữ kiện bóc tách, có trùng lặp không?

**Trả lời:** Hai tầng phục vụ hai câu hỏi khác nhau: “Điều 24 ghi gì?” và “điều
kiện nghỉ học tạm thời là gì?”. Trùng nội dung có kiểm soát tạo khả năng đối
chiếu; test yêu cầu văn bản con nằm trong văn bản cha và dữ kiện nghiệp vụ dẫn
về phần nhỏ nhất.

### 12. Tại sao bảng không tách thành từng cell để truy vấn đẹp hơn?

**Trả lời:** Nguồn có ô rỗng và header nhiều tầng; làm phẳng từng cell từng gây
lệch cột. Snapshot ưu tiên fidelity: trả nguyên khối Markdown. Đánh đổi là LLM
phải đọc bảng và truy vấn theo cell kém linh hoạt.

### 13. 6.350 và 7.704 triple, số nào là quy mô thật?

**Trả lời:** Cả hai, với hai đơn vị khác nhau. 6.350 là phát biểu trong Turtle;
7.704 là đồ thị runtime sau khi thêm 677 cặp trích dẫn-URL, tức 1.354 triple dẫn
xuất. Không được dùng phần chênh như số tri thức mới.

### 14. 4.057 “khả năng trả lời” có nghĩa chatbot trả lời được 4.057 câu à?

**Trả lời:** Không. Đó là số đường từ một neo qua thuộc tính/quan hệ tới literal
được catalogue bao phủ. Một đường có thể ứng với vô số cách hỏi, và có đường
được hỗ trợ nhưng model vẫn chọn sai.

### 15. Thiếu triple có nghĩa câu trả lời là “không” không?

**Trả lời:** Không. Dự án tôn trọng khác biệt giữa open-world semantics và chính
sách runtime. Thiếu dữ liệu chỉ dẫn tới “dữ liệu hiện có không chứa chi tiết”,
không dẫn tới phủ định chi tiết đó trong thực tế.

### 16. Văn bản cũ, sửa đổi và hiệu lực được giải quyết thế nào?

**Trả lời:** Hiện xử lý theo trường hợp được biên soạn và test, chưa có reasoner
hiệu lực tổng quát. Ví dụ phạm vi dùng Quyết định 753 được khoá bằng một quy tắc
cụ thể. Khi có văn bản mới vẫn cần người có chuyên môn rà quan hệ sửa đổi/thay
thế.

### 17. Nguồn web thay đổi thì câu trả lời có lỗi thời không?

**Trả lời:** Có thể. `retrievedDate` chỉ cho biết ngày snapshot, không tự phát
hiện thay đổi sau đó. Cần lịch crawl/rà soát, version hoá snapshot và invalidation
metric/model khi nguồn đổi; dự án chưa tự động hoá đầy đủ phần này.

## C. Catalogue, nhãn và runtime

### 18. 50, 566, 344 và 4.057 có mâu thuẫn không?

**Trả lời:** Không; đó là bốn đơn vị: 50 họ dùng để nhóm nhu cầu, 566 cặp họ-đích
thô trước chuẩn hoá, 344 nhãn classifier nối với 343 template SPARQL và 1
template `no-information`, còn 4.057 là số đường dữ kiện được catalogue bao phủ.

### 19. Gộp Khoản/Điểm lên Điều có làm mất câu trả lời không?

**Trả lời:** Có làm giảm độ phân giải truy xuất. Mục tiêu là giảm đuôi dài và
nhãn cực ít mẫu. Runtime có thể trả cả Điều rồi dựa vào trích dẫn/LLM chọn chi
tiết. Đây là đánh đổi, không phải cải tiến miễn phí.

### 20. Truy vấn dựng sẵn thì hệ thống có thật sự “hiểu” câu hỏi không?

**Trả lời:** Nghiên cứu không cần khẳng định hiểu theo nghĩa nhận thức. Nó đo khả
năng ánh xạ biểu thức ngôn ngữ vào hành động truy xuất phù hợp trong ontology
đóng. Từ “nhận diện/chọn nhãn” chính xác hơn từ “hiểu”.

### 21. Thêm một thực thể ontology có cần huấn luyện lại không?

**Trả lời:** Nếu chỉ thêm dữ kiện vào node đã có và truy vấn cũ đã bao phủ, có
thể không đổi label space. Nếu thêm một đích mà bộ phân loại phải chọn, bảng nhãn
và lớp phân loại thay đổi nên phải tạo dữ liệu, huấn luyện và xuất model lại.
Không nên nói chung rằng thêm thực thể luôn không cần train.

### 22. Tại sao LLM nhận câu đầy đủ nhưng classifier chỉ nhận từ khoá?

**Trả lời:** Dataset của classifier chủ yếu là câu/cụm ngắn theo ý định; tool
contract yêu cầu LLM nén câu hội thoại về tên chủ đề. Cách này giảm nhiễu lịch
sự nhưng thêm một điểm lỗi do LLM rút từ khoá. Chưa có ablation câu đầy đủ so
với từ khoá trên cùng benchmark, nên chưa chứng minh lựa chọn này tối ưu.

### 23. Truy vấn luôn hợp lệ có đồng nghĩa câu trả lời luôn đúng không?

**Trả lời:** Không. Nhãn sai vẫn ánh xạ tới một truy vấn hợp lệ và dữ liệu thật.
Đây là failure mode nguy hiểm vì câu trả lời nhìn có nguồn. Cần chấm retrieval
relevance và end-to-end, không chỉ syntax validity.

### 24. LLM bị prompt bắt gọi tool thì có còn hallucinate được không?

**Trả lời:** Có. Prompt là ràng buộc hành vi mềm. LLM có thể không gọi tool, rút
sai từ khoá, bỏ sót dòng hoặc nối hai dữ kiện. Lượt end-to-end cũ có ba trường
hợp nối dữ kiện ở nhóm cần từ chối.

## D. Dataset và split

### 25. Dataset này là dữ liệu thật hay synthetic?

**Trả lời:** Bộ 6.313 dòng chủ yếu là dữ liệu biên soạn/tổng hợp có kiểm soát từ
ontology, khung ý định và phép biến đổi phong cách. Vì vậy không gọi dataset là
log người dùng hoặc mẫu đại diện cho phân bố sử dụng thực tế.

### 26. Câu hỏi được tạo cụ thể như thế nào?

**Trả lời:** Ghép cách gọi thực thể từ ontology với khung ý định soạn tay, rồi
tạo biến thể phong cách/từ để hỏi/nhiễu; bổ sung câu soạn riêng và bảy lớp câu
từ chối. Chi tiết nằm ở [DATASET.md](DATASET.md).

### 27. Bốn register có được người gán nhãn độc lập không?

**Trả lời:** Không. Đây là nhãn thiết kế từ cơ chế tạo và câu soạn, không phải
nhãn xã hội-ngôn ngữ đã đo agreement. Vì thế kết quả theo register nên xem là
phân tích theo phép biến đổi, không suy rộng thành hành vi của bốn nhóm người.

### 28. Tại sao tỷ lệ từ chối là 13,1%? Có giống thực tế không?

**Trả lời:** Đó là lựa chọn sampling để model nhìn thấy đủ negative, không phải
ước lượng traffic. Nếu tỷ lệ triển khai khác, precision/recall và calibration
cũng có thể khác dù conditional accuracy giữ nguyên.

### 29. Có rò rỉ train-test không?

**Trả lời:** Không có câu trùng nguyên văn hoặc trùng sau chuẩn hoá/bỏ dấu; khung
ý định được chia theo split. Nhưng cùng thực thể và đích xuất hiện ở train và
test. Vì vậy không có text leakage theo các luật đã kiểm, nhưng có content overlap
có chủ đích và không được gọi là zero-shot.

### 30. Nếu mọi target test đã có ở train thì test có quá dễ không?

**Trả lời:** Test phù hợp câu hỏi nghiên cứu hẹp về paraphrase của nội dung đã
biết. Nó không phù hợp để đo cập nhật ontology hay target mới. Muốn đánh giá
khái quát mạnh hơn cần entity-held-out, document-held-out và tập người dùng thật.

### 31. Dataset sinh từ ontology rồi lại dùng để hỏi ontology có phải vòng tròn?

**Trả lời:** Có phụ thuộc cấu trúc: nhãn và cách gọi bắt nguồn từ ontology. Điều
này chấp nhận được khi đo mapping nội bộ, nhưng làm benchmark không độc lập để
đánh giá ontology đúng/đủ hay ngôn ngữ ngoài thực tế. Kết luận phải giới hạn theo
đó.

### 32. Mỗi câu chỉ có một nhãn, nếu hai query đều trả lời đúng thì sao?

**Trả lời:** Exact match sẽ phạt một nhãn khác dù dữ kiện tương đương. Dự án đã
nhận diện hạn chế này nhưng chưa có bộ equivalence dựa trên kết quả thực thi.
Hướng đúng là chấm cả relevance/answer equivalence, không chỉ label ID.

### 33. 390 câu cho 344 nhãn có đủ không?

**Trả lời:** Không đủ để ước lượng tin cậy từng nhãn; nhiều nhãn vắng khỏi test
hoặc chỉ có một mẫu. Accuracy tổng thể còn đọc được ở mức thô, nhưng macro metric
và phân tích nhãn hiếm có phương sai lớn. Cần tăng mẫu độc lập, không chỉ sinh
thêm biến thể gần nhau.

### 34. Vì sao dataset được coi là snapshot bất biến?

**Trả lời:** Mọi kết quả benchmark phải chỉ đến đúng ba split và checksum đã
công bố. Thay đổi một dòng tạo thành một snapshot nghiên cứu khác, không được
trộn kết quả của hai snapshot.

## E. Thực nghiệm và kết quả

### 35. Accuracy 85,1% có phải kết quả hiện tại không?

**Trả lời:** Có. Đây là kết quả mới nhất được báo cáo cho XLM-R trên snapshot
6.313 câu. Trọng số phục vụ được phát hành trên Hugging Face Hub và nằm trong ảnh
Docker; repository mã nguồn không lưu các tệp model nặng.

### 36. "Baseline" trong nghiên cứu này là gì?

**Trả lời:** Chỉ là mô hình TF-IDF + LinearSVC dùng làm mốc so sánh với bốn
encoder. Dự án không có một "phiên bản baseline" riêng.

### 37. Có thể kết luận XLM-R tốt nhất không?

**Trả lời:** XLM-R đứng đầu accuracy trong kết quả quan sát, còn BamiBERT đứng
đầu một số macro metric. Chưa có nhiều seed, khoảng tin cậy hoặc kiểm định thống
kê, nên chưa thể khẳng định thứ hạng sẽ ổn định khi huấn luyện lại.

### 38. Baseline TF-IDF + LinearSVC có quá yếu không?

**Trả lời:** Nó là baseline hợp lý cho dữ liệu ngắn, nhiều overlap tên và lỗi
chính tả vì dùng cả word và character n-gram; thực tế đạt 80,3%.
Nhưng nghiên cứu chưa so với BM25, nearest-neighbour encoder, LLM prompting hay
RAG, nên chưa thể nói đã bao phủ toàn bộ baseline cạnh tranh.

### 39. Tại sao dùng epoch cuối thay vì checkpoint tốt nhất?

**Trả lời:** Đó là quy ước của thiết lập đã báo cáo và tránh dùng test để chọn. Tuy
nhiên validation hoàn toàn có thể dùng để chọn checkpoint trước khi mở test;
không làm vậy có thể làm giảm kết quả và không phải lựa chọn tối ưu. Lần chạy
mới nên định nghĩa early stopping trước.

### 40. Chỉ chạy một seed thì so mô hình có hợp lệ không?

**Trả lời:** Chỉ đủ cho mô tả kết quả quan sát, không đủ xếp hạng chắc chắn. Cần
chạy nhiều seed và báo trung bình, độ lệch hoặc khoảng tin cậy.

### 41. End-to-end 85 câu có được chọn sau khi xem lỗi không?

**Trả lời:** Danh sách được mô tả là rút phân tầng một lần rồi đóng băng; script
chỉ đồng bộ nhãn, không chọn lại. Tuy vậy bản ghi không có một protocol tiền đăng
ký độc lập, nên không thể loại trừ hoàn toàn selection bias bằng artifact hiện có.

**Bằng chứng:** `resources/end-to-end/question_set.py` và `questions.json`.

### 42. Dùng LLM chấm LLM có đáng tin không?

**Trả lời:** Chỉ là ước lượng. Bộ chấm buộc trích bằng chứng và có tín hiệu tất
định để đối chiếu, nhưng chưa có hai người chấm độc lập hay agreement. Không nên
gọi nhãn LLM là chuẩn vàng.

### 43. Tại sao không cộng 61 câu trả lời được và 24 câu cần từ chối thành một số?

**Trả lời:** Hai nhóm có tiêu chí thành công khác nhau và tỷ lệ sampling do người
xây dựng chọn. Một số gộp sẽ phụ thuộc mạnh tỷ lệ negative và che việc model có
thể tốt ở trả lời nhưng kém ở từ chối, hoặc ngược lại.

### 44. Không có câu bị chấm “sai” có chứng minh hết hallucination không?

**Trả lời:** Không. Mẫu nhỏ, judge tự động và ba câu ở nhóm cần từ chối đã tạo
quan hệ không được dữ liệu khẳng định. “0 sai” chỉ là count theo taxonomy của
lượt đó, không phải xác suất hallucination bằng 0.

## F. Thực tiễn và vận hành

### 45. Hệ thống có thể dùng để quyết định quyền lợi sinh viên không?

**Trả lời:** Không nên dùng như cơ quan ra quyết định. Nó là công cụ tra cứu có
nguồn; câu trả lời cần dẫn người dùng tới văn bản/đơn vị chịu trách nhiệm, nhất
là các trường hợp cá nhân và hiệu lực thay đổi.

### 46. Khi có quy định mới cần cập nhật gì?

**Trả lời:** Cập nhật snapshot nguồn, tầng văn bản, tầng nghiệp vụ và `basedOn`;
sinh lại inventory/catalogue/report/manifest; nếu label/data đổi thì train và
export lại classifier; cuối cùng chạy lại end-to-end và đổi metric provenance.

### 47. Hệ thống xử lý dữ liệu cá nhân thế nào?

**Trả lời:** Ontology không lưu hồ sơ sinh viên và thiết kế từ chối học phí cá
nhân. Tuy nhiên lớp LLM/API bên ngoài vẫn nhận nội dung hội thoại; repository
chưa trình bày DPIA, retention policy hay redaction. Triển khai thật cần bổ sung
chính sách riêng tư, log và secret management.

### 48. Nếu LLM hoặc mạng ngoài lỗi thì sao?

**Trả lời:** Lõi ontology/classifier chạy cục bộ nhưng hội thoại phụ thuộc API
LLM. Runtime có timeout và giới hạn vòng gọi, song chưa có đánh giá availability
dài hạn hay phương án giao diện fallback chỉ trả dữ liệu thô.

### 49. Kết quả latency có áp dụng khi nhiều người dùng không?

**Trả lời:** Không. Lượt đo chạy tuần tự, một cấu hình, và latency gồm mạng/LLM.
Nó mô tả single-request behavior, không chứng minh throughput, queueing hay p95
dưới tải.

### 50. Nếu chỉ được nêu một hạn chế quan trọng nhất, đó là gì?

**Trả lời đề xuất:** Bằng chứng ngoại tại còn yếu: dataset chính là synthetic và
mọi target ở test đã xuất hiện trong train. Điều này giới hạn kết luận về câu hỏi
thật và nội dung mới. Ưu tiên tiếp theo là một tập đánh giá độc lập từ người dùng.

## Checklist 60 giây trước buổi phản biện

- Nói rõ 85,1% là accuracy của classifier, không phải độ đúng toàn hệ thống.
- Không gọi 6.313 câu là câu người dùng thật.
- Không gọi 4.057 là số câu hỏi.
- Không gọi ontology là chân lý cao hơn văn bản chính thức.
- Không nói prompt loại bỏ hoàn toàn hallucination.
- Không nói split đo target mới hoặc zero-shot.
- Không xếp hạng bốn encoder nếu chưa có nhiều seed.
- Khi bị hỏi “bằng chứng đâu”, mở artifact máy đọc được trước rồi mới mở README.
